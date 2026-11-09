import hashlib
import socket
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
            # Give the seeder a concrete OS-selected port: libtorrent's port-zero listener
            # intermittently remained at listen_port()==0 on the Windows fixture.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
                reservation.bind(("127.0.0.1", 0))
                seed_port = reservation.getsockname()[1]
            settings = {"listen_interfaces": f"127.0.0.1:{seed_port}", "enable_dht": False, "enable_lsd": False,
                        "enable_upnp": False, "enable_natpmp": False,
                        "enable_outgoing_utp": False, "enable_incoming_utp": False,
                        "enable_outgoing_tcp": True, "enable_incoming_tcp": True}
            seeder = lt.session(settings)
            params = lt.add_torrent_params()
            params.ti = lt.torrent_info(str(source))
            params.save_path = str(seed)
            params.flags |= lt.torrent_flags.seed_mode
            params.flags &= ~lt.torrent_flags.auto_managed
            seed_handle = seeder.add_torrent(params)
            seed_handle.resume()
            job = TorrentJob(str(source), root/"download", local_only=True)
            def diagnostics():
                seed_status, download_status = seed_handle.status(), job.handle.status()
                return {"seed_port": seeder.listen_port(), "seed_state": str(seed_status.state),
                        "seed_error": seed_status.errc.message(), "seed_peers": seed_status.num_peers,
                        "download": job.status(), "download_state": str(download_status.state),
                        "done": download_status.total_done,
                        "seed_alerts": [alert.message() for alert in seeder.pop_alerts()]}

            def ready(*, allow_complete=False):
                # The downloader otherwise retains uTP negotiation while the seeder disables it.
                # Keep this loopback checkpoint fixture independent of transport fallback timing.
                job.session.apply_settings({"enable_outgoing_utp": False, "enable_incoming_utp": False,
                                            "enable_outgoing_tcp": True, "enable_incoming_tcp": True})
                deadline = time.monotonic()+10
                while time.monotonic() < deadline:
                    status = job.handle.status()
                    transferring = (status.state == lt.torrent_status.downloading
                                    and not status.flags & lt.torrent_flags.paused)
                    # On resume, a loopback peer can finish before this polling loop runs.
                    # Completion is valid here; the initial pause must still be incomplete.
                    if (seeder.listen_port() and seed_handle.status().is_seeding
                            and (transferring or (allow_complete and job.completed))):
                        return
                    time.sleep(0.02)
                self.fail("Loopback torrent fixture was not ready: "+str(diagnostics()))

            def wait_for(predicate):
                deadline = time.monotonic()+25
                next_connect = 0
                while not predicate() and time.monotonic() < deadline:
                    now = time.monotonic()
                    if now >= next_connect:
                        job.handle.connect_peer(("127.0.0.1", seeder.listen_port()))
                        next_connect = now+1
                    time.sleep(0.1)
            try:
                job.select([0])
                job.handle.set_download_limit(512*1024)
                ready()
                wait_for(lambda: job.handle.status().total_done > 0)
                self.assertGreater(job.handle.status().total_done, 0, str(diagnostics()))
                self.assertLess(job.handle.status().total_done, len(data), "Fixture must pause an incomplete transfer")
                job.pause()
                job.close()
                self.assertTrue(job.resume_path.is_file())
                job = TorrentJob(str(source), root/"download", local_only=True)
                self.assertTrue(job.restored)
                job.handle.set_download_limit(0)
                job.resume()
                ready(allow_complete=True)
                wait_for(lambda: job.completed)
                self.assertTrue(job.completed, str(diagnostics()))
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
