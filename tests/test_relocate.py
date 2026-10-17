"""Real Git, files, locks and crash recovery; no provider traffic."""
import copy
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

import test_pair as fixtures
import session_store
import workspace
import relocate


class Relocation(unittest.TestCase):
    def setUp(self):
        fixtures.PairRouting.setUp(self)
        self.root = self.root.resolve()
        self.work = self.work.resolve()
        self.repo = self.root/'repo'
        self.repo.mkdir()
        self.git(self.repo, 'init', '-q')
        self.git(self.repo, 'config', 'user.email', 'test@example.invalid')
        self.git(self.repo, 'config', 'user.name', 'Test')
        (self.repo/'source.txt').write_text('retained source\n')
        (self.repo/'.gitignore').write_text('ignored/\n')
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-qm', 'source')
        self.work.rmdir()
        self.git(self.repo, 'worktree', 'add', '-q', '--detach', str(self.work))
        self.target = self.root/'target'
        self.git(self.repo, 'worktree', 'add', '-q', '--detach', str(self.target))
        fixtures.PairRouting.initialize(self)
        self.assertEqual(fixtures.PairRouting.send(self).returncode, 0)
        self.env_patch = patch.dict(os.environ, self.env)
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.before = json.loads(self.pair.read_text())
        self.state = workspace.pair_workspace(self.before)
        self.state_before = json.loads(self.state.read_text())

    command = fixtures.PairRouting.command
    def git(self, root, *args):
        r = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def plan(self, **kwargs):
        return relocate.plan(self.pair.resolve(), self.before['task_id'], 'codex', 'codex-A',
                             self.target, 'Owner requested stable project directory', True, **kwargs)

    def apply(self, plan):
        return relocate.apply(plan, relocate.digest(plan))

    def test_relocation_keeps_peer_history_cursor_evidence_and_source(self):
        history = list(self.store.glob('projects/*/*.jsonl'))[0]
        raw = history.read_bytes()
        (self.work/'ignored').mkdir()
        (self.work/'ignored'/'keep').write_text('private ignored evidence')
        p = self.plan()
        self.assertEqual(json.loads(self.pair.read_text()), self.before, 'Planning mutated pair')
        result = self.apply(p)
        after = json.loads(self.pair.read_text())
        for key, value in self.before.items():
            if key != 'workdir':
                self.assertEqual(after[key], value, key)
        self.assertEqual(after['workdir'], str(self.target))
        self.assertEqual(history.read_bytes(), raw)
        self.assertEqual((self.work/'ignored'/'keep').read_text(), 'private ignored evidence')
        self.assertEqual(result['status'], 'committed')
        session_store.validate(after, self.pair.resolve())
        workspace.bind(self.state, self.target)
        self.assertNotEqual(fixtures.PairRouting.send(self).returncode, 0)
        self.assertEqual(fixtures.PairRouting.send(self, cwd=self.target).returncode, 0)
        calls = [json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls[-1]['cwd'], str(self.target))
        self.assertIn(self.before['peer_session_id'], calls[-1]['args'])
        self.assertTrue(history.read_bytes().startswith(raw))

    def test_refuses_unpreserved_untracked_and_dirty_source_or_target(self):
        for root in (self.work, self.target):
            with self.subTest(root=root):
                extra = root/'unique.txt'; extra.write_text('unsaved work')
                with self.assertRaisesRegex(ValueError, 'clean'):
                    self.plan()
                extra.unlink()
                source = root/'source.txt'; source.write_text('dirty')
                with self.assertRaisesRegex(ValueError, 'clean'):
                    self.plan()
                source.write_text('retained source\n')
        self.assertEqual(json.loads(self.pair.read_text()), self.before)

    def test_refuses_same_repository_different_tree_and_unrelated_same_tree(self):
        (self.target/'source.txt').write_text('different\n')
        self.git(self.target, 'add', '.'); self.git(self.target, 'commit', '-qm', 'different')
        with self.assertRaisesRegex(ValueError, 'tree'):
            self.plan()
        other = self.root/'clone'
        self.git(self.repo, 'clone', '-q', str(self.repo), str(other))
        self.target = other
        with self.assertRaisesRegex(ValueError, 'repository'):
            self.plan()

    def test_refuses_stale_plan_after_pair_target_or_peer_changes(self):
        p = self.plan()
        after = dict(self.before, task='new title')
        self.pair.write_text(json.dumps(after))
        with self.assertRaises(ValueError): self.apply(p)
        self.pair.write_text(json.dumps(self.before))
        (self.target/'new').write_text('new work')
        with self.assertRaises(ValueError): self.apply(p)
        (self.target/'new').unlink()
        history = list(self.store.glob('projects/*/*.jsonl'))[0]
        history.write_text(history.read_text() + json.dumps({'type': 'assistant',
            'sessionId': self.before['peer_session_id'], 'uuid': 'new',
            'message': {'content': 'new native decision'}})+'\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            self.apply(p)

    def test_refuses_symlink_and_replaced_source_inode(self):
        alias = self.root/'alias'; alias.symlink_to(self.target, target_is_directory=True)
        self.target = alias
        with self.assertRaises(ValueError): self.plan()
        self.target = self.root/'target'
        moved = self.root/'saved-old'; self.work.rename(moved)
        self.work.mkdir()
        with self.assertRaises(ValueError): self.plan()

    def test_refuses_active_pair_manual_state_and_disposable_runs(self):
        with self.pair.with_name('pair.json.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(ValueError, 'active'): self.plan()
        self.pair.write_text(json.dumps(dict(self.before, status='held')))
        with self.assertRaisesRegex(ValueError, 'ready'): self.plan()
        self.pair.write_text(json.dumps(self.before))
        data = copy.deepcopy(self.state_before); data['runs']['unfinished'] = {'cleaned': False}
        self.state.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'run'): self.plan()

    def test_wrong_owner_task_or_unconfirmed_idle_cannot_plan(self):
        for task, owner, thread, idle in [('wrong', 'codex', 'codex-A', True),
                 (self.before['task_id'], 'codex', 'wrong', True),
                 (self.before['task_id'], 'codex', 'codex-A', False)]:
            with self.assertRaises(ValueError):
                relocate.plan(self.pair.resolve(), task, owner, thread, self.target, 'reason', idle)

    def test_missing_source_requires_verified_standalone_bundle_and_exact_commit(self):
        bundle = self.root/'source.bundle'
        self.git(self.repo, 'bundle', 'create', str(bundle), '--all')
        commit = self.git(self.work, 'rev-parse', 'HEAD')
        shutil.rmtree(self.work)
        with self.assertRaises(ValueError): self.plan()
        with self.assertRaises(ValueError): self.plan(source_commit='0'*40, source_bundle=bundle)
        p = self.plan(source_commit=commit, source_bundle=bundle)
        self.assertEqual(p['proof']['mode'], 'recovered-commit')
        self.apply(p)
        workspace.bind(self.state, self.target)

    def test_partial_write_blocks_dispatch_and_rollback_preserves_other_index_entries(self):
        p = self.plan()
        original = relocate.durable_write
        def interrupted(path, data):
            if Path(path) == self.pair.resolve():
                raise OSError('simulated storage failure')
            return original(path, data)
        with patch.object(relocate, 'durable_write', side_effect=interrupted):
            with self.assertRaises(OSError): self.apply(p)
        with self.assertRaisesRegex(ValueError, 'relocation'):
            session_store.validate(self.before, self.pair.resolve())
        with self.assertRaisesRegex(ValueError, 'relocation'):
            workspace.bind(self.state, self.work)
        index = session_store.read_index(); index['unrelated'] = {'retained': True}
        session_store.write_json(session_store.state_dir()/'tasks.json', index)
        marker = json.loads(relocate.marker_path(self.state).read_text())
        result = relocate.rollback(self.pair.resolve(), self.before['task_id'], 'codex', 'codex-A', marker['id'])
        self.assertEqual(result['status'], 'rolled_back')
        self.assertEqual(json.loads(self.pair.read_text()), self.before)
        self.assertEqual(json.loads(self.state.read_text()), self.state_before)
        self.assertEqual(session_store.read_index()['unrelated'], {'retained': True})
        session_store.validate(self.before, self.pair.resolve())

    def test_rollback_refuses_unknown_edits_instead_of_overwriting_them(self):
        p = self.plan(); original = relocate.durable_write
        def interrupted(path, data):
            if Path(path) == self.pair.resolve(): raise OSError('crash')
            return original(path, data)
        with patch.object(relocate, 'durable_write', side_effect=interrupted):
            with self.assertRaises(OSError): self.apply(p)
        self.pair.write_text(json.dumps(dict(self.before, task='human changed this')))
        marker = json.loads(relocate.marker_path(self.state).read_text())
        with self.assertRaisesRegex(ValueError, 'changed'):
            relocate.rollback(self.pair.resolve(), self.before['task_id'], 'codex', 'codex-A', marker['id'])
        self.assertEqual(json.loads(self.pair.read_text())['task'], 'human changed this')

    def test_modified_plan_digest_is_rejected_without_state_changes(self):
        p = self.plan(); expected = relocate.digest(p); p['reason'] = 'altered'
        with self.assertRaisesRegex(ValueError, 'digest'): relocate.apply(p, expected)
        self.assertEqual(json.loads(self.pair.read_text()), self.before)

    def test_each_interrupted_commit_step_recovers_and_recovery_can_be_retried(self):
        for step in ('workspace', 'pair', 'index', 'receipt'):
            with self.subTest(step=step):
                p = self.plan(); original = relocate.durable_write
                def interrupted(path, data):
                    original(path, data)
                    matches = ((step == 'workspace' and Path(path) == self.state)
                        or (step == 'pair' and Path(path) == self.pair.resolve())
                        or (step == 'index' and Path(path) == session_store.state_dir()/'tasks.json')
                        or (step == 'receipt' and data.get('status') == 'committed' and 'plan' in data))
                    if matches: raise OSError('crash after persisted '+step)
                with patch.object(relocate, 'durable_write', side_effect=interrupted):
                    with self.assertRaises(OSError): self.apply(p)
                self.assertNotEqual(fixtures.PairRouting.send(self).returncode, 0)
                current = json.loads(self.pair.read_text())
                with self.assertRaisesRegex(ValueError, 'relocation'):
                    session_store.validate(current, self.pair.resolve())
                marker = json.loads(relocate.marker_path(self.state).read_text())
                def failed_recovery(path, data):
                    original(path, data)
                    if Path(path) == self.state: raise OSError('recovery interrupted')
                with patch.object(relocate, 'durable_write', side_effect=failed_recovery):
                    with self.assertRaises(OSError):
                        relocate.rollback(self.pair.resolve(), self.before['task_id'], 'codex', 'codex-A', marker['id'])
                relocate.rollback(self.pair.resolve(), self.before['task_id'], 'codex', 'codex-A', marker['id'])
                self.assertEqual(json.loads(self.pair.read_text()), self.before)
                self.assertEqual(json.loads(self.state.read_text()), self.state_before)

    def test_target_inode_replacement_invalidates_same_content_plan(self):
        p = self.plan()
        self.git(self.repo, 'worktree', 'move', str(self.target), str(self.root/'retained-target'))
        self.git(self.repo, 'worktree', 'add', '-q', '--detach', str(self.target))
        with self.assertRaisesRegex(ValueError, 'changed'): self.apply(p)

    def test_missing_duplicate_and_rewritten_native_history_fail_closed(self):
        history = list(self.store.glob('projects/*/*.jsonl'))[0]
        raw = history.read_bytes()
        other = self.store/'projects'/'duplicate'; other.mkdir()
        duplicate = other/history.name; duplicate.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'ambiguous'): self.plan()
        duplicate.unlink()
        history.write_bytes(raw.replace(b'Reviewed', b'Rewritten'))
        with self.assertRaisesRegex(ValueError, 'rewritten'): self.plan()
        history.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'): self.plan()

    def test_source_or_peer_change_during_apply_retains_pending_barrier(self):
        p = self.plan(); original = relocate.durable_write
        def changed(path, data):
            original(path, data)
            if Path(path) == self.pair.resolve():
                (self.target/'source.txt').write_text('concurrent source change')
        with patch.object(relocate, 'durable_write', side_effect=changed):
            with self.assertRaises(ValueError): self.apply(p)
        marker = json.loads(relocate.marker_path(self.state).read_text())
        self.assertEqual(marker['status'], 'pending')
        with self.assertRaisesRegex(ValueError, 'relocation'):
            session_store.validate(json.loads(self.pair.read_text()), self.pair.resolve())
        relocate.rollback(self.pair.resolve(), self.before['task_id'], 'codex', 'codex-A', marker['id'])
        self.assertEqual((self.target/'source.txt').read_text(), 'concurrent source change')

    def test_pinned_clean_submodule_can_be_initialized_only_at_destination(self):
        dependency = self.root/'dependency'; dependency.mkdir()
        self.git(dependency, 'init', '-q')
        self.git(dependency, 'config', 'user.email', 'test@example.invalid')
        self.git(dependency, 'config', 'user.name', 'Test')
        (dependency/'library.txt').write_text('pinned library')
        self.git(dependency, 'add', '.'); self.git(dependency, 'commit', '-qm', 'library')
        self.git(self.work, '-c', 'protocol.file.allow=always', 'submodule', 'add', '-q', str(dependency), 'vendor')
        self.git(self.work, 'commit', '-qam', 'add pinned submodule')
        head = self.git(self.work, 'rev-parse', 'HEAD')
        self.git(self.target, 'checkout', '-q', head)
        self.git(self.target, '-c', 'protocol.file.allow=always', 'submodule', 'update', '--init', '-q')
        self.git(self.work, 'submodule', 'deinit', '-f', 'vendor')
        p = self.plan()
        self.assertFalse(p['proof']['source']['submodules']['vendor']['initialized'])
        self.assertTrue(p['target']['submodules']['vendor']['initialized'])
        (self.target/'vendor'/'unique.txt').write_text('uncommitted local work')
        with self.assertRaisesRegex(ValueError, 'clean'): self.apply(p)
        (self.target/'vendor'/'unique.txt').unlink()
        self.apply(p)
        self.assertEqual((self.target/'vendor'/'library.txt').read_text(), 'pinned library')

    def test_old_checkout_cannot_silently_create_replacement_task_after_move(self):
        self.apply(self.plan())
        other = self.root/'accidental-copy.json'
        result = self.command('init', '--pair', str(other), '--thread', 'codex-A',
            '--task', self.before['task'], '--opus-model', 'claude-opus-5-5')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('relocated', result.stderr)
        self.assertFalse(other.exists())

    def test_pending_mismatch_stays_discoverable_without_blocking_other_tasks(self):
        p = self.plan(); original = relocate.durable_write
        def interrupted(path, data):
            original(path, data)
            if Path(path) == self.pair.resolve(): raise OSError('crash after pair')
        with patch.object(relocate, 'durable_write', side_effect=interrupted):
            with self.assertRaises(OSError): self.apply(p)
        entries = session_store.listing()
        self.assertEqual(entries[0]['status'], 'relocation_pending')
        self.assertEqual(entries[0]['task_id'], self.before['task_id'])

    def test_resumed_peer_cannot_rewrite_pre_move_history(self):
        self.apply(self.plan())
        # Simulate a provider retaining the UUID but replacing prior native bytes.
        fake = self.fake.read_text()
        fake = fake.replace("    with (store / (session + '.jsonl')).open('a') as f:",
            "    (store / (session + '.jsonl')).write_text('')\n    with (store / (session + '.jsonl')).open('a') as f:")
        self.fake.write_text(fake)
        result = fixtures.PairRouting.send(self, cwd=self.target)
        self.assertNotEqual(result.returncode, 0)
        after = json.loads(self.pair.read_text())
        self.assertEqual(after['status'], 'held')
        self.assertEqual(after['read_head'], self.before['read_head'])
        self.assertIn('rewritten', result.stderr)

    def test_reverse_duo_keeps_exact_codex_session_after_relocation(self):
        self.pair = self.root/'reverse.json'
        fixtures.PairRouting.initialize_reverse(self)
        self.assertEqual(fixtures.PairRouting.send_reverse(self).returncode, 0)
        before = json.loads(self.pair.read_text())
        p = relocate.plan(self.pair.resolve(), before['task_id'], 'claude', 'claude-A',
                          self.target, 'same reverse task moves', True)
        self.apply(p)
        result = self.command('run', '--owner', 'claude', '--pair', str(self.pair),
            '--thread', 'claude-A', '--prompt', str(self.prompt), '--snapshot', 'after-move', cwd=self.target)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = json.loads(self.pair.read_text())
        self.assertEqual(after['peer_session_id'], before['peer_session_id'])
        self.assertEqual(after['owner_thread'], 'claude-A')
        calls = [json.loads(x) for x in (self.root/'calls.jsonl').read_text().splitlines()]
        self.assertEqual(calls[-1]['cwd'], str(self.target))
        self.assertIn(before['peer_session_id'], calls[-1]['args'])

    def test_provider_duplicate_history_after_move_is_held(self):
        self.apply(self.plan())
        fake = self.fake.read_text().replace("'projects' / 'test-project'", "'projects' / 'new-project'")
        self.fake.write_text(fake)
        result = fixtures.PairRouting.send(self, cwd=self.target)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ambiguous', result.stderr)
        after = json.loads(self.pair.read_text())
        self.assertEqual(after['status'], 'held')
        self.assertEqual(after['read_head'], self.before['read_head'])

    def test_reconstructed_old_directory_needs_bundle_proof_and_clean_exact_source(self):
        bundle = self.root/'source.bundle'
        self.git(self.repo, 'bundle', 'create', str(bundle), '--all')
        commit = self.git(self.work, 'rev-parse', 'HEAD')
        self.git(self.repo, 'worktree', 'move', str(self.work), str(self.root/'old-preserved'))
        self.git(self.repo, 'worktree', 'add', '-q', '--detach', str(self.work), commit)
        with self.assertRaises(ValueError): self.plan()
        p = self.plan(source_commit=commit, source_bundle=bundle)
        self.assertEqual(p['proof']['mode'], 'recovered-commit')
        self.apply(p)
        self.assertTrue((self.root/'old-preserved'/'source.txt').is_file())


if __name__ == '__main__': unittest.main()
