import tempfile
import unittest
from pathlib import Path

from hngoos_dm import processing
from hngoos_dm.media import find_ffmpeg


class MediaQualityTests(unittest.TestCase):
    def test_processing_prefers_bundled_ffmpeg_without_searching_user_paths(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder)
            runtime = package/"assets/runtime"/("ffmpeg.exe" if __import__("sys").platform == "win32" else "ffmpeg")
            runtime.parent.mkdir(parents=True)
            runtime.write_bytes(b"bundled codec fixture")
            with patch("importlib.resources.files", return_value=package), \
                    patch("hngoos_dm.media.shutil.which", return_value="other-ffmpeg") as search:
                self.assertEqual(find_ffmpeg(), str(runtime))
                search.assert_not_called()

    def test_external_progress_matches_selected_stream_using_real_ytdlp(self):
        import http.server
        import subprocess
        import sys
        import threading
        from unittest.mock import patch

        from hngoos_dm.media import external_download, ydl_options

        payload = b"\x00\x00\x00\x18ftypmp42"+b"\x00"*8192
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, *_args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        launch = subprocess.Popen
        def launch_module(arguments, **kwargs):
            return launch([sys.executable, "-m", "yt_dlp", *arguments[1:]], **kwargs)
        received = []
        try:
            with tempfile.TemporaryDirectory() as folder, patch("subprocess.Popen", side_effect=launch_module):
                external_download(sys.executable, f"http://127.0.0.1:{server.server_port}/video.mp4",
                                  ydl_options(folder), threading.Event(), received.append)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
        counters = [item for item in received if "downloaded_bytes" in item]
        self.assertTrue(counters)
        self.assertTrue(all(item["total_bytes"] == len(payload) for item in counters), counters)
        self.assertEqual(counters[-1]["downloaded_bytes"], len(payload))
        self.assertEqual(counters[-1]["status"], "finished")

    def test_external_progress_preserves_decimal_byte_totals(self):
        import io
        import threading
        from types import SimpleNamespace
        from unittest.mock import patch

        from hngoos_dm.media import external_download, ydl_options

        process = SimpleNamespace(
            stdout=io.StringIO("HDM_PROGRESS:191260262|NA|699123456.0|31981568.5\n"),
            poll=lambda: 0, returncode=0)
        received = []
        with patch("subprocess.Popen", return_value=process):
            external_download("yt-dlp", "https://example.com/video", ydl_options("out"),
                              threading.Event(), received.append)
        self.assertEqual(received[0]["downloaded_bytes"], 191260262)
        self.assertEqual(received[0]["total_bytes_estimate"], 699123456)
        self.assertEqual(received[0]["speed"], 31981568.5)

    def test_youtube_uses_bundled_quickjs_when_system_runtimes_are_absent(self):
        import sys
        from unittest.mock import patch

        from hngoos_dm.media import ydl_options

        with tempfile.TemporaryDirectory() as folder:
            package = Path(folder)
            runtime = package / "assets" / "runtime" / ("qjs.exe" if sys.platform == "win32" else "qjs")
            runtime.parent.mkdir(parents=True)
            runtime.write_bytes(b"bundled runtime fixture")
            with patch("hngoos_dm.media.shutil.which", return_value=None), \
                    patch("importlib.resources.files", return_value=package):
                self.assertEqual(ydl_options("out")["js_runtimes"], {"quickjs": {"path": str(runtime)}})

    def test_missing_optional_browser_package_does_not_break_media_options(self):
        from unittest.mock import patch

        from hngoos_dm.media import ydl_options

        with patch("hngoos_dm.media.shutil.which", return_value=None), \
                patch("importlib.resources.files", side_effect=ModuleNotFoundError):
            self.assertEqual(ydl_options("out")["js_runtimes"], {})

    def test_external_downloader_does_not_probe_unconfigured_runtimes_in_blocked_paths(self):
        import subprocess
        import sys
        import threading
        from unittest.mock import patch

        from yt_dlp import YoutubeDL, parse_options

        from hngoos_dm.media import external_download, ydl_options

        class CaptureCommand(Exception):
            pass

        settings = ydl_options("out")
        settings["js_runtimes"] = {"node": {"path": sys.executable}}
        with patch.object(subprocess, "Popen", side_effect=CaptureCommand) as launch, self.assertRaises(CaptureCommand):
            external_download("yt-dlp", "https://example.com/video", settings,
                              threading.Event(), None)
        parsed = parse_options(launch.call_args.args[0][1:])
        with patch("yt_dlp.utils._jsruntime._find_exe", side_effect=PermissionError("Untrusted mount point")), \
                YoutubeDL(parsed.ydl_opts) as downloader:
            for runtime in downloader._js_runtimes.values():
                _ = runtime.info
            self.assertEqual(set(downloader._js_runtimes), {"node"})

    def test_portrait_quality_uses_source_tier_instead_of_pixel_height(self):
        from hngoos_dm.media import video_quality
        self.assertEqual(video_quality({"format_note": "360p", "width": 360, "height": 468}), 360)
        self.assertEqual(video_quality({"width": 144, "height": 188}), 144)
        self.assertEqual(video_quality({"width": 1920, "height": 1080}), 1080)
        self.assertEqual(video_quality({"format_note": "1080p60", "height": 1440}), 1080)

    def test_youtube_runtime_configuration_is_shared_by_preview_and_download(self):
        from unittest.mock import patch

        from hngoos_dm.media import ydl_options
        with patch("hngoos_dm.media.shutil.which", side_effect=lambda name: "C:/Node/node.exe" if name == "node" else None):
            settings = ydl_options("out")
        self.assertEqual(settings["js_runtimes"], {"node": {"path": "C:/Node/node.exe"}})

    def test_explicit_source_streams_keep_selected_container_and_require_merger(self):
        from hngoos_dm.media import MediaOptions, ydl_options
        options = MediaOptions(container="webm", format_id="247+251")
        settings = ydl_options("out", options, ffmpeg="ffmpeg")
        self.assertEqual(settings["format"], "247+251")
        self.assertEqual(settings["merge_output_format"], "webm")
        self.assertNotIn("postprocessors", settings)
        with self.assertRaises(ValueError):
            ydl_options("out", options)
        native_audio = ydl_options("out", MediaOptions(format_id="140"))
        self.assertEqual(native_audio["format"], "140")
        self.assertNotIn("postprocessors", native_audio)

    def test_real_selector_respects_cap_and_refuses_only_oversize_formats(self):
        from yt_dlp import YoutubeDL
        from yt_dlp.utils import DownloadError, ExtractorError

        from hngoos_dm.media import MediaOptions, ydl_options
        formats = [{"format_id": str(height), "url": f"https://example.com/{height}.mp4", "height": height,
                    "ext": "mp4", "vcodec": "avc1.640028", "acodec": "mp4a.40.2"}
                   for height in (480, 1080, 2160)]
        for ffmpeg in (None, "ffmpeg"):
            with self.subTest(ffmpeg=ffmpeg), tempfile.TemporaryDirectory() as folder:
                options = ydl_options(folder, MediaOptions(height=720), ffmpeg)
                options["skip_download"] = True
                with YoutubeDL(options) as downloader:
                    result = downloader.process_ie_result({"id": "fixture", "title": "Fixture", "formats": formats}, download=False)
                    self.assertEqual(result["height"], 480)
                    with self.assertRaises((DownloadError, ExtractorError)):
                        downloader.process_ie_result({"id": "oversize", "title": "Oversize", "extractor": "fixture",
                                                      "formats": formats[1:]}, download=False)


class ProcessingTests(unittest.TestCase):
    def test_video_audio_exports_as_pcm_wav_with_original_sample_rate(self):
        import threading
        import wave

        from hngoos_dm.media import MediaOptions, normalize_audio, ydl_options

        options = MediaOptions(audio="wav")
        settings = ydl_options(self.folder, options, ffmpeg=find_ffmpeg())
        self.assertEqual(settings["format"], "bestaudio/best")
        normalize_audio(self.folder, options, threading.Event())
        target = self.folder/"source.wav"
        with wave.open(str(target), "rb") as audio:
            self.assertEqual(audio.getframerate(), 48000)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertEqual(audio.getcomptype(), "NONE")
            self.assertGreater(audio.getnframes(), 90000)
        self.assertFalse(self.source.exists())

    @classmethod
    def setUpClass(cls):
        try:
            find_ffmpeg()
        except ValueError as exc:
            raise unittest.SkipTest(str(exc)) from exc

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.source = processing.run_ffmpeg([
            "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac"], self.folder/"source.mp4")

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_cut_duration(self):
        result = processing.cut(self.source, self.folder/"cut.mp4", 0.4, 1.4, exact=True)
        self.assertAlmostEqual(processing.inspect_media(result)["duration"], 1, delta=0.15)
        self.assertTrue(self.source.exists())

    def test_common_video_codecs_decode_and_convert_with_real_frames(self):
        import subprocess

        fixtures = Path(__file__).parent/"fixtures/media"
        for name in ("av1.mkv", "hevc.mkv", "vp9.webm"):
            with self.subTest(codec=name):
                source = fixtures/name
                frame = subprocess.run([find_ffmpeg(), "-nostdin", "-v", "error", "-i", str(source),
                    "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                    check=True, capture_output=True, timeout=30,
                    creationflags=0x08000000 if __import__("os").name == "nt" else 0).stdout
                self.assertEqual(len(frame), 64*64*3)
                self.assertGreater(frame[0], 200)
                self.assertLess(frame[1], 10)
                self.assertLess(frame[2], 10)
                output = processing.convert(source, self.folder/(name+".mp4"), prefer_hardware=False)
                info = processing.inspect_media(output)
                self.assertEqual((info["width"], info["height"]), (64, 64))
                self.assertAlmostEqual(info["duration"], .4, delta=.15)

    def test_extract_mp3_and_m4a(self):
        for suffix in ("mp3", "m4a"):
            result = processing.extract_audio(self.source, self.folder/f"audio.{suffix}")
            self.assertFalse(processing.inspect_media(result)["video"])
            self.assertTrue(processing.inspect_media(result)["audio"])

    def test_join_normalizes_inputs_and_preserves_order_duration(self):
        larger = processing.run_ffmpeg(["-f", "lavfi", "-i", "color=c=blue:s=960x540:r=24",
            "-t", "1", "-c:v", "libx264", "-pix_fmt", "yuv420p"], self.folder/"larger.mp4")
        result = processing.concatenate([self.source, larger], self.folder/"joined.mp4")
        info = processing.inspect_media(result)
        self.assertAlmostEqual(info["duration"], 3, delta=0.4)
        self.assertEqual((info["width"], info["height"]), (960, 540))

    def test_invalid_cut_and_overwrite_are_rejected(self):
        with self.assertRaises(ValueError):
            processing.cut(self.source, self.folder/"bad.mp4", 2, 1)
        with self.assertRaises(ValueError):
            processing.convert(self.source, self.source)

    def test_two_pass_compression_meets_size_and_preserves_source(self):
        source = processing.run_ffmpeg(["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=25", "-t", "4",
            "-c:v", "libx264", "-crf", "5", "-pix_fmt", "yuv420p"], self.folder/"large.mp4")
        original = source.read_bytes()
        target_bytes = int(len(original)*0.65)
        output = processing.compress(source, self.folder/"small.mp4", target_bytes/(1024*1024))
        self.assertLessEqual(output.stat().st_size, target_bytes)
        self.assertAlmostEqual(processing.inspect_media(output)["duration"], 4, delta=0.15)
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(list(self.folder.glob(".hdm-compress-*")))


class PdfRedactionTests(unittest.TestCase):
    def test_huge_pdf_page_is_rejected_before_renderer_allocation(self):
        from unittest.mock import Mock

        from hngoos_dm.pdf_tools import render_bounded
        page = Mock()
        page.get_size.return_value = (100000, 100000)
        with self.assertRaises(ValueError):
            render_bounded(page, 2)
        page.render.assert_not_called()

    def test_sensitive_text_removed_and_region_blackened(self):
        try:
            import pypdfium2 as pdfium
            from PIL import Image
        except ImportError as exc:
            raise unittest.SkipTest("PDF extras not installed") from exc
        from hngoos_dm.pdf_tools import preview, redact
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            source, output = folder/"source.pdf", folder/"redacted.pdf"
            # Synthetic vector PDF: the sensitive text is a real text object, not a drawn image.
            content = b"BT /F1 20 Tf 30 100 Td (SECRET_PHONE_0912345678) Tj ET"
            objects = [b"<< /Type /Catalog /Pages 2 0 R >>",
                       b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                       b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
                       b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                       b"<< /Length "+str(len(content)).encode()+b" >>\nstream\n"+content+b"\nendstream"]
            data = bytearray(b"%PDF-1.4\n")
            offsets = [0]
            for index, obj in enumerate(objects, 1):
                offsets.append(len(data))
                data += f"{index} 0 obj\n".encode()+obj+b"\nendobj\n"
            xref = len(data)
            data += f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode()
            for offset in offsets[1:]:
                data += f"{offset:010} 00000 n \n".encode()
            data += f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
            source.write_bytes(data)
            with pdfium.PdfDocument(source) as doc:
                page = doc[0]
                textpage = page.get_textpage()
                self.assertIn("SECRET_PHONE", textpage.get_text_range())
                textpage.close()
                page.close()
            redact(source, output, {0: [(0, 0.3, 1, 0.6)]})
            self.assertNotIn(b"SECRET_PHONE", output.read_bytes())
            with pdfium.PdfDocument(output) as doc:
                page = doc[0]
                textpage = page.get_textpage()
                self.assertEqual(textpage.get_text_range(), "")
                textpage.close()
                page.close()
            rendered, count = preview(output, scale=1)
            self.assertEqual(count, 1)
            self.assertIsInstance(rendered, Image.Image)
            self.assertLess(sum(rendered.convert("RGB").getpixel((200, 90))), 20)
            rendered.close()
