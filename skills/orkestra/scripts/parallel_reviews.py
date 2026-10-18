#!/usr/bin/env python3
"""Run independent review CLIs concurrently and retain each transport outcome."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

DUO_SCRIPTS = Path(__file__).resolve().parents[2] / 'duo' / 'scripts'
if not (DUO_SCRIPTS / 'process_control.py').is_file():
    raise SystemExit('Install Duo alongside Orkestra: both skill directories must share the same parent. '
                     'Use the Niche Skills shortcut with --skill orkestra, or install both duo and orkestra with your skill manager.')
sys.path.insert(0, str(DUO_SCRIPTS))
from process_control import stop_group as stop


def stamp():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)


def validate(manifest):
    jobs = manifest.get('jobs')
    if not isinstance(jobs, list) or not jobs:
        raise ValueError('Manifest needs a nonempty jobs list')
    seen = set()
    sessions = set()
    for job in jobs:
        if not isinstance(job, dict) or not re.fullmatch(r'[a-zA-Z0-9_-]+', str(job.get('id', ''))):
            raise ValueError('Each job needs a filesystem-safe id')
        if job['id'] in seen:
            raise ValueError('Duplicate job id: ' + job['id'])
        seen.add(job['id'])
        command = job.get('command')
        if not isinstance(command, list) or not command or not command[0] or not all(isinstance(x, str) and '\0' not in x for x in command):
            raise ValueError('Each command must be a nonempty argv array')
        if not Path(str(job.get('cwd', ''))).is_absolute() or not Path(job['cwd']).is_dir():
            raise ValueError('Each cwd must be an existing absolute directory')
        timeout = job.get('timeout_seconds')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 86400:
            raise ValueError('Each timeout_seconds must be positive and at most one day')
        session = job.get('session_id')
        if job.get('new_session') is True:
            if session is not None:
                raise ValueError('Use new_session only when the provider has not assigned an ID yet')
        else:
            if not isinstance(session, str) or not session:
                raise ValueError('Provide exact session_id or explicitly request new_session')
            if session in sessions:
                raise ValueError('A native session cannot be dispatched twice in parallel')
            sessions.add(session)
    return jobs


def interrupted(_signal, _frame):
    raise KeyboardInterrupt


def run(jobs, output):
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    active = {}
    statuses = {}
    try:
        for job in jobs:
            folder = output / job['id']
            folder.mkdir(mode=0o700)
            status = {'id': job['id'], 'session_id': job.get('session_id'),
                      'new_session': job.get('new_session') is True,
                      'state': 'launching', 'started_at': stamp(),
                      'timeout_seconds': job['timeout_seconds']}
            save(folder / 'status.json', status)
            statuses[job['id']] = status
            try:
                with (folder / 'stdout').open('xb') as stdout, (folder / 'stderr').open('xb') as stderr:
                    process = subprocess.Popen(job['command'], cwd=job['cwd'], stdin=subprocess.DEVNULL,
                                               stdout=stdout, stderr=stderr, start_new_session=True)
            except OSError as error:
                status.update(state='launch_failed', error_type=type(error).__name__, finished_at=stamp())
                save(folder / 'status.json', status)
                print(json.dumps({'event': 'finished', 'id': job['id'], 'state': status['state']}), flush=True)
                continue
            active[job['id']] = (process, time.monotonic() + job['timeout_seconds'])
            status.update(state='running', pid=process.pid)
            save(folder / 'status.json', status)
            print(json.dumps({'event': 'started', 'id': job['id'], 'pid': process.pid}), flush=True)
        while active:
            for name, (process, deadline) in list(active.items()):
                code = process.poll()
                timed_out = code is None and time.monotonic() >= deadline
                if timed_out or code is not None:
                    status = statuses[name]
                    try:
                        # A CLI wrapper can exit while its descendants still run.
                        stop(process)
                        status['state'] = 'timed_out' if timed_out else 'exited'
                    except (OSError, subprocess.TimeoutExpired) as error:
                        status.update(state='cleanup_failed', error_type=type(error).__name__)
                    status.update(exit_code=process.poll(), finished_at=stamp(),
                                  elapsed_seconds=round(time.monotonic() - deadline + status['timeout_seconds'], 3))
                    save(output / name / 'status.json', status)
                    print(json.dumps({'event': 'finished', 'id': name, 'state': status['state'],
                                      'exit_code': status['exit_code']}), flush=True)
                    del active[name]
            if active:
                time.sleep(0.05)
    except BaseException:
        for name, (process, _) in active.items():
            try:
                stop(process)
                statuses[name]['state'] = 'interrupted'
            except (OSError, subprocess.TimeoutExpired) as error:
                statuses[name].update(state='cleanup_failed', error_type=type(error).__name__)
            statuses[name].update(exit_code=process.poll(), finished_at=stamp())
            save(output / name / 'status.json', statuses[name])
        raise
    return 0 if all(s['state'] == 'exited' and s['exit_code'] == 0 for s in statuses.values()) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    jobs = validate(json.loads(args.manifest.read_text()))
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    return run(jobs, args.output)


if __name__ == '__main__':
    raise SystemExit(main())
