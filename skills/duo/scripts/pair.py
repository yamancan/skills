#!/usr/bin/env python3
"""Bind a Codex or Claude task to one persistent peer session. POSIX, stdlib only."""
import argparse
import json
import os
import signal
from pathlib import Path
import subprocess
import tempfile
import uuid

from native_history import config_home, delta, snapshot
from setup_models import selected_peer
import workspace
import review_packet
from session_commands import handle, pair_lock, require_task
from process_control import stop_group
from session_store import create, is_versioned_model, new_pair, validate, write_json


def save(path, data):
    write_json(path, data)


def load(path):
    record = json.loads(path.read_text())
    if 'owner' not in record:  # Keep existing Codex -> Opus pairs resumable.
        record.update(owner='codex', owner_thread=record.pop('codex_thread'),
                      peer_tool='claude', peer_model=record.pop('opus_model'),
                      peer_session_id=record.pop('opus_session_id'))
    return record


def claude_state_dir():
    return Path(os.environ.get('CLAUDE_CONFIG_DIR') or Path.home() / '.claude').expanduser().resolve()


def claude_transcript(record, required):
    native = snapshot(record, 'claude', optional=not required)
    responses = {turn['uuid']: turn['text'] for turn in native['turns']
                 if turn['role'] == 'assistant' and turn.get('uuid') and turn['text']}
    if required and not responses:
        raise ValueError('No persisted assistant response in the recorded Claude session.')
    return Path(native['path']) if native['path'] else None, responses


def prepare_claude(record):
    state = claude_state_dir()
    if record.get('claude_config_dir', str(state)) != str(state):
        raise ValueError('Claude state directory changed; use the paired CLAUDE_CONFIG_DIR.')
    record['claude_config_dir'] = str(state)
    transcript, responses = claude_transcript(record, required=record['started'])
    if transcript and not record['started']:
        raise ValueError('Unstarted pair already has a persisted transcript; inspect the session before resuming.')
    try:
        projects = state / 'projects'
        projects.mkdir(parents=True, exist_ok=True)
        # A real create/write/delete probe catches host sandbox denial that os.access misses.
        with tempfile.TemporaryFile(dir=projects) as probe:
            probe.write(b'duo'); probe.flush()
        if transcript:
            with tempfile.TemporaryFile(dir=transcript.parent) as probe:
                probe.write(b'duo'); probe.flush()
            with transcript.open('ab'):
                pass  # Check append permission without altering conversation contents.
    except OSError as error:
        raise ValueError(f'Claude session storage is not writable: {state} ({error.strerror}). '
                         'Use host-approved session-state write access; keep reviewer tools read-only.') from error
    return responses


def peer_command(record):
    if record['peer_tool'] == 'claude':
        flag = '--resume' if record['started'] else '--session-id'
        return ['claude', '--safe-mode', '--model', record['peer_model'], '--effort', 'xhigh',
                flag, record['peer_session_id'], '--tools', 'Read,Grep,Glob',
                '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '-p', '--output-format', 'stream-json', '--verbose']
    command = ['codex', 'exec']
    if record['peer_session_id']:
        command += ['resume', record['peer_session_id']]
    return command + ['--model', record['peer_model'], '--json', '--ignore-user-config',
                      '-c', 'model_reasoning_effort="xhigh"',
                      '-c', 'sandbox_mode="read-only"', '-c', 'approval_policy="never"', '-']


def retain_codex_id(raw, record):
    # Recover an emitted ID even when a later JSONL line is cut off.
    for line in raw.split('\n'):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get('type') == 'thread.started':
            session = event.get('thread_id')
            if isinstance(session, str) and session and not record['peer_session_id']:
                record['peer_session_id'] = session


def invoke(command, workdir, prompt, output, errors, timeout):
    process = subprocess.Popen(command, cwd=workdir, stdin=subprocess.PIPE,
                               stdout=output, stderr=errors, text=True, start_new_session=True)
    try:
        process.communicate(input=prompt, timeout=timeout)
    except BaseException:
        stop_group(process)
        raise
    stop_group(process)
    return process.returncode


def codex_result(raw, record):
    # JSONL rows end at LF only; splitlines() would also cut at U+2028/U+2029 inside JSON strings.
    events = [json.loads(line) for line in raw.split('\n') if line.strip()]
    if not all(isinstance(event, dict) for event in events):
        raise ValueError('Invalid Codex event')
    ids = [e['thread_id'] for e in events if e.get('type') == 'thread.started']
    if len(ids) != 1 or not isinstance(ids[0], str) or not ids[0]:
        raise ValueError('Missing or ambiguous Codex session ID')
    if record['peer_session_id'] and ids[0] != record['peer_session_id']:
        raise ValueError('Codex resumed another session')
    record['peer_session_id'] = ids[0]  # Preserve even when the turn did not complete.
    completed = [e for e in events if e.get('type') == 'turn.completed']
    if len(completed) != 1 or any(e.get('type') in ('error', 'turn.failed') for e in events):
        raise ValueError('Codex turn incomplete or failed')
    messages = [e['item']['text'] for e in events if e.get('type') == 'item.completed'
                and e.get('item', {}).get('type') == 'agent_message']
    if not messages:
        raise ValueError('Codex returned no answer')
    return {'session_id': ids[0], 'is_error': False, 'result': '\n'.join(messages),
            'usage': completed[0].get('usage', {})}


def claude_result(raw, record):
    """A stream can show work long before it contains a completed response."""
    events = [json.loads(line) for line in raw.split('\n') if line.strip()]
    if not all(isinstance(event, dict) for event in events):
        raise ValueError('Invalid Claude event')
    results = [event for event in events if event.get('type') == 'result']
    if len(results) != 1 or any(event.get('type') == 'error' for event in events):
        raise ValueError('Claude stream has no unique completed result; progress is not a review.')
    result = dict(results[0])
    initial = [event for event in events
               if event.get('type') == 'system' and event.get('subtype') == 'init']
    if len(initial) != 1:
        raise ValueError('Claude stream needs one runtime initialization event.')
    runtime = initial[0]
    tools = runtime.get('tools')
    if (runtime.get('session_id') != record['peer_session_id']
            or runtime.get('model') != record['peer_model']
            or not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools)
            or set(tools) != {'Read', 'Grep', 'Glob'}
            or runtime.get('mcp_servers') != []
            or runtime.get('permissionMode') == 'bypassPermissions'):
        raise ValueError('Claude runtime differs from the pinned session/model or read-only tool policy.')
    result['runtime_evidence'] = {key: runtime.get(key) for key in (
        'session_id', 'model', 'tools', 'mcp_servers', 'apiKeySource', 'permissionMode', 'claude_code_version')}
    return result


def dispatch(parser, args, path):
    with pair_lock(path):
        record = load(path)
        validate(record, path)
        require_task(record, args.task_id)
        if record['owner'] != args.owner or record['owner_thread'] != args.thread:
            parser.error('This pair belongs to another owner tool or conversation.')
        if Path.cwd().resolve() != Path(record['workdir']).resolve():
            parser.error('Run from the paired workdir; do not reuse another checkout.')
        if record['status'] != 'ready':
            parser.error('Prior call is unresolved. Inspect the paired session before recovery.')
        workspace.bind(workspace.pair_workspace(record), record['workdir'])
        expected_peer = 'claude' if record['owner'] == 'codex' else 'codex'
        if (record['peer_tool'] != expected_peer or record['effort'] != 'xhigh'
                or not is_versioned_model(record['peer_model'])
                or (expected_peer == 'claude' and 'opus' not in record['peer_model'].lower())
                or (record['started'] and not record['peer_session_id'])):
            parser.error('Retain the paired peer model, session and xhigh effort.')
        prior_responses = {}
        if expected_peer == 'claude':
            try:
                prior_responses = prepare_claude(record)
            except (OSError, ValueError) as error:
                parser.error(f'{error} No peer started.')
        current = delta(record)
        if current['turns'] or 'owner_manual_head' in record:
            parser.error('Unread native conversation changes; run sync, reconcile decisions and ack before dispatch.')
        prompt = args.prompt.read_text()
        review = {'source_verified': False, 'reason': 'Legacy snapshot label; no source manifest supplied.'}
        if args.packet:
            review = review_packet.check(args.packet.resolve(), record['workdir'])
            if not review['source_matches']:
                raise ValueError('Review packet is stale; refresh changed inputs before dispatch.')
            prompt += '\n\nReview the frozen inputs listed by '+str(args.packet.resolve())+'. Report actual file coverage and missing required context.'
        result_path = path.with_name(path.stem + '.' + expected_peer + '-' + str(uuid.uuid4()) + '.jsonl')
        stderr_path = result_path.with_suffix('.stderr.txt')
        record.update(status='in_flight', pending_snapshot=args.snapshot,
                      last_attempt_result=str(result_path), last_attempt_stderr=str(stderr_path))
        save(path, record)
        try:
            # Persist output during the call, including when the parent is interrupted.
            result_path.touch(mode=0o600, exist_ok=False)
            stderr_path.touch(mode=0o600, exist_ok=False)
            with result_path.open('w') as output, stderr_path.open('w') as errors:
                returncode = invoke(peer_command(record), record['workdir'], prompt,
                                    output, errors, args.timeout)
            raw = result_path.read_text()
            if expected_peer == 'codex':
                retain_codex_id(raw, record)
            result = claude_result(raw, record) if expected_peer == 'claude' else codex_result(raw, record)
            save(path, record)
            if (returncode != 0 or not isinstance(result, dict)
                    or result.get('is_error') is not False
                    or result.get('session_id') != record['peer_session_id']):
                raise ValueError('Peer did not complete in the paired session')
            if expected_peer == 'claude':
                _, responses = claude_transcript(record, required=True)
                matching = [key for key, value in responses.items()
                            if key not in prior_responses and value == result.get('result')]
                if not matching:
                    raise ValueError('The new Claude response was not persisted in the paired session.')
                record['peer_response_id'] = matching[-1]
            # Require retained native history for both routes, and acknowledge this returned turn.
            native = snapshot(record, expected_peer, previous=current['head'])
            if expected_peer == 'codex':
                before_size = current['head']['size'] if current['head'] else 0
                new_answers = [turn['text'] for turn in native['turns']
                               if turn['role'] == 'assistant' and turn['offset'] > before_size]
                if '\n'.join(new_answers) != result['result']:
                    raise ValueError('The new Codex response was not persisted in the paired native transcript.')
            record['read_head'] = native['head']
        except (Exception, KeyboardInterrupt) as error:
            if expected_peer == 'codex' and result_path.exists():
                retain_codex_id(result_path.read_text(), record)
            record.update(status='held', last_error=str(error) or 'Peer interrupted')
            save(path, record)
            parser.error(f'{error}; call held. Inspect {result_path} and {stderr_path}.')
        record.update(started=True, status='ready', last_snapshot=args.snapshot,
                      last_result=str(result_path))
        if expected_peer == 'claude':
            record['last_runtime_evidence'] = result['runtime_evidence']
        record.pop('pending_snapshot', None)
        record.pop('last_error', None)
        if args.packet:
            try:
                review = review_packet.check(args.packet.resolve(), record['workdir'])
                review['source_verified'] = review['source_matches']
            except (OSError, ValueError, KeyError) as error:
                review = {'source_verified': False, 'manifest': str(args.packet.resolve()), 'error': str(error)}
        record['last_review_evidence'] = review
        save(path, record)
        result['review_evidence'] = review
        print(json.dumps(result))
        if args.packet and not review['source_verified']:
            raise SystemExit(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    run = commands.add_parser('run')
    show = commands.add_parser('show', help='Show exact native IDs and managed manual commands.')
    adopt = commands.add_parser('adopt', help='Index an existing pair in place without creating a peer.')
    handoff = commands.add_parser('handoff', help='Explicitly transfer a ready task, preserving peer history.')
    fork = commands.add_parser('fork', help='Create an explicitly separate fresh context with a parent task.')
    manual = commands.add_parser('manual', help='Open the exact native peer while holding the canonical lock.')
    sync = commands.add_parser('sync', help='Read native turns added since the last acknowledged result.')
    ack = commands.add_parser('ack', help='Acknowledge the exact native history returned by sync.')
    listed = commands.add_parser('list', help='Discover tasks across owner conversations.')
    listed.add_argument('--task', default='', help='Case-insensitive title search; never an identity selector.')
    listed.add_argument('--workdir', type=Path)
    for command in (init, run, handoff, fork, sync, ack):
        command.add_argument('--pair', type=Path, required=True)
        command.add_argument('--thread', required=True)
        command.add_argument('--owner', choices=('codex', 'claude'), default='codex')
    for command in (show, adopt, manual):
        command.add_argument('--pair', type=Path, required=True)
    for command in (init, handoff, fork):
        command.add_argument('--owner-model', help='Observed active owner model; otherwise retained as unknown.')
        command.add_argument('--opus-model')
        command.add_argument('--codex-model')
    init.add_argument('--task', required=True)
    init.add_argument('--task-id', help='Continue this exact discovered task; never invent its identity.')
    init.add_argument('--new-task', action='store_true', help='Explicitly create a separate task, even with the same title.')
    init.add_argument('--workdir', type=Path, default=Path.cwd(),
                      help='Optional legacy assertion; must equal the caller directory.')
    run.add_argument('--task-id', required=True)
    run.add_argument('--prompt', type=Path, required=True)
    run.add_argument('--snapshot', required=True)
    run.add_argument('--packet', type=Path, help='Frozen source manifest; stale inputs fail before/after dispatch.')
    run.add_argument('--timeout', type=int, default=300)
    handoff.add_argument('--task-id', required=True)
    handoff.add_argument('--expect-owner', choices=('codex', 'claude'), required=True)
    handoff.add_argument('--expect-thread', required=True)
    handoff.add_argument('--reason', required=True)
    handoff.add_argument('--context', type=Path, required=True, help='Current scope, decisions, acceptance and pending work.')
    fork.add_argument('--new-pair', type=Path, required=True)
    fork.add_argument('--task', required=True)
    fork.add_argument('--reason', required=True)
    manual.add_argument('--role', choices=('codex', 'claude'), required=True)
    manual.add_argument('--model', help='Required when the recorded owner model is unknown.')
    ack.add_argument('--token', required=True)
    args = parser.parse_args()
    path = args.pair.resolve() if hasattr(args, 'pair') else None
    if args.command not in ('init', 'run'):
        handle(parser, args, path, load, save)
        return
    if args.command == 'init':
        if args.workdir.resolve() != Path.cwd().resolve():
            parser.error('Initialize from the caller directory; workdir must match it.')
        model = args.opus_model if args.owner == 'codex' else args.codex_model
        try:
            model = model or selected_peer(args.owner)
            record = new_pair(args.owner, args.thread, args.task, args.workdir, model, args.owner_model)
        except ValueError as error:
            parser.error(str(error))
        if args.new_task and args.task_id:
            parser.error('Choose either existing task identity or an explicitly new task.')
        try:
            record = create(record, path, new_task=args.new_task, task_id=args.task_id)
            workspace.bind(workspace.pair_workspace(record), record['workdir'])
            print(json.dumps(record))
        except (OSError, ValueError) as error:
            parser.error(str(error))
        return
    if args.timeout <= 0:
        parser.error('Timeout must be positive.')
    try:
        dispatch(parser, args, path)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, signal.default_int_handler)
    signal.signal(signal.SIGHUP, signal.default_int_handler)
    main()
