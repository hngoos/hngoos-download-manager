"""Explicit VirusTotal v3 operations. No embedded key and no automatic file upload."""

import hashlib
import http.client
import json
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

API = "https://www.virustotal.com/api/v3"
MAX_UPLOAD = 650*1024*1024


class VirusTotalError(ValueError):
    pass


class VirusTotalClient:
    def __init__(self, key):
        self.key = key.strip()
        if not re.fullmatch(r"[a-fA-F0-9]{64}", self.key):
            raise VirusTotalError("Enter your VirusTotal API key (64 hexadecimal characters).")

    def request(self, method, url, *, path=None, expected_sha256=None):
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "www.virustotal.com"
                or parsed.port not in {None, 443} or parsed.username or parsed.password):
            raise VirusTotalError("Untrusted VirusTotal endpoint.")
        connection = http.client.HTTPSConnection(parsed.hostname, timeout=60)
        location = parsed.path+("?"+parsed.query if parsed.query else "")
        try:
            if path is None:
                connection.request(method, location, headers={"x-apikey": self.key, "Accept": "application/json"})
            else:
                # A single open handle supplies the exact bytes hashed and submitted; no shell or browser automation.
                boundary = "HDM"+uuid.uuid4().hex
                prefix = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                          'filename="hdm-file.bin"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
                suffix = f"\r\n--{boundary}--\r\n".encode()
                with Path(path).open("rb") as stream:
                    import os
                    length = os.fstat(stream.fileno()).st_size
                    if not 0 < length <= MAX_UPLOAD:
                        raise VirusTotalError("VirusTotal uploads must be between 1 byte and 650 MB.")
                    connection.putrequest(method, location)
                    connection.putheader("x-apikey", self.key)
                    connection.putheader("Content-Type", "multipart/form-data; boundary="+boundary)
                    connection.putheader("Content-Length", str(length+len(prefix)+len(suffix)))
                    connection.endheaders()
                    connection.send(prefix)
                    remaining = length
                    digest = hashlib.sha256()
                    while remaining:
                        block = stream.read(min(1024*1024, remaining))
                        if not block:
                            raise VirusTotalError("File changed during upload. Scan again.")
                        connection.send(block)
                        digest.update(block)
                        remaining -= len(block)
                    if digest.hexdigest() != expected_sha256:
                        raise VirusTotalError("File changed during upload. Scan again.")
                    connection.send(suffix)
            response = connection.getresponse()
            data = response.read(4*1024*1024+1)
            if response.status == 404:
                return None
            if response.status in {401, 403}:
                raise VirusTotalError("VirusTotal API key rejected or access unavailable.")
            if response.status == 429:
                raise VirusTotalError("VirusTotal rate limit reached. Wait before checking again.")
            if not 200 <= response.status < 300:
                raise VirusTotalError(f"VirusTotal request failed (HTTP {response.status}).")
            if len(data) > 4*1024*1024:
                raise VirusTotalError("VirusTotal response exceeds the size limit.")
            return json.loads(data)
        finally:
            connection.close()

    def lookup(self, sha256):
        if not re.fullmatch(r"[a-f0-9]{64}", sha256):
            raise VirusTotalError("Invalid SHA-256.")
        data = self.request("GET", API+"/files/"+sha256)
        return summarize(data, analysis=False) if data else None

    def upload(self, path, expected_sha256, *, consent=False):
        if not consent:
            raise VirusTotalError("File upload requires explicit consent.")
        path = Path(path)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_UPLOAD:
            raise VirusTotalError("VirusTotal uploads must be between 1 byte and 650 MB.")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != expected_sha256:
                raise VirusTotalError("File changed after checking. Scan again before upload.")
        url = API+"/files"
        if path.stat().st_size > 32*1024*1024:
            url = self.request("GET", API+"/files/upload_url")["data"]
        data = self.request("POST", url, path=path, expected_sha256=expected_sha256)
        identifier = data["data"]["id"]
        if not re.fullmatch(r"[A-Za-z0-9_=:-]+", identifier):
            raise VirusTotalError("Invalid analysis identifier.")
        return identifier

    def analysis(self, identifier):
        if not re.fullmatch(r"[A-Za-z0-9_=:-]+", identifier):
            raise VirusTotalError("Invalid analysis identifier.")
        data = self.request("GET", API+"/analyses/"+identifier)
        if data is None:
            raise VirusTotalError("Analysis not available yet.")
        return summarize(data, analysis=True)


def summarize(data, *, analysis):
    attributes = data["data"]["attributes"]
    stats = attributes.get("stats" if analysis else "last_analysis_stats", {})
    results = attributes.get("results" if analysis else "last_analysis_results", {})
    return {"status": attributes.get("status", "completed") if analysis else
            ("completed" if stats else "unknown"), "stats": stats,
            "date": attributes.get("date" if analysis else "last_analysis_date"),
            "engines": [{"name": name, "category": item.get("category", "unknown"),
                         "result": item.get("result") or ""} for name, item in sorted(results.items())]}
