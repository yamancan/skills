"""Offline installation checks using disposable client homes."""
import os
from pathlib import Path
import pty
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASH = '/bin/bash' if Path('/bin/bash').is_file() else 'bash'


class Installation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="niche install ' ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.env = dict(os.environ, SKILLS_INSTALL_HOME=str(self.base),
                        CODEX_HOME=str(self.base / 'codex home'),
                        CLAUDE_CONFIG_DIR=str(self.base / 'claude home'),
                        DUO_STATE_DIR=str(self.base / 'state'),
                        PYTHONDONTWRITEBYTECODE='1')

    def install(self, *args):
        return subprocess.run([BASH, str(ROOT / 'install.sh'), *args],
                              cwd=self.base, env=self.env, text=True,
                              capture_output=True, timeout=10)

    def test_selected_skill_installs_to_both_hosts_idempotently(self):
        for _ in range(2):
            result = self.install('--skill', 'let-chinese-somehow', '--no-setup')
            self.assertEqual(result.returncode, 0, result.stderr)
        for client in ('codex home', 'claude home'):
            target = self.base / client / 'skills/let-chinese-somehow'
            self.assertTrue(target.is_symlink())
            self.assertEqual(target.resolve(), ROOT / 'skills/let-chinese-somehow')
        self.assertFalse(list(self.base.rglob('*.bak-*')))

    def test_orkestra_installs_its_duo_dependency(self):
        result = self.install('--skill', 'orkestra', '--no-setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('orkestra', 'duo'):
            self.assertEqual((self.base / 'codex home/skills' / name).resolve(), ROOT / 'skills' / name)

    def test_check_all_is_read_only_and_has_no_missing_x_dependency(self):
        result = self.install('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_all_installs_only_the_published_coding_collection(self):
        result = self.install('--no-setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        names = {p.name for p in (self.base / 'codex home/skills').iterdir()}
        self.assertEqual(names, {'duo', 'orkestra', 'project-context', 'let-chinese', 'let-chinese-somehow'})

    def test_unknown_skill_fails_before_writing(self):
        result = self.install('--skill', '../outside')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_existing_directory_is_preserved_as_a_backup(self):
        target = self.base / 'codex home/skills/let-chinese'
        target.mkdir(parents=True)
        (target / 'my-note').write_text('keep my data')
        result = self.install('--skill', 'let-chinese', '--no-setup')
        self.assertEqual(result.returncode, 0, result.stderr)
        backups = list(target.parent.glob('let-chinese.bak-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / 'my-note').read_text(), 'keep my data')

    def test_noninteractive_install_does_not_start_a_provider_or_login(self):
        fake_bin = self.base / 'bin'
        fake_bin.mkdir()
        for name in ('zro', 'opencode', 'claude', 'codex'):
            tool = fake_bin / name
            tool.write_text('#!/bin/sh\nprintf called > "$NATIVE_CALL_MARKER"\nexit 73\n')
            tool.chmod(0o700)
        self.env.update(PATH=str(fake_bin) + os.pathsep + self.env['PATH'],
                        NATIVE_CALL_MARKER=str(self.base / 'unexpected-provider-call'))
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.base / 'unexpected-provider-call').exists())
        self.assertIn('terminal', result.stdout)

    def test_setup_failure_explains_that_skills_are_already_linked(self):
        clone = self.base / 'source copy'
        clone.mkdir()
        shutil.copy2(ROOT / 'install.sh', clone / 'install.sh')
        shutil.copytree(ROOT / 'skills/duo', clone / 'skills/duo')
        (clone / 'skills/duo/scripts/setup.sh').write_text('#!/bin/sh\nexit 7\n')
        master, slave = pty.openpty()
        try:
            result = subprocess.run([BASH, str(clone / 'install.sh'), '--skill', 'duo'],
                                    cwd=self.base, env=self.env, stdin=slave,
                                    capture_output=True, text=True, timeout=10)
        finally:
            os.close(master)
            os.close(slave)
        self.assertEqual(result.returncode, 1)
        self.assertIn('Skills are linked', result.stderr)
        self.assertIn('setup is incomplete', result.stderr)
        self.assertTrue((self.base / 'codex home/skills/duo').is_symlink())


if __name__ == '__main__':
    unittest.main()
