"""Network-isolated VirusTotal protocol, privacy and verdict regression checks."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hngoos_dm.virustotal import API, VirusTotalClient, VirusTotalError, summarize


class VirusTotalTests(unittest.TestCase):
    def setUp(self):
        self.client = VirusTotalClient("a"*64)

    def test_requires_consent_and_unchanged_bytes_before_upload(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"sample.bin"
            path.write_bytes(b"synthetic scan fixture")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            with patch.object(self.client, "request") as request:
                with self.assertRaisesRegex(VirusTotalError, "consent"):
                    self.client.upload(path, digest)
                with self.assertRaisesRegex(VirusTotalError, "changed"):
                    self.client.upload(path, "0"*64, consent=True)
                request.assert_not_called()
                request.return_value = {"data": {"id": "analysis-fixture"}}
                self.assertEqual(self.client.upload(path, digest, consent=True), "analysis-fixture")
                request.assert_called_once_with("POST", API+"/files", path=path, expected_sha256=digest)

    def test_unknown_is_not_a_clean_verdict_and_hash_lookups_do_not_upload(self):
        with patch.object(self.client, "request", return_value=None) as request:
            self.assertIsNone(self.client.lookup("b"*64))
            request.assert_called_once_with("GET", API+"/files/"+"b"*64)
        empty = summarize({"data": {"attributes": {}}}, analysis=False)
        self.assertEqual(empty["status"], "unknown")
        self.assertEqual(empty["engines"], [])
        queued = summarize({"data": {"attributes": {"status": "queued", "stats": {}}}}, analysis=True)
        self.assertEqual(queued["status"], "queued")

    def test_multi_engine_results_preserve_malicious_suspicious_and_unsupported(self):
        data = {"data": {"attributes": {"last_analysis_date": 123,
            "last_analysis_stats": {"malicious": 1, "suspicious": 1, "undetected": 3, "type-unsupported": 2},
            "last_analysis_results": {"Engine A": {"category": "malicious", "result": "Ransom.Fixture"},
                                      "Engine B": {"category": "suspicious", "result": "Heuristic.Fixture"}}}}}
        result = summarize(data, analysis=False)
        self.assertEqual(result["stats"]["malicious"], 1)
        self.assertEqual(result["stats"]["type-unsupported"], 2)
        self.assertEqual(result["engines"][0]["result"], "Ransom.Fixture")

    def test_rejects_redirect_hosts_and_reports_auth_and_quota_without_leaking_key(self):
        with patch("hngoos_dm.virustotal.http.client.HTTPSConnection") as connect:
            for url in ("http://www.virustotal.com/files", "https://attacker.example/files",
                        "https://www.virustotal.com.attacker.example/files"):
                with self.assertRaises(VirusTotalError):
                    self.client.request("POST", url)
            connect.assert_not_called()
            for status in (301, 401, 403, 429, 503):
                response = MagicMock(status=status)
                response.read.return_value = b"{}"
                connect.return_value.getresponse.return_value = response
                with self.assertRaises(VirusTotalError) as error:
                    self.client.lookup("b"*64)
                self.assertNotIn(self.client.key, str(error.exception))

    def test_streamed_upload_sends_exact_multipart_and_auth_only_to_virustotal(self):
        content = b"test content, not a real user file"
        digest = hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"private name.bin"
            path.write_bytes(content)
            response = MagicMock(status=200)
            response.read.return_value = json.dumps({"data": {"id": "ok"}}).encode()
            connection = MagicMock()
            connection.getresponse.return_value = response
            with patch("hngoos_dm.virustotal.http.client.HTTPSConnection", return_value=connection):
                self.client.request("POST", API+"/files", path=path, expected_sha256=digest)
            body = b"".join(call.args[0] for call in connection.send.call_args_list)
            length = next(call.args[1] for call in connection.putheader.call_args_list if call.args[0] == "Content-Length")
            self.assertEqual(len(body), int(length))
            self.assertIn(content, body)
            self.assertNotIn(b"private name", body)
            self.assertNotIn(self.client.key.encode(), body)
            self.assertTrue(body.endswith(b"--\r\n"))
            connection.close.assert_called_once()

    def test_large_upload_url_is_validated_before_any_key_is_sent_to_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"large.bin"
            with path.open("wb") as output:
                output.truncate(33*1024*1024)
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
            with patch.object(self.client, "request", side_effect=[{"data": "https://attacker.example/upload"},
                         {"data": {"id": "fixture"}}]) as request:
                self.client.upload(path, digest, consent=True)
                self.assertEqual(request.call_args_list[0].args, ("GET", API+"/files/upload_url"))
            # The transport's host validation is also enforced for signed-in upload endpoints.
            with self.assertRaises(VirusTotalError):
                self.client.request("POST", "https://attacker.example/upload", path=path)
