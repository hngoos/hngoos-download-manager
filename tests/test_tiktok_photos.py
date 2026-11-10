"""TikTok photo albums use source images rather than the video extractor."""

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from hngoos_dm.media import MediaCancelled, MediaOptions, describe_media, download_video

URL = "https://www.tiktok.com/@example/photo/7680913365123796231?is_from_webapp=1"


class TikTokPhotoTests(unittest.TestCase):
    def test_embed_metadata_keeps_all_images_in_source_order(self):
        from hngoos_dm.tiktok_photos import parse_embed

        images = [{"urlList": [f"https://p16.tiktokcdn.com/{i}.jpeg"], "width": 1170, "height": 2080}
                  for i in range(3)]
        data = {"source": {"data": {"/embed/7680913365123796231": {"videoData": {
            "itemInfos": {"id": "7680913365123796231", "text": "Album"},
            "imagePostInfo": {"displayImages": images}}}}}}
        html = '<script id="__FRONTITY_CONNECT_STATE__" type="application/json">'+json.dumps(data)+'</script>'
        album = parse_embed(html, "7680913365123796231")
        self.assertEqual(album["title"], "Album")
        self.assertEqual([x["url"] for x in album["images"]], [x["urlList"][0] for x in images])
        with self.assertRaises(ValueError):
            parse_embed(html, "111")
        images[1]["urlList"] = ["https://unrelated.example/payload.exe"]
        with self.assertRaises(ValueError):
            parse_embed('<script id="__FRONTITY_CONNECT_STATE__">'+json.dumps(data)+'</script>',
                        "7680913365123796231")

    def test_photo_preview_does_not_invoke_video_extraction(self):
        from yt_dlp import YoutubeDL

        album = {"title": "Album", "images": [{"url": "https://p16.tiktokcdn.com/1.jpeg", "ext": "jpg"}]}
        with patch("hngoos_dm.tiktok_photos.describe_album", return_value=album), \
                patch.object(YoutubeDL, "extract_info", side_effect=AssertionError("video extractor")):
            info = describe_media(URL)
        self.assertEqual(info["media_type"], "photos")
        self.assertEqual(info["extension"], "jpg")

    def test_album_download_publishes_each_image_without_video_processing(self):
        payloads = {"/1.jpg": b"\xff\xd8\xff"+b"a"*100, "/2.jpg": b"\xff\xd8\xff"+b"b"*200}

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                data = payloads[self.path]
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *_args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        album = {"title": "Album", "images": [
            {"url": f"http://127.0.0.1:{server.server_port}/{i}.jpg", "ext": "jpg"} for i in (1, 2)]}
        try:
            with tempfile.TemporaryDirectory() as folder, \
                    patch("hngoos_dm.tiktok_photos.describe_album", return_value=album):
                stop = threading.Event()
                def cancel(data):
                    if data.get("downloaded_bytes"):
                        stop.set()
                with self.assertRaises(MediaCancelled):
                    download_video(URL, Path(folder)/"out", staging_root=Path(folder)/"stage", stop=stop,
                                   options=MediaOptions(filename="Album.jpg"), progress=cancel)
                self.assertFalse(list((Path(folder)/"out").glob("*")))
                events = []
                paths = download_video(URL, Path(folder)/"out", staging_root=Path(folder)/"stage",
                                       options=MediaOptions(filename="Album.jpg"), progress=events.append)
                self.assertEqual([p.name for p in paths], ["Album - 001.jpg", "Album - 002.jpg"])
                self.assertEqual([p.read_bytes() for p in paths], list(payloads.values()))
                last = next(event for event in reversed(events) if "downloaded_bytes" in event)
                self.assertEqual(last["total_bytes"], sum(map(len, payloads.values())))
                self.assertEqual(last["downloaded_bytes"], last["total_bytes"])
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    unittest.main()
