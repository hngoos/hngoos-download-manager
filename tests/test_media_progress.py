"""Progress counts selected media streams once, including audio and resumes."""

import unittest


class MediaProgressTests(unittest.TestCase):
    def test_separate_video_and_audio_share_one_total(self):
        from hngoos_dm.media_progress import MediaProgress

        received = []
        progress = MediaProgress(received.append)
        progress.plan({"id": "clip", "requested_formats": [
            {"format_id": "137", "filesize": 80_000_000},
            {"format_id": "140", "filesize": 10_000_000}]})
        progress({"status": "downloading", "downloaded_bytes": 40_000_000,
                  "info_dict": {"id": "clip", "format_id": "137"}})
        self.assertEqual((received[-1]["downloaded_bytes"], received[-1]["total_bytes"]),
                         (40_000_000, 90_000_000))
        progress({"status": "finished", "downloaded_bytes": 80_000_000,
                  "info_dict": {"id": "clip", "format_id": "137"}})
        self.assertEqual(received[-1]["status"], "downloading")
        for _ in range(2):
            progress({"status": "downloading", "downloaded_bytes": 5_000_000,
                      "info_dict": {"id": "clip", "format_id": "140"}})
        self.assertEqual((received[-1]["downloaded_bytes"], received[-1]["total_bytes"]),
                         (85_000_000, 90_000_000))
        progress({"status": "finished", "downloaded_bytes": 10_000_000,
                  "info_dict": {"id": "clip", "format_id": "140"}})
        self.assertEqual(received[-1]["status"], "finished")
        self.assertFalse(received[-1]["total_estimated"])

    def test_missing_hook_total_keeps_exact_metadata_size(self):
        from hngoos_dm.media_progress import MediaProgress

        received = []
        progress = MediaProgress(received.append)
        progress({"status": "downloading", "downloaded_bytes": 182_000_000,
                  "total_bytes": None, "info_dict": {"id": "clip", "format_id": "18", "filesize": 689_145_749}})
        self.assertEqual(received[-1]["total_bytes"], 689_145_749)
        progress({"status": "downloading", "downloaded_bytes": 190_000_000,
                  "info_dict": {"id": "clip", "format_id": "18"}})
        self.assertEqual(received[-1]["total_bytes"], 689_145_749)

    def test_estimate_is_explicit_and_replaced_by_measured_size(self):
        from hngoos_dm.media_progress import MediaProgress

        received = []
        progress = MediaProgress(received.append)
        progress({"status": "downloading", "downloaded_bytes": 1024,
                  "total_bytes_estimate": 90_000_000.5, "info_dict": {"format_id": "hls"}})
        self.assertEqual(received[-1]["total_bytes"], 90_000_000)
        self.assertTrue(received[-1]["total_estimated"])
        progress({"status": "finished", "downloaded_bytes": 89_000_000,
                  "info_dict": {"format_id": "hls"}})
        self.assertEqual(received[-1]["total_bytes"], 89_000_000)
        self.assertFalse(received[-1]["total_estimated"])

    def test_postprocessor_finished_does_not_reset_downloaded_bytes(self):
        from hngoos_dm.media_progress import MediaProgress

        received = []
        progress = MediaProgress(received.append)
        progress({"status": "finished", "downloaded_bytes": 90_000_000,
                  "info_dict": {"format_id": "18"}})
        progress({"status": "finished", "postprocessor": "Merger", "info_dict": {"format_id": "18"}})
        self.assertEqual(received[-1]["downloaded_bytes"], 90_000_000)
