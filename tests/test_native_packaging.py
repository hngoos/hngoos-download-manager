"""DiskImages retries must not hide packaging or verification failures."""

import runpy
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class NativePackagingTests(unittest.TestCase):
    def package(self, outcomes):
        module = runpy.run_path(str(Path(__file__).resolve().parents[1]/"scripts/package-native.py"))
        function = module["package_macos"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/"dist/HDM.app").mkdir(parents=True)
            (root/"dist/extension").mkdir()
            with patch.dict(function.__globals__, ROOT=root), \
                    patch.object(Path, "symlink_to"), \
                    patch("subprocess.run", side_effect=outcomes) as run, \
                    patch("time.sleep") as sleep:
                try:
                    result = function()
                except subprocess.CalledProcessError as error:
                    return error, run.call_args_list, sleep.call_args_list
                return result, run.call_args_list, sleep.call_args_list

    @staticmethod
    def failure(message, action="create"):
        return subprocess.CalledProcessError(1, ["hdiutil", action], stderr=message)

    def test_resource_busy_retries_then_verifies_created_image(self):
        result, calls, waits = self.package([
            self.failure("hdiutil: create failed - Resource busy\n"),
            subprocess.CompletedProcess([], 0), subprocess.CompletedProcess([], 0)])
        self.assertIsInstance(result, list)
        self.assertEqual([call.args[0][:2] for call in calls],
                         [["hdiutil", "create"], ["hdiutil", "create"], ["hdiutil", "verify"]])
        self.assertEqual(len(waits), 1)

    def test_resource_busy_retry_is_bounded_and_preserves_last_failure(self):
        failures = [self.failure("hdiutil: create failed - Resource busy\n") for _ in range(3)]
        result, calls, waits = self.package(failures)
        self.assertIs(result, failures[-1])
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(waits), 2)

    def test_other_creation_errors_are_not_retried(self):
        failure = self.failure("hdiutil: create failed - No space left on device\n")
        result, calls, waits = self.package([failure])
        self.assertIs(result, failure)
        self.assertEqual(len(calls), 1)
        self.assertFalse(waits)

    def test_verification_failure_is_fatal_without_retry(self):
        failure = self.failure("hdiutil: verify failed - Resource busy\n", "verify")
        result, calls, waits = self.package([subprocess.CompletedProcess([], 0), failure])
        self.assertIs(result, failure)
        self.assertEqual(len(calls), 2)
        self.assertFalse(waits)
