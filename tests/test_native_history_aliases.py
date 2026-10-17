import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import _support
from native_history import snapshot


class NativeHistoryAliases(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.projects = self.root / 'projects'
        self.actual = self.projects / 'actual'
        self.actual.mkdir(parents=True)
        self.env = patch.dict(os.environ, {'CLAUDE_CONFIG_DIR': str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.session = '7568b164-1782-4b98-9546-d636e0591e4f'
        self.path = self.actual / (self.session + '.jsonl')
        self.row = {'type': 'assistant', 'sessionId': self.session, 'uuid': 'answer-1',
                    'message': {'content': [{'type': 'text', 'text': 'review complete'}]}}
        self.path.write_text(json.dumps(self.row) + '\n')
        self.record = {'owner': 'codex', 'peer_tool': 'claude',
                       'peer_session_id': self.session, 'peer_model': 'claude-opus-5-5',
                       'claude_config_dir': str(self.root)}

    def test_two_directory_aliases_read_one_actual_transcript(self):
        (self.projects / 'alias').symlink_to(self.actual, target_is_directory=True)
        result = snapshot(self.record, 'claude')
        self.assertEqual([turn['text'] for turn in result['turns']], ['review complete'])
        self.assertEqual(Path(result['path']).resolve(), self.path.resolve())

    def test_distinct_files_with_same_session_and_bytes_remain_ambiguous(self):
        other = self.projects / 'other'
        other.mkdir()
        (other / self.path.name).write_bytes(self.path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
            snapshot(self.record, 'claude')

    def test_wrong_session_identity_remains_rejected(self):
        self.row['sessionId'] = 'another-session'
        self.path.write_text(json.dumps(self.row) + '\n')
        with self.assertRaisesRegex(ValueError, 'another session identity'):
            snapshot(self.record, 'claude')

    def test_rewritten_history_remains_rejected_through_an_alias(self):
        previous = snapshot(self.record, 'claude')['head']
        (self.projects / 'alias').symlink_to(self.actual, target_is_directory=True)
        self.row['message']['content'][0]['text'] = 'changed answer'
        self.path.write_text(json.dumps(self.row) + '\n')
        with self.assertRaisesRegex(ValueError, 'history was rewritten'):
            snapshot(self.record, 'claude', previous=previous)

    def test_missing_required_history_remains_rejected(self):
        self.path.unlink()
        with self.assertRaisesRegex(ValueError, 'missing or ambiguous'):
            snapshot(self.record, 'claude')


if __name__ == '__main__':
    unittest.main()
