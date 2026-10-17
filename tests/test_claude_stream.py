"""Claude's transport events are evidence of progress, not a completed review."""
import json
import unittest

import _support
import pair


class ClaudeStream(unittest.TestCase):
    record = {'peer_session_id': 'exact-session', 'peer_model': 'claude-opus-5-5'}
    initial = {'type': 'system', 'subtype': 'init', 'session_id': 'exact-session',
               'model': 'claude-opus-5-5', 'tools': ['Read', 'Grep', 'Glob'],
               'mcp_servers': [], 'permissionMode': 'auto'}

    def test_completed_stream_returns_only_the_final_result(self):
        raw = '\n'.join(json.dumps(e) for e in [
            self.initial,
            {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Partial'}]}},
            {'type': 'result', 'subtype': 'success', 'is_error': False,
             'session_id': 'exact-session', 'result': 'Final findings'},
        ])
        result = pair.claude_result(raw, self.record)
        self.assertEqual(result['result'], 'Final findings')
        self.assertEqual(result['session_id'], 'exact-session')

    def test_progress_without_completion_is_rejected(self):
        for event in ({'type': 'system', 'subtype': 'init'},
                      {'type': 'assistant', 'message': {'content': []}}):
            with self.subTest(event=event), self.assertRaises(ValueError):
                pair.claude_result(json.dumps(event), self.record)

    def test_duplicate_or_truncated_completion_is_rejected(self):
        event = json.dumps({'type': 'result', 'is_error': False, 'result': 'One answer'})
        for raw in (event+'\n'+event, event+'\n{"type":', '{"type":"error"}\n'+event):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                pair.claude_result(raw, self.record)

    def test_completion_without_runtime_is_rejected(self):
        raw = '{"session_id":"exact-session","is_error":false,"result":"Saved result"}'
        with self.assertRaises(ValueError):
            pair.claude_result(raw, self.record)
