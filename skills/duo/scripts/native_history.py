"""Read supported native JSONL shapes without modifying or copying native history."""
import hashlib
import json
import os
from pathlib import Path


def config_home(tool):
    variable = 'CLAUDE_CONFIG_DIR' if tool == 'claude' else 'CODEX_HOME'
    default = '.claude' if tool == 'claude' else '.codex'
    return str(Path(os.environ.get(variable) or Path.home()/default).expanduser().resolve())


def seat(record, role):
    if role == record['owner']:
        return {'session_id': record['owner_thread'], 'model': record.get('owner_model'),
                'config_home': record.get('owner_config_dir', config_home(role))}
    if role != record['peer_tool']:
        raise ValueError('Unknown seat for this pair.')
    return {'session_id': record['peer_session_id'], 'model': record['peer_model'],
            'config_home': record.get(role+'_config_dir', config_home(role))}


def snapshot(record, role, *, optional=False, through=None, previous=None):
    info = seat(record, role)
    session = info['session_id']
    if not session:
        if optional:
            return {'head': None, 'turns': [], 'path': None}
        raise ValueError('This conversation has not started; dispatch it first.')
    if not isinstance(session, str) or '/' in session or '\\' in session or any(c in session for c in '*?['):
        raise ValueError('Invalid native session identity.')
    if info['config_home'] != config_home(role):
        raise ValueError(f'{role} state directory changed; retain the recorded configuration home.')
    root = Path(info['config_home'])
    paths = list((root/'projects').glob('*/'+session+'.jsonl')) if role == 'claude' else [
        p for folder in ('sessions', 'archived_sessions')
        for p in (root/folder).rglob('*'+session+'.jsonl')]
    # Directory aliases may expose the same persisted transcript more than once.
    paths = list(dict.fromkeys(path.resolve() for path in paths))
    if not paths and optional:
        return {'head': None, 'turns': [], 'path': None}
    if len(paths) != 1:
        raise ValueError(f'Expected one persisted {role} transcript; missing or ambiguous native history.')
    raw = paths[0].read_bytes()
    if through:
        raw = raw[:through['size']]
        if len(raw) != through['size'] or hashlib.sha256(raw).hexdigest() != through['sha256']:
            raise ValueError('Managed manual history was rewritten; inspect before reconciliation.')
    if previous:
        prefix = raw[:previous['size']]
        if len(prefix) != previous['size'] or hashlib.sha256(prefix).hexdigest() != previous['sha256']:
            raise ValueError('Native history was rewritten; inspect it before reconciling.')
    turns = []
    offset = 0
    metadata = False
    for line in raw.splitlines(keepends=True):
        offset += len(line)
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError as error:
            raise ValueError(f'Malformed {"Claude" if role == "claude" else "Codex"} transcript; inspect before resume.') from error
        if not isinstance(item, dict):
            raise ValueError(f'Invalid {role} transcript row.')
        if role == 'claude':
            if item.get('type') not in ('user', 'assistant'):
                continue
            if item.get('sessionId') != session:
                raise ValueError('Claude transcript contains another session identity.')
            payload = item.get('message', {})
            author = item['type']
        else:
            payload = item.get('payload', {})
            if item.get('type') == 'session_meta':
                if not isinstance(payload, dict) or payload.get('id', payload.get('session_id')) != session:
                    raise ValueError('Codex transcript session identity mismatch.')
                metadata = True
            if item.get('type') != 'response_item' or not isinstance(payload, dict) or payload.get('type') != 'message':
                continue
            author = payload.get('role')
            if author not in ('user', 'assistant'):
                continue
        if not isinstance(payload, dict):
            raise ValueError('Invalid native message.')
        content = payload.get('content', [])
        attachments = []
        if isinstance(content, str):
            message = content
        elif isinstance(content, list):
            if not all(isinstance(block, dict) for block in content):
                raise ValueError('Unsupported native message content blocks.')
            message = ''.join(block.get('text', '') for block in content if isinstance(block, dict)
                              and block.get('type') in ('text', 'input_text', 'output_text')
                              and isinstance(block.get('text'), str))
            hidden = ('text', 'input_text', 'output_text', 'tool_use', 'tool_result', 'thinking', 'redacted_thinking')
            attachments = [{'type': block.get('type', 'unknown')} for block in content
                           if block.get('type') not in hidden]
        else:
            raise ValueError('Unsupported native message content.')
        if message or attachments:
            turn = {'role': author, 'text': message, 'offset': offset}
            if role == 'claude' and item.get('uuid'):
                turn['uuid'] = item['uuid']
            if attachments:
                turn['attachments'] = attachments
            turns.append(turn)
    if role == 'codex' and not metadata:
        raise ValueError('Missing native Codex session metadata.')
    return {'head': {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()},
            'turns': turns, 'path': str(paths[0])}


def changes(record, role, previous, *, optional=False, through=None):
    current = snapshot(record, role, optional=optional, through=through, previous=previous)
    if previous and current['path'] is None:
        raise ValueError('Previously read native history is missing.')
    current['turns'] = [turn for turn in current['turns']
                        if turn['offset'] > (previous['size'] if previous else 0)]
    return current


def delta(record):
    return changes(record, record['peer_tool'], record.get('read_head'), optional=not record['started'])


def owner_manual_changes(record):
    if 'owner_manual_head' not in record:
        return {'head': None, 'turns': [], 'path': None}
    return changes(record, record['owner'], record['owner_manual_head'], through=record.get('owner_manual_end'))
