"""Real CLI lifecycle checks using small disposable directories, no provider calls."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from _support import DUO_SCRIPTS
import workspace

SCRIPT = DUO_SCRIPTS / 'workspace.py'


class Workspaces(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = self.root/'source'; self.source.mkdir()
        self.state = self.root/'private'/'workspace.json'
        self.call('bind', '--workdir', str(self.source), '--budget-mib', '4')

    def call(self, *args, expected=0):
        p = subprocess.run([sys.executable, str(SCRIPT), '--state', str(self.state), *args],
                           capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, expected, p.stdout+p.stderr)
        return json.loads(p.stdout) if expected == 0 else p

    def run_job(self, code, *extra, expected=0):
        return self.call('run', '--name', 'test', '--reserve-mib', '2', *extra,
                         '--', sys.executable, '-c', code, expected=expected)

    def test_bind_reuses_source_and_rejects_another_checkout(self):
        before = self.state.read_bytes()
        self.call('bind', '--workdir', str(self.source))
        self.assertEqual(before, self.state.read_bytes())
        other = self.root/'copy'; other.mkdir()
        self.call('bind', '--workdir', str(other), expected=2)
        self.assertEqual(before, self.state.read_bytes())

    def test_replacing_source_at_same_path_is_detected(self):
        self.source.rename(self.root/'old')
        self.source.mkdir()
        self.run_job('print("must not run")', expected=2)

    def test_success_cleans_dependencies_and_preserves_output(self):
        result = self.run_job('from pathlib import Path; p=Path("node_modules"); p.mkdir(); (p/"x").write_bytes(b"x"*100000); print("verified")')
        self.assertEqual(result['status'], 'complete')
        self.assertTrue(result['cleaned'])
        self.assertFalse(Path(result['scratch']).exists())
        self.assertIn('verified', Path(result['stdout']).read_text())
        again = self.run_job('print("again")')
        self.assertNotEqual(again['id'], result['id'])
        self.assertEqual(self.call('status')['active_runs'], [])

    def test_failed_test_still_cleans_scratch_and_keeps_receipt(self):
        result = self.run_job('from pathlib import Path; Path("generated").write_text("x"); raise SystemExit(7)', expected=7)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['status'], 'failed')
        self.assertTrue(receipt['cleaned'])
        self.assertTrue(Path(receipt['receipt']).is_file())

    def test_timeout_cleans_scratch(self):
        result = self.run_job('import time; time.sleep(10)', '--timeout', '0.2', expected=124)
        self.assertTrue(json.loads(result.stdout)['cleaned'])

    def test_storage_overrun_is_failed_even_when_command_exits_quickly(self):
        result = self.run_job('from pathlib import Path; Path("huge").write_bytes(b"x"*3000000)', expected=125)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['status'], 'budget_exceeded')
        self.assertTrue(receipt['cleaned'])

    def test_parallel_reservations_cannot_overbook(self):
        command = [sys.executable, str(SCRIPT), '--state', str(self.state), 'run', '--name', 'first',
                   '--reserve-mib', '3', '--', sys.executable, '-c', 'import time; time.sleep(2)']
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            if self.call('status')['active_runs']: break
            time.sleep(.05)
        result = self.run_job('print("must not run")', expected=2)
        self.assertIn('budget', result.stderr.lower())
        stdout, stderr = p.communicate(timeout=5)
        self.assertEqual(p.returncode, 0, stdout+stderr)

    def test_active_logs_use_the_existing_reservation(self):
        self.call('budget', '--mib', '5', '--reason', 'Exercise two concurrent small checks')
        command = [sys.executable, str(SCRIPT), '--state', str(self.state), 'run', '--name', 'logging',
            '--reserve-mib', '3', '--', sys.executable, '-c',
            'import sys,time; sys.stdout.write("x"*2000000); sys.stdout.flush(); time.sleep(2)']
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            if self.call('status')['used_bytes'] >= 2000000: break
            time.sleep(.03)
        result = self.call('run', '--name', 'second', '--reserve-mib', '1', '--',
                           sys.executable, '-c', 'print("second")')
        self.assertTrue(result['cleaned'])
        stdout, stderr = p.communicate(timeout=5)
        self.assertEqual(p.returncode, 0, stdout+stderr)

    def test_nonfinite_timeout_never_launches(self):
        for value in ('nan', 'inf', '-inf'):
            result = self.run_job('print("must not run")', '--timeout='+value, expected=2)
            self.assertIn('positive timeout', result.stderr)
            self.assertEqual(self.call('status')['active_runs'], [])

    def test_admission_never_shrinks_reservations_while_a_writer_grows(self):
        # Force the old unsafe interleaving: overall storage was 0, then one active
        # run grew by 1 MiB before its later measurement. Fixed reservations remain 3 MiB.
        run = {'name': 'writer', 'cleaned': False, 'reserve_bytes': 3*1024*1024,
               'scratch': str(self.root/'scratch'), 'stdout': str(self.root/'out'),
               'stderr': str(self.root/'err')}
        with patch.object(workspace, 'tree_bytes', return_value=0), \
             patch.object(workspace, 'run_bytes', return_value=1024*1024):
            committed = workspace.committed_bytes(self.root, {'runs': {'writer': run}})
        self.assertEqual(committed, 3*1024*1024)

    def test_storage_walk_tolerates_actual_child_cleanup_between_enumeration_and_descent(self):
        import shutil
        gone = self.source/'temporary'; gone.mkdir()
        (gone/'data').write_bytes(b'disposable')
        (self.source/'kept').write_bytes(b'kept!')
        original_walk = workspace.os.walk
        def racing_walk(root, **kwargs):
            for entry in original_walk(root, **kwargs):
                yield entry
                if Path(entry[0]) == self.source and gone.exists():
                    shutil.rmtree(gone)
        with patch.object(workspace.os, 'walk', side_effect=racing_walk):
            self.assertEqual(workspace.tree_bytes(self.source), 5)
        self.assertFalse(gone.exists())
        self.assertEqual((self.source/'kept').read_bytes(), b'kept!')

    def test_final_storage_scan_error_returns_failure_exit(self):
        unreadable = Path(self.call('status')['root'])/'unreadable'
        code = 'from pathlib import Path; p=Path('+repr(str(unreadable))+'); p.mkdir(); p.chmod(0)'
        try:
            result = self.run_job(code, expected=126)
            receipt = json.loads(result.stdout)
            self.assertEqual(receipt['status'], 'failed')
            self.assertEqual(receipt['exit_code'], 126)
            self.assertTrue(receipt['cleaned'])
        finally:
            if unreadable.exists(): unreadable.chmod(0o700)

    def test_unregistered_directory_is_preserved(self):
        info = self.call('status')
        target = Path(info['root'])/'scratch'/'test'; target.mkdir(parents=True)
        (target/'user-work').write_text('preserve')
        self.run_job('print("must not run")', expected=2)
        self.assertEqual((target/'user-work').read_text(), 'preserve')

    def test_symlink_replacement_is_not_deleted(self):
        outside = self.root/'outside'; outside.mkdir(); (outside/'keep').write_text('yes')
        code = 'import os; from pathlib import Path; p=Path.cwd(); os.chdir(p.parent); p.rename(p.with_name("moved")); p.symlink_to('+repr(str(outside))+', target_is_directory=True)'
        result = self.run_job(code, expected=126)
        self.assertFalse(json.loads(result.stdout)['cleaned'])
        self.assertTrue((outside/'keep').exists())

    def test_unknown_launch_outcome_cannot_be_recovered_as_an_idle_run(self):
        info = self.call('status')
        target = Path(info['root'])/'scratch'/'unknown'; target.mkdir(parents=True)
        (target/'.duo-scratch.json').write_text(json.dumps({'id': 'unknown-run'}))
        state = json.loads(self.state.read_text())
        st = target.stat()
        state['runs']['unknown'] = {'name': 'unknown', 'id': 'unknown-run', 'status': 'starting',
            'cleaned': False, 'runner_pid': 1073741824, 'child_pid': None,
            'scratch': str(target), 'scratch_identity': [st.st_dev, st.st_ino],
            'receipt': str(Path(info['root'])/'unknown.json'), 'reserve_bytes': 1024}
        self.state.write_text(json.dumps(state))
        result = self.call('recover', '--name', 'unknown', '--id', 'unknown-run', expected=2)
        self.assertIn('launch outcome', result.stderr.lower())
        self.assertTrue(target.exists())

    def test_interrupt_stops_descendants_and_cleans(self):
        p = subprocess.Popen([sys.executable, str(SCRIPT), '--state', str(self.state), 'run', '--name', 'interrupt',
            '--reserve-mib', '2', '--', sys.executable, '-c', 'import time; time.sleep(10)'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: p.poll() is None and p.kill())
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            state=json.loads(self.state.read_text())
            if state['runs'].get('interrupt',{}).get('child_pid'):break
            time.sleep(.03)
        p.send_signal(signal.SIGTERM)
        stdout,stderr=p.communicate(timeout=5)
        self.assertEqual(p.returncode,130,stderr)
        self.assertTrue(json.loads(stdout)['cleaned'])


if __name__ == '__main__': unittest.main()
