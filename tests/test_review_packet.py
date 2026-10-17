"""Frozen input reuse, source drift, and the actual paired dispatch path."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

from _support import DUO_SCRIPTS
import review_packet
import test_workspaces
import test_pair as fixtures

PACKET = DUO_SCRIPTS / 'review_packet.py'
WORKSPACE = DUO_SCRIPTS / 'workspace.py'


class Packets(unittest.TestCase):
    setUp = test_workspaces.Workspaces.setUp
    call = test_workspaces.Workspaces.call
    run_job = test_workspaces.Workspaces.run_job
    def packet(self, *files, expected=0):
        args=[sys.executable,str(PACKET),'make','--state',str(self.state)]
        for name in files: args += ['--file',name]
        p=subprocess.run(args,capture_output=True,text=True,timeout=4)
        self.assertEqual(p.returncode,expected,p.stdout+p.stderr)
        return json.loads(p.stdout) if expected==0 else p

    def test_same_bytes_reuse_packet_and_mutation_invalidates_evidence(self):
        (self.source/'source.py').write_text('print("one")')
        first=self.packet('source.py')
        m=Path(first['manifest']); before=m.stat()
        second=self.packet('source.py')
        self.assertEqual(first['packet_id'],second['packet_id'])
        self.assertEqual(before.st_mtime_ns,m.stat().st_mtime_ns)
        (self.source/'source.py').write_text('print("two")')
        result=subprocess.run([sys.executable,str(PACKET),'check','--manifest',str(m)],capture_output=True,text=True)
        self.assertEqual(result.returncode,3,result.stderr)
        self.assertEqual(json.loads(result.stdout)['changed_files'],['source.py'])
        self.assertNotEqual(self.packet('source.py')['packet_id'],first['packet_id'])

    def test_unchanged_packet_reuses_existing_storage_when_budget_is_nearly_full(self):
        (self.source/'large').write_bytes(b'x' * (3 * 1024 * 1024))
        first = self.packet('large')
        second = self.packet('large')
        self.assertEqual(first['packet_id'], second['packet_id'])

    def test_packet_rejects_cache_traversal_and_symlinks(self):
        (self.source/'node_modules').mkdir()
        (self.source/'node_modules'/'dep').write_text('cache')
        (self.root/'outside').write_text('private')
        (self.source/'link').symlink_to(self.root/'outside')
        os.mkfifo(self.source / 'fifo')
        for name in ['node_modules/dep','../outside','link','fifo']:
            self.packet(name,expected=2)

    def capture_during_swap(self, name, swapped_component, swap, *, after_open=False):
        selected = self.source / name
        original_open, original_stat = os.open, os.stat
        swapped = False
        def maybe_swap(path):
            nonlocal swapped
            # Old capture stats the full filename; safe traversal opens one component.
            if not swapped and path in (selected, str(selected), swapped_component):
                swap()
                swapped = True
        def racing_open(path, *args, **kwargs):
            if after_open:
                descriptor = original_open(path, *args, **kwargs)
                maybe_swap(path)
                return descriptor
            maybe_swap(path)
            return original_open(path, *args, **kwargs)
        def racing_stat(path, *args, **kwargs):
            maybe_swap(path)
            return original_stat(path, *args, **kwargs)
        captured = None
        with patch.object(os, 'open', racing_open), patch.object(os, 'stat', racing_stat):
            try:
                captured = review_packet.regular_file(self.source, name)
            except (OSError, ValueError):
                pass
        self.assertTrue(swapped, 'The source swap must occur at the capture boundary')
        return captured

    def test_capture_rejects_a_leaf_swapped_to_an_outside_symlink(self):
        selected = self.source / 'selected.txt'
        selected.write_text('selected source')
        outside = self.root / 'outside-canary'
        outside.write_text('SYNTHETIC_OUTSIDE_CANARY')
        def swap():
            selected.unlink()
            selected.symlink_to(outside)
        self.assertIsNone(self.capture_during_swap('selected.txt', 'selected.txt', swap))

    def test_capture_rejects_an_intermediate_directory_swapped_to_an_outside_symlink(self):
        directory = self.source / 'nested'
        directory.mkdir()
        (directory / 'selected.txt').write_text('selected source')
        outside = self.root / 'outside-canary-directory'
        outside.mkdir()
        (outside / 'selected.txt').write_text('SYNTHETIC_OUTSIDE_CANARY')
        def swap():
            directory.rename(self.source / 'original-nested')
            directory.symlink_to(outside, target_is_directory=True)
        self.assertIsNone(self.capture_during_swap('nested/selected.txt', 'nested', swap))

    def test_capture_keeps_the_open_directory_when_its_path_is_replaced(self):
        directory = self.source / 'nested'
        directory.mkdir()
        (directory / 'selected.txt').write_text('selected source')
        outside = self.root / 'outside-canary-directory'
        outside.mkdir()
        (outside / 'selected.txt').write_text('SYNTHETIC_OUTSIDE_CANARY')
        def swap():
            directory.rename(self.source / 'original-nested')
            directory.symlink_to(outside, target_is_directory=True)
        captured = self.capture_during_swap('nested/selected.txt', 'nested', swap, after_open=True)
        self.assertIn(captured, (None, (b'selected source', False)))

    def test_capture_bounds_reads_when_a_file_grows_after_its_descriptor_stat(self):
        selected = self.source / 'growing.txt'
        selected.write_bytes(b'initial')
        original_fstat, original_fdopen = os.fstat, os.fdopen
        grown, reads = False, []
        def grow_after_stat(descriptor):
            nonlocal grown
            before = original_fstat(descriptor)
            if not grown:
                selected.write_bytes(b'x' * 2048)
                grown = True
            return before
        def track_reads(*args, **kwargs):
            stream = original_fdopen(*args, **kwargs)
            original_read = stream.read
            def read(size=-1):
                raw = original_read(size)
                reads.append(len(raw))
                return raw
            stream.read = read
            return stream
        with patch.object(review_packet, 'MAX_PACKET_BYTES', 32), \
                patch.object(os, 'fstat', grow_after_stat), patch.object(os, 'fdopen', track_reads):
            with self.assertRaises(ValueError):
                review_packet.regular_file(self.source, 'growing.txt')
        self.assertTrue(grown)
        self.assertTrue(reads, 'The file must grow before an actual read')
        self.assertLessEqual(max(reads), 33, 'A changed file must not cause an unbounded read')

    def test_packet_tampering_is_detected(self):
        (self.source/'source').write_text('original')
        m=Path(self.packet('source')['manifest'])
        copy=m.parent/'source'/'source';copy.chmod(0o600);copy.write_text('tampered')
        result=subprocess.run([sys.executable,str(PACKET),'check','--manifest',str(m)],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('modified',result.stderr)

    def test_source_edit_during_test_invalidates_the_successful_test_receipt(self):
        source = self.source/'source'; source.write_text('original')
        m = Path(self.packet('source')['manifest'])
        result = self.run_job('from pathlib import Path; Path('+repr(str(source))+').write_text("changed")',
                              '--packet', str(m), expected=3)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt['status'], 'stale_source')
        self.assertFalse(receipt['input_packet']['source_matches'])
        self.assertTrue(receipt['cleaned'])

    def test_test_command_uses_packet_without_changing_original(self):
        (self.source/'source').write_text('original')
        m=Path(self.packet('source')['manifest'])
        result=self.run_job('from pathlib import Path; assert Path("source").read_text()=="original"; Path("source").write_text("temporary")', '--packet',str(m))
        self.assertTrue(result['cleaned'])
        self.assertEqual((self.source/'source').read_text(),'original')


class PairedEvidence(unittest.TestCase):
    setUp=fixtures.PairRouting.setUp
    command=fixtures.PairRouting.command
    initialize=fixtures.PairRouting.initialize

    def make_packet(self):
        self.initialize()
        record=json.loads(self.pair.read_text())
        state=self.root/'duo-state'/'workspaces'/record['task_id']/'workspace.json'
        self.source=self.work/'code.py';self.source.write_text('print("original")')
        p=subprocess.run([sys.executable,str(PACKET),'make','--state',str(state),'--file','code.py'],
                         env=self.env,capture_output=True,text=True,timeout=4)
        self.assertEqual(p.returncode,0,p.stderr)
        return json.loads(p.stdout)['manifest'],record['task_id']

    def test_legacy_pair_gets_workspace_guard_on_dispatch(self):
        self.initialize()
        record=json.loads(self.pair.read_text())
        state=self.root/'duo-state'/'workspaces'/record['task_id']/'workspace.json'
        self.assertTrue(state.exists())
        self.work.rename(self.root/'old-work');self.work.mkdir()
        p=self.command('run','--pair',str(self.pair),'--thread','codex-A','--task-id',record['task_id'],
                       '--prompt',str(self.prompt),'--snapshot','test')
        self.assertNotEqual(p.returncode,0)
        self.assertIn('replaced',p.stderr)
        self.assertFalse((self.root/'calls.jsonl').exists())

    def test_changed_source_after_response_invalidates_review_without_losing_session(self):
        packet,task_id=self.make_packet()
        gate=self.root/'gate';self.env['GATE']=str(gate)
        p=subprocess.Popen([sys.executable,str(fixtures.SCRIPT),'run','--pair',str(self.pair),
            '--thread','codex-A','--task-id',task_id,'--prompt',str(self.prompt),'--snapshot','commit',
            '--packet',packet],cwd=self.work,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        self.addCleanup(lambda:p.poll() is None and p.kill())
        deadline=time.monotonic()+4
        while not Path(str(gate)+'.entered').exists() and time.monotonic()<deadline:time.sleep(.02)
        self.assertTrue(Path(str(gate)+'.entered').exists())
        self.source.write_text('print("changed during review")');gate.touch()
        stdout,stderr=p.communicate(timeout=5)
        self.assertEqual(p.returncode,3,stderr)
        self.assertFalse(json.loads(stdout)['review_evidence']['source_verified'])
        record=json.loads(self.pair.read_text())
        self.assertEqual(record['status'],'ready')
        self.assertTrue(record['started'])
        self.assertEqual(record['last_review_evidence']['changed_files'],['code.py'])

    def test_stale_packet_blocks_provider_launch(self):
        packet,task_id=self.make_packet();self.source.write_text('different')
        p=self.command('run','--pair',str(self.pair),'--thread','codex-A','--task-id',task_id,
                       '--prompt',str(self.prompt),'--snapshot','commit','--packet',packet)
        self.assertNotEqual(p.returncode,0)
        self.assertFalse((self.root/'calls.jsonl').exists())


if __name__=='__main__':unittest.main()
