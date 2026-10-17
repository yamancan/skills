"""Terminate managed POSIX process groups, including remaining descendants."""
import os
import signal
import subprocess
import time


def stop_group(process):
    # Each managed child has its own group, including manual interactive processes.
    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            pass
        except PermissionError as error:
            # macOS can report EPERM as a group vanishes after TERM.
            # Accept only confirmed absence; live/uninspectable groups still fail.
            for attempt in range(3):
                try:
                    os.killpg(process.pid, 0)
                except ProcessLookupError:
                    break
                except PermissionError:
                    if attempt == 2:
                        raise error
                    time.sleep(0.01)
                else:
                    raise error
        if signum == signal.SIGTERM:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
    process.wait()
