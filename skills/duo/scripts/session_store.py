"""One shared discovery index. Native transcripts and canonical pairs stay in place."""
from contextlib import contextmanager
import fcntl
import json
import os
import re
from pathlib import Path

from native_history import config_home
import uuid


def state_dir():
    return Path(os.environ.get('DUO_STATE_DIR') or Path.home()/'.local/state/duo').expanduser().resolve()


def write_json(path, data):
    temporary = path.with_name(path.name+'.'+str(uuid.uuid4())+'.tmp')
    try:
        with temporary.open('x') as file:
            os.chmod(temporary, 0o600)
            json.dump(data, file, indent=2)
            file.write('\n')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def index():
    root = state_dir()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root/'tasks.json'
    with (root/'tasks.lock').open('a') as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield read_index()


def read_index():
    path = state_dir()/'tasks.json'
    data = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError('Invalid task index; inspect it without replacing records.')
    return data


def is_versioned_model(model):
    return (isinstance(model, str) and bool(re.fullmatch(r'[A-Za-z0-9./_-]+', model))
            and any(c.isdigit() for c in model) and 'latest' not in model.lower())


def new_pair(owner, thread, task, workdir, model, owner_model=None):
    if not Path(workdir).is_dir() or not is_versioned_model(model) or (owner == 'codex' and 'opus' not in model.lower()):
        raise ValueError('A real workdir and explicit versioned peer model are required (Opus for a Codex owner).')
    if owner_model and not is_versioned_model(owner_model):
        raise ValueError('Supply an explicit versioned owner model, or leave it unknown.')
    return {'pair_id': str(uuid.uuid4()), 'owner': owner, 'owner_thread': thread,
            'owner_model': owner_model, 'owner_config_dir': config_home(owner),
            'task': task, 'workdir': str(Path(workdir).resolve()),
            'peer_tool': 'claude' if owner == 'codex' else 'codex', 'peer_model': model,
            'effort': 'xhigh', 'peer_session_id': str(uuid.uuid4()) if owner == 'codex' else None,
            'started': False, 'status': 'ready', 'claude_config_dir': config_home('claude'),
            'codex_config_dir': config_home('codex')}


def entry(record, path):
    result = {key: record[key] for key in ('task_id', 'task', 'workdir')} | {'pair_path': str(path)}
    if record.get('moved_from'):
        result['moved_from'] = record['moved_from']
    return result


def register(record, path):
    task_relocation_guard(record)
    record.setdefault('task_id', record['pair_id'])
    record.setdefault('pair_path', str(path))
    if record['pair_path'] != str(path):
        raise ValueError('Use the canonical pair path; a copied pair cannot dispatch.')
    with index() as data:
        existing = data.get(record['task_id'])
        wanted = entry(record, path)
        if existing and existing != wanted:
            raise ValueError('Task identity already points to another canonical record.')
        if existing != wanted:
            data[record['task_id']] = wanted
            write_json(state_dir()/'tasks.json', data)


def guard_relocation(state):
    marker = state.with_suffix('.relocation.json')
    if marker.exists():
        status = json.loads(marker.read_text()).get('status')
        if status not in ('committed', 'rolled_back'):
            raise ValueError('Pending relocation; inspect the journal and run relocate.py rollback before continuing.')


def task_relocation_guard(record):
    if 'task_id' in record:
        guard_relocation(state_dir()/'workspaces'/record['task_id']/'workspace.json')


def validate(record, path):
    task_relocation_guard(record)
    if 'task_id' not in record or record.get('pair_path') != str(path):
        raise ValueError('Use the canonical pair; adopt an unindexed legacy record in place first.')
    if read_index().get(record['task_id']) != entry(record, path):
        raise ValueError('Task index and canonical record disagree; adopt the original in the correct shared index.')


def create(record, path, *, new_task=False, task_id=None):
    """Serialize discovery and creation even when callers choose different paths."""
    with index() as data:
        if task_id:
            if task_id not in data:
                raise ValueError('Unknown task identity; list tasks before continuing.')
            matches = [data[task_id]]
        elif new_task:
            matches = []
        else:
            matches = [item for item in data.values()
                       if item['workdir'] == record['workdir']
                       and item['task'].casefold() == record['task'].casefold()]
        if not matches and not new_task and not task_id:
            relocated = [item for item in data.values()
                         if item['task'].casefold() == record['task'].casefold()
                         and record['workdir'] in item.get('moved_from', [])]
            if relocated:
                raise ValueError('This task relocated to another checkout; list it and continue the exact --task-id.')
        if len(matches) > 1:
            raise ValueError('Ambiguous existing tasks; list and select an exact --task-id.')
        if matches:
            canonical = Path(matches[0]['pair_path'])
            existing = json.loads(canonical.read_text())
            task_relocation_guard(existing)
            if entry(existing, canonical) != matches[0] or existing.get('pair_path') != str(canonical):
                raise ValueError('Task index and canonical record disagree; inspect before continuing.')
            if existing['workdir'] != record['workdir'] or existing['task'].casefold() != record['task'].casefold():
                raise ValueError('Task identity/workdir mismatch; inspect the existing task.')
            if existing['owner'] != record['owner'] or existing['owner_thread'] != record['owner_thread']:
                raise ValueError(f'Existing task {existing["task_id"]} at {canonical}; resume or explicitly handoff.')
            if existing['peer_model'] != record['peer_model']:
                raise ValueError('Retain the selected peer model for the existing task.')
            return existing
        if path.exists():
            raise ValueError('Pair path already exists; adopt the original record instead of replacing it.')
        record.update(task_id=record['pair_id'], pair_path=str(path))
        # Record the index first. A crash leaves a visible missing record, never an unnoticed duplicate.
        data[record['task_id']] = entry(record, path)
        write_json(state_dir()/'tasks.json', data)
        with path.open('x') as file:
            os.chmod(path, 0o600)
            json.dump(record, file, indent=2)
            file.write('\n')
        return record


def listing(task='', workdir=None):
    data = read_index()
    matches = [item for item in data.values() if task.casefold() in item['task'].casefold()
                   and (workdir is None or item['workdir'] == str(workdir.resolve()))]
    result = []
    for item in matches:
        path = Path(item['pair_path'])
        if not path.exists():
            result.append(item | {'status': 'missing_record'})
            continue
        try:
            task_relocation_guard(item)
        except ValueError as error:
            result.append(item | {'status': 'relocation_pending', 'error': str(error)})
            continue
        record = json.loads(path.read_text())
        if entry(record, path) != item or record.get('pair_path') != str(path):
            # Report it like a missing record; one stale entry must not hide every other task.
            result.append(item | {'status': 'index_mismatch'})
            continue
        result.append(record)
    return result
