"""Sizing contracts independent of a build host's physical display."""

import unittest
from types import SimpleNamespace

from hngoos_dm.ui_scale import WindowScale


def window(width, height, dpi=4/3):
    return SimpleNamespace(winfo_width=lambda: width, winfo_height=lambda: height,
                           tk=SimpleNamespace(call=lambda *_: dpi))


class WindowScaleTests(unittest.TestCase):
    def test_proportional_sizes_stop_at_readable_minimums(self):
        scales = [WindowScale(window(width, height)) for width, height in
                  ((1280, 800), (1120, 700), (960, 600), (800, 500), (640, 400))]
        self.assertEqual([scale.font_size(14, 11) for scale in scales], [14, 12, 11, 11, 11])
        self.assertEqual([scale.size(24, 16) for scale in scales], [24, 21, 18, 16, 16])
        self.assertEqual([scale.font_size(12, 9) for scale in scales], [12, 10, 9, 9, 9])

    def test_high_dpi_text_stays_within_the_same_pixel_layout(self):
        for width, height in ((1280, 800), (960, 600), (800, 500)):
            baseline = WindowScale(window(width, height)).font_size(14, 11)*(4/3)
            for dpi in (4/3, 5/3, 2, 8/3):
                with self.subTest(width=width, height=height, dpi=dpi):
                    pixels = WindowScale(window(width, height, dpi)).font_size(14, 11)*dpi
                    self.assertGreaterEqual(pixels, baseline)
                    self.assertLessEqual(pixels, baseline+dpi)
