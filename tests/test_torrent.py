import hashlib
import tempfile
import time
import unittest
from pathlib import Path


class TorrentTests(unittest.TestCase):
    def test_local_download_checkpoint_reopen_and_finish_without_seeding(self):
        import libtorrent as lt

        from hngoos_dm.torrent import TorrentJob
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            seed = root/"seed"
            seed.mkdir()
            data = bytes(range(256))*32768
            (seed/"payload.bin").write_bytes(data)
            files = lt.file_storage()
            files.add_file("payload.bin", len(data))
            created = lt.create_torrent(files, 256*1024, flags=lt.create_torrent.v1_only)
            lt.set_piece_hashes(created, str(seed))
            source = root/"payload.torrent"
            source.write_bytes(lt.bencode(created.generate()))
            settings = {"listen_interfaces": "127.0.0.1:0", "enable_dht": False, "enable_lsd": False,
                        "enable_upnp": False, "enable_natpmp": False, "enable_outgoing_utp": False}
            seeder = lt.session(settings)
            params = lt.add_torrent_params()
            params.ti = lt.torrent_info(str(source))
            params.save_path = str(seed)
            params.flags |= lt.torrent_flags.seed_mode
            params.flags &= ~lt.torrent_flags.auto_managed
            seed_handle = seeder.add_torrent(params)
            seed_handle.resume()
            job = TorrentJob(str(source), root/"download", local_only=True)
            try:
                job.select([0])
                job.handle.set_download_limit(512*1024)
                deadline = time.monotonic()+25
                while job.handle.status().total_done == 0 and time.monotonic() < deadline:
                    if seeder.listen_port():
                        job.handle.connect_peer(("127.0.0.1", seeder.listen_port()))
                    time.sleep(0.1)
                self.assertGreater(job.handle.status().total_done, 0)
                job.pause()
                job.close()
                self.assertTrue(job.resume_path.is_file())
                job = TorrentJob(str(source), root/"download", local_only=True)
                self.assertTrue(job.restored)
                job.handle.set_download_limit(0)
                job.resume()
                deadline = time.monotonic()+25
                while not job.completed and time.monotonic() < deadline:
                    job.handle.connect_peer(("127.0.0.1", seeder.listen_port()))
                    time.sleep(0.1)
                self.assertTrue(job.completed)
                self.assertTrue(job.status()["paused"])
                received = (root/"download/payload.bin").read_bytes()
                details = {"size": len(received), "expected": len(data), "status": job.status(),
                           "pieces": job.handle.status().num_pieces, "wanted": job.handle.status().total_wanted,
                           "done": job.handle.status().total_wanted_done,
                           "first_difference": next((index for index, (a, b) in enumerate(zip(received, data)) if a != b), None)}
                self.assertEqual(hashlib.sha256(received).digest(), hashlib.sha256(data).digest(), str(details))
            finally:
                job.close()
                seeder.pause()

    def test_metadata_risky_files_and_selection_priorities(self):
        try:
            import libtorrent as lt
        except ImportError as exc:
            raise unittest.SkipTest("torrent extras not installed") from exc
        from hngoos_dm.torrent import TorrentJob
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            files = lt.file_storage()
            files.add_file("example/movie.mp4", 4)
            files.add_file("example/run.exe", 2)
            (folder/"example").mkdir()
            (folder/"example"/"movie.mp4").write_bytes(b"data")
            (folder/"example"/"run.exe").write_bytes(b"MZ")
            created = lt.create_torrent(files, flags=lt.create_torrent.v1_only)
            lt.set_piece_hashes(created, str(folder))
            torrent = folder/"example.torrent"
            torrent.write_bytes(lt.bencode(created.generate()))
            job = TorrentJob(str(torrent), folder/"download", local_only=True)
            try:
                items = job.files()
                self.assertEqual(len(items), 2)
                self.assertFalse(items[0]["risky"])
                self.assertTrue(items[1]["risky"])
                job.select([0])
                until = time.monotonic()+2
                while list(job.handle.get_file_priorities()) != [4, 0] and time.monotonic() < until:
                    time.sleep(0.02)
                self.assertEqual(list(job.handle.get_file_priorities()), [4, 0])
                job.pause()
            finally:
                job.close()
