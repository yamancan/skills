#!/usr/bin/env python3
"""Bind one checkout and run disposable checks with storage reservations. POSIX, stdlib."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import time
import uuid

from session_store import guard_relocation, state_dir, write_json
from process_control import stop_group

MIB = 1024 * 1024


def pair_workspace(record):
    return state_dir() / 'workspaces' / record['task_id'] / 'workspace.json'


def identity(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError(f'Expected an actual directory, not a symlink: {path}')
    return [info.st_dev, info.st_ino]


def root_for(path):
    return path.with_name(path.stem + '.data')


@contextmanager
def locked(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.with_suffix(path.suffix + '.lock').open('a') as file:
        os.chmod(file.name, 0o600)
        fcntl.flock(file, fcntl.LOCK_EX)
        yield


def load(path):
    guard_relocation(path)
    data = json.loads(path.read_text())
    if data.get('version') != 1 or data.get('state') != str(path):
        raise ValueError('Use the original canonical workspace record; inspect copied/invalid state.')
    return data


def validate_source(data, workdir=None):
    source = Path(data['workdir'])
    if workdir is not None and str(Path(workdir).resolve()) != str(source):
        raise ValueError('Canonical checkout differs; resume its recorded path or resolve a supported handoff.')
    if source.resolve() != source or identity(source) != data['source_identity']:
        raise ValueError('Canonical checkout was replaced; inspect before continuing.')


def bind(path, workdir, budget_mib=None):
    path = path.expanduser().resolve()
    with locked(path):
        if path.exists():
            data = load(path)
            validate_source(data, workdir)
            if budget_mib is not None and budget_mib * MIB != data['budget_bytes']:
                raise ValueError('Use budget with an explicit reason to change an existing limit.')
            return data
        source = Path(workdir).expanduser().resolve()
        source_id = identity(source)
        budget = (2048 if budget_mib is None else budget_mib) * MIB
        if budget <= 0:
            raise ValueError('Storage budget must be positive.')
        root = root_for(path)
        if root.exists() or root.is_symlink():
            raise ValueError('Unregistered workspace storage exists; inspect without replacing it.')
        root.mkdir(mode=0o700)
        data = {'version': 1, 'state': str(path), 'workdir': str(source),
                'source_identity': source_id, 'root_identity': identity(root),
                'budget_bytes': budget, 'runs': {}}
        write_json(path, data)
        return data


def storage_root(path, data):
    root = root_for(path)
    if root.resolve() != root or identity(root) != data['root_identity']:
        raise ValueError('Managed storage was replaced; preserve it for inspection.')
    return root


def tree_bytes(root, excluded=()):
    """Logical file bytes, without following symlinks or counting hardlinks twice."""
    total, seen = 0, set()
    excluded = set(excluded)
    if root.is_symlink():
        raise ValueError('Measured storage root must not be a symlink.')
    if not root.exists():
        return 0
    def unreadable(error):
        # Active commands may remove a directory after os.walk enumerates it.
        # Preserve failures for inaccessible storage; a vanished entry uses no bytes.
        if not isinstance(error, FileNotFoundError):
            raise error
    for here, dirs, files in os.walk(root, followlinks=False, onerror=unreadable):
        dirs[:] = [name for name in dirs if Path(here)/name not in excluded
                   and not (Path(here)/name).is_symlink()]
        for name in files:
            if Path(here)/name in excluded:
                continue
            try:
                info = (Path(here)/name).lstat()
            except FileNotFoundError:
                continue
            key = (info.st_dev, info.st_ino)
            if stat.S_ISREG(info.st_mode) and key not in seen:
                total += info.st_size
                seen.add(key)
    return total


def alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def active_runs(data):
    return [run for run in data['runs'].values() if not run.get('cleaned', False)]


def run_bytes(run):
    total = tree_bytes(Path(run['scratch']))
    for key in ('stdout', 'stderr'):
        file = Path(run[key])
        total += file.stat().st_size if file.exists() else 0
    return total


def committed_bytes(root, data):
    runs = active_runs(data)
    excluded = {Path(run[key]) for run in runs for key in ('scratch', 'stdout', 'stderr')}
    # Writers do not take the index lock. Count fixed reservations separately rather than
    # subtracting a later usage sample from an earlier total while files can grow.
    retained = tree_bytes(root, excluded)
    return retained + sum(max(run['reserve_bytes'], run_bytes(run)) for run in runs)


def status(path):
    data = load(path)
    root = storage_root(path, data)
    result = dict(data, root=str(root), used_bytes=tree_bytes(root),
                  committed_bytes=committed_bytes(root, data),
                  active_runs=[dict(run, runner_alive=alive(run['runner_pid'])) for run in active_runs(data)])
    try:
        validate_source(data)
        result['source_valid'] = True
    except (OSError, ValueError) as error:
        result.update(source_valid=False, source_error=str(error))
    return result


def remove_scratch(run):
    target = Path(run['scratch'])
    if identity(target) != run['scratch_identity'] or target.resolve() != target:
        raise ValueError('Scratch identity changed; refusing cleanup.')
    marker = target/'.duo-scratch.json'
    if marker.is_symlink() or json.loads(marker.read_text()) != {'id': run['id']}:
        raise ValueError('Scratch ownership marker changed; refusing cleanup.')
    shutil.rmtree(target)




def reserve(path, name, reserve_mib):
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}', name) or reserve_mib <= 0:
        raise ValueError('Use a short alphanumeric run name and a positive reservation.')
    with locked(path):
        data = load(path)
        validate_source(data)
        root = storage_root(path, data)
        if any(run['name'] == name for run in active_runs(data)):
            raise ValueError('Run is active or unresolved; inspect/recover it instead of creating a replacement.')
        amount = reserve_mib * MIB
        if committed_bytes(root, data) + amount > data['budget_bytes']:
            raise ValueError('Workspace storage budget exceeded; close existing runs or justify a revised budget.')
        if shutil.disk_usage(root).free < amount:
            raise ValueError('Insufficient free disk for the declared reservation.')
        parent = root/'scratch'
        if parent.is_symlink():
            raise ValueError('Scratch parent must not be a symlink.')
        parent.mkdir(exist_ok=True, mode=0o700)
        evidence = root/'results'
        if evidence.is_symlink():
            raise ValueError('Results parent must not be a symlink.')
        evidence.mkdir(exist_ok=True, mode=0o700)
        target = parent/name
        target.mkdir(mode=0o700)  # Existing unregistered contents are never adopted or removed.
        token = str(uuid.uuid4())
        write_json(target/'.duo-scratch.json', {'id': token})
        run = {'id': token, 'name': name, 'status': 'starting', 'cleaned': False,
               'runner_pid': os.getpid(), 'child_pid': None, 'reserve_bytes': amount,
               'scratch': str(target), 'scratch_identity': identity(target),
               'stdout': str(evidence/(token+'.stdout.txt')), 'stderr': str(evidence/(token+'.stderr.txt')),
               'receipt': str(evidence/(token+'.json'))}
        data['runs'][name] = run
        write_json(path, data)
        return run


def save_run(path, run):
    with locked(path):
        data = load(path)
        if data['runs'].get(run['name'], {}).get('id') != run['id']:
            raise ValueError('Run ownership changed; inspect before continuing.')
        storage_root(path, data)
        data['runs'][run['name']] = run
        write_json(path, data)


def over_budget(path, run):
    data = load(path)
    root = storage_root(path, data)
    return run_bytes(run) > run['reserve_bytes'] or tree_bytes(root) > data['budget_bytes']


def execute(path, args):
    command = args.argv[1:] if args.argv[:1] == ['--'] else args.argv
    if not command or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('Supply a command and positive timeout.')
    run = reserve(path, args.name, args.reserve_mib)
    process = None
    code = 126
    try:
        if args.packet:
            from review_packet import check, materialize
            run['input_packet'] = materialize(args.packet.resolve(), Path(run['scratch']), load(path)['workdir'])
        with open(run['stdout'], 'x') as output, open(run['stderr'], 'x') as errors:
            os.chmod(run['stdout'], 0o600)
            os.chmod(run['stderr'], 0o600)
            process = subprocess.Popen(command, cwd=run['scratch'], stdin=subprocess.DEVNULL,
                                       stdout=output, stderr=errors, start_new_session=True)
            run.update(status='running', child_pid=process.pid)
            save_run(path, run)
            deadline = time.monotonic() + args.timeout
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    run['status'], code = 'timeout', 124
                    break
                if over_budget(path, run):
                    run['status'], code = 'budget_exceeded', 125
                    break
                time.sleep(.2)
            else:
                code = process.returncode
                run['status'] = 'complete' if code == 0 else 'failed'
            stop_group(process)
            if over_budget(path, run):
                run['status'], code = 'budget_exceeded', 125
            if args.packet:
                run['input_packet']['source_matches'] = False
                run['input_packet'] = check(args.packet.resolve(), load(path)['workdir'])
                if not run['input_packet']['source_matches'] and code == 0:
                    run['status'], code = 'stale_source', 3
    except KeyboardInterrupt:
        run['status'], code = 'interrupted', 130
    except (OSError, ValueError) as error:
        run.update(status='failed', error=str(error))
        code = 126
    finally:
        if process:
            stop_group(process)
        try:
            storage_root(path, load(path))
            remove_scratch(run)
            run['cleaned'] = True
        except (OSError, ValueError) as error:
            run.update(status='cleanup_required', error=str(error))
            code = 126
        run['exit_code'] = code
        save_run(path, run)
        write_json(Path(run['receipt']), run)
    return run, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', type=Path, required=True)
    commands = parser.add_subparsers(dest='command', required=True)
    bound = commands.add_parser('bind')
    bound.add_argument('--workdir', type=Path, required=True)
    bound.add_argument('--budget-mib', type=int)
    commands.add_parser('status')
    budget = commands.add_parser('budget')
    budget.add_argument('--mib', type=int, required=True)
    budget.add_argument('--reason', required=True)
    run = commands.add_parser('run', help='Only disposable checks; scratch is removed even on failure.')
    run.add_argument('--name', required=True)
    run.add_argument('--reserve-mib', type=int, required=True)
    run.add_argument('--timeout', type=float, default=1800)
    run.add_argument('--packet', type=Path)
    run.add_argument('argv', nargs=argparse.REMAINDER)
    recover = commands.add_parser('recover')
    recover.add_argument('--name', required=True)
    recover.add_argument('--id', required=True)
    args = parser.parse_args()
    path = args.state.expanduser().resolve()
    code = 0
    try:
        if args.command == 'bind':
            result = bind(path, args.workdir, args.budget_mib)
        elif args.command == 'status':
            result = status(path)
        elif args.command == 'run':
            result, code = execute(path, args)
        elif args.command == 'budget':
            with locked(path):
                data = load(path)
                root = storage_root(path, data)
                if args.mib <= 0 or not args.reason.strip() or args.mib*MIB < committed_bytes(root, data):
                    raise ValueError('Supply a reason and budget covering existing use/reservations.')
                data.setdefault('budget_changes', []).append({'before': data['budget_bytes'],
                    'after': args.mib*MIB, 'reason': args.reason})
                data['budget_bytes'] = args.mib*MIB
                write_json(path, data)
                result = data
        else:
            with locked(path):
                data = load(path)
                storage_root(path, data)
                run = data['runs'].get(args.name)
                if not run or run['id'] != args.id or run['cleaned']:
                    raise ValueError('Select the exact unresolved run from status.')
                if run['status'] == 'starting' and run['child_pid'] is None:
                    raise ValueError('Launch outcome is unknown; inspect host processes before any manual recovery.')
                if alive(run['runner_pid']) or alive(run['child_pid']):
                    raise ValueError('Runner/child is still present; stop or inspect it through its host first.')
                if run['child_pid']:
                    try:
                        os.killpg(run['child_pid'], 0)
                    except ProcessLookupError:
                        pass
                    else:
                        raise ValueError('Child process group is still present; inspect it before recovery.')
                remove_scratch(run)
                run.update(status='recovered', cleaned=True)
                write_json(path, data)
                write_json(Path(run['receipt']), run)
                result = run
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    raise SystemExit(code)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    signal.signal(signal.SIGHUP, signal.default_int_handler)
    main()
