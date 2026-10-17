#!/usr/bin/env python3
"""Explicit, journaled Duo checkout rebinding. Never move source or native history."""
import argparse
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import uuid

from native_history import snapshot
from session_commands import pair_lock
import session_store as store
import workspace


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def durable_write(path, data):
    """Persist each journal/state replacement before the next transaction step."""
    path = Path(path)
    temporary = path.with_name(path.name+'.'+str(uuid.uuid4())+'.tmp')
    try:
        with temporary.open('x') as file:
            os.chmod(temporary, 0o600)
            json.dump(data, file, indent=2); file.write('\n'); file.flush(); os.fsync(file.fileno())
        temporary.replace(path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def marker_path(state):
    return state.with_suffix('.relocation.json')


def git(path, *args):
    result = subprocess.run(['git', '-C', str(path), *args], capture_output=True,
                            env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'), timeout=120)
    if result.returncode:
        raise ValueError('Git source verification failed: '+result.stderr.decode(errors='replace')[:1000])
    return result.stdout


def canonical(path):
    path = Path(os.path.abspath(Path(path).expanduser()))
    if path.resolve() != path or path.is_symlink():
        raise ValueError('Use an actual canonical path, not a directory alias.')
    return path


def source(path):
    physical = workspace.identity(path)
    if Path(os.fsdecode(git(path, 'rev-parse', '--show-toplevel')).strip()).resolve() != path:
        raise ValueError('Relocation currently requires a Git checkout root.')
    if git(path, 'status', '--porcelain=v1', '--untracked-files=all'):
        raise ValueError('Source and destination must be clean; preserve unique changes first.')
    entries, submodules = [], {}
    for line in git(path, 'ls-files', '--stage', '-z').split(b'\0'):
        if not line: continue
        info, name = line.split(b'\t', 1)
        mode, oid, stage = info.decode().split()
        if stage != '0' or mode not in ('100644', '100755', '120000', '160000'):
            raise ValueError('Resolve unmerged files before relocation.')
        relative = Path(os.fsdecode(name)); file = path/relative
        if file.parent.resolve() != file.parent:
            raise ValueError('Tracked source traverses a symlink.')
        if mode == '160000':
            entries.append([os.fsdecode(name), mode, oid])
            if file.is_symlink(): raise ValueError('Submodule directory must not be an alias.')
            if not file.exists() or not any(file.iterdir()):
                submodules[os.fsdecode(name)] = {'initialized': False, 'commit': oid}
            else:
                nested = source(file)
                if nested['head'] != oid:
                    raise ValueError('Submodule must be clean at its recorded Git commit.')
                submodules[os.fsdecode(name)] = {'initialized': True, 'commit': oid, 'source': nested}
            continue
        kind = file.lstat().st_mode
        if mode == '120000' and stat.S_ISLNK(kind):
            raw = os.fsencode(os.readlink(file))
        elif mode != '120000' and stat.S_ISREG(kind):
            raw = file.read_bytes()
        else:
            raise ValueError('Tracked source file type changed.')
        entries.append([os.fsdecode(name), mode, hashlib.sha256(raw).hexdigest()])
    common = Path(os.fsdecode(git(path, 'rev-parse', '--git-common-dir')).strip())
    if not common.is_absolute(): common = path/common
    return {'path': str(path), 'identity': physical, 'common_dir': str(common.resolve()),
            'head': git(path, 'rev-parse', 'HEAD').decode().strip(),
            'tree': git(path, 'rev-parse', 'HEAD^{tree}').decode().strip(),
            'files_sha256': digest(entries), 'submodules': submodules}


def recovered(bundle, commit, target):
    bundle = canonical(bundle)
    if not bundle.is_file() or bundle.is_symlink() or len(commit) not in (40, 64) or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Missing source requires an exact commit and standalone bundle.')
    raw_hash = hashlib.sha256(bundle.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix='duo-bundle-check-') as temporary:
        root = Path(temporary)
        git(root, 'init', '--bare', '-q')
        git(root, 'bundle', 'verify', str(bundle))  # Empty repository rejects prerequisites.
        refs = [line.split(' ', 1) for line in git(root, 'bundle', 'list-heads', str(bundle)).decode().splitlines()]
        names = [name for sha, name in refs if sha == commit]
        if not names:
            raise ValueError('Recovery commit is not an advertised exact bundle ref.')
        git(root, 'fetch', '--no-tags', '--no-write-fetch-head', str(bundle), names[0]+':refs/duo/recovery')
        tree = git(root, 'rev-parse', commit+'^{tree}').decode().strip()
        if tree != target['tree']:
            raise ValueError('Recovery source tree differs from destination tree.')
    if hashlib.sha256(bundle.read_bytes()).hexdigest() != raw_hash:
        raise ValueError('Recovery bundle changed while being verified.')
    return {'mode': 'recovered-commit', 'bundle': str(bundle), 'bundle_sha256': raw_hash,
            'commit': commit, 'tree': tree,
            'limitation': 'Committed source only. This does not prove lost dirty/ignored files were preserved.'}


@contextmanager
def locked_pair(path, task):
    path = canonical(path)
    with pair_lock(path):
        record = json.loads(path.read_text())
        if record.get('task_id') != task or record.get('pair_path') != str(path):
            raise ValueError('Task identity or canonical pair path changed.')
        state = workspace.pair_workspace(record)
        if not state.exists():
            raise ValueError('Existing workspace binding required; adopt/bind before planning a move.')
        with workspace.locked(state), store.index() as index:
            yield path, record, state, index


def inspect(path, record, state, index, owner, thread, target, reason, idle,
            source_commit=None, source_bundle=None):
    store.validate(record, path)
    if record['owner'] != owner or record['owner_thread'] != thread:
        raise ValueError('Owner changed; use the actual current owner and native thread.')
    if record['status'] != 'ready' or 'owner_manual_head' in record:
        raise ValueError('Pair must be ready with managed manual use reconciled.')
    if not idle or not reason.strip():
        raise ValueError('Confirm both native seats are idle for relocation and supply a reason.')
    data = workspace.load(state)
    workspace.storage_root(state, data)
    if workspace.active_runs(data):
        raise ValueError('Outstanding disposable run; close or recover it first.')
    old = canonical(record['workdir']); target = canonical(target)
    if old == target or data['workdir'] != str(old):
        raise ValueError('Destination must differ and pair/workspace must agree.')
    for retained in (path, state, store.state_dir()):
        if retained == old or old in retained.parents or retained == target or target in retained.parents:
            raise ValueError('Pair/index/workspace evidence must remain outside both checkouts.')
    destination = source(target)
    if old.exists():
        original = source(old)
        if original['common_dir'] != destination['common_dir']:
            raise ValueError('Existing source and destination must share one Git repository.')
        if (original['tree'], original['files_sha256']) != (destination['tree'], destination['files_sha256']):
            raise ValueError('Source and destination tree/content differ; integrate explicitly first.')
        if source_commit or source_bundle:
            if not source_commit or not source_bundle or original['identity'] == data['source_identity']:
                raise ValueError('Recovery flags require a missing/reconstructed binding and exact bundle evidence.')
            if original['head'] != source_commit:
                raise ValueError('Reconstructed source must match the exact recovery commit.')
            proof = recovered(source_bundle, source_commit, destination)
            proof['reconstructed_source'] = original
        else:
            workspace.validate_source(data)
            proof = {'mode': 'existing-clean', 'source': original}
    else:
        if not source_commit or not source_bundle:
            raise ValueError('Missing source requires an exact source commit and verified standalone bundle.')
        proof = recovered(source_bundle, source_commit, destination)
    peer = snapshot(record, record['peer_tool'], optional=not record['started'], previous=record.get('read_head'))
    if not record['started'] and peer['path']:
        raise ValueError('Unstarted pair has native history; inspect interrupted call first.')
    # An owner's ongoing tool log may grow; do not freeze it or alter either cursor.
    return {'version': 1, 'pair_path': str(path), 'task_id': record['task_id'],
            'owner': owner, 'thread': thread, 'target': destination, 'proof': proof,
            'reason': reason, 'native_idle_confirmed': idle,
            'before': {'pair': record, 'workspace': data, 'index_entry': index[record['task_id']]},
            'peer_history': {'path': peer['path'], 'head': peer['head']}}


def plan(path, task, owner, thread, target, reason, idle, source_commit=None, source_bundle=None):
    with locked_pair(path, task) as (path, record, state, index):
        return inspect(path, record, state, index, owner, thread, target, reason, idle, source_commit, source_bundle)


def apply(proposal, expected):
    if digest(proposal) != expected:
        raise ValueError('Plan digest mismatch; inspect the original plan.')
    path = Path(proposal['pair_path']); task = proposal['task_id']
    with locked_pair(path, task) as (path, record, state, index):
        proof = proposal['proof']
        current = inspect(path, record, state, index, proposal['owner'], proposal['thread'],
            Path(proposal['target']['path']), proposal['reason'], proposal['native_idle_confirmed'],
            proof.get('commit'), proof.get('bundle'))
        if current != proposal:
            raise ValueError('Relocation plan changed; inspect and plan again.')
        updated = copy.deepcopy(record); updated['workdir'] = proposal['target']['path']
        previous_paths = updated.setdefault('moved_from', [])
        if record['workdir'] not in previous_paths:
            previous_paths.append(record['workdir'])
        new_state = copy.deepcopy(proposal['before']['workspace'])
        new_state.update(workdir=updated['workdir'], source_identity=proposal['target']['identity'])
        transaction = {'id': str(uuid.uuid4()), 'status': 'pending', 'plan_sha256': expected,
                       'plan': proposal, 'after': {'pair': updated, 'workspace': new_state,
                                                  'index_entry': store.entry(updated, path)}}
        journal_dir = workspace.storage_root(state, new_state)/'relocations'
        journal_dir.mkdir(mode=0o700, exist_ok=True)
        if journal_dir.is_symlink(): raise ValueError('Relocation journal directory must not be an alias.')
        journal = journal_dir/(transaction['id']+'.json')
        transaction['journal'] = str(journal)
        durable_write(journal, transaction)
        # Barrier remains pending through every write, including any interrupted recovery.
        durable_write(marker_path(state), {'id': transaction['id'], 'status': 'pending', 'journal': str(journal)})
        durable_write(state, new_state)
        durable_write(path, updated)
        index[task] = transaction['after']['index_entry']
        durable_write(store.state_dir()/'tasks.json', index)
        if source(Path(updated['workdir'])) != proposal['target']:
            raise ValueError('Destination changed during relocation; pending journal retained.')
        prior_source = proof.get('source', proof.get('reconstructed_source'))
        if prior_source and source(Path(record['workdir'])) != prior_source:
            raise ValueError('Source changed during relocation; pending journal retained.')
        if not prior_source and Path(record['workdir']).exists():
            raise ValueError('Previously missing source appeared during relocation; pending journal retained.')
        native = snapshot(record, record['peer_tool'], optional=not record['started'], previous=record.get('read_head'))
        if {'path': native['path'], 'head': native['head']} != proposal['peer_history']:
            raise ValueError('Native peer history changed during relocation; pending journal retained.')
        transaction['status'] = 'committed'; durable_write(journal, transaction)
        durable_write(marker_path(state), {'id': transaction['id'], 'status': 'committed', 'journal': str(journal)})
        return {'status': 'committed', 'journal': str(journal), 'task_id': task,
                'workdir': updated['workdir'], 'peer_session_id': updated['peer_session_id'],
                'native_resume': 'not exercised; original native transcript retained'}


def rollback(path, task, owner, thread, transaction_id):
    with locked_pair(path, task) as (path, record, state, index):
        marker = json.loads(marker_path(state).read_text())
        if marker['id'] != transaction_id or marker['status'] != 'pending':
            raise ValueError('Only the exact pending relocation can be rolled back.')
        journal = workspace.root_for(state)/'relocations'/(transaction_id+'.json')
        if str(journal) != marker['journal'] or journal.resolve() != journal:
            raise ValueError('Relocation journal path changed.')
        transaction = json.loads(journal.read_text()); proposal = transaction['plan']
        if (transaction['id'] != transaction_id or proposal['pair_path'] != str(path)
            or proposal['task_id'] != task or proposal['owner'] != owner or proposal['thread'] != thread
            or digest(proposal) != transaction['plan_sha256']):
            raise ValueError('Relocation journal identity or owner changed.')
        before, after = proposal['before'], transaction['after']
        actual = {'pair': record, 'workspace': json.loads(state.read_text()), 'index_entry': index.get(task)}
        if any(actual[key] not in (before[key], after[key]) for key in actual):
            raise ValueError('State changed outside this relocation; preserve it and inspect before recovery.')
        workspace.storage_root(state, before['workspace'])
        durable_write(state, before['workspace'])
        durable_write(path, before['pair'])
        index[task] = before['index_entry']
        durable_write(store.state_dir()/'tasks.json', index)
        transaction['status'] = 'rolled_back'; durable_write(journal, transaction)
        durable_write(marker_path(state), {'id': transaction_id, 'status': 'rolled_back', 'journal': str(journal)})
        return {'status': 'rolled_back', 'journal': str(journal)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    planned = commands.add_parser('plan', help='Write a private plan; do not change bindings.')
    applied = commands.add_parser('apply', help='Revalidate and apply an exact frozen plan.')
    recovery = commands.add_parser('rollback', help='Restore a known interrupted relocation only.')
    for command in (planned, recovery):
        command.add_argument('--pair', type=Path, required=True)
        command.add_argument('--task-id', required=True)
        command.add_argument('--owner', choices=('codex', 'claude'), required=True)
        command.add_argument('--thread', required=True)
    planned.add_argument('--to', type=Path, required=True)
    planned.add_argument('--reason', required=True)
    planned.add_argument('--native-idle-confirmed', action='store_true')
    planned.add_argument('--source-commit')
    planned.add_argument('--source-bundle', type=Path)
    planned.add_argument('--output', type=Path, required=True)
    applied.add_argument('--plan', type=Path, required=True)
    applied.add_argument('--expect', required=True, help='SHA256 printed by plan.')
    recovery.add_argument('--transaction-id', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            if args.output.exists(): raise ValueError('Use a new plan path; retain the earlier evidence.')
            result = plan(args.pair, args.task_id, args.owner, args.thread, args.to, args.reason,
                          args.native_idle_confirmed, args.source_commit, args.source_bundle)
            durable_write(args.output, result)
            print(json.dumps({'plan': str(args.output.resolve()), 'sha256': digest(result),
                              'source_mode': result['proof']['mode'], 'target': result['target']}))
        elif args.command == 'apply':
            print(json.dumps(apply(json.loads(args.plan.read_text()), args.expect)))
        else:
            print(json.dumps(rollback(args.pair, args.task_id, args.owner, args.thread, args.transaction_id)))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        parser.error(str(error))


if __name__ == '__main__': main()
