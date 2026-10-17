"""Exercise real registry/lock/history behavior; only provider executables are fakes."""
import errno
import json
import os
import pty
import select
import signal
from pathlib import Path
import subprocess
import sys
import time
import unittest

import test_pair as fixtures

SCRIPT = fixtures.SCRIPT


class TaskSessions(unittest.TestCase):
    setUp = fixtures.PairRouting.setUp
    def command(self, *args, cwd=None):
        if args[0] == 'handoff' and '--context' not in args:
            args += ('--context', str(self.prompt))
        return fixtures.PairRouting.command(self, *args, cwd=cwd)
    initialize = fixtures.PairRouting.initialize
    initialize_reverse = fixtures.PairRouting.initialize_reverse
    send = fixtures.PairRouting.send
    send_reverse = fixtures.PairRouting.send_reverse
    seed_transcript = fixtures.PairRouting.seed_transcript

    def record(self):
        return json.loads(self.pair.read_text())

    def test_same_task_at_second_path_reuses_canonical_pair(self):
        self.initialize()
        before = self.record()
        other = self.root/'pair-copy.json'
        result = self.command('init', '--pair', str(other), '--thread', 'codex-A',
            '--task', 'Registration repair', '--opus-model', 'claude-opus-5-5')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['pair_id'], before['pair_id'])
        self.assertFalse(other.exists(), 'A second dispatchable copy was created')

    def test_title_case_variation_reuses_existing_task_without_renaming_it(self):
        self.initialize()
        result = self.command('init', '--pair', str(self.root/'lower-case.json'), '--thread', 'codex-A',
            '--task', 'registration repair', '--opus-model', 'claude-opus-5-5')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['pair_id'], self.record()['pair_id'])
        self.assertEqual(json.loads(result.stdout)['task'], 'Registration repair')

    def test_new_sol_cannot_silently_create_a_second_opus_for_same_task(self):
        self.initialize_reverse()
        other = self.root/'sol-2.json'
        result = self.command('init', '--pair', str(other), '--thread', 'sol-2',
            '--task', 'Reverse review', '--opus-model', 'claude-opus-5-5')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('existing task', result.stderr.lower())
        self.assertFalse(other.exists())

    def test_list_finds_native_ids_without_the_old_checkpoint(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        result = self.command('list', '--task', 'registration')
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = json.loads(result.stdout)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['pair_path'], str(self.pair.resolve()))
        self.assertEqual(entries[0]['peer_session_id'], self.record()['peer_session_id'])
        self.assertEqual(entries[0]['task'], 'Registration repair')

    def test_new_owner_model_cannot_be_a_mutable_alias(self):
        result = self.command('init', '--pair', str(self.pair), '--thread', 'codex-A',
            '--task', 'Alias owner', '--owner-model', 'latest', '--opus-model', 'claude-opus-5-5')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.pair.exists())

    def test_unknown_owner_manual_resume_requires_a_versioned_model(self):
        self.initialize_reverse()
        self.seed_transcript('claude-A')
        before = self.record()
        result = self.command('manual', '--pair', str(self.pair), '--role', 'claude', '--model', 'opus')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record(), before)
        self.assertFalse((self.root/'calls.jsonl').exists())

    def test_handoff_cannot_turn_a_legacy_owner_alias_into_a_pinned_peer(self):
        self.initialize_reverse()
        self.seed_transcript('claude-A')
        before = self.record(); before['owner_model'] = 'opus'
        self.pair.write_text(json.dumps(before))
        result = self.command('handoff', '--pair', str(self.pair), '--task-id', before['task_id'],
            '--expect-owner', 'claude', '--expect-thread', 'claude-A', '--owner', 'codex',
            '--thread', 'sol-2', '--reason', 'Transfer same task')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record(), before)

    def test_saved_defaults_start_new_tasks_without_changing_existing_pair(self):
        self.initialize()
        old = self.record()
        setup = SCRIPT.with_name('setup_models.py')
        result = subprocess.run([sys.executable, str(setup), '--save', '--set',
            'opus=claude-opus-5-6:xhigh'], env=self.env, capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.command('init', '--pair', str(self.root/'new-default.json'),
            '--thread', 'codex-B', '--task', 'A separate task')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['peer_model'], 'claude-opus-5-6')
        self.assertEqual(self.record(), old)
        result = self.command('init', '--pair', str(self.root/'replacement.json'),
            '--thread', 'codex-A', '--task', old['task'])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record(), old)
        self.assertFalse((self.root/'replacement.json').exists())

    def test_discovery_and_validation_do_not_rewrite_index(self):
        self.initialize()
        index = self.root/'duo-state'/'tasks.json'
        before = index.stat()
        self.assertEqual(self.command('list').returncode, 0)
        self.assertEqual(self.send().returncode, 0)
        after = index.stat()
        self.assertEqual((before.st_ino, before.st_mtime_ns), (after.st_ino, after.st_mtime_ns))

    def test_empty_discovery_does_not_create_state(self):
        self.assertEqual(self.command('list').returncode, 0)
        self.assertFalse((self.root/'duo-state').exists())

    def test_managed_resume_command_restores_directory_and_homes(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        self.fake.write_text('#!/usr/bin/env python3\n')
        description = json.loads(self.command('show', '--pair', str(self.pair)).stdout)
        command = description['conversations']['claude']['manual_command']
        env = dict(self.env, DUO_STATE_DIR=str(self.root/'wrong-index'),
                   CLAUDE_CONFIG_DIR=str(self.root/'wrong-claude'), CODEX_HOME=str(self.root/'wrong-codex'))
        result = subprocess.run(['bash', '-c', command], cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_handoff_cannot_replace_known_owner_model(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        self.seed_transcript('claude-A')
        before = self.record()
        before['owner_model'] = 'claude-opus-5-5'
        self.pair.write_text(json.dumps(before))
        result = self.command('handoff', '--pair', str(self.pair), '--task-id', before['task_id'],
            '--expect-owner', 'claude', '--expect-thread', 'claude-A', '--owner', 'codex',
            '--thread', 'sol-2', '--opus-model', 'claude-opus-5', '--reason', 'Transfer same task')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record(), before)

    def test_same_name_requires_explicit_separate_task_and_then_is_ambiguous(self):
        self.initialize()
        other = self.root/'independent.json'
        result = self.command('init', '--pair', str(other), '--thread', 'codex-B',
            '--task', 'Registration repair', '--new-task', '--opus-model', 'claude-opus-5-5')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(json.loads(result.stdout)['task_id'], self.record()['task_id'])
        result = self.command('init', '--pair', str(self.root/'third.json'), '--thread', 'codex-C',
            '--task', 'Registration repair', '--opus-model', 'claude-opus-5-5')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ambiguous', result.stderr.lower())

    def test_same_provider_handoff_keeps_peer_and_revokes_previous_owner(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        before = self.record()
        result = self.command('handoff', '--pair', str(self.pair), '--task-id', before.get('task_id', before['pair_id']),
            '--expect-owner', 'codex', '--expect-thread', 'codex-A',
            '--owner', 'codex', '--thread', 'codex-B', '--reason', 'User moved to a new coordinator')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record()['peer_session_id'], before['peer_session_id'])
        self.assertNotEqual(self.send().returncode, 0)
        sync = self.command('sync', '--pair', str(self.pair), '--owner', 'codex', '--thread', 'codex-B')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        token = json.loads(sync.stdout)['token']
        self.assertEqual(self.command('ack', '--pair', str(self.pair), '--owner', 'codex',
            '--thread', 'codex-B', '--token', token).returncode, 0)
        self.assertEqual(self.send(thread='codex-B').returncode, 0)

    def test_sol_two_takeover_reuses_original_opus_in_reverse_direction(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        self.seed_transcript('claude-A')
        old = self.record()
        result = self.command('handoff', '--pair', str(self.pair), '--task-id', old.get('task_id', old['pair_id']),
            '--expect-owner', 'claude', '--expect-thread', 'claude-A',
            '--owner', 'codex', '--thread', 'sol-2', '--opus-model', 'claude-opus-5-5',
            '--reason', 'Explicit replacement of Sol 1 by Sol 2')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.record()['peer_session_id'], 'claude-A')
        self.assertEqual(self.record()['task_id'], old['task_id'])
        sync = self.command('sync', '--pair', str(self.pair), '--thread', 'sol-2')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        self.assertEqual(self.command('ack', '--pair', str(self.pair), '--thread', 'sol-2',
            '--token', json.loads(sync.stdout)['token']).returncode, 0)
        result = self.send(thread='sol-2')
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.root/'calls.jsonl').read_text().splitlines()[-1])['args']
        self.assertEqual(args[args.index('--resume')+1], 'claude-A')
        self.assertNotIn('--session-id', args)

    def test_manual_message_requires_read_and_ack_before_dispatch(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        session = self.record()['peer_session_id']
        path = self.store/'projects'/'test-project'/(session+'.jsonl')
        with path.open('a') as file:
            file.write(json.dumps({'type': 'user', 'sessionId': session, 'uuid': 'manual-decision',
                'message': {'role': 'user', 'content': 'Keep the legacy URL working.'}})+'\n')
        self.assertNotEqual(self.send().returncode, 0)
        self.assertEqual(len((self.root/'calls.jsonl').read_text().splitlines()), 1)
        result = self.command('sync', '--pair', str(self.pair), '--thread', 'codex-A')
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual([turn['text'] for turn in packet['turns']], ['Keep the legacy URL working.'])
        self.assertNotEqual(self.send().returncode, 0, 'Reading without acknowledgement lost the decision')
        self.assertEqual(self.command('ack', '--pair', str(self.pair), '--thread', 'codex-A',
            '--token', packet['token']).returncode, 0)
        self.assertEqual(self.send().returncode, 0)
        again = self.command('sync', '--pair', str(self.pair), '--thread', 'codex-A')
        self.assertEqual(json.loads(again.stdout)['turns'], [])

    def test_changes_after_sync_make_ack_stale(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        sync = self.command('sync', '--pair', str(self.pair), '--thread', 'codex-A')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        path = self.store/'projects'/'test-project'/(self.record()['peer_session_id']+'.jsonl')
        with path.open('a') as file:
            file.write(json.dumps({'type': 'user', 'sessionId': self.record()['peer_session_id'],
                'message': {'content': 'One more decision'}})+'\n')
        ack = self.command('ack', '--pair', str(self.pair), '--thread', 'codex-A',
            '--token', json.loads(sync.stdout)['token'])
        self.assertNotEqual(ack.returncode, 0)
        self.assertIn('changed', ack.stderr.lower())

    def test_dispatch_rejects_wrong_expected_task(self):
        self.initialize()
        result = self.command('run', '--pair', str(self.pair), '--thread', 'codex-A',
            '--task-id', 'another-task', '--prompt', str(self.prompt), '--snapshot', 'one')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('task identity', result.stderr.lower())
        self.assertFalse((self.root/'calls.jsonl').exists())

    def test_fork_keeps_original_pair_and_records_separate_context(self):
        self.initialize()
        before = self.record()
        result = self.command('fork', '--pair', str(self.pair), '--new-pair', str(self.root/'fresh.json'),
            '--thread', 'codex-B', '--task', 'Independent review', '--opus-model', 'claude-opus-5-5',
            '--reason', 'Fresh independent reviewer')
        self.assertEqual(result.returncode, 0, result.stderr)
        child = json.loads(result.stdout)
        self.assertEqual(child['parent_task_id'], before['task_id'])
        self.assertNotEqual(child['peer_session_id'], before['peer_session_id'])
        self.assertEqual(self.record(), before)

    def test_managed_manual_resume_blocks_dispatch_until_process_exits(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        gate = self.root/'manual-gate'
        self.env['GATE'] = str(gate)
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'manual', '--pair', str(self.pair),
            '--role', 'claude'], cwd=self.work, env=self.env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic()+3
            while not Path(str(gate)+'.entered').exists() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertTrue(Path(str(gate)+'.entered').exists())
            self.assertNotEqual(self.send().returncode, 0)
            self.assertEqual(self.record()['status'], 'manual')
        finally:
            gate.touch()
            out, err = process.communicate(timeout=3)
        self.assertEqual(process.returncode, 0, err)
        self.assertEqual(self.record()['status'], 'ready')
        self.assertNotEqual(self.send().returncode, 0, 'Manual additions must be synchronized first')

    def test_concurrent_initializers_create_only_one_canonical_task(self):
        processes = []
        paths = [self.root/'race-a.json', self.root/'race-b.json']
        for path in paths:
            processes.append(subprocess.Popen([sys.executable, str(SCRIPT), 'init', '--pair', str(path),
                '--thread', 'codex-A', '--task', 'One concurrent task', '--opus-model', 'claude-opus-5-5'],
                cwd=self.work, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        records = []
        for process in processes:
            out, err = process.communicate(timeout=3)
            self.assertEqual(process.returncode, 0, err)
            records.append(json.loads(out))
        self.assertEqual(records[0]['pair_id'], records[1]['pair_id'])
        self.assertEqual(sum(path.exists() for path in paths), 1)

    def test_copied_pair_cannot_dispatch(self):
        self.initialize()
        copy = self.root/'copy.json'
        copy.write_bytes(self.pair.read_bytes())
        result = self.command('run', '--pair', str(copy), '--thread', 'codex-A',
            '--prompt', str(self.prompt), '--snapshot', 'one')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('canonical', result.stderr.lower())
        self.assertFalse((self.root/'calls.jsonl').exists())

    def test_missing_canonical_record_does_not_create_replacement(self):
        self.initialize()
        self.pair.unlink()
        other = self.root/'replacement.json'
        result = self.command('init', '--pair', str(other), '--thread', 'codex-A',
            '--task', 'Registration repair', '--opus-model', 'claude-opus-5-5')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(other.exists())
        entries = self.command('list')
        self.assertEqual(json.loads(entries.stdout)[0]['status'], 'missing_record')

    def test_stale_duplicate_index_entry_does_not_block_listing(self):
        self.initialize()
        index = self.root/'duo-state'/'tasks.json'
        data = json.loads(index.read_text())
        (task_id, item), = data.items()
        data['stale-' + task_id] = item | {'task_id': 'stale-' + task_id}
        index.write_text(json.dumps(data))
        entries = self.command('list')
        self.assertEqual(entries.returncode, 0, entries.stderr)
        statuses = {e['task_id']: e.get('status') for e in json.loads(entries.stdout)}
        self.assertEqual(statuses['stale-' + task_id], 'index_mismatch')
        self.assertNotEqual(statuses[task_id], 'index_mismatch')

    def test_codex_manual_turns_are_reconciled_without_exposing_reasoning(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        path = next((self.root/'codex-home'/'sessions').rglob('*.jsonl'))
        with path.open('a') as file:
            for payload in [{'type': 'reasoning', 'summary': [{'text': 'Private thought'}]},
                {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'Keep rollback.'}]},
                {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Agreed.'}]}]:
                file.write(json.dumps({'type': 'response_item', 'payload': payload})+'\n')
        self.assertNotEqual(self.send_reverse().returncode, 0)
        sync = self.command('sync', '--pair', str(self.pair), '--owner', 'claude', '--thread', 'claude-A')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        self.assertEqual([t['text'] for t in json.loads(sync.stdout)['turns']], ['Keep rollback.', 'Agreed.'])

    def test_rewritten_native_history_is_not_silently_acknowledged(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        path = self.store/'projects'/'test-project'/(self.record()['peer_session_id']+'.jsonl')
        path.write_text(path.read_text().replace('Reviewed', 'Revised!'))
        result = self.command('sync', '--pair', str(self.pair), '--thread', 'codex-A')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('rewritten', result.stderr.lower())
        self.assertNotEqual(self.send().returncode, 0)

    def test_handoff_rejects_stale_expected_owner(self):
        self.initialize()
        args = ('handoff', '--pair', str(self.pair), '--task-id', self.record()['task_id'],
            '--expect-owner', 'codex', '--expect-thread', 'codex-A', '--owner', 'codex',
            '--thread', 'codex-B', '--reason', 'Take over')
        self.assertEqual(self.command(*args).returncode, 0)
        result = self.command(*args)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('ownership changed', result.stderr.lower())

    def test_show_exposes_managed_exact_id_resume_without_faking_native_titles(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        result = self.command('show', '--pair', str(self.pair))
        self.assertEqual(result.returncode, 0, result.stderr)
        peer = json.loads(result.stdout)['conversations']['claude']
        self.assertIn(self.record()['peer_session_id'], peer['native_command'])
        self.assertIn('manual', peer['manual_command'])
        self.assertIn('Registration repair', peer['name'])

    def test_returned_result_must_match_the_new_native_codex_message(self):
        self.initialize_reverse()
        self.env['CODEX_TRANSCRIPT_TEXT'] = 'An old unrelated answer'
        result = self.send_reverse()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record()['status'], 'held')

    def test_handoff_validates_native_peer_before_transferring_ownership(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        before = self.record()
        path = self.store/'projects'/'test-project'/(before['peer_session_id']+'.jsonl')
        path.unlink()
        result = self.command('handoff', '--pair', str(self.pair), '--task-id', before['task_id'],
            '--expect-owner', 'codex', '--expect-thread', 'codex-A', '--owner', 'codex',
            '--thread', 'codex-B', '--reason', 'Take over')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record(), before)

    def test_handoff_rejects_rewritten_history_instead_of_resetting_cursor(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        path = self.store/'projects'/'test-project'/(self.record()['peer_session_id']+'.jsonl')
        path.write_text(path.read_text().replace('Reviewed', 'Revised!'))
        before = self.record()
        result = self.command('handoff', '--pair', str(self.pair), '--task-id', before['task_id'],
            '--expect-owner', 'codex', '--expect-thread', 'codex-A', '--owner', 'codex',
            '--thread', 'codex-B', '--reason', 'Take over')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record(), before)

    def test_show_legacy_pair_does_not_create_a_broken_index_entry(self):
        self.pair.write_text(json.dumps({'pair_id': 'legacy-pair', 'codex_thread': 'codex-A',
            'task': 'Old slice', 'workdir': str(self.work), 'opus_model': 'claude-opus-5-5',
            'effort': 'xhigh', 'opus_session_id': '11111111-2222-4333-8444-555555555555',
            'started': True, 'status': 'ready'}))
        self.assertEqual(self.command('show', '--pair', str(self.pair)).returncode, 0)
        entries = self.command('list')
        self.assertEqual(entries.returncode, 0, entries.stderr)
        self.assertEqual(json.loads(entries.stdout), [])

    def test_owner_seat_manual_additions_are_synced_before_dispatch(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        self.seed_transcript('claude-A')
        result = self.command('manual', '--pair', str(self.pair), '--role', 'claude', '--model', 'claude-opus-5-5')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(self.send_reverse().returncode, 0)
        sync = self.command('sync', '--pair', str(self.pair), '--owner', 'claude', '--thread', 'claude-A')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        packet = json.loads(sync.stdout)
        self.assertEqual([turn['text'] for turn in packet['manual_owner_turns']], ['Reviewed'])
        self.assertEqual(self.command('ack', '--pair', str(self.pair), '--owner', 'claude', '--thread', 'claude-A',
            '--token', packet['token']).returncode, 0)
        self.assertEqual(self.send_reverse().returncode, 0)

    def test_coordinator_tool_logging_does_not_invalidate_manual_owner_ack(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        path = self.seed_transcript('claude-A')
        self.assertEqual(self.command('manual', '--pair', str(self.pair), '--role', 'claude',
            '--model', 'claude-opus-5-5').returncode, 0)
        sync = self.command('sync', '--pair', str(self.pair), '--owner', 'claude', '--thread', 'claude-A')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        packet = json.loads(sync.stdout)
        with path.open('a') as file:
            file.write(json.dumps({'type': 'assistant', 'sessionId': 'claude-A',
                'message': {'content': [{'type': 'tool_use', 'name': 'Bash', 'id': 'ack-tool',
                    'input': {'command': 'python3 pair.py ack'}}]}})+'\n')
        ack = self.command('ack', '--pair', str(self.pair), '--owner', 'claude', '--thread', 'claude-A',
            '--token', packet['token'])
        self.assertEqual(ack.returncode, 0, ack.stderr)
        self.assertEqual(self.send_reverse().returncode, 0)

    def test_another_managed_owner_manual_run_invalidates_previous_sync_token(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        self.seed_transcript('claude-A')
        manual = ('manual', '--pair', str(self.pair), '--role', 'claude', '--model', 'claude-opus-5-5')
        self.assertEqual(self.command(*manual).returncode, 0)
        sync = self.command('sync', '--pair', str(self.pair), '--owner', 'claude', '--thread', 'claude-A')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        self.assertEqual(self.command(*manual).returncode, 0)
        ack = self.command('ack', '--pair', str(self.pair), '--owner', 'claude', '--thread', 'claude-A',
            '--token', json.loads(sync.stdout)['token'])
        self.assertNotEqual(ack.returncode, 0)
        self.assertIn('changed', ack.stderr.lower())

    def test_image_only_user_turn_is_exposed_and_requires_ack(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        path = self.store/'projects'/'test-project'/(self.record()['peer_session_id']+'.jsonl')
        with path.open('a') as file:
            file.write(json.dumps({'type': 'user', 'sessionId': self.record()['peer_session_id'],
                'message': {'content': [{'type': 'image', 'source': {'type': 'base64',
                    'media_type': 'image/png', 'data': 'PRIVATE_IMAGE_BYTES'}}]}})+'\n')
        self.assertNotEqual(self.send().returncode, 0)
        sync = self.command('sync', '--pair', str(self.pair), '--thread', 'codex-A')
        self.assertEqual(sync.returncode, 0, sync.stderr)
        packet = json.loads(sync.stdout)
        self.assertEqual(len(packet['turns']), 1)
        self.assertEqual(packet['turns'][0]['attachments'], [{'type': 'image'}])
        self.assertNotIn('PRIVATE_IMAGE_BYTES', sync.stdout)
        self.assertNotEqual(self.send().returncode, 0)
        self.assertEqual(self.command('ack', '--pair', str(self.pair), '--thread', 'codex-A',
            '--token', packet['token']).returncode, 0)
        self.assertEqual(self.send().returncode, 0)

    def test_manual_interrupt_stops_provider_descendants(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        heartbeat = self.root/'manual-child-heartbeat'
        fake = self.root/'codex'
        fake.write_text('''#!/usr/bin/env python3
import os, subprocess, sys, time
from pathlib import Path
code = 'import time; from pathlib import Path; p=Path('+repr(os.environ['HEARTBEAT'])+'); [(p.write_text(str(i)), time.sleep(0.02)) for i in range(2000)]'
subprocess.Popen([sys.executable, '-c', code])
time.sleep(30)
''')
        self.env['HEARTBEAT'] = str(heartbeat)
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'manual', '--pair', str(self.pair), '--role', 'codex'],
            cwd=self.work, env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic()+3
            while not heartbeat.exists() and time.monotonic()<deadline:
                time.sleep(0.01)
            self.assertTrue(heartbeat.exists())
            process.terminate()
            process.communicate(timeout=3)
            value = heartbeat.read_text()
            time.sleep(0.15)
            self.assertEqual(heartbeat.read_text(), value, 'Manual provider descendant survived cleanup')
            self.assertEqual(self.record()['status'], 'held')
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=3)

    def test_manual_tui_receives_input_and_restores_foreground_terminal(self):
        self.initialize()
        self.assertEqual(self.send().returncode, 0)
        fake = self.root/'claude'
        fake.write_text('''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
a=sys.argv[1:]; session=a[a.index('--resume')+1]
print('MANUAL_READY', flush=True)
message=input()
path=Path(os.environ['CLAUDE_CONFIG_DIR'])/'projects'/'test-project'/(session+'.jsonl')
with path.open('a') as f:
    f.write(json.dumps({'type':'user','sessionId':session,'message':{'content':message}})+'\\n')
print('MANUAL_DONE', flush=True)
''')
        child, descriptor = pty.fork()
        if child == 0:
            os.chdir(self.work)
            os.environ.clear()
            os.environ.update(self.env)
            program = ('import os, subprocess, sys; initial=os.tcgetpgrp(0); '
                'r=subprocess.run([sys.executable, '+repr(str(SCRIPT))+', "manual", "--pair", '+
                repr(str(self.pair))+', "--role", "claude"]); '
                'print("FOREGROUND_RESTORED", os.tcgetpgrp(0)==initial, flush=True); sys.exit(r.returncode)')
            os.execl(sys.executable, sys.executable, '-c', program)
        output = b''
        status = None
        read_descriptors = [descriptor]
        try:
            deadline = time.monotonic()+5
            wrote = False
            while time.monotonic() < deadline:
                if select.select(read_descriptors, [], [], 0.05)[0]:
                    try:
                        chunk = os.read(descriptor, 4096)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        chunk = b''  # Linux PTY EOF; still poll/reap the child.
                    output += chunk
                    if not chunk:
                        read_descriptors = []
                if b'MANUAL_READY' in output and not wrote:
                    self.assertNotEqual(self.send().returncode, 0)
                    os.write(descriptor, b'Keep the existing URL.\n')
                    wrote = True
                finished, status = os.waitpid(child, os.WNOHANG)
                if finished:
                    break
                status = None
            self.assertIsNotNone(status, output.decode(errors='replace'))
            self.assertEqual(os.waitstatus_to_exitcode(status), 0, output.decode(errors='replace'))
            self.assertIn(b'FOREGROUND_RESTORED True', output)
            self.assertEqual(self.record()['status'], 'ready')
            self.assertNotEqual(self.send().returncode, 0)
        finally:
            os.close(descriptor)
            if status is None:
                try:
                    os.kill(child, signal.SIGKILL)
                    os.waitpid(child, 0)
                except ProcessLookupError:
                    pass

    def test_successful_manual_exit_also_stops_managed_descendants(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        heartbeat = self.root/'success-child-heartbeat'
        child_id = self.root/'success-child-pid'
        fake = self.root/'codex'
        fake.write_text('''#!/usr/bin/env python3
import os, subprocess, sys, time
from pathlib import Path
code='import time; from pathlib import Path; p=Path('+repr(os.environ['HEARTBEAT'])+'); [(p.write_text(str(i)), time.sleep(0.02)) for i in range(2000)]'
child=subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
Path(os.environ['CHILD_ID']).write_text(str(child.pid))
while not Path(os.environ['HEARTBEAT']).exists(): time.sleep(0.01)
''')
        self.env.update(HEARTBEAT=str(heartbeat), CHILD_ID=str(child_id))
        try:
            result = self.command('manual', '--pair', str(self.pair), '--role', 'codex')
            self.assertEqual(result.returncode, 0, result.stderr)
            value = heartbeat.read_text()
            time.sleep(0.15)
            self.assertEqual(heartbeat.read_text(), value, 'Managed child kept working after ready')
            self.assertEqual(self.record()['status'], 'ready')
        finally:
            if child_id.exists():
                try:
                    os.kill(int(child_id.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_manual_cleanup_failure_is_held_even_when_cleanup_retry_fails(self):
        self.initialize_reverse()
        self.assertEqual(self.send_reverse().returncode, 0)
        (self.root/'codex').write_text('#!/usr/bin/env python3\n')
        injection = self.root/'denied-cleanup'
        injection.mkdir()
        (injection/'sitecustomize.py').write_text(
            'import os\n'
            'def denied(group, signum):\n'
            '    raise PermissionError("synthetic cleanup denial")\n'
            'os.killpg = denied\n')
        self.env['PYTHONPATH'] = str(injection)
        result = self.command('manual', '--pair', str(self.pair), '--role', 'codex')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record()['status'], 'held',
                         'A failed cleanup left the pair marked as manual instead of held')

    def test_successful_dispatch_also_stops_managed_descendants(self):
        self.initialize_reverse()
        heartbeat = self.root/'dispatch-child-heartbeat'
        child_id = self.root/'dispatch-child-pid'
        self.env.update(CODEX_SUCCESS_CHILD=str(heartbeat), CHILD_ID=str(child_id))
        try:
            result = self.send_reverse()
            self.assertEqual(result.returncode, 0, result.stderr)
            value = heartbeat.read_text()
            time.sleep(0.15)
            self.assertEqual(heartbeat.read_text(), value, 'Managed child kept working after returned result')
        finally:
            if child_id.exists():
                try:
                    os.kill(int(child_id.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == '__main__':
    unittest.main()
