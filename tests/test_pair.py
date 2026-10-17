import json
import os
import signal
import uuid
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


from _support import DUO_SCRIPTS

SCRIPT = DUO_SCRIPTS / 'pair.py'


class PairRouting(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'work'
        self.work.mkdir()
        self.pair = self.root / 'pair.json'
        self.prompt = self.root / 'brief.txt'
        self.prompt.write_text('Review this bounded slice.')
        self.fake = self.root / 'claude'
        self.fake.write_text('''#!/usr/bin/env python3
import json, os, sys, time, uuid
from pathlib import Path
a = sys.argv[1:]
session = a[a.index('--session-id')+1] if '--session-id' in a else a[a.index('--resume')+1]
if 'CUSTOM_STARTUP_FAILS' in os.environ and '--safe-mode' not in a:
    print('Custom startup blocked the reviewer', file=sys.stderr)
    sys.exit(42)
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps({'args': a, 'prompt': sys.stdin.read(), 'cwd': os.getcwd()})+'\\n')
streaming = '--output-format' in a and a[a.index('--output-format')+1] == 'stream-json'
if streaming:
    initial = {'type': 'system', 'subtype': 'init', 'session_id': session,
               'model': a[a.index('--model')+1], 'tools': ['Read', 'Grep', 'Glob'],
               'mcp_servers': [], 'apiKeySource': 'none', 'permissionMode': 'auto'}
    bad = os.environ.get('BAD_CLAUDE_INIT')
    if bad == 'session': initial['session_id'] = 'unrelated-session'
    if bad == 'model': initial['model'] = 'unrequested-model'
    if bad == 'tools': initial['tools'].append('Bash')
    if bad == 'mcp': initial['mcp_servers'] = [{'name': 'unrequested-server'}]
    if bad == 'permission': initial['permissionMode'] = 'bypassPermissions'
    if bad != 'missing': print(json.dumps(initial), flush=True)
if 'GATE' in os.environ:
    Path(os.environ['GATE']+'.entered').touch()
    while not Path(os.environ['GATE']).exists(): time.sleep(0.01)
store = Path(os.environ['CLAUDE_CONFIG_DIR']) / 'projects' / 'test-project'
if 'NO_PERSIST' not in os.environ:
    store.mkdir(parents=True, exist_ok=True)
    with (store / (session + '.jsonl')).open('a') as f:
        row = {'type': 'assistant', 'sessionId': os.environ.get('TRANSCRIPT_SESSION', session),
               'uuid': str(uuid.uuid4()), 'message': {'content': [{'type': 'text', 'text': 'Reviewed'}]}}
        if 'METADATA_ONLY' in os.environ:
            row = {'type': 'cost-state', 'sessionId': session}
        f.write(json.dumps(row)+'\\n')
result = {'session_id': os.environ.get('WRONG_SESSION', session), 'is_error': False, 'result': 'Reviewed'}
if streaming:
    result.update(type='result', subtype='success')
print(json.dumps(result))
''')
        self.fake.chmod(0o700)
        codex = self.root / 'codex'
        codex.write_text('''#!/usr/bin/env python3
import json, os, sys, subprocess, time
from pathlib import Path
a = sys.argv[1:]
state = Path(os.environ['CODEX_STATE'])
if 'resume' in a:
    session = a[a.index('resume')+1]
else:
    session = os.environ.get('CODEX_NEW_SESSION', '01a10000-1111-7222-8333-000000000001')
    state.write_text(session)
with open(os.environ['CALL_LOG'], 'a') as f:
    f.write(json.dumps({'args': a, 'prompt': sys.stdin.read(), 'cwd': os.getcwd()})+'\\n')
print(json.dumps({'type': 'thread.started', 'thread_id': os.environ.get('WRONG_SESSION', session)}), flush=True)
if 'CODEX_SUCCESS_CHILD' in os.environ:
    child = subprocess.Popen([sys.executable, '-c', 'import time; from pathlib import Path; p=Path('+repr(os.environ['CODEX_SUCCESS_CHILD'])+'); [(p.write_text(str(i)), time.sleep(0.02)) for i in range(2000)]'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Path(os.environ['CHILD_ID']).write_text(str(child.pid))
    while not Path(os.environ['CODEX_SUCCESS_CHILD']).exists(): time.sleep(0.01)
if 'TIMEOUT_CHILD' in os.environ:
    subprocess.Popen([sys.executable, '-c', 'import time; from pathlib import Path; p=Path('+repr(os.environ['TIMEOUT_CHILD'])+'); [(p.write_text(str(i)), time.sleep(0.02)) for i in range(2000)]'])
    time.sleep(30)
if 'TRUNCATE' in os.environ:
    print('{broken', flush=True)
    sys.exit(1)
item = 'malformed item' if 'BAD_ITEM' in os.environ else {'id': 'item_0', 'type': 'agent_message', 'text': 'Codex reviewed'}
print(json.dumps({'type': 'item.completed', 'item': item}))
if 'INCOMPLETE' not in os.environ:
    print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 8, 'cached_input_tokens': 0, 'output_tokens': 2}}))
if 'CLI_FAIL' in os.environ:
    print('Provider refused the request', file=sys.stderr)
    sys.exit(1)
store = Path(os.environ['CODEX_HOME']) / 'sessions' / '2026' / '10' / '08'
store.mkdir(parents=True, exist_ok=True)
transcript = store / ('rollout-test-' + session + '.jsonl')
if not transcript.exists():
    transcript.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': session, 'cwd': os.getcwd()}})+'\\n')
with transcript.open('a') as f:
    f.write(json.dumps({'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant',
        'content': [{'type': 'output_text', 'text': os.environ.get('CODEX_TRANSCRIPT_TEXT', 'Codex reviewed')}]}})+'\\n')
''')
        codex.chmod(0o700)
        self.store = self.root/'claude-state'
        self.store.mkdir()
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=str(self.store), CODEX_HOME=str(self.root/'codex-home'),
                        DUO_STATE_DIR=str(self.root/'duo-state'), PATH=str(self.root)+os.pathsep+os.environ['PATH'],
                        CALL_LOG=str(self.root/'calls.jsonl'), CODEX_STATE=str(self.root/'codex-state'))

    def command(self, *args, cwd=None):
        if args[0] == 'run' and '--task-id' not in args:
            record = json.loads(Path(args[args.index('--pair')+1]).read_text())
            args += ('--task-id', record.get('task_id', record['pair_id']))
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              cwd=cwd or self.work, env=self.env,
                              capture_output=True, text=True, timeout=3)

    def initialize(self):
        r = self.command('init', '--pair', str(self.pair), '--thread', 'codex-A',
                         '--task', 'Registration repair', '--workdir', str(self.work),
                         '--opus-model', 'claude-opus-5-5')
        self.assertEqual(r.returncode, 0, r.stderr)

    def send(self, thread='codex-A', cwd=None):
        return self.command('run', '--pair', str(self.pair), '--thread', thread,
                            '--prompt', str(self.prompt), '--snapshot', 'commit-one', cwd=cwd)

    def test_both_owners_inherit_caller_directory_without_workdir_flag(self):
        for owner, peer_flag, model in [('codex', '--opus-model', 'claude-opus-5-5'),
                                       ('claude', '--codex-model', 'gpt-6.1-sol')]:
            with self.subTest(owner=owner):
                caller = self.root / (owner + '-caller')
                caller.mkdir()
                pair = self.root / (owner + '-inherited.json')
                thread = owner + '-caller-id'
                result = self.command('init', '--owner', owner, '--pair', str(pair),
                                      '--thread', thread, '--task', 'Caller directory',
                                      peer_flag, model, cwd=caller)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(pair.read_text())['workdir'], str(caller.resolve()))
                for _ in range(2):
                    result = self.command('run', '--owner', owner, '--pair', str(pair),
                                          '--thread', thread, '--prompt', str(self.prompt),
                                          '--snapshot', 'caller-directory-check', cwd=caller)
                    self.assertEqual(result.returncode, 0, result.stderr)
                calls = [json.loads(line) for line in (self.root/'calls.jsonl').read_text().splitlines()]
                self.assertEqual([call['cwd'] for call in calls[-2:]], [str(caller.resolve())] * 2)

    def test_initialization_rejects_a_different_workdir_for_both_owners(self):
        other = self.root / 'other-project'
        other.mkdir()
        for owner, peer_flag, model in [('codex', '--opus-model', 'claude-opus-5-5'),
                                       ('claude', '--codex-model', 'gpt-6.1-sol')]:
            with self.subTest(owner=owner):
                pair = self.root / (owner + '-wrong-project.json')
                result = self.command('init', '--owner', owner, '--pair', str(pair),
                                      '--thread', owner + '-id', '--task', 'Wrong project',
                                      '--workdir', str(other), peer_flag, model)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(pair.exists())
                self.assertFalse((self.root/'calls.jsonl').exists())

    def test_same_pair_starts_then_resumes_its_exact_opus(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        self.prompt.write_text('Review only the correction.')
        self.assertEqual(self.send().returncode, 0)
        calls = [json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(len(calls), 2)
        first, follow = calls[0]['args'], calls[1]['args']
        session = first[first.index('--session-id')+1]
        self.assertEqual(follow[follow.index('--resume')+1], session)
        self.assertEqual(calls[1]['prompt'], 'Review only the correction.')
        self.assertEqual(calls[0]['cwd'], str(self.work.resolve()))
        self.assertEqual(first[first.index('--effort')+1], 'xhigh')
        self.assertEqual(first[first.index('--model')+1], 'claude-opus-5-5')
        self.assertNotIn('--continue', follow)

    def test_read_only_review_isolated_from_custom_startup_failure(self):
        self.initialize()
        self.env['CUSTOM_STARTUP_FAILS'] = '1'
        result = self.send()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['result'], 'Reviewed')
        call = json.loads((self.root/'calls.jsonl').read_text().splitlines()[0])
        self.assertNotIn('--include-partial-messages', call['args'],
                         'Init/tool/final events suffice; token deltas needlessly duplicate the review log')

    def test_timeout_retains_stream_progress_without_claiming_completion(self):
        self.initialize()
        original = json.loads(self.pair.read_text())
        self.env['GATE'] = str(self.root/'stream-timeout-gate')
        result = self.command('run', '--pair', str(self.pair), '--thread', 'codex-A',
                              '--prompt', str(self.prompt), '--snapshot', 'stream-progress', '--timeout', '1')
        self.assertNotEqual(result.returncode, 0)
        record = json.loads(self.pair.read_text())
        self.assertEqual(record['status'], 'held')
        self.assertEqual(record['peer_session_id'], original['peer_session_id'])
        raw = Path(record['last_attempt_result']).read_text()
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        self.assertTrue(any(e.get('type') == 'system' and e.get('subtype') == 'init' for e in events),
                        'Reviewer startup progress was lost until the final response')
        self.assertFalse(any(e.get('type') == 'result' for e in events))
        self.assertNotIn('peer_response_id', record)
        for key in ('last_attempt_result', 'last_attempt_stderr'):
            self.assertEqual(Path(record[key]).stat().st_mode & 0o777, 0o600)

    def test_successful_result_cannot_hide_missing_or_wrong_initial_runtime(self):
        for wrong in ('session', 'model', 'tools', 'mcp', 'permission', 'missing'):
            with self.subTest(wrong=wrong):
                self.env['DUO_STATE_DIR'] = str(self.root/('runtime-'+wrong))
                self.pair = self.root/(wrong+'-runtime.json')
                self.env['BAD_CLAUDE_INIT'] = wrong
                self.initialize()
                result = self.send()
                self.assertNotEqual(result.returncode, 0, 'An unverified initial runtime was accepted')
                self.assertEqual(json.loads(self.pair.read_text())['status'], 'held')

    def test_wrong_thread_or_workdir_cannot_dispatch(self):
        self.initialize()
        other = self.root / 'other-work'
        other.mkdir()
        for thread, cwd in [('codex-B', self.work), ('codex-A', other)]:
            with self.subTest(thread=thread, cwd=cwd):
                self.assertNotEqual(self.send(thread, cwd).returncode, 0)
                self.assertFalse((self.root/'calls.jsonl').exists())

    def test_overlapping_dispatch_does_not_launch_a_second_opus(self):
        self.initialize()
        gate = self.root/'release'
        self.env['GATE'] = str(gate)
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'run', '--pair', str(self.pair),
                                    '--thread', 'codex-A', '--prompt', str(self.prompt),
                                    '--task-id', json.loads(self.pair.read_text())['task_id'],
                                    '--snapshot', 'commit-one'], cwd=self.work, env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic()+3
            while not Path(str(gate)+'.entered').exists() and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertTrue(Path(str(gate)+'.entered').exists())
            self.assertNotEqual(self.send().returncode, 0)
        finally:
            gate.touch()
            process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    def test_wrong_response_session_blocks_further_calls(self):
        self.initialize()
        self.env['WRONG_SESSION'] = 'unrelated-opus-session'
        self.assertNotEqual(self.send().returncode, 0)
        self.env.pop('WRONG_SESSION')
        self.assertNotEqual(self.send().returncode, 0)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    def test_two_codex_threads_keep_distinct_opus_sessions(self):
        self.initialize()
        second = self.root/'pair-B.json'
        r = self.command('init', '--pair', str(second), '--thread', 'codex-B',
                         '--task', 'Celo compatibility', '--workdir', str(self.work),
                         '--opus-model', 'claude-opus-5-5')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.send().returncode, 0)
        for _ in range(2):
            r = self.command('run', '--pair', str(second), '--thread', 'codex-B',
                             '--prompt', str(self.prompt), '--snapshot', 'commit-two')
            self.assertEqual(r.returncode, 0, r.stderr)
        calls = [json.loads(x)['args'] for x in (self.root/'calls.jsonl').read_text().splitlines()]
        session_a = calls[0][calls[0].index('--session-id')+1]
        session_b = calls[1][calls[1].index('--session-id')+1]
        self.assertNotEqual(session_a, session_b)
        self.assertEqual(calls[2][calls[2].index('--resume')+1], session_b)

    def test_existing_pair_cannot_be_replaced_by_another_thread(self):
        self.initialize()
        r = self.command('init', '--pair', str(self.pair), '--thread', 'codex-B',
                         '--task', 'Different task', '--workdir', str(self.work),
                         '--opus-model', 'claude-opus-5-5')
        self.assertNotEqual(r.returncode, 0)
        self.assertEqual(self.send().returncode, 0)

    def initialize_reverse(self):
        r = self.command('init', '--owner', 'claude', '--pair', str(self.pair),
                         '--thread', 'claude-A', '--task', 'Reverse review',
                         '--workdir', str(self.work), '--codex-model', 'gpt-6.1-sol')
        self.assertEqual(r.returncode, 0, r.stderr)

    def send_reverse(self, owner='claude'):
        return self.command('run', '--owner', owner, '--pair', str(self.pair),
                            '--thread', 'claude-A', '--prompt', str(self.prompt),
                            '--snapshot', 'reverse-one')

    def test_claude_owner_starts_then_resumes_only_its_codex(self):
        self.initialize_reverse()
        first = self.send_reverse()
        self.assertEqual(first.returncode, 0, first.stderr)
        result = json.loads(first.stdout)
        self.assertEqual(result['result'], 'Codex reviewed')
        self.prompt.write_text('Verify the revised reverse slice.')
        follow = self.send_reverse()
        self.assertEqual(follow.returncode, 0, follow.stderr)
        self.assertEqual(json.loads(follow.stdout)['session_id'], result['session_id'])
        calls = [json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertNotIn('resume', calls[0]['args'])
        self.assertEqual(calls[1]['args'][calls[1]['args'].index('resume')+1], result['session_id'])
        self.assertIn('model_reasoning_effort="xhigh"', calls[0]['args'])
        self.assertIn('sandbox_mode="read-only"', calls[1]['args'])
        self.assertIn('approval_policy="never"', calls[1]['args'])
        self.assertIn('--ignore-user-config', calls[0]['args'])
        self.assertNotIn('--last', calls[1]['args'])
        self.assertEqual(calls[1]['prompt'], 'Verify the revised reverse slice.')

    def test_reverse_pair_rejects_the_other_owner_tool(self):
        self.initialize_reverse()
        self.assertNotEqual(self.send_reverse('codex').returncode, 0)
        self.assertFalse((self.root/'calls.jsonl').exists())

    def test_codex_incomplete_turn_is_held_and_keeps_returned_session(self):
        self.initialize_reverse()
        self.env['INCOMPLETE'] = '1'
        self.assertNotEqual(self.send_reverse().returncode, 0)
        record = json.loads(self.pair.read_text())
        self.assertEqual(record['peer_session_id'], '01a10000-1111-7222-8333-000000000001')
        self.assertEqual(record['status'], 'held')
        self.env.pop('INCOMPLETE')
        self.assertNotEqual(self.send_reverse().returncode, 0)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    def test_codex_resume_session_mismatch_is_held(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        self.env['WRONG_SESSION'] = 'unrelated-codex-session'
        self.assertNotEqual(self.send_reverse().returncode, 0)
        self.env.pop('WRONG_SESSION')
        self.assertNotEqual(self.send_reverse().returncode, 0)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 2)

    def test_provider_failure_preserves_stderr_without_retry(self):
        self.initialize_reverse()
        self.env['CLI_FAIL'] = '1'
        self.assertNotEqual(self.send_reverse().returncode, 0)
        record = json.loads(self.pair.read_text())
        self.assertIn('Provider refused', Path(record['last_attempt_stderr']).read_text())
        self.env.pop('CLI_FAIL')
        self.assertNotEqual(self.send_reverse().returncode, 0)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    def test_two_claude_owners_keep_distinct_codex_sessions(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        second = self.root/'reverse-B.json'
        r = self.command('init', '--owner', 'claude', '--pair', str(second),
                         '--thread', 'claude-B', '--task', 'Another reverse task',
                         '--workdir', str(self.work), '--codex-model', 'gpt-6.1-sol')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.env['CODEX_NEW_SESSION'] = '01a10000-1111-7222-8333-000000000002'
        r = self.command('run', '--owner', 'claude', '--pair', str(second),
                         '--thread', 'claude-B', '--prompt', str(self.prompt),
                         '--snapshot', 'reverse-B')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['session_id'], '01a10000-1111-7222-8333-000000000002')
        self.assertEqual(json.loads(self.send_reverse().stdout)['session_id'],
                         '01a10000-1111-7222-8333-000000000001')

    def test_pre_upgrade_opus_pair_resumes_the_existing_session(self):
        self.seed_transcript('11111111-2222-4333-8444-555555555555')
        self.pair.write_text(json.dumps({'pair_id': 'legacy-pair', 'codex_thread': 'codex-A',
            'task': 'Old slice', 'workdir': str(self.work), 'opus_model': 'claude-opus-5-5',
            'effort': 'xhigh', 'opus_session_id': '11111111-2222-4333-8444-555555555555',
            'started': True, 'status': 'ready'}))
        self.assertEqual(self.command('adopt', '--pair', str(self.pair)).returncode, 0)
        sync = self.command('sync', '--pair', str(self.pair), '--thread', 'codex-A')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        self.assertEqual(self.command('ack', '--pair', str(self.pair), '--thread', 'codex-A',
            '--token', json.loads(sync.stdout)['token']).returncode, 0)
        r = self.send()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['session_id'], '11111111-2222-4333-8444-555555555555')
        call = json.loads((self.root/'calls.jsonl').read_text())
        self.assertEqual(call['args'][call['args'].index('--resume')+1],
                         '11111111-2222-4333-8444-555555555555')

    def seed_transcript(self, session):
        path = self.store/'projects'/'test-project'/(session+'.jsonl')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'type': 'assistant', 'sessionId': session,
            'uuid': str(uuid.uuid4()), 'message': {'content': [{'type': 'text', 'text': 'Earlier'}]}})+'\n')
        return path

    @unittest.skipIf(os.geteuid() == 0, 'root bypasses ordinary filesystem write permissions')
    def test_unwritable_store_refuses_before_spending_a_peer_call(self):
        self.initialize()
        projects = self.store/'projects'
        projects.mkdir()
        projects.chmod(0o500)
        try:
            r = self.send()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('session storage is not writable', r.stderr)
            self.assertIn('No peer started', r.stderr)
            self.assertFalse((self.root/'calls.jsonl').exists())
            self.assertEqual(json.loads(self.pair.read_text())['status'], 'ready')
        finally:
            projects.chmod(0o700)
        self.assertEqual(self.send().returncode, 0, 'correcting the precondition permits a first call')

    def test_success_without_persisted_conversation_is_held(self):
        self.initialize()
        self.env['NO_PERSIST'] = '1'
        r = self.send()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('persisted', r.stderr)
        record = json.loads(self.pair.read_text())
        self.assertEqual(record['status'], 'held')
        self.assertTrue(Path(record['last_attempt_result']).read_text())
        self.env.pop('NO_PERSIST')
        self.assertNotEqual(self.send().returncode, 0)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    def test_unstarted_pair_with_existing_transcript_refuses_before_launch(self):
        self.initialize()
        before = self.pair.read_text()
        self.seed_transcript(json.loads(before)['peer_session_id'])
        r = self.send()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Unstarted pair already has a persisted transcript', r.stderr)
        self.assertFalse((self.root/'calls.jsonl').exists())
        self.assertEqual(self.pair.read_text(), before)

    def test_malformed_transcript_requires_inspection_without_launching(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        before = self.pair.read_text()
        session = json.loads(before)['peer_session_id']
        transcript = self.store/'projects'/'test-project'/(session+'.jsonl')
        with transcript.open('a') as file:
            file.write('{truncated')
        r = self.send()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Malformed Claude transcript', r.stderr)
        self.assertEqual(self.pair.read_text(), before)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    def test_malformed_codex_item_is_held_and_preserves_evidence(self):
        self.initialize_reverse()
        self.env['BAD_ITEM'] = '1'
        r = self.send_reverse()
        self.assertNotEqual(r.returncode, 0)
        record = json.loads(self.pair.read_text())
        self.assertEqual(record['status'], 'held')
        self.assertTrue(record['last_error'])
        self.assertIn('malformed item', Path(record['last_attempt_result']).read_text())
        self.assertNotEqual(self.send_reverse().returncode, 0)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    @unittest.skipIf(os.geteuid() == 0, 'root bypasses ordinary filesystem write permissions')
    def test_resume_requires_writable_transcript_and_its_directory(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        before = self.pair.read_text()
        session = json.loads(before)['peer_session_id']
        transcript = self.store/'projects'/'test-project'/(session+'.jsonl')
        for path in [transcript, transcript.parent]:
            mode = path.stat().st_mode
            with self.subTest(path=path.name):
                path.chmod(0o500 if path.is_dir() else 0o400)
                try:
                    r = self.send()
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn('No peer started', r.stderr)
                    self.assertEqual(self.pair.read_text(), before)
                    self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)
                finally:
                    path.chmod(mode)

    def test_forward_timeout_is_held_with_original_session_and_output_paths(self):
        self.initialize()
        before = json.loads(self.pair.read_text())
        self.env['GATE'] = str(self.root/'timeout-gate')
        r = self.command('run', '--pair', str(self.pair), '--thread', 'codex-A',
            '--prompt', str(self.prompt), '--snapshot', 'forward-timeout', '--timeout', '1')
        self.assertNotEqual(r.returncode, 0)
        record = json.loads(self.pair.read_text())
        self.assertEqual(record['status'], 'held')
        self.assertEqual(record['peer_session_id'], before['peer_session_id'])
        self.assertNotIn('peer_response_id', record)
        self.assertTrue(Path(record['last_attempt_result']).exists())
        self.assertTrue(Path(record['last_attempt_stderr']).exists())

    def test_stale_or_metadata_only_transcript_cannot_verify_new_response(self):
        for flag in ['NO_PERSIST', 'METADATA_ONLY', 'TRANSCRIPT_SESSION']:
            with self.subTest(flag=flag):
                self.env['DUO_STATE_DIR'] = str(self.root/(flag+'-registry'))
                self.pair = self.root/(flag+'.json')
                self.initialize()
                self.assertEqual(self.send().returncode, 0)
                self.env[flag] = 'different-session' if flag == 'TRANSCRIPT_SESSION' else '1'
                r = self.send()
                self.env.pop(flag)
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(json.loads(self.pair.read_text())['status'], 'held')

    def test_state_directory_change_refuses_without_another_peer_call(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        self.env['CLAUDE_CONFIG_DIR'] = str(self.root/'other-state')
        r = self.send()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('state directory changed', r.stderr)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    def test_missing_resume_transcript_refuses_without_another_peer_call(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        record = json.loads(self.pair.read_text())
        for path in (self.store/'projects').glob('*/'+record['peer_session_id']+'.jsonl'):
            path.unlink()
        r = self.send()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('persisted', r.stderr)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)

    def test_timeout_stops_the_wrapper_child_and_retains_session_id(self):
        self.initialize_reverse()
        heartbeat = self.root/'child-heartbeat'
        self.env['TIMEOUT_CHILD'] = str(heartbeat)
        r = self.command('run', '--owner', 'claude', '--pair', str(self.pair),
                         '--thread', 'claude-A', '--prompt', str(self.prompt),
                         '--snapshot', 'timeout-test', '--timeout', '1')
        self.assertNotEqual(r.returncode, 0)
        record = json.loads(self.pair.read_text())
        self.assertEqual(record['status'], 'held')
        self.assertTrue(heartbeat.exists())
        value = heartbeat.read_text()
        time.sleep(0.15)
        self.assertEqual(heartbeat.read_text(), value, 'Timed-out child is still working')
        self.assertEqual(record['peer_session_id'], '01a10000-1111-7222-8333-000000000001')

    def test_truncated_codex_output_still_retains_the_emitted_session_id(self):
        self.initialize_reverse()
        self.env['TRUNCATE'] = '1'
        r = self.send_reverse()
        self.assertNotEqual(r.returncode, 0)
        record = json.loads(self.pair.read_text())
        self.assertEqual(record['status'], 'held')
        self.assertEqual(record['peer_session_id'], '01a10000-1111-7222-8333-000000000001')

    def test_terminal_hangup_stops_the_peer_child_and_keeps_the_pair_held(self):
        self.initialize_reverse()
        heartbeat = self.root/'hangup-heartbeat'
        self.env['TIMEOUT_CHILD'] = str(heartbeat)
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'run', '--owner', 'claude',
            '--pair', str(self.pair), '--thread', 'claude-A', '--prompt', str(self.prompt),
            '--task-id', json.loads(self.pair.read_text())['task_id'],
            '--snapshot', 'hangup-test', '--timeout', '20'], cwd=self.work, env=self.env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic()+3
            while not heartbeat.exists() and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertTrue(heartbeat.exists())
            process.send_signal(signal.SIGHUP)
            process.communicate(timeout=3)
            value = heartbeat.read_text()
            time.sleep(0.15)
            self.assertEqual(heartbeat.read_text(), value, 'Peer survived the terminal hangup')
            self.assertEqual(json.loads(self.pair.read_text())['status'], 'held')
            self.assertNotEqual(self.send_reverse().returncode, 0)
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=3)


if __name__ == '__main__':
    unittest.main()
