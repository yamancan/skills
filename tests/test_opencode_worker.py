"""Exercise the launcher boundary with local fake CLIs; never access real auth/models."""

import json
import importlib.util
import itertools
import os
from pathlib import Path
import signal
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
WORKERS = [ROOT / 'skills' / skill / 'scripts' / 'worker.py'
           for skill in ('let-chinese', 'let-chinese-somehow')]
FAKE = r'''#!PYTHON
import json, os, pathlib, signal, subprocess, sys, time
a = sys.argv[1:]
if '--help' in a:
    assert not any(key in os.environ for key in ['ZRO_API_KEY','OPENCODE_AUTH_CONTENT'])
    print('--pure --model --format --dir --file --session --auto --sanitize')
    sys.exit(0)
data = pathlib.Path(os.environ['XDG_DATA_HOME'])
store = data / 'fake-session.json'
if a[:2] == ['debug', 'config']:
    config = json.loads(os.environ['OPENCODE_CONFIG_CONTENT'])
    print(json.dumps(config))
    sys.exit(0)
if a and a[0] == 'export':
    assert not any(key in os.environ for key in ['ZRO_API_KEY','OPENCODE_AUTH_CONTENT'])
    obj = json.loads(store.read_text())
    if a[1] != obj['info']['id']:
        sys.exit(1)
    print(json.dumps(obj))
    sys.exit(0)
assert a[0] == 'run', a
assert '--pure' in a and '--continue' not in a
model = a[a.index('--model') + 1]
provider, model_id = model.split('/', 1)
brief = pathlib.Path(a[a.index('--file') + 1]).read_text()
scenario = brief.splitlines()[0]
key = os.environ.get('ZRO_API_KEY', '')
auth = json.loads(os.environ.get('OPENCODE_AUTH_CONTENT', '{}'))
if auth:
    key = next(iter(auth.values()))['key']
assert not any(x in os.environ for x in ['UNRELATED_SECRET', 'OPENCODE_CONFIG', 'OPENAI_BASE_URL'])
assert os.environ['OPENCODE_DISABLE_PROJECT_CONFIG'] == '1'
assert os.environ['OPENCODE_EXPERIMENTAL_DISABLE_FILEWATCHER'] == '1'
assert not (pathlib.Path(os.environ['XDG_CONFIG_HOME']) / 'private-marker').exists()
assert not (pathlib.Path(os.environ['HOME']) / '.claude' / 'CLAUDE.md').exists()
assert set(auth) <= {provider}
config = json.loads(os.environ['OPENCODE_CONFIG_CONTENT'])
assert config['mcp']['zro']['enabled'] is False
assert config['permission']['task'] == 'deny'
assert config['permission']['external_directory'] == 'deny'
assert config['lsp'] is False
session = 'ses_worker1'
old = []
if '--session' in a:
    assert a[a.index('--session')+1] == session
    old = json.loads(store.read_text())['messages']
record = {'auto': '--auto' in a, 'args': a, 'home': os.environ['HOME'],
          'data': str(data), 'has_key': bool(key), 'auth_providers': sorted(auth), 'path':os.environ['PATH']}
(data / 'invocation.json').write_text(json.dumps(record))
(data / 'parent.pid').write_text(str(os.getpid()))
(data / 'processes.json').write_text(json.dumps([[os.getpid(), os.getppid(), os.getpgrp()]]))
if scenario in ['timeout', 'detached-timeout']:
    child = subprocess.Popen([sys.executable, '-c', 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(120)'], start_new_session=scenario == 'detached-timeout')
    (data / 'descendant.pid').write_text(str(child.pid))
    (data / 'processes.json').write_text(json.dumps([[os.getpid(), os.getppid(), os.getpgrp()], [child.pid, os.getpid(), os.getpgid(child.pid)]]))
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    def stop(sig, frame):
        if scenario == 'timeout':
            child.kill()
        child.wait(); sys.exit(0)
    signal.signal(signal.SIGTERM, stop)
    time.sleep(120)
if scenario == 'escape':
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'], start_new_session=True)
    (data / 'descendant.pid').write_text(str(child.pid))
    time.sleep(120)
mid = old[0]['info']['id'] if scenario == 'stale' else 'msg_' + str(len(old)+1)
event_session = 'ses_wrong' if scenario == 'wrong-session' else session
def emit(kind, **extra):
    print(json.dumps({'type': kind, 'timestamp': 1, 'sessionID': event_session, **extra}), flush=True)
emit('step_start', part={'id':'prt_start', 'messageID':mid, 'sessionID':event_session,'type':'step-start'})
if scenario == 'unexpected-tool':
    emit('tool_use', part={'id':'prt_tool','messageID':mid,'sessionID':event_session,'type':'tool','tool':'zro_remote_write','state':{'status':'completed','output':'done'}})
if scenario == 'false-success':
    emit('error', error={'name':'APIError','data':{'message':'key '+key+' invalid'}})
    sys.exit(0)
text = 'Finished task; ' + key if scenario == 'leak' else 'Finished task.'
emit('text', part={'id':'prt_text', 'messageID':mid,'sessionID':event_session,'type':'text','text':text,'time':{'start':1,'end':2}})
emit('step_finish', part={'id':'prt_finish','messageID':mid,'sessionID':event_session,'type':'step-finish','reason':'stop','cost':0,'tokens':{'input':1,'output':1}})
if scenario == 'wrong-model':
    model_id = 'unrequested-model'
info = {'id':mid,'sessionID':session,'role':'assistant','providerID':provider,'modelID':model_id,'finish':'stop','time':{'created':1,'completed':2}}
messages = old + [{'info':info,'parts':[{'type':'text','text':text,'messageID':mid,'sessionID':session}]}]
store.write_text(json.dumps({'info':{'id':session,'directory':str(pathlib.Path.cwd())},'messages':messages}))
print('stderr key '+key, file=sys.stderr)
'''

ZRO = r'''#!PYTHON
import os, sys
a = sys.argv[1:]
if '--help' in a:
    print('launch --model -- --auto'); sys.exit(0)
assert a[:4] == ['launch', 'opencode', '--model', 'dolly1-security'], a
assert a[4] == '--'
assert a[5] == 'debug' or '--auto' in a
os.execvp('opencode', ['opencode'] + a[5:])
'''

PS = r'''#!PYTHON
import json, os, pathlib, sys
data = pathlib.Path(os.environ['XDG_DATA_HOME'])
rows = data / 'processes.json'
if not rows.exists():
    sys.exit(1)
for row in json.loads(rows.read_text()):
    print(*row)
'''


@unittest.skipUnless(os.name == 'posix', 'Worker supports POSIX only')
class OpenCodeWorker(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='worker-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.bin = self.base / 'bin'
        self.bin.mkdir()
        for name, source in [('opencode', FAKE), ('zro', ZRO), ('ps', PS)]:
            path = self.bin / name
            path.write_text(source.replace('PYTHON', sys.executable))
            path.chmod(0o700)
        self.workspace = self.base / 'workspace'
        self.workspace.mkdir()
        self.home = self.base / 'home'
        self.home.mkdir()
        self.config = self.home / '.config'
        (self.config / 'zro').mkdir(parents=True)
        (self.config / 'private-marker').write_text('private config')
        (self.config / 'zro' / 'credentials.json').write_text(json.dumps({'apiKey':'zro-test-secret'}))
        self.data = self.home / '.local' / 'share'
        (self.data / 'opencode').mkdir(parents=True)
        (self.data / 'opencode' / 'auth.json').write_text(json.dumps({
            'openrouter': {'type':'api','key':'selected-test-secret'},
            'opencode-go': {'type':'api','key':'go-test-secret'},
            'unrelated': {'type':'api','key':'other-test-secret'},
        }))
        (self.home / '.claude').mkdir()
        (self.home / '.claude' / 'CLAUDE.md').write_text('private memory')
        self.env = dict(os.environ, PATH=str(self.bin)+os.pathsep+os.defpath,
                        HOME=str(self.home), XDG_CONFIG_HOME=str(self.config),
                        XDG_DATA_HOME=str(self.data), UNRELATED_SECRET='do-not-inherit',
                        OPENCODE_CONFIG='/private/config', OPENAI_BASE_URL='http://wrong')

    def launch(self, scenario='success', *, extra=(), worker=0, state=None, model='openrouter/deepseek/deepseek-v3.2', cwd=None):
        brief = self.base / ('input-'+str(time.monotonic_ns())+'.txt')
        brief.write_text(scenario+'\nDo the bounded task.')
        cmd = [sys.executable, str(WORKERS[worker]), '--dir', str(self.workspace), '--brief', str(brief), '--timeout', '8']
        if model:
            cmd += ['--model', model]
        if state:
            cmd += ['--state-dir', str(state)]
        proc = subprocess.run(cmd+list(extra), cwd=cwd, env=self.env, text=True, capture_output=True, timeout=15)
        self.assertTrue(proc.stdout.strip(), proc.stderr)
        result = json.loads(proc.stdout)
        if result.get('state_dir') and not Path(result['state_dir']).is_relative_to(self.base):
            self.addCleanup(shutil.rmtree, result['state_dir'], ignore_errors=True)
        return proc, result

    def test_finished_requires_observed_model_and_private_artifacts(self):
        proc, result = self.launch()
        self.assertEqual(proc.returncode, 0, result)
        self.assertEqual(result['status'], 'finished')
        self.assertFalse(result['accepted'])
        self.assertEqual(result['session'], 'ses_worker1')
        self.assertEqual(result['model'], 'openrouter/deepseek/deepseek-v3.2')
        self.assertEqual(result['final_response'], 'Finished task.')
        state = Path(result['state_dir'])
        self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
        for artifact in result['artifacts'].values():
            self.assertEqual(stat.S_IMODE(Path(artifact).stat().st_mode), 0o600)
        record = json.loads((state/'data'/'invocation.json').read_text())
        self.assertFalse(record['auto'])
        self.assertEqual(record['auth_providers'], ['openrouter'])

    def test_native_help_may_be_printed_to_stderr(self):
        path = self.bin/'opencode'
        path.write_text(path.read_text().replace(
            "print('--pure --model --format --dir --file --session --auto --sanitize')",
            "print('--pure --model --format --dir --file --session --auto --sanitize', file=sys.stderr)"))
        proc, result = self.launch()
        self.assertEqual(proc.returncode, 0, result)

    def test_relative_and_empty_path_entries_keep_original_cli_on_both_routes(self):
        local_bin = self.workspace/'bin'
        local_bin.mkdir()
        marker = self.workspace/'substituted-cli'
        for name in ['opencode', 'zro']:
            wrong = local_bin/name
            wrong.write_text('#!'+sys.executable+'\nfrom pathlib import Path\nPath('+repr(str(marker))+').write_text("wrong CLI")\nraise SystemExit(23)\n')
            wrong.chmod(0o700)
        self.env['PATH'] = 'bin'+os.pathsep+os.pathsep+str(local_bin)+os.pathsep+os.defpath
        for zro in [False, True]:
            with self.subTest(zro=zro):
                proc, result = self.launch(cwd=self.base, worker=int(zro), model=None if zro else 'openrouter/deepseek/deepseek-v3.2', extra=['--zro'] if zro else [])
                self.assertEqual(proc.returncode, 0, result)
                self.assertFalse(marker.exists())
                record = json.loads((Path(result['state_dir'])/'data'/'invocation.json').read_text())
                self.assertTrue(all(Path(part).is_absolute() for part in record['path'].split(os.pathsep)))
                self.assertTrue(all(not Path(part).resolve().is_relative_to(self.workspace.resolve())
                                    for part in record['path'].split(os.pathsep)))

    def test_checkout_control_clis_and_symlink_targets_are_rejected_before_auth(self):
        (self.data/'opencode'/'auth.json').write_text('not valid authentication JSON')
        (self.config/'zro'/'credentials.json').write_text('not valid authentication JSON')
        local_bin = self.workspace/'bin'
        local_bin.mkdir()
        for name in ['opencode', 'zro']:
            (local_bin/name).write_text('#!'+sys.executable+'\nraise SystemExit(23)\n')
            (local_bin/name).chmod(0o700)
        link_bin = self.base/'symlink-bin'
        link_bin.mkdir()
        for name in ['opencode', 'zro']:
            (link_bin/name).symlink_to(local_bin/name)
        for zro, control in [(False, 'opencode'), (True, 'opencode'), (True, 'zro')]:
            for symlink in [False, True]:
                with self.subTest(zro=zro, control=control, symlink=symlink):
                    selected = (self.base if symlink else self.workspace)/('selection-'+str(time.monotonic_ns()))
                    selected.mkdir()
                    if symlink:
                        (selected/control).symlink_to(link_bin/control)
                    else:
                        shutil.copy2(local_bin/control, selected/control)
                    self.env['PATH'] = str(selected)+os.pathsep+str(self.bin)+os.pathsep+os.defpath
                    proc, result = self.launch(worker=int(zro), model=None if zro else 'openrouter/deepseek/deepseek-v3.2', extra=['--zro'] if zro else [])
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertIn('outside', result['error'].lower())
                    self.assertIn(control, result['error'].lower())
                    self.assertEqual(result['artifacts'], {})

    def test_default_temp_inside_task_directory_fails_before_artifacts(self):
        self.env['TMPDIR'] = str(self.workspace)
        proc, result = self.launch()
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(result['artifacts'], {})
        self.assertEqual(list(self.workspace.iterdir()), [])

    def test_nested_checkout_state_is_rejected_for_git_directory_and_worktree_file(self):
        checkout = self.workspace
        nested_repo = checkout/'module'
        nested_repo.mkdir()
        (nested_repo/'.git').mkdir()
        nested = nested_repo/'src'
        nested.mkdir()
        temp = checkout/'temp'
        temp.mkdir()
        self.workspace = nested
        marker = checkout/'.git'
        for worktree in [False, True]:
            if worktree:
                marker.rmdir()
                marker.write_text('gitdir: ../metadata/worktrees/example\n')
            else:
                marker.mkdir()
            for explicit in [False, True]:
                with self.subTest(worktree=worktree, explicit=explicit):
                    self.env['TMPDIR'] = str(temp)
                    state = checkout/'private-runtime' if explicit else None
                    proc, result = self.launch(state=state)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(result['artifacts'], {})
                    self.assertFalse((checkout/'private-runtime').exists())
                    self.assertEqual(list(temp.iterdir()), [])

    def test_enabled_mcp_or_plugin_in_resolved_config_blocks_before_inference(self):
        original = (self.bin/'opencode').read_text()
        for field in ["config['mcp']['zro']['enabled'] = True", "config['plugin'] = ['private-plugin']",
                      "config['mcp'] = []", "config['model'] = 'unrequested/model'",
                      "config['permission']['task'] = 'allow'", "config = []"]:
            with self.subTest(field=field):
                (self.bin/'opencode').write_text(original.replace(
                    "    print(json.dumps(config))", "    "+field+"\n    print(json.dumps(config))"))
                state = self.base/('unsafe-config-'+str(time.monotonic_ns()))
                proc, result = self.launch(state=state)
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse((state/'data'/'invocation.json').exists())

    def test_unexpected_remote_tool_is_never_accepted_as_finished(self):
        proc, result = self.launch('unexpected-tool')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('tool', result['error'].lower())

    def test_false_exit_zero_error_is_failure_and_secret_is_redacted(self):
        proc, result = self.launch('false-success')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('invalid', result['error'])
        self.assertNotIn('selected-test-secret', proc.stdout+proc.stderr)

    def test_resume_pins_exact_session_model_and_original_data(self):
        _, first = self.launch()
        proc, second = self.launch(state=first['state_dir'], extra=['--session', first['session']])
        self.assertEqual(proc.returncode, 0, second)
        self.assertEqual(first['session'], second['session'])
        self.assertEqual(first['state_dir'], second['state_dir'])
        record = json.loads((Path(second['state_dir'])/'data'/'invocation.json').read_text())
        self.assertEqual(record['args'][record['args'].index('--session')+1], 'ses_worker1')
        self.assertNotIn('--continue', record['args'])
        binding = (Path(first['state_dir'])/'binding.json').read_text()
        proc, wrong = self.launch(state=first['state_dir'], extra=['--session', 'ses_other'])
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('session', wrong['error'].lower())
        self.assertEqual((Path(first['state_dir'])/'binding.json').read_text(), binding)
        proc, wrong = self.launch(state=first['state_dir'], extra=['--session', first['session']], model='opencode-go/deepseek-v3.2')
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('model', wrong['error'].lower())
        self.assertEqual((Path(first['state_dir'])/'binding.json').read_text(), binding)

    def test_resumed_worker_cannot_reuse_old_message_as_new_model_proof(self):
        _, first = self.launch()
        proc, result = self.launch('stale', state=first['state_dir'], extra=['--session', first['session']])
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(result['status'], 'failed')

    def test_active_state_is_not_modified_by_concurrent_launcher(self):
        import fcntl
        _, first = self.launch()
        state = Path(first['state_dir'])
        binding = (state/'binding.json').read_text()
        with (state/'worker.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            proc, result = self.launch(state=state, extra=['--session', first['session']])
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual((state/'binding.json').read_text(), binding)

    def test_wrong_observed_model_or_session_is_never_finished(self):
        for scenario in ['wrong-model', 'wrong-session']:
            with self.subTest(scenario=scenario):
                proc, result = self.launch(scenario)
                self.assertNotEqual(proc.returncode, 0)
                self.assertEqual(result['status'], 'failed')

    def test_timeout_reaps_owned_descendant(self):
        proc, result = self.launch('timeout', extra=['--timeout', '0.6'])
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(result['status'], 'timeout')
        child = int((Path(result['state_dir'])/'data'/'descendant.pid').read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)

    def test_timeout_cleans_observed_native_detached_shell_group(self):
        proc, result = self.launch('detached-timeout', extra=['--timeout', '0.6'])
        child = int((Path(result['state_dir'])/'data'/'descendant.pid').read_text())
        try:
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(result['status'], 'timeout', result)
            with self.assertRaises(ProcessLookupError):
                os.kill(child, 0)
        finally:
            try:
                os.killpg(child, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_denied_descendant_inspection_is_held_even_when_root_group_stops(self):
        (self.bin/'ps').write_text('#!'+sys.executable+'\nraise PermissionError("process inspection denied")\n')
        proc, result = self.launch('timeout', extra=['--timeout', '0.6'])
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(result['status'], 'held', result)

    def test_interrupt_and_hangup_stop_owned_process_group(self):
        for signum in [signal.SIGINT, signal.SIGHUP]:
            with self.subTest(signal=signum):
                self.check_signal_cleanup(signum)

    def check_signal_cleanup(self, signum):
        brief = self.base/'interrupt.txt'
        brief.write_text('timeout\nWait for cancellation.')
        state = self.base/('interrupt-state-'+str(signum))
        command = [sys.executable, str(WORKERS[0]), '--dir', str(self.workspace), '--brief', str(brief),
                   '--model', 'openrouter/deepseek/deepseek-v3.2', '--state-dir', str(state)]
        proc = subprocess.Popen(command, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        deadline = time.monotonic()+5
        pid_path = state/'data'/'descendant.pid'
        while not pid_path.exists() and time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.02)
        self.assertTrue(pid_path.exists(), 'Fake child never started')
        child = int(pid_path.read_text())
        proc.send_signal(signum)
        stdout, stderr = proc.communicate(timeout=8)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(json.loads(stdout)['status'], 'interrupted', stderr)
        with self.assertRaises(ProcessLookupError):
            os.kill(child, 0)

    def test_sigkill_leaves_running_binding_and_blocks_resume(self):
        _, first = self.launch()
        state = Path(first['state_dir'])
        brief = self.base/'killed.txt'
        brief.write_text('timeout\nWait for interruption.')
        command = [sys.executable, str(WORKERS[0]), '--dir', str(self.workspace), '--brief', str(brief),
                   '--model', first['model'], '--state-dir', str(state), '--session', first['session']]
        proc = subprocess.Popen(command, env=self.env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        pid_path = state/'data'/'descendant.pid'
        deadline = time.monotonic()+5
        while not pid_path.exists() and time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.02)
        self.assertTrue(pid_path.exists(), 'Fake child never started')
        record = json.loads((state/'binding.json').read_text())
        pgid = record.get('process_group')
        try:
            proc.kill()
            proc.wait(timeout=5)
            self.assertEqual(record['status'], 'running')
            self.assertEqual(record['launcher_pid'], proc.pid)
            self.assertIsInstance(pgid, int)
            os.killpg(pgid, 0)
            resumed, result = self.launch(state=state, extra=['--session', first['session']])
            self.assertNotEqual(resumed.returncode, 0)
            self.assertEqual(result['status'], 'held')
            self.assertEqual(json.loads((state/'binding.json').read_text()), record)
        finally:
            # A SIGKILL cannot run the launcher's cleanup; the test owns this fake group.
            if pgid is None:
                pgid = int((state/'data'/'parent.pid').read_text())
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            proc.communicate(timeout=5)

    def test_credentials_and_private_config_are_not_copied_and_output_is_redacted(self):
        proc, result = self.launch('leak')
        self.assertEqual(proc.returncode, 0, result)
        self.assertNotIn('selected-test-secret', proc.stdout+proc.stderr)
        for name, path in result['artifacts'].items():
            self.assertNotIn('selected-test-secret', Path(path).read_text(), name)
        state = Path(result['state_dir'])
        self.assertEqual(list(state.rglob('auth.json')), [])
        self.assertEqual(list(state.rglob('credentials.json')), [])
        self.assertEqual(list(state.rglob('private-marker')), [])
        self.assertEqual(list(state.rglob('CLAUDE.md')), [])

    def test_free_opencode_model_needs_no_auth_and_paid_zen_is_rejected(self):
        (self.data/'opencode'/'auth.json').unlink()
        proc, result = self.launch(model='opencode/glm-5.3-flash-free')
        self.assertEqual(proc.returncode, 0, result)
        self.assertEqual(result['status'], 'finished')
        record = json.loads((Path(result['state_dir'])/'data'/'invocation.json').read_text())
        self.assertEqual(record['auth_providers'], [])
        proc, result = self.launch(model='opencode/paid-model')
        self.assertNotEqual(proc.returncode, 0)

    def test_zro_uses_native_auth_auto_and_fixed_model(self):
        proc, result = self.launch(worker=1, model=None, extra=['--zro'])
        self.assertEqual(proc.returncode, 0, result)
        self.assertEqual(result['route'], 'zro')
        self.assertEqual(result['model'], 'zro/dolly1-security')
        record = json.loads((Path(result['state_dir'])/'data'/'invocation.json').read_text())
        self.assertTrue(record['auto'])
        self.assertTrue(record['has_key'])
        self.assertEqual(record['auth_providers'], [])

    def test_missing_cli_never_installs_and_reports_prerequisite(self):
        (self.bin/'opencode').unlink()
        self.env['PATH'] = str(self.bin)
        proc, result = self.launch()
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('opencode', result['error'].lower())
        self.assertIn('installed', result['error'].lower())

    def test_rejects_state_symlink_existing_initial_state_and_custom_routes(self):
        occupied = self.base/'occupied'
        occupied.mkdir()
        link = self.base/'link'
        link.symlink_to(occupied, target_is_directory=True)
        for state in [occupied, link]:
            proc, result = self.launch(state=state)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(list(occupied.iterdir()), [])
        proc, result = self.launch(model='custom/unknown')
        self.assertNotEqual(proc.returncode, 0)
        ancestor = self.base/'workspace-link'
        ancestor.symlink_to(self.workspace, target_is_directory=True)
        proc, result = self.launch(state=ancestor/'runtime')
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse((self.workspace/'runtime').exists())

    def test_skill_copies_are_standalone_and_identical(self):
        self.assertEqual(WORKERS[0].read_bytes(), WORKERS[1].read_bytes())


class GroupCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('opencode_worker', WORKERS[0])
        cls.worker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.worker)

    def cleanup_with(self, signal_group):
        clock = itertools.count(0, 0.1)
        proc = SimpleNamespace(pid=123456, poll=lambda: 0)
        with patch.object(self.worker.os, 'killpg', side_effect=signal_group), \
                patch.object(self.worker.time, 'monotonic', side_effect=lambda: next(clock)), \
                patch.object(self.worker.time, 'sleep'):
            return self.worker.stop_group(proc)

    def test_permission_race_can_settle_to_confirmed_absence(self):
        probes = 0
        def signal_group(pgid, signum):
            nonlocal probes
            if signum:
                raise PermissionError('group may be vanishing')
            probes += 1
            if probes == 1:
                raise PermissionError('group still uninspectable')
            raise ProcessLookupError('group gone')
        self.assertTrue(self.cleanup_with(signal_group))

    def test_live_or_uninspectable_groups_fail_cleanup(self):
        for uninspectable in [False, True]:
            with self.subTest(uninspectable=uninspectable):
                def signal_group(pgid, signum):
                    if signum or uninspectable:
                        raise PermissionError('group still exists or cannot be inspected')
                self.assertFalse(self.cleanup_with(signal_group))

    def test_permission_denied_probe_means_possibly_alive(self):
        with patch.object(self.worker.os, 'killpg', side_effect=PermissionError('uninspectable')):
            self.assertTrue(self.worker.group_exists(123456))

    def test_missing_inspection_tool_does_not_fall_back_to_current_directory(self):
        with patch.object(self.worker.shutil, 'which', return_value=None), \
                patch.object(self.worker.subprocess, 'run') as run:
            self.assertIsNone(self.worker.descendant_groups(SimpleNamespace(pid=123456),
                {'PATH': '', 'XDG_DATA_HOME': '/unused'}))
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
