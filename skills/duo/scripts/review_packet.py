#!/usr/bin/env python3
"""Content-addressed review inputs from explicitly selected files; no repository clones."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat

from session_store import write_json
import workspace

MAX_PACKET_BYTES = 64 * workspace.MIB

EXCLUDED = {'.git', 'node_modules', '__pycache__', '.cache', '.npm', '.venv', 'venv'}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular_file(root, name):
    relative = Path(name)
    if not name or relative.is_absolute() or any(part in ('.', '..') for part in relative.parts):
        raise ValueError(f'Use a relative file path without traversal: {name}')
    if name != relative.as_posix() or any(part in EXCLUDED for part in relative.parts):
        raise ValueError(f'Excluded/noncanonical review input: {name}')
    root = Path(root).absolute()
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    directory = os.open(root.anchor, directory_flags)
    try:
        # Pin every component; replacing a checked pathname cannot redirect later reads.
        for part in root.parts[1:] + relative.parts[:-1]:
            child = os.open(part, directory_flags, dir_fd=directory)
            os.close(directory)
            directory = child
        # NONBLOCK lets fstat reject a substituted FIFO without waiting for a writer.
        file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        with os.fdopen(os.open(relative.name, file_flags, dir_fd=directory), 'rb') as selected:
            before = os.fstat(selected.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError(f'Review inputs must be regular files: {name}')
            if before.st_size > MAX_PACKET_BYTES:
                raise ValueError(f'Review input exceeds the packet size limit: {name}')
            raw = selected.read(MAX_PACKET_BYTES + 1)
            after = os.fstat(selected.fileno())
            if len(raw) > MAX_PACKET_BYTES:
                raise ValueError(f'Review input exceeds the packet size limit: {name}')
    finally:
        os.close(directory)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError(f'Source changed during capture: {name}')
    return raw, bool(before.st_mode & 0o111)


def read_manifest(path):
    value = json.loads(path.read_text())
    if value.get('version') != 1 or not isinstance(value.get('files'), dict) or not value['files']:
        raise ValueError('Invalid/empty packet manifest.')
    content = {key: value[key] for key in ('version', 'workdir', 'source_identity', 'files')}
    if digest(json.dumps(content, sort_keys=True).encode()) != value.get('id'):
        raise ValueError('Packet manifest hash mismatch.')
    return value


def check(path, workdir=None):
    manifest = read_manifest(path)
    source = Path(manifest['workdir'])
    if workdir is not None and source != Path(workdir).resolve():
        raise ValueError('Packet belongs to another canonical checkout.')
    if source.resolve() != source or workspace.identity(source) != manifest['source_identity']:
        raise ValueError('Packet source checkout was replaced.')
    changed = []
    packet_source = path.parent/'source'
    if packet_source.is_symlink():
        raise ValueError('Packet source must not be a symlink.')
    for name, expected in manifest['files'].items():
        raw, executable = regular_file(packet_source, name)
        if digest(raw) != expected['sha256'] or executable != expected['executable']:
            raise ValueError(f'Frozen packet was modified: {name}')
        try:
            raw, executable = regular_file(source, name)
            matches = digest(raw) == expected['sha256'] and executable == expected['executable']
        except (OSError, ValueError):
            matches = False
        if not matches:
            changed.append(name)
    return {'packet_id': manifest['id'], 'manifest': str(path), 'source_matches': not changed,
            'changed_files': changed, 'files': list(manifest['files']),
            'coverage': 'Only the listed files; caller must include required diff, callers, contracts and tests.'}


def create(state, files):
    with workspace.locked(state):
        data = workspace.load(state)
        workspace.validate_source(data)
        root = workspace.storage_root(state, data)
        source = Path(data['workdir'])
        if not files or len(files) != len(set(files)):
            raise ValueError('Select a nonempty, unique list of review input files.')
        capture_limit = min(data['budget_bytes'], MAX_PACKET_BYTES)
        content, total = {}, 0
        for name in sorted(files):
            # Check the file size before reading so oversized inputs cannot exhaust memory.
            target = source/name
            if target.stat().st_size > capture_limit-total:
                raise ValueError('Packet exceeds its storage limit (task budget or 64 MiB per packet).')
            raw, executable = regular_file(source, name)
            total += len(raw)
            if total > capture_limit:
                raise ValueError('Packet exceeds its storage limit (task budget or 64 MiB per packet).')
            content[name] = (raw, executable)
        manifest = {'version': 1, 'workdir': str(source), 'source_identity': data['source_identity'],
                    'files': {name: {'sha256': digest(raw), 'executable': executable}
                              for name, (raw, executable) in content.items()}}
        token = digest(json.dumps(manifest, sort_keys=True).encode())
        manifest['id'] = token
        parent = root/'packets'
        if parent.is_symlink():
            raise ValueError('Packet parent must not be a symlink.')
        parent.mkdir(exist_ok=True, mode=0o700)
        target = parent/token
        path = target/'manifest.json'
        if target.exists() or target.is_symlink():
            if target.is_symlink() or not path.is_file():
                raise ValueError('Incomplete/replaced packet; inspect the recorded directory.')
            result = check(path, str(source))
            if not result['source_matches']:
                raise ValueError('Source changed during packet creation.')
            return result
        if workspace.committed_bytes(root, data) + total + len(json.dumps(manifest).encode()) > data['budget_bytes']:
            raise ValueError('Packet would exceed the workspace storage budget.')
        target.mkdir(mode=0o700)
        for name, (raw, executable) in content.items():
            destination = target/'source'/name
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            destination.write_bytes(raw)
            destination.chmod(0o500 if executable else 0o400)
        write_json(path, manifest)
        result = check(path, str(source))
        if not result['source_matches']:
            raise ValueError('Source changed during packet creation; snapshot is historical only.')
        return result


def materialize(path, destination, workdir):
    result = check(path, workdir)
    if not result['source_matches']:
        raise ValueError('Packet source is stale; refresh affected evidence before testing.')
    manifest = read_manifest(path)
    for name, info in manifest['files'].items():
        target = destination/name
        if target.exists() or target.is_symlink():
            raise ValueError('Packet would replace existing scratch metadata.')
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(path.parent/'source'/name, target)
        target.chmod(0o700 if info['executable'] else 0o600)
        if digest(target.read_bytes()) != info['sha256']:
            raise ValueError('Packet changed while copying test inputs.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    make = commands.add_parser('make')
    make.add_argument('--state', type=Path, required=True)
    make.add_argument('--file', action='append', dest='files', required=True)
    verify = commands.add_parser('check')
    verify.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = create(args.state.resolve(), args.files) if args.command == 'make' else check(args.manifest.resolve())
        print(json.dumps(result, indent=2))
        if not result['source_matches']:
            raise SystemExit(3)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
