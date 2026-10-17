"""Discovery, explicit ownership transfer, managed manual use, and acknowledged sync."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import uuid

from native_history import config_home, delta, owner_manual_changes, seat, snapshot
from setup_models import selected_peer
from process_control import stop_group
import workspace
from session_store import create, is_versioned_model, listing, new_pair, register, state_dir, validate


@contextmanager
def pair_lock(path):
    with path.with_name(path.name+'.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('This pair already has an active call; reattach or wait.') from error
        yield


def require_owner(record, args):
    if record['owner'] != args.owner or record['owner_thread'] != args.thread:
        raise ValueError('This pair belongs to another owner tool or conversation.')


def require_task(record, task_id):
    if task_id != record.get('task_id'):
        raise ValueError('Task identity mismatch; supply the intended --task-id from list/show.')


def resume_command(record, role, model=None):
    info = seat(record, role)
    if not info['session_id']:
        raise ValueError('Peer not started; no resumable native identity yet.')
    if model and info['model'] and model != info['model']:
        raise ValueError('Retain the recorded model for this conversation.')
    model = model or info['model']
    if not model:
        raise ValueError('The selected owner model is unknown; supply --model from the actual host.')
    if not is_versioned_model(model):
        raise ValueError('Bind the actual versioned model before resuming; mutable aliases cannot pin this seat.')
    if role == 'claude':
        return ['claude', '--resume', info['session_id'], '--model', model, '--effort', 'xhigh',
                '--tools', 'Read,Grep,Glob', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}']
    return ['codex', 'resume', info['session_id'], '--model', model,
            '-c', 'model_reasoning_effort="xhigh"', '--sandbox', 'read-only', '--ask-for-approval', 'never']


def describe(record, path):
    result = dict(record)
    result['conversations'] = {}
    if 'task_id' in record:
        result['workspace_state'] = str(workspace.pair_workspace(record))
        result['workspace_status_command'] = shlex.join([sys.executable,
            str(Path(__file__).with_name('workspace.py')), '--state', result['workspace_state'], 'status'])
    for role in ('codex', 'claude'):
        info = seat(record, role)
        environment = ['env', 'DUO_STATE_DIR='+str(state_dir()),
                       'CODEX_HOME='+seat(record, 'codex')['config_home'],
                       'CLAUDE_CONFIG_DIR='+seat(record, 'claude')['config_home']]
        def terminal_command(command):
            return '(cd '+shlex.quote(record['workdir'])+' && '+shlex.join(environment+command)+')'
        item = info | {'name': record['task']+' · '+role,
                       'manual_command': terminal_command([sys.executable,
                           str(Path(__file__).with_name('pair.py')), 'manual', '--pair', str(path), '--role', role])}
        item['requires_model'] = not bool(info['model'])
        item['resumable'] = role == record['owner'] or bool(record['started'])
        if item['resumable'] and info['model']:
            item['native_command'] = terminal_command(resume_command(record, role))
        result['conversations'][role] = item
    return result




@contextmanager
def manual_terminal(process):
    """Give the new child group the controlling terminal, then restore its owner."""
    descriptor = sys.stdin.fileno()
    if not os.isatty(descriptor):
        yield
        return
    original = os.tcgetpgrp(descriptor)
    handler = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    try:
        os.tcsetpgrp(descriptor, process.pid)
        os.killpg(process.pid, signal.SIGCONT)
        yield
    finally:
        os.tcsetpgrp(descriptor, original)
        signal.signal(signal.SIGTTOU, handler)


def handle(parser, args, path, load, save):
    try:
        if args.command == 'list':
            print(json.dumps(listing(args.task, args.workdir), indent=2))
            return
        with pair_lock(path):
            record = load(path)
            if args.command == 'adopt':
                # Register in place. A second physical copy cannot claim the same task ID.
                record.setdefault('claude_config_dir', config_home('claude'))
                record.setdefault('codex_config_dir', config_home('codex'))
                register(record, path)
                save(path, record)
                print(json.dumps(describe(record, path), indent=2))
                return
            if args.command == 'show':
                if 'task_id' not in record:
                    record['needs_adoption'] = True
                print(json.dumps(describe(record, path), indent=2))
                return
            validate(record, path)
            if Path.cwd().resolve() != Path(record['workdir']).resolve():
                raise ValueError('Run from the paired workdir; do not reuse another checkout.')
            if record['status'] != 'ready':
                raise ValueError('Prior call is unresolved or manual use is active; inspect before continuing.')
            if args.command == 'fork':
                model = args.opus_model if args.owner == 'codex' else args.codex_model
                model = model or selected_peer(args.owner)
                child = new_pair(args.owner, args.thread, args.task, record['workdir'], model, args.owner_model)
                child.update(parent_task_id=record['task_id'], fork_reason=args.reason)
                print(json.dumps(create(child, args.new_pair.resolve(), new_task=True)))
                return
            if args.command in ('handoff', 'manual'):
                workspace.bind(workspace.pair_workspace(record), record['workdir'])
            if args.command == 'handoff':
                require_task(record, args.task_id)
                if args.owner_model and not is_versioned_model(args.owner_model):
                    raise ValueError('Supply an explicit versioned owner model, or leave it unknown.')
                if record['owner'] != args.expect_owner or record['owner_thread'] != args.expect_thread:
                    raise ValueError('Ownership changed; inspect the current owner before handoff.')
                delta(record)  # Validate acknowledged history before resetting a new owner's cursor.
                if 'owner_manual_head' in record:
                    raise ValueError('Reconcile managed owner manual changes with sync/ack before handoff.')
                context = args.context.read_text()
                if not context.strip():
                    raise ValueError('Handoff context must contain current scope, decisions and pending work.')
                previous = {'owner': record['owner'], 'owner_thread': record['owner_thread'],
                            'peer_tool': record['peer_tool'], 'peer_session_id': record['peer_session_id'],
                            'reason': args.reason, 'context': context}
                if args.owner != record['owner']:
                    peer = seat(record, record['owner'])
                    model = args.opus_model if record['owner'] == 'claude' else args.codex_model
                    if model and peer['model'] and model != peer['model']:
                        raise ValueError('Retain the recorded model for the continuing conversation.')
                    model = model or peer['model']
                    if not is_versioned_model(model) or (record['owner'] == 'claude' and 'opus' not in model.lower()):
                        raise ValueError('Supply the selected previous-owner model for the new peer route.')
                    snapshot(record, record['owner'])  # Prove retained native history before reversal.
                    record.update(peer_tool=record['owner'], peer_session_id=peer['session_id'],
                                  peer_model=model, started=True)
                record.setdefault('handoffs', []).append(previous)
                record.update(owner=args.owner, owner_thread=args.thread, owner_model=args.owner_model,
                              owner_config_dir=config_home(args.owner))
                record.pop('read_head', None)
                record.pop('sync_pending', None)
                save(path, record)
                print(json.dumps(describe(record, path), indent=2))
                return
            if args.command in ('sync', 'ack'):
                require_owner(record, args)
                current = delta(record)
                owner_changes = owner_manual_changes(record)
                if args.command == 'sync':
                    token = str(uuid.uuid4())
                    record['sync_pending'] = {'token': token, 'head': current['head'], 'owner_head': owner_changes['head']}
                    save(path, record)
                    print(json.dumps({'token': token, 'turns': current['turns'],
                        'native_history_path': current['path'], 'manual_owner_turns': owner_changes['turns'],
                        'manual_owner_history_path': owner_changes['path'],
                        'handoffs': record.get('handoffs', []), 'last_snapshot': record.get('last_snapshot'),
                        'last_result': record.get('last_result')}, indent=2))
                else:
                    pending = record.get('sync_pending', {})
                    if pending.get('token') != args.token:
                        raise ValueError('Unknown or stale sync token; read sync before acknowledgement.')
                    if pending.get('head') != current['head'] or pending.get('owner_head') != owner_changes['head']:
                        raise ValueError('Native history changed after sync; read the new turns before acknowledgement.')
                    record['read_head'] = current['head']
                    record.pop('owner_manual_head', None)
                    record.pop('owner_manual_end', None)
                    record.pop('sync_pending', None)
                    save(path, record)
                    print(json.dumps({'acknowledged': True}))
                return
            if args.command == 'manual':
                if args.role == record['peer_tool'] and not record['started']:
                    raise ValueError('Peer not started; dispatch before opening it manually.')
                before = snapshot(record, args.role)
                command = resume_command(record, args.role, args.model)
                if args.role == record['owner']:
                    record.setdefault('owner_manual_head', before['head'])
                    if not record.get('owner_model'):
                        record['owner_model'] = args.model
                record.update(status='manual', manual_role=args.role)
                save(path, record)
                process = None
                try:
                    # Inherit the user's terminal. The canonical lock stays held for the whole TUI.
                    process = subprocess.Popen(command, cwd=record['workdir'], preexec_fn=os.setpgrp)
                    record['manual_pid'] = process.pid
                    save(path, record)
                    with manual_terminal(process):
                        code = process.wait()
                    if code:
                        raise ValueError(f'Manual CLI exited {code}; inspect its native history.')
                    stop_group(process)
                    after = snapshot(record, args.role)
                    if args.role == record['owner']:
                        record['owner_manual_end'] = after['head']
                except BaseException:
                    try:
                        if process:
                            stop_group(process)
                    finally:
                        record['status'] = 'held'
                        save(path, record)
                    raise
                record['status'] = 'ready'
                record.pop('manual_pid', None)
                record.pop('manual_role', None)
                save(path, record)
                return
    except (OSError, ValueError) as error:
        parser.error(str(error))
