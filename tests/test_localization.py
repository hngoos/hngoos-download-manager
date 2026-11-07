"""Language changes translate presentation, preserving user and provider data."""

import unittest

from hngoos_dm.ui_preferences import Localizer


class LocalizationTests(unittest.TestCase):
    def test_new_preferences_and_provider_errors_have_both_languages(self):
        locale = Localizer(None, "en")
        for vi, en in (
            ("Thư mục lưu", "Download folder"),
            ("Tích hợp trình duyệt", "Browser integration"),
            ("Nâng cao", "Advanced"),
            ("Bỏ qua tên miền", "Skip domains"),
            ("Quét lại", "Scan again"),
            ("Nhập khóa API VirusTotal của bạn (64 ký tự thập lục phân).",
             "Enter your VirusTotal API key (64 hexadecimal characters)."),
        ):
            with self.subTest(vi=vi):
                self.assertEqual(locale.text(vi), en)
                locale.language = "vi"
                self.assertEqual(locale.text(en), vi)
                locale.language = "en"

    def test_formatted_messages_switch_language_without_changing_file_data(self):
        locale = Localizer(None, "en")
        source = "Đã lưu: C:/Tài liệu/English report.pdf"
        translated = "Saved: C:/Tài liệu/English report.pdf"
        self.assertEqual(locale.text(source), translated)
        locale.language = "vi"
        self.assertEqual(locale.text(translated), source)
        for value in ("C:/Download/Report.pdf", "https://example.com/Tài-liệu.pdf", "Windows Defender", "320 kbps"):
            self.assertEqual(locale.text(value), value)
