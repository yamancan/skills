"""A process group disappearing between TERM and KILL is already cleaned up."""
import signal
import unittest
from unittest.mock import patch

import _support
import process_control


class Process:
    pid = 123456
    returncode = None

    def wait(self, timeout=None):
        self.returncode = 0
        return 0


class GroupCleanup(unittest.TestCase):
    def test_permission_race_is_benign_only_when_group_is_now_missing(self):
        def signal_group(group, signum):
            if signum == signal.SIGKILL:
                raise PermissionError('group disappeared during KILL')
            if signum == 0:
                raise ProcessLookupError('group is gone')

        process = Process()
        with patch.object(process_control.os, 'killpg', side_effect=signal_group):
            process_control.stop_group(process)
        self.assertEqual(process.returncode, 0)

    def test_live_group_permission_error_remains_a_failure(self):
        def signal_group(group, signum):
            if signum:
                raise PermissionError('live group permission denied')

        with patch.object(process_control.os, 'killpg', side_effect=signal_group):
            with self.assertRaises(PermissionError):
                process_control.stop_group(Process())

    def test_uninspectable_group_is_not_treated_as_dead(self):
        with patch.object(process_control.os, 'killpg', side_effect=PermissionError('not allowed')):
            with self.assertRaises(PermissionError):
                process_control.stop_group(Process())

    def test_vanishing_group_can_report_permission_denied_during_existence_probe(self):
        probes = 0

        def signal_group(group, signum):
            nonlocal probes
            if signum == signal.SIGKILL:
                raise PermissionError('KILL raced with group removal')
            if signum == 0:
                probes += 1
                if probes == 1:
                    raise PermissionError('kernel still removing group')
                raise ProcessLookupError('removal complete')

        process = Process()
        with patch.object(process_control.os, 'killpg', side_effect=signal_group):
            process_control.stop_group(process)
        self.assertEqual(process.returncode, 0)
