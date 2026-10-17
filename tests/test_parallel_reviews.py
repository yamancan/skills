import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import unittest


from _support import ROOT

SCRIPT = ROOT / 'skills' / 'orkestra' / 'scripts' / 'parallel_reviews.py'


class ParallelReviews(unittest.TestCase):
    def test_missing_sibling_duo_explains_required_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / 'orkestra' / 'scripts' / SCRIPT.name
            script.parent.mkdir(parents=True)
            shutil.copy2(SCRIPT, script)
            result = subprocess.run([sys.executable, str(script), '--help'],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Install Duo alongside Orkestra', result.stderr)
            self.assertNotIn('Traceback', result.stderr)

    def test_empty_argument_reaches_cli_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps({'jobs': [
                {'id': 'no-tools', 'command': [sys.executable, '-c', 'import sys; assert sys.argv[1] == ""; print("tools disabled")', ''],
                 'cwd': tmp, 'timeout_seconds': 2, 'session_id': 'recorded-native-id'},
            ]}))
            result = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                     '--output', str(root / 'results')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'results/no-tools/stdout').read_text(), 'tools disabled\n')

    def test_explicit_new_session_preserves_unknown_identity_until_provider_returns_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps({'jobs': [
                {'id': 'fresh', 'command': [sys.executable, '-c', 'print(\'{"sessionID":"provider-created-id"}\')'],
                 'cwd': tmp, 'timeout_seconds': 2, 'new_session': True},
            ]}))
            result = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                     '--output', str(root / 'results')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads((root / 'results/fresh/status.json').read_text())
            self.assertIsNone(status['session_id'])
            self.assertTrue(status['new_session'])
            self.assertEqual(json.loads((root / 'results/fresh/stdout').read_text())['sessionID'], 'provider-created-id')

    def test_slow_peer_does_not_block_completed_peer_or_erase_its_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = {
                'jobs': [
                    {'id': 'fast', 'command': [sys.executable, '-c', 'print("review complete")'],
                     'cwd': tmp, 'timeout_seconds': 3, 'session_id': 'fast-native'},
                    {'id': 'slow', 'command': [sys.executable, '-c', 'import time; time.sleep(10)'],
                     'cwd': tmp, 'timeout_seconds': 1, 'session_id': 'slow-native'},
                ]
            }
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps(jobs))
            result = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                     '--output', str(root / 'results')], capture_output=True,
                                    text=True, timeout=6)
            self.assertEqual(result.returncode, 1, result.stderr)
            fast = json.loads((root / 'results/fast/status.json').read_text())
            slow = json.loads((root / 'results/slow/status.json').read_text())
            self.assertEqual(fast['state'], 'exited')
            self.assertEqual(fast['exit_code'], 0)
            self.assertEqual((root / 'results/fast/stdout').read_text(), 'review complete\n')
            self.assertEqual(slow['state'], 'timed_out')
            self.assertEqual(slow['session_id'], 'slow-native')
            self.assertLess(fast['finished_at'], slow['finished_at'])

    def test_invalid_manifest_launches_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / 'launched'
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps({'jobs': [
                {'id': 'valid', 'command': [sys.executable, '-c', f'open({str(marker)!r}, "w").close()'],
                 'cwd': tmp, 'timeout_seconds': 3, 'session_id': 'one'},
                {'id': 'valid', 'command': [sys.executable, '-c', 'pass'],
                 'cwd': tmp, 'timeout_seconds': 3, 'session_id': 'two'},
            ]}))
            result = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                     '--output', str(root / 'results')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())

    def test_same_native_session_cannot_be_dispatched_twice_in_parallel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / 'launched'
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps({'jobs': [
                {'id': name, 'command': [sys.executable, '-c', f'open({str(marker)!r}, "w").close()'],
                 'cwd': tmp, 'timeout_seconds': 2, 'session_id': 'same-native-id'}
                for name in ['opus-one', 'opus-two']
            ]}))
            result = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                     '--output', str(root / 'results')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(marker.exists())

    def test_one_launch_failure_does_not_cancel_other_reviews(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps({'jobs': [
                {'id': 'missing', 'command': [str(root / 'no-such-cli')],
                 'cwd': tmp, 'timeout_seconds': 2, 'session_id': 'missing-native'},
                {'id': 'working', 'command': [sys.executable, '-c', 'print("useful review")'],
                 'cwd': tmp, 'timeout_seconds': 2, 'session_id': 'working-native'},
            ]}))
            result = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                     '--output', str(root / 'results')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads((root / 'results/missing/status.json').read_text())['state'], 'launch_failed')
            self.assertEqual(json.loads((root / 'results/working/status.json').read_text())['state'], 'exited')
            self.assertEqual((root / 'results/working/stdout').read_text(), 'useful review\n')

    def test_timeout_stops_spawned_child_in_same_process_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / 'orphan-ran'
            child = 'import time; from pathlib import Path; time.sleep(1); Path(' + repr(str(marker)) + ').write_text("late")'
            parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); time.sleep(10)'
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps({'jobs': [
                {'id': 'parent', 'command': [sys.executable, '-c', parent], 'cwd': tmp,
                 'timeout_seconds': 0.2, 'session_id': 'owned-session'},
            ]}))
            result = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                     '--output', str(root / 'results')], capture_output=True, text=True, timeout=4)
            self.assertEqual(result.returncode, 1, result.stderr)
            import time
            time.sleep(1.1)
            self.assertFalse(marker.exists())

    def test_successful_wrapper_exit_does_not_leave_a_term_ignoring_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            import time
            root = Path(tmp)
            marker, ready, pidfile = root / 'orphan-ran', root / 'ready', root / 'pid'
            child = ('import signal,time; from pathlib import Path; '
                     'signal.signal(signal.SIGTERM,signal.SIG_IGN); Path(' + repr(str(ready)) + ').touch(); '
                     'time.sleep(1); Path(' + repr(str(marker)) + ').touch()')
            parent = ('import subprocess,sys,time; from pathlib import Path; '
                      'p=subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); '
                      'Path(' + repr(str(pidfile)) + ').write_text(str(p.pid)); '
                      '\nwhile not Path(' + repr(str(ready)) + ').exists(): time.sleep(.01)')
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps({'jobs': [
                {'id': 'wrapper', 'command': [sys.executable, '-c', parent], 'cwd': tmp,
                 'timeout_seconds': 3, 'session_id': 'wrapper-native'},
            ]}))
            try:
                result = subprocess.run([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                         '--output', str(root / 'results')], capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                time.sleep(1.1)
                self.assertFalse(marker.exists(), 'Review descendant survived successful wrapper exit')
            finally:
                if pidfile.exists():
                    try: os.kill(int(pidfile.read_text()), signal.SIGKILL)
                    except ProcessLookupError: pass

    def test_runner_signal_stops_active_review_and_records_interruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            marker = root / 'finished'
            manifest = root / 'jobs.json'
            manifest.write_text(json.dumps({'jobs': [
                {'id': 'long', 'command': [sys.executable, '-c',
                 'import time; from pathlib import Path; time.sleep(1); Path(' + repr(str(marker)) + ').write_text("late")'],
                 'cwd': tmp, 'timeout_seconds': 5, 'session_id': 'original-session'},
            ]}))
            runner = subprocess.Popen([sys.executable, str(SCRIPT), '--manifest', str(manifest),
                                       '--output', str(root / 'results')], stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True)
            try:
                import time
                status_path = root / 'results/long/status.json'
                until = time.monotonic() + 2
                while time.monotonic() < until:
                    if status_path.exists() and json.loads(status_path.read_text())['state'] == 'running':
                        break
                    time.sleep(0.02)
                else:
                    self.fail('review never started')
                os.kill(runner.pid, signal.SIGTERM)
                runner.communicate(timeout=3)
                self.assertEqual(json.loads(status_path.read_text())['state'], 'interrupted')
                time.sleep(1.1)
                self.assertFalse(marker.exists())
            finally:
                if runner.poll() is None:
                    runner.kill()
                    runner.wait()


if __name__ == '__main__':
    unittest.main()
