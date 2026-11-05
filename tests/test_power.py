import unittest
from unittest.mock import patch

from hngoos_dm.power import cancel_shutdown, shutdown_in


class PowerTests(unittest.TestCase):
    @patch("hngoos_dm.power.os.name", "nt")
    @patch("hngoos_dm.power.subprocess.run")
    def test_shutdown_has_cancelable_countdown_and_cancel_is_separate(self, run):
        shutdown_in(0)
        args = run.call_args.args[0]
        self.assertEqual(args[0], "shutdown.exe")
        self.assertEqual(args[args.index("/t")+1], "30")
        cancel_shutdown()
        self.assertEqual(run.call_args.args[0], ["shutdown.exe", "/a"])
