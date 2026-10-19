#!/usr/bin/env python3
"""One bounded OpenCode worker. POSIX only; native permissions are not a sandbox."""

import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import uuid


class WorkerError(Exception):
    pass


class Stopped(WorkerError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def private_open(path, flags=os.O_WRONLY | os.O_CREAT | os.O_EXCL):
    fd = os.open(path, flags | os.O_NOFOLLOW, 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise WorkerError('Runtime file is not a private, owned regular file')
    return os.fdopen(fd, 'r' if flags == os.O_RDONLY else 'w', encoding='utf-8')


def private_json(path):
    with private_open(path, os.O_RDONLY) as stream:
        return json.load(stream)


def write_private(path, value):
    with private_open(path) as stream:
        stream.write(value)


def write_binding(state, binding):
    temp = state / ('binding-'+uuid.uuid4().hex+'.json')
    with private_open(temp) as stream:
        stream.write(json.dumps(binding, indent=2)+'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, state / 'binding.json')


def private_directory(path, create=False):
    if create:
        path.mkdir(mode=0o700)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise WorkerError('State directory must be owned, mode 0700, and not a symlink')


def checkout_boundary(directory):
    boundary = directory
    for parent in (directory, *directory.parents):
        try:
            (parent / '.git').lstat()  # Both ordinary .git directories and worktree files.
        except FileNotFoundError:
            continue
        boundary = parent  # Protect every enclosing checkout, including nested repositories.
    return boundary


def require_outside_checkout(path, boundary):
    resolved = path.resolve()
    if resolved == boundary or boundary in resolved.parents:
        raise WorkerError('State directory must be outside the checkout; choose an allowed outside --state-dir')


def native_auth(zro, provider):
    """Read native auth in memory before isolating HOME. Never copy auth files."""
    home = Path.home()
    try:
        if zro:
            key = os.environ.get('ZRO_API_KEY')
            if not key:
                config = Path(os.environ.get('XDG_CONFIG_HOME', home / '.config'))
                key = json.loads((config / 'zro' / 'credentials.json').read_text())['apiKey']
            if not isinstance(key, str) or not key:
                raise ValueError()
            return {'ZRO_API_KEY': key}, [key]
        data = Path(os.environ.get('XDG_DATA_HOME', home / '.local' / 'share'))
        entry = json.loads((data / 'opencode' / 'auth.json').read_text())[provider]
        # These initial built-in routes use API auth; custom/OAuth config is unsupported.
        if entry.get('type') != 'api' or not isinstance(entry.get('key'), str) or not entry['key']:
            raise ValueError()
        return {'OPENCODE_AUTH_CONTENT': json.dumps({provider: entry})}, [entry['key']]
    except (OSError, ValueError, KeyError, TypeError):
        raise WorkerError('Native authentication unavailable; sign in with zro login' if zro else
                          'Native API authentication unavailable; connect the selected provider in opencode') from None


def isolated_environment(state, auth, model, search_path):
    env = {'PATH': search_path, 'LANG': 'C.UTF-8', 'TERM': 'dumb'}
    directories = {'HOME': 'home', 'XDG_CONFIG_HOME': 'config', 'XDG_DATA_HOME': 'data',
                   'XDG_CACHE_HOME': 'cache', 'XDG_STATE_HOME': 'state', 'TMPDIR': 'tmp'}
    for key, name in directories.items():
        path = state / name
        if not path.exists():
            private_directory(path, create=True)
        else:
            private_directory(path)
        env[key] = str(path)
    for flag in ['OPENCODE_DISABLE_PROJECT_CONFIG', 'OPENCODE_DISABLE_CLAUDE_CODE',
                 'OPENCODE_DISABLE_EXTERNAL_SKILLS', 'OPENCODE_DISABLE_AUTOUPDATE',
                 'OPENCODE_DISABLE_LSP_DOWNLOAD', 'OPENCODE_DISABLE_DEFAULT_PLUGINS',
                 'OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER', 'OPENCODE_PURE']:
        env[flag] = '1'
    # Defense in depth only: bash and child tools still have the parent's OS access.
    config = {'model': model, 'share': 'disabled', 'autoupdate': False, 'plugin': [],
              'lsp': False, 'mcp': {'zro': {'enabled': False}},
              'permission': {'external_directory': 'deny', 'task': 'deny',
                             'read': {'*': 'allow', '*.env': 'deny', '*.env.*': 'deny',
                                      '*.pem': 'deny', '*credentials*': 'deny', '*auth.json': 'deny'}}}
    env['OPENCODE_CONFIG_CONTENT'] = json.dumps(config)
    env.update(auth)
    return env


def group_exists(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # An uninspectable group may still be alive.


def stop_group(proc, pgid=None, deadline=None):
    """Never declare cleanup successful while the owned group still exists."""
    pgid = proc.pid if pgid is None else pgid
    for sig, grace in [(signal.SIGTERM, 1.0), (signal.SIGKILL, 1.0)]:
        try:
            os.killpg(pgid, sig)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass  # A transient EPERM can settle to confirmed absence during grace.
        end = time.monotonic() + grace
        if deadline is not None:
            end = min(end, deadline)
        while time.monotonic() < end:
            proc.poll()  # Reap our direct child before probing its process group.
            if not group_exists(pgid):
                return True
            time.sleep(0.025)
    return not group_exists(pgid)


def descendant_groups(proc, env):
    """A same-sandbox snapshot; never elevate if host process inspection is denied."""
    try:
        executable = shutil.which('ps', path=env['PATH'])
        if not executable:
            return None
        command = [executable, '-axo', 'pid=,ppid=,pgid=']
        inspection_env = {key: env[key] for key in ('PATH', 'XDG_DATA_HOME')}
        snapshot = subprocess.run(command, env=inspection_env, stdin=subprocess.DEVNULL,
                                  capture_output=True, text=True, timeout=1)
        if snapshot.returncode:
            return None
        rows = [tuple(map(int, line.split())) for line in snapshot.stdout.splitlines() if line.strip()]
        if not any(pid == proc.pid and pgid == proc.pid for pid, _, pgid in rows):
            return None
        owned = {proc.pid}
        while True:
            children = {pid for pid, parent, _ in rows if parent in owned}
            if children <= owned:
                break
            owned.update(children)
        groups = {pgid for pid, _, pgid in rows if pid in owned}
        # Signal only observed descendant-led groups, never the launcher's/foreign group.
        if os.getpgrp() in groups or not groups <= owned:
            return None
        return groups
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def cleanup_process(proc, env):
    handlers = {sig: signal.signal(sig, signal.SIG_IGN)
                for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    try:
        groups = descendant_groups(proc, env)
        deadline = time.monotonic() + 4
        clean = True
        # Native POSIX shell tools normally create their own groups. Stop them while
        # their OpenCode parent can reap them, then stop the root group.
        for pgid in sorted((groups or set()) - {proc.pid}) + [proc.pid]:
            clean = stop_group(proc, pgid, deadline) and clean
        return groups is not None and clean
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)


def run_process(command, cwd, env, timeout, stdout_path, stderr_path, clean, event=None, on_start=None):
    """Bound subprocess lifetime and output; use a new owned POSIX process group."""
    with private_open(stdout_path) as out, private_open(stderr_path) as err:
        proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                start_new_session=True)
        selector = selectors.DefaultSelector()
        buffers = {}
        captured = []
        total = 0
        cleanup_attempted = False
        deadline = time.monotonic() + timeout
        for pipe, target in [(proc.stdout, out), (proc.stderr, err)]:
            selector.register(pipe, selectors.EVENT_READ, target)
            buffers[pipe] = b''
        try:
            if on_start:
                on_start(proc)
            while selector.get_map() or proc.poll() is None:
                if time.monotonic() >= deadline:
                    raise Stopped('timeout', 'Worker deadline exceeded')
                for key, _ in selector.select(min(0.1, max(0, deadline-time.monotonic()))):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    total += len(chunk)
                    if total > 16 * 1024 * 1024:
                        raise WorkerError('Worker output exceeded 16 MiB')
                    buffers[key.fileobj] += chunk
                    if len(buffers[key.fileobj]) > 1024 * 1024:
                        raise WorkerError('Worker output line exceeded 1 MiB')
                    lines = buffers[key.fileobj].split(b'\n')
                    buffers[key.fileobj] = lines.pop()
                    if not chunk:
                        lines.append(buffers[key.fileobj])
                        buffers[key.fileobj] = b''
                        selector.unregister(key.fileobj)
                    for raw in lines:
                        line = raw.decode('utf-8', errors='replace')
                        key.data.write(clean(line)+'\n')
                        key.data.flush()
                        if key.fileobj is proc.stdout:
                            captured.append(line)
                            if event and line:
                                event(line)
            code = proc.wait()
            if group_exists(proc.pid):
                cleanup_attempted = True
                if not cleanup_process(proc, env):
                    raise Stopped('held', 'Descendant cleanup cannot be verified; inspect owned processes before retrying')
            return code, '\n'.join(captured)
        except BaseException as exc:
            if not cleanup_attempted and not cleanup_process(proc, env):
                reason = str(exc) or type(exc).__name__
                raise Stopped('held', reason+'; descendant inspection or cleanup failed; inspect owned processes before retrying') from exc
            raise
        finally:
            selector.close()
            proc.stdout.close()
            proc.stderr.close()


class Events:
    def __init__(self, expected_session, clean):
        self.session = expected_session
        self.ids = set()
        self.text = {}
        self.finish = None
        self.error = None
        self.clean = clean

    def consume(self, line):
        try:
            obj = json.loads(line)
        except ValueError:
            return  # Native launch banners are not session proof.
        if not isinstance(obj, dict) or obj.get('type') not in {
                'step_start', 'step_finish', 'text', 'tool_use', 'error', 'reasoning'}:
            return
        session = obj.get('sessionID')
        if not isinstance(session, str) or not re.fullmatch(r'ses_[A-Za-z0-9_-]+', session):
            raise WorkerError('Missing structured worker session ID')
        if self.session and self.session != session:
            raise WorkerError('Worker session does not match the exact requested session')
        self.session = session
        part = obj.get('part', {})
        if part.get('sessionID', session) != session:
            raise WorkerError('Event part has a conflicting session ID')
        if obj['type'] == 'error':
            error = obj.get('error', {})
            self.error = error.get('data', {}).get('message') or error.get('name') or 'Native worker error'
            print('worker error: '+self.clean(str(self.error)), file=sys.stderr, flush=True)
            return
        message = part.get('messageID')
        if not isinstance(message, str) or not message:
            raise WorkerError('Worker event lacks message ID needed for model proof')
        self.ids.add(message)
        if obj['type'] == 'text':
            self.text[message] = self.text.get(message, '') + part.get('text', '')
            print('worker: '+self.clean(part.get('text', ''))[:400], file=sys.stderr, flush=True)
        elif obj['type'] == 'tool_use':
            tool = str(part.get('tool', 'unknown'))
            if tool.startswith(('zro_', 'mcp_', 'mcp__')) or '__' in tool or '/' in tool or '.' in tool:
                raise WorkerError('Unexpected external worker tool: '+tool)
            print('worker tool: '+self.clean(tool)[:80], file=sys.stderr, flush=True)
        elif obj['type'] == 'step_finish':
            self.finish = (message, part.get('reason'))


def verify_export(value, session, model, directory, ids=None):
    if value.get('info', {}).get('id') != session:
        raise WorkerError('Exported session does not match requested session')
    if Path(value.get('info', {}).get('directory', '')).resolve() != directory:
        raise WorkerError('Exported session belongs to another working directory')
    messages = {m['info']['id']: m['info'] for m in value.get('messages', [])
                if m.get('info', {}).get('role') == 'assistant'}
    selected = ids if ids is not None else set(messages)
    if not selected or not selected <= messages.keys():
        raise WorkerError('Native export lacks observed assistant model proof')
    for message in selected:
        info = messages[message]
        if info.get('sessionID') != session:
            raise WorkerError('Exported assistant has a conflicting session ID')
        observed = str(info.get('providerID', '')) + '/' + str(info.get('modelID', ''))
        if observed != model:
            raise WorkerError('Observed assistant model differs from requested model')
        if info.get('error'):
            raise WorkerError('Exported assistant reports a native error')
    return messages


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dir', required=True, type=Path)
    parser.add_argument('--brief', required=True, type=Path)
    parser.add_argument('--model', help='Native openrouter/*, opencode-go/* or free opencode/*-free model')
    parser.add_argument('--zro', action='store_true', help='Pin zro/dolly1-security and --auto')
    parser.add_argument('--auto', action='store_true', help='Explicitly opt in to native automatic approvals')
    parser.add_argument('--session', help='Exact session ID; requires its original --state-dir')
    parser.add_argument('--state-dir', type=Path, help='New private runtime directory; original directory for resume')
    parser.add_argument('--timeout', type=float, default=1800, help='Worker deadline in seconds (default 1800)')
    return parser.parse_args()


def main():
    args = arguments()
    result = {'status': 'failed', 'accepted': False, 'route': 'zro' if args.zro else 'opencode',
              'model': args.model, 'session': args.session, 'state_dir': None,
              'final_response': '', 'artifacts': {}}
    secrets = []
    clean = lambda value: str(value)
    lock = None
    state = None
    valid_state = False
    started = False
    events = None
    try:
        if os.name != 'posix' or sys.platform not in {'darwin', 'linux'}:
            raise WorkerError('Supported hosts: macOS and Linux (POSIX)')
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise WorkerError('Timeout must be a finite positive number')
        directory = args.dir.resolve(strict=True)
        if not directory.is_dir():
            raise WorkerError('Working directory must be a directory')
        boundary = checkout_boundary(directory)
        # Freeze relative/empty PATH entries before child cwd changes, including
        # Zro's subsequent bare `opencode` lookup.
        search_path = os.pathsep.join(os.path.abspath(entry or os.curdir)
                                      for entry in os.environ.get('PATH', os.defpath).split(os.pathsep))
        # OpenCode Zen's free models run without an account or key.
        free = not args.zro and (args.model or '').startswith('opencode/') and args.model.endswith('-free')
        if args.zro:
            if args.model and args.model != 'zro/dolly1-security':
                raise WorkerError('Zro worker requires zro/dolly1-security')
            args.model = 'zro/dolly1-security'
        elif not free and (not args.model or args.model.split('/', 1)[0] not in {'openrouter', 'opencode-go'} or '/' not in args.model):
            raise WorkerError('Choose an explicit native openrouter/*, opencode-go/* or free opencode/*-free model; custom configs unsupported')
        result['model'] = args.model
        binaries = {}
        for name in ['opencode'] + (['zro'] if args.zro else []):
            binaries[name] = shutil.which(name, path=search_path)
            if not binaries[name]:
                raise WorkerError(name+' must be installed; this worker never installs prerequisites')
            control = Path(binaries[name]).resolve(strict=True)
            if control.is_relative_to(boundary):
                raise WorkerError(name+' must be a trusted installed CLI outside the checkout')
            binaries[name] = str(control)
        search_path = os.pathsep.join(entry for entry in search_path.split(os.pathsep)
                                      if not Path(entry).resolve().is_relative_to(boundary))
        auth, secrets = ({}, []) if free else native_auth(args.zro, args.model.split('/', 1)[0])
        def clean(value):
            text = str(value)
            for secret in secrets:
                text = text.replace(secret, '[REDACTED]')
            return text
        if args.session and not args.state_dir:
            raise WorkerError('Exact session continuation requires the original --state-dir')
        if args.state_dir:
            state = args.state_dir.absolute()
            require_outside_checkout(state, boundary)
            private_directory(state, create=not bool(args.session))
            state = state.resolve(strict=True)
        else:
            temp_parent = Path(tempfile.gettempdir()).resolve(strict=True)
            require_outside_checkout(temp_parent, boundary)
            state = Path(tempfile.mkdtemp(prefix='opencode-worker-', dir=temp_parent)).resolve()
        require_outside_checkout(state, boundary)
        result['state_dir'] = str(state)
        lock_path = state / 'worker.lock'
        lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        lock = os.fdopen(lock_fd, 'w')
        info = os.fstat(lock_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise WorkerError('Worker lock must be a private, owned regular file')
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise WorkerError('This worker state already has an active launcher') from None
        binding = {'route': result['route'], 'model': args.model, 'directory': str(directory),
                   'auto': args.auto or args.zro}
        if args.session:
            recorded = private_json(state / 'binding.json')
            if recorded.get('status') in {'running', 'held'}:
                raise Stopped('held', 'Prior worker may still be running; inspect owned processes before continuation')
            for field, expected in {**binding, 'session': args.session}.items():
                if recorded.get(field) != expected:
                    raise WorkerError('Continuation '+field+' does not match original worker state')
        valid_state = True
        env = isolated_environment(state, auth, args.model, search_path)
        attempt = uuid.uuid4().hex[:12]
        def artifact(name):
            path = state / (attempt+'-'+name)
            result['artifacts'][name] = str(path)
            return path
        brief = artifact('brief.txt')
        write_private(brief, args.brief.read_text())
        def invoke(command, name, event=None, timeout=None, on_start=None, authenticated=True):
            child_env = env if authenticated else {key: value for key, value in env.items() if key not in auth}
            return run_process(command, directory, child_env, timeout or min(15, args.timeout),
                               artifact(name+'.stdout.log'), artifact(name+'.stderr.log'), clean, event, on_start)
        code, help_text = invoke([binaries['opencode'], 'run', '--help'], 'help', authenticated=False)
        help_text += Path(result['artifacts']['help.stderr.log']).read_text()
        required = ['--pure', '--model', '--format', '--dir', '--file', '--session']
        if args.auto or args.zro:
            required.append('--auto')
        if code or any(flag not in help_text for flag in required):
            raise WorkerError('Installed opencode lacks required native run flags')
        launch = ([binaries['zro'], 'launch', 'opencode', '--model', 'dolly1-security', '--']
                  if args.zro else [binaries['opencode']])
        code, text = invoke(launch + ['debug', 'config', '--pure'], 'config')
        if code:
            raise WorkerError('Cannot inspect resolved native configuration before inference')
        config = json.loads(text)
        if not isinstance(config, dict) or not isinstance(config.get('mcp', {}), dict):
            raise WorkerError('Resolved native configuration or MCP configuration is not an object')
        permission = config.get('permission', {})
        if (config.get('model') != args.model or not isinstance(permission, dict) or
                any(permission.get(name) != 'deny' for name in ('task', 'external_directory'))):
            raise WorkerError('Resolved native model or permission restrictions differ from the requested worker profile')
        if config.get('plugin') or config.get('instructions') or any(
                not isinstance(entry, dict) or entry.get('enabled') is not False
                for entry in config.get('mcp', {}).values()):
            raise WorkerError('Resolved native configuration includes external MCP, plugins, or instructions')
        previous = set()
        if args.session:
            code, text = invoke([binaries['opencode'], 'export', args.session, '--pure'], 'before', authenticated=False)
            if code:
                raise WorkerError('Cannot export exact session before continuation')
            previous = set(verify_export(json.loads(text), args.session, args.model, directory))
        events = Events(args.session, clean)
        command = launch + ['run',
                   'Complete the attached brief and report changes, checks, and blockers.',
                   '--pure', '--model', args.model, '--format', 'json', '--dir', str(directory)]
        if args.auto or args.zro:
            command.append('--auto')
        if args.session:
            command += ['--session', args.session]
        command += ['--file', str(brief)]
        binding.update(session=args.session, status='running', launcher_pid=os.getpid(),
                       process_group=None, phase='run')
        write_binding(state, binding)  # SIGKILL must leave a held state, never the last finished state.
        started = True
        def launched(proc):
            binding['process_group'] = proc.pid
            write_binding(state, binding)
        code, _ = invoke(command, 'run', events.consume, args.timeout, launched)
        result['session'] = events.session
        if events.error:
            raise WorkerError(str(events.error))
        if code:
            raise WorkerError('Native worker exited with status '+str(code)+'; inspect private stderr artifact')
        if not events.session or not events.finish or events.finish[1] != 'stop':
            raise WorkerError('No completed native assistant response was observed')
        if events.ids & previous:
            raise WorkerError('Worker replayed existing messages instead of producing a new response')
        code, text = invoke([binaries['opencode'], 'export', events.session, '--pure'], 'export', authenticated=False)
        if code:
            raise WorkerError('Cannot export exact worker session for model proof')
        messages = verify_export(json.loads(text), events.session, args.model, directory, events.ids)
        final_id = events.finish[0]
        if messages[final_id].get('finish') != 'stop' or not events.text.get(final_id, '').strip():
            raise WorkerError('Native assistant did not finish with a final text response')
        result.update(status='finished', final_response=clean(events.text[final_id]))
    except KeyboardInterrupt:
        result.update(status='interrupted', error='Worker interrupted; owned process group stopped')
    except Stopped as exc:
        result.update(status=exc.status, error=clean(exc))
    except (WorkerError, OSError, ValueError, KeyError, TypeError) as exc:
        result.update(status='failed', error=clean(exc))
    finally:
        if events:
            result['session'] = events.session
        if state and valid_state:
            try:
                binding.update(route=result['route'], model=result['model'],
                               directory=str(args.dir.resolve()), auto=args.auto or args.zro,
                               session=result['session'], status=result['status'],
                               phase='cleanup-held' if result['status'] == 'held' else 'stopped')
                if started or not args.session:
                    write_binding(state, binding)
                path = state / (uuid.uuid4().hex[:12]+'-result.json')
                result['artifacts']['result.json'] = str(path)
                write_private(path, clean(json.dumps(result, indent=2))+'\n')
            except OSError:
                result.update(status='held', error='Cannot persist private worker result; inspect state before retrying')
        if lock:
            lock.close()
    print(clean(json.dumps(result, ensure_ascii=False)), flush=True)
    return 0 if result['status'] == 'finished' else 1


if __name__ == '__main__':
    # A private umask also covers files created by the native CLI and its children.
    os.umask(0o077)
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    sys.exit(main())
