import json
import os
from pathlib import Path
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


from _support import DUO_SCRIPTS

SCRIPT = DUO_SCRIPTS / 'setup_models.py'


class SetupModels(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.env = dict(os.environ, DUO_STATE_DIR=str(self.state),
                        CODEX_HOME=str(self.root / 'codex-home'),
                        CLAUDE_CONFIG_DIR=str(self.root / 'claude-home'),
                        PYTHONDONTWRITEBYTECODE='1')

    def setup(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], env=self.env,
                              capture_output=True, text=True, timeout=3)

    def test_normal_setup_supplies_both_duo_directions_without_repinning_old_pairs(self):
        old = self.setup('--profile', 'normal', '--save', '--set', 'opus=claude-opus-5-5:xhigh')
        self.assertEqual(old.returncode, 0, old.stderr)
        pair_script = SCRIPT.with_name('pair.py')
        def initialize(name, owner):
            result = subprocess.run([sys.executable, str(pair_script), 'init', '--owner', owner,
                '--pair', str(self.root / (name + '.json')), '--thread', name, '--task', name],
                cwd=self.root, env=self.env, capture_output=True, text=True, timeout=3)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        old_pair = initialize('old', 'codex')
        saved = self.setup('--profile', 'normal', '--save', '--set',
                           'codex=gpt-6.2-sol:high', '--set', 'opus=claude-opus-5-6:xhigh')
        self.assertEqual(saved.returncode, 0, saved.stderr)
        self.assertEqual(initialize('new-codex', 'codex')['peer_model'], 'claude-opus-5-6')
        reverse = initialize('new-claude', 'claude')
        self.assertEqual(reverse['peer_model'], 'gpt-6.2-sol')
        self.assertEqual(reverse['effort'], 'xhigh')
        self.assertEqual(json.loads((self.root / 'old.json').read_text()), old_pair)
        self.assertIn('xhigh', json.loads(saved.stdout)['duo_transport_note'])

    def test_legacy_normal_choices_gain_opus_without_replacing_other_profiles(self):
        self.state.mkdir()
        legacy = {'codex': {'model': 'gpt-6.2-sol', 'effort': 'high'},
                  'astra': {'model': 'gpt-6-astra', 'effort': 'medium'},
                  'fable': {'model': 'claude-fable-5-2', 'effort': 'high'}}
        (self.state / 'models.json').write_text(json.dumps({'profiles': {
            'normal': legacy, 'unrelated': {'keep': 'this'}}}))
        result = self.setup('--profile', 'normal', '--save')
        self.assertEqual(result.returncode, 0, result.stderr)
        profiles = json.loads((self.state / 'models.json').read_text())['profiles']
        self.assertEqual({key: profiles['normal'][key] for key in legacy}, legacy)
        self.assertIn('opus', profiles['normal'])
        self.assertEqual(profiles['unrelated'], {'keep': 'this'})

    def test_preview_is_read_only_and_bad_selection_preserves_saved_choices(self):
        check = self.setup('--profile', 'normal', '--check')
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.setup('--profile', 'normal', '--save').returncode, 0)
        before = (self.state / 'models.json').read_bytes()
        invalid = self.setup('--profile', 'normal', '--save', '--set', 'opus=latest:xhigh')
        self.assertNotEqual(invalid.returncode, 0)
        self.assertEqual((self.state / 'models.json').read_bytes(), before)

    def test_wizard_edits_choices_in_the_terminal_and_saves_the_bridge(self):
        binaries = self.root / 'bin'
        binaries.mkdir()
        for cli in ('codex', 'claude'):
            path = binaries / cli
            path.write_text('#!/bin/sh\nexit 0\n')
            path.chmod(0o700)
        self.env['PATH'] = str(binaries) + os.pathsep + self.env['PATH']
        self.env['TERM'] = 'xterm'
        installed = self.root / "user's skill files" / 'duo'
        shutil.copytree(SCRIPT.parent.parent, installed)
        noninteractive = subprocess.run(['bash', str(installed / 'scripts/setup.sh'), 'normal'],
            cwd=self.root, env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True)
        self.assertEqual(noninteractive.returncode, 1, noninteractive.stderr)
        self.assertFalse(self.state.exists())
        continuation = noninteractive.stderr.splitlines()[-1]
        elsewhere = self.root / 'another working directory'
        elsewhere.mkdir()
        terminal_env = dict(self.env, DUO_STATE_DIR=str(self.root / 'another state'),
                            CODEX_HOME=str(self.root / 'another codex home'),
                            CLAUDE_CONFIG_DIR=str(self.root / 'another claude home'))
        master, slave = pty.openpty()
        process = subprocess.Popen(['bash', '-c', continuation], cwd=elsewhere,
            stdin=slave, stdout=slave, stderr=slave, env=terminal_env)
        os.close(slave)
        output = b''
        try:
            # Codex model/effort, Astra, Fable, Opus, save confirmation.
            os.write(master, b'gpt-6.2-sol\nhigh\n\n\n\n\nclaude-opus-5-6\nxhigh\ny\n')
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if select.select([master], [], [], .1)[0]:
                    try:
                        output += os.read(master, 65536)
                    except OSError:
                        break
                if process.poll() is not None:
                    break
            process.wait(timeout=1)
            self.assertEqual(process.returncode, 0, output.decode(errors='replace'))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            os.close(master)
        self.assertTrue((self.state / 'models.json').exists(), 'Continuation lost the original shared state directory')
        saved = json.loads((self.state / 'models.json').read_text())['profiles']
        self.assertEqual(saved['normal']['codex'], {'model': 'gpt-6.2-sol', 'effort': 'high'})
        self.assertEqual(saved['duo']['opus'], {'model': 'claude-opus-5-6', 'effort': 'xhigh'})


if __name__ == '__main__':
    unittest.main()
