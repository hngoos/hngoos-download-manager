"""HTTP downloader: bounded parallel ranges, durable resume, retries and triage."""

import concurrent.futures
import math
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

from .files import assemble_parts, category, checksums, deliver
from .policy import BandwidthBudget, HostPolicy, TransferCancelled
from .safety import filename_from_url, inspect_download, safe_filename, validate_url

BLOCK = 128 * 1024


class Paused(TransferCancelled):
    pass


def request(url, headers=None, proxy=None):
    from .network import open_url
    return open_url(urllib.request.Request(validate_url(url), headers={
        "User-Agent": "HDM/0.1", "Accept-Encoding": "identity", **(headers or {})
    }), timeout=15, proxy=proxy)


def strong_etag(value):
    return bool(value and not value.startswith("W/"))


def probe(url, proxy=None):
    try:
        response = request(url, {"Range": "bytes=0-0"}, **({"proxy": proxy} if proxy else {}))
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and exc.headers.get("Content-Range") == "bytes */0":
            return {"total": 0, "ranged": False, "etag": "", "modified": "", "empty": True}
        raise
    with response:
        ranged = response.status == 206
        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
            raise ValueError("Máy chủ bỏ qua yêu cầu không nén; không thể xác định byte an toàn.")
        if ranged:
            match = re.fullmatch(r"bytes 0-0/(\d+)", response.headers.get("Content-Range", ""))
            if not match:
                raise ValueError("Máy chủ trả Content-Range không hợp lệ.")
            total = int(match[1])
        else:
            total = int(response.headers.get("Content-Length", 0))
        return {"total": total, "ranged": ranged, "empty": response.headers.get("Content-Length") == "0",
                "filename": safe_filename(response.headers.get_filename()) if response.headers.get_filename() else "",
                "etag": response.headers.get("ETag", ""),
                "modified": response.headers.get("Last-Modified", "")}


class DownloadManager:
    def _request(self, url, headers=None):
        proxy = self.store.setting("proxy")
        return request(url, headers, **({"proxy": proxy} if proxy else {}))

    def _probe(self, url):
        proxy = self.store.setting("proxy")
        return probe(url, **({"proxy": proxy} if proxy else {}))

    def __init__(self, store, simultaneous=2):
        self.store = store
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=simultaneous)
        self.safety_pool = concurrent.futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="hdm-safety")
        self.active = {}
        self.lock = threading.RLock()
        self.closed = False
        self.store.recover()
        self.bandwidth = BandwidthBudget()
        self.bandwidth.configure(self.store.setting("bandwidth_mode", "maximum"))
        self.hosts = HostPolicy(store)
        self.relocations = {}
        self.scheduler_stop = threading.Event()
        self.scheduler = threading.Thread(target=self._schedule_loop, daemon=True)
        self.scheduler.start()

    def add(self, url, directory, filename, connections=32, expected_sha256="", start=True,
            mirrors=None, scheduled_at=0, expected_hashes=None):
        from urllib.parse import urlsplit

        from .cloud import resolve
        original_url = url
        if urlsplit(url).hostname in {"drive.google.com", "docs.google.com", "dropbox.com", "www.dropbox.com", "onedrive.live.com", "1drv.ms", "www.mediafire.com", "mediafire.com"}:
            proxy = self.store.setting("proxy")
            url = resolve(url, **({"proxy": proxy} if proxy else {}))
        validate_url(url)
        if expected_sha256 and not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256):
            raise ValueError("SHA-256 phải có đúng 64 ký tự hex.")
        expected_hashes = {key.lower(): value.lower() for key, value in (expected_hashes or {}).items()}
        for algorithm, value in expected_hashes.items():
            lengths = {"md5": 32, "sha1": 40, "sha256": 64, "sha512": 128}
            if algorithm not in lengths or not re.fullmatch(f"[a-fA-F0-9]{{{lengths[algorithm]}}}", value):
                raise ValueError("Thuật toán/mã băm mong đợi không hợp lệ.")
        expected_sha256 = expected_sha256 or expected_hashes.get("sha256", "")
        mirrors = list(dict.fromkeys(validate_url(value) for value in (mirrors or [])))
        if mirrors and not expected_sha256:
            raise ValueError("Tải mirror cần SHA-256 từ nguồn tin cậy để phát hiện nội dung khác nhau.")
        if self.store.setting("auto_category", False):
            directory = Path(directory) / category(filename)
        job = self.store.create(url, directory, safe_filename(filename), connections, expected_sha256)
        self.store.update(job["id"], mirrors=mirrors, scheduled_at=float(scheduled_at or 0),
                          expected_hashes=expected_hashes, original_url=original_url,
                          staging_directory=str(self.store.path.parent / "staging" / job["id"]),
                          state="scheduled" if scheduled_at else "paused")
        if start and not scheduled_at:
            self.start(job["id"])
        return job["id"]

    def set_bandwidth(self, mode):
        self.bandwidth.configure(mode)
        self.store.set_setting("bandwidth_mode", mode)

    def adopt_partial(self, url, partial, directory, filename, connections=32):
        """Verify the entire contiguous browser prefix, keep its original, then adopt it."""
        import hashlib
        partial = Path(partial).resolve()
        size = partial.stat().st_size
        info = self._probe(url)
        if not info["ranged"] or not strong_etag(info["etag"]) or not 0 < size < info["total"]:
            raise ValueError("Cần tệp dở là tiền tố liên tục, máy chủ hỗ trợ Range/ETag và tệp còn thiếu byte.")
        expected = f"bytes 0-{size-1}/{info['total']}"
        digest = hashlib.sha256()
        with partial.open("rb") as local, self._request(url, {"Range": f"bytes=0-{size-1}", "If-Match": info["etag"]}) as response:
            if (response.status != 206 or response.headers.get("Content-Range") != expected
                    or response.headers.get("ETag") != info["etag"]):
                raise ValueError("Không xác minh được tiền tố từ máy chủ.")
            count = 0
            for block in iter(lambda: response.read(BLOCK), b""):
                if local.read(len(block)) != block:
                    raise ValueError("Phần trình duyệt đã tải khác nội dung máy chủ; không tiếp quản.")
                count += len(block)
                digest.update(block)
            if count != size:
                raise ValueError("Phản hồi xác minh không đủ byte.")
        job_id = self.add(url, directory, filename, connections, start=False)
        job = self.store.get(job_id)
        staging = self.staging_path(job)
        staging.mkdir(parents=True, exist_ok=True)
        try:
            with partial.open("rb") as source, (staging/"0.part").open("xb") as output:
                shutil.copyfileobj(source, output, BLOCK)
                output.flush()
                os.fsync(output.fileno())
            if checksums(staging/"0.part", ("sha256",))["sha256"] != digest.hexdigest():
                raise ValueError("Tệp dở bị thay đổi trong lúc tiếp quản.")
            chunk_size = max(1024*1024, math.ceil((info["total"]-size)/(connections*8)))
            ranges = [(0, size-1)] + [(start, min(start+chunk_size, info["total"])-1)
                                      for start in range(size, info["total"], chunk_size)]
            self.store.set_chunks(job_id, ranges)
            self.store.mark_chunk(job_id, 0)
            self.store.update(job_id, **info, downloaded=size)
            self.store.event(job_id, "adopt", "Đã xác minh toàn bộ tiền tố tải dở; bản gốc được giữ lại")
            self.start(job_id)
            return job_id
        except (OSError, ValueError) as exc:
            self.store.update(job_id, state="error", error=str(exc))
            raise

    def _schedule_loop(self):
        while not self.scheduler_stop.wait(0.5):
            self._schedule_once(time.time())

    def _schedule_once(self, now):
        for job in self.store.all():
            scheduled = job["state"] == "scheduled" and job.get("scheduled_at", 0) <= now
            retry = (self.store.setting("retry_failed", True) and job["state"] == "error"
                     and job.get("retry_at", 0) and job["retry_at"] <= now)
            if scheduled or retry:
                self.start(job["id"], automatic=True)

    def maintain_history(self):
        """History is a journal. Only explicit user actions remove its records."""

    def relocate(self, job_id, directory):
        directory = str(Path(directory).expanduser().resolve())
        with self.lock:
            if job_id in self.active:
                self.relocations[job_id] = directory
                self.active[job_id].set()
                return
            self._relocate(job_id, directory)

    def _relocate(self, job_id, directory):
        job = self.store.get(job_id)
        if Path(directory).resolve() == Path(job["directory"]).resolve():
            return
        if job["state"] in {"complete", "quarantined"}:
            raise ValueError("Tệp đã hoàn tất. Di chuyển tệp từ thư mục lưu thay vì đổi lượt tải.")
        if job.get("staging_directory"):
            self.store.update(job_id, directory=directory)
            self.store.event(job_id, "relocate", "Đã đổi nơi nhận tệp; phần tải dở vẫn giữ trong bộ nhớ đệm cục bộ")
            return
        old_parent = (Path(job["directory"]) / ".hngoos").resolve()
        new_parent = (Path(directory) / ".hngoos").resolve()
        source, target = (old_parent / job_id).resolve(), (new_parent / job_id).resolve()
        if source.parent != old_parent or target.parent != new_parent:
            raise ValueError("Đường dẫn staging không hợp lệ.")
        if source.exists():
            new_parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise ValueError("Nơi lưu mới đã có dữ liệu cho lượt tải này.")
            shutil.move(str(source), str(target))
        self.store.update(job_id, directory=directory)
        self.store.event(job_id, "relocate", "Đã chuyển dữ liệu tải dở sang nơi lưu mới")

    def start(self, job_id, automatic=False):
        with self.lock:
            if self.closed or job_id in self.active:
                return
            if self.store.get(job_id)["state"] in {"complete", "quarantined"}:
                return
            stop = threading.Event()
            self.active[job_id] = stop
            changes = {} if automatic else {"retry_count": 0}
            self.store.update(job_id, state="queued", error="", retry_at=0, **changes)
            self.pool.submit(self._run, job_id, stop)

    def pause(self, job_id):
        with self.lock:
            if job_id in self.active:
                self.active[job_id].set()
            elif self.store.get(job_id)["state"] == "scheduled":
                self.store.update(job_id, state="paused", scheduled_at=0)
            elif self.store.get(job_id)["state"] == "error":
                self.store.update(job_id, state="paused", retry_at=0)

    def replace_url(self, job_id, url):
        validate_url(url)
        with self.lock:
            if job_id in self.active:
                raise ValueError("Hãy tạm dừng và đợi lượt tải dừng hẳn trước khi đổi link.")
            changes = {"url": url, "state": "paused", "error": ""}
            if self.store.get(job_id)["url"] != url:
                # ETags identify versions of one URL, not unrelated resources.
                # Force fresh ranges even if the replacement reuses the same tag.
                changes.update(etag="", modified="", ranged=False, downloaded=0,
                               speed=0, chunk_sources={}, mirror_fallback=False)
            self.store.update(job_id, **changes)

    def close(self):
        with self.lock:
            self.closed = True
            self.scheduler_stop.set()
            for stop in self.active.values():
                stop.set()
        self.scheduler.join(timeout=35)
        self.pool.shutdown(wait=False)
        self.safety_pool.shutdown(wait=False, cancel_futures=True)

    def _run(self, job_id, stop):
        try:
            self._download(job_id, stop)
        except TransferCancelled:
            self.store.update(job_id, state="paused", speed=0)
        except Exception as exc:  # noqa: BLE001 -- Persist job errors at the worker boundary.
            count = self.store.get(job_id).get("retry_count", 0)
            transient = (isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError))
                         and not isinstance(exc, (PermissionError, FileNotFoundError)))
            if isinstance(exc, urllib.error.HTTPError):
                transient = exc.code in {408, 429, 500, 502, 503, 504}
            retry = self.store.setting("retry_failed", True) and transient and count < 3
            self.store.update(job_id, state="error", error=str(exc), speed=0,
                              retry_count=count+1 if retry else count,
                              retry_at=time.time()+30*2**count if retry else 0)
        finally:
            self.store.update(job_id, active_connections=0)
            with self.lock:
                self.active.pop(job_id, None)
                destination = self.relocations.pop(job_id, None)
            if destination and not self.closed:
                try:
                    self._relocate(job_id, destination)
                    self.start(job_id)
                except (ValueError, OSError) as exc:
                    self.store.update(job_id, state="error", error=str(exc))

    @staticmethod
    def staging_path(job):
        return Path(job.get("staging_directory") or Path(job["directory"])/".hngoos"/job["id"])

    def _download(self, job_id, stop):
        if stop.is_set():
            raise Paused()
        job = self.store.get(job_id)
        self.store.update(job_id, state="downloading", speed=0)
        info = self._probe(job["url"])
        suggested = info.pop("filename", "")
        if suggested and job["filename"] in {"download.bin", filename_from_url(job["url"])}:
            job["filename"] = suggested
            self.store.update(job_id, filename=suggested)
        sources = [(job["url"], info)]
        if job.get("expected_sha256") and not job.get("mirror_fallback") and strong_etag(info["etag"]):
            for mirror in job.get("mirrors", []):
                if stop.is_set():
                    raise Paused()
                try:
                    mirror_info = self._probe(mirror)
                    if (mirror_info["ranged"] and strong_etag(mirror_info["etag"])
                            and mirror_info["total"] == info["total"]):
                        sources.append((mirror, mirror_info))
                    else:
                        self.store.event(job_id, "mirror_rejected", "Mirror không hỗ trợ Range/ETag/kích thước phù hợp")
                except (OSError, ValueError) as exc:
                    self.store.event(job_id, "mirror_rejected", f"Mirror không truy cập được: {type(exc).__name__}")
        rejected_sources = set()
        source_lock = threading.Lock()
        folder = Path(job["directory"]).expanduser().resolve()
        staging = self.staging_path(job)
        staging.mkdir(parents=True, exist_ok=True)
        chunks = self.store.chunks(job_id)
        # Strong ETag and length establish identity; no validator means restart safely.
        reusable = (info["ranged"] and job["ranged"] and strong_etag(info["etag"])
                    and info["etag"] == job["etag"] and info["total"] == job["total"])
        if not reusable or not chunks:
            for item in staging.glob("*.part"):
                item.unlink()
            if info["ranged"] and info["total"]:
                chunk_size = max(1024 * 1024, math.ceil(info["total"] / (job["connections"] * 8)))
                ranges = [(start, min(start + chunk_size, info["total"]) - 1)
                          for start in range(0, info["total"], chunk_size)]
            else:
                ranges = [(0, info["total"] - 1)]
            self.store.set_chunks(job_id, ranges)
            chunks = self.store.chunks(job_id)
        self.store.update(job_id, **info)
        existing = sum(part.stat().st_size for part in staging.glob("*.part"))
        if info["total"] and shutil.disk_usage(staging).free < max(0, info["total"]*2-existing) + 16*1024*1024:
            raise OSError("Không đủ dung lượng trống cho các phần tải và tệp ghép; hãy đổi nơi lưu hoặc dọn ổ đĩa.")
        progress = {}
        chunk_sources = job.get("chunk_sources", {}) if reusable else {}
        for idx, start, end, done in chunks:
            part = staging / f"{idx}.part"
            size = part.stat().st_size if part.exists() else 0
            progress[idx] = size if (done or reusable) and 0 <= size <= end-start+1 else 0
        progress_lock = threading.Lock()
        began = time.monotonic()
        initial = sum(progress.values())
        last_write = [0.0]
        active_lock = threading.Lock()
        counts = {"active": 0, "peak": 0}

        @contextmanager
        def connection(source_url):
            with self.hosts.connection(source_url, stop):
                with active_lock:
                    counts["active"] += 1
                    if counts["active"] > counts["peak"]:
                        counts["peak"] = counts["active"]
                        self.store.update(job_id, active_connections=counts["active"], peak_connections=counts["peak"])
                try:
                    yield
                finally:
                    with active_lock:
                        counts["active"] -= 1

        def report(idx, count, force=False):
            with progress_lock:
                progress[idx] = count
                now = time.monotonic()
                if force or now - last_write[0] > 0.4:
                    total = sum(progress.values())
                    with active_lock:
                        active, peak = counts["active"], counts["peak"]
                    self.store.update(job_id, downloaded=total,
                                      speed=max(0, total-initial)/max(0.1, now-began),
                                      active_connections=active, peak_connections=peak)
                    last_write[0] = now

        def transfer(chunk):
            idx, start, end, done = chunk
            target = staging / f"{idx}.part"
            if done and progress[idx] == end-start+1:
                return
            if info["empty"]:
                with target.open("wb") as output:
                    output.flush()
                    os.fsync(output.fileno())
                self.store.mark_chunk(job_id, idx)
                return
            for attempt in range(5):
                if stop.is_set():
                    raise Paused()
                with source_lock:
                    available = [source for source in sources if source[0] not in rejected_sources]
                    source_url, source_info = available[(idx + attempt) % len(available)]
                headers = {}
                offset = 0
                if (info["ranged"] and strong_etag(source_info["etag"]) and len(sources) == 1
                        and target.exists() and target.stat().st_size <= end-start+1):
                    offset = target.stat().st_size
                if offset > 0 and offset == end-start+1:
                    self.store.mark_chunk(job_id, idx)
                    report(idx, offset, True)
                    return
                if info["ranged"]:
                    headers["Range"] = f"bytes={start+offset}-{end}"
                if strong_etag(source_info["etag"]):
                    headers["If-Match"] = source_info["etag"]
                try:
                    with connection(source_url), self._request(source_url, headers) as response:
                        if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                            raise ValueError("Máy chủ trả nội dung đã nén ngoài dự kiến.")
                        if info["ranged"]:
                            wanted = f"bytes {start+offset}-{end}/{info['total']}"
                            if response.status != 206 or response.headers.get("Content-Range") != wanted:
                                raise ValueError("Máy chủ không giữ đúng Range; dừng để tránh hỏng tệp.")
                        if strong_etag(source_info["etag"]) and response.headers.get("ETag") != source_info["etag"]:
                            raise ValueError("ETag đã thay đổi hoặc bị thiếu trong lúc tải.")
                        count = offset
                        with target.open("ab" if offset else "wb") as output:
                            while True:
                                if stop.is_set():
                                    raise Paused()
                                block = response.read(BLOCK)
                                if not block:
                                    break
                                self.bandwidth.consume(len(block), stop)
                                count += len(block)
                                if info["total"] and count > end-start+1:
                                    raise ValueError("Máy chủ gửi nhiều byte hơn kích thước khai báo.")
                                output.write(block)
                                report(idx, count)
                            output.flush()
                            os.fsync(output.fileno())
                        if info["total"] and count != end-start+1:
                            raise OSError("Kết nối đóng khi tệp chưa đủ byte.")
                    self.store.mark_chunk(job_id, idx)
                    if len(sources) > 1:
                        with source_lock:
                            chunk_sources[str(idx)] = source_url
                            self.store.update(job_id, chunk_sources=dict(chunk_sources))
                    self.hosts.succeeded(source_url)
                    report(idx, count)
                    return
                except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
                    report(idx, 0, True)
                    if source_url != job["url"]:
                        with source_lock:
                            rejected_sources.add(source_url)
                        self.store.event(job_id, "mirror_rejected", f"Đã loại mirror lỗi: {type(exc).__name__}")
                        continue
                    if isinstance(exc, ValueError):
                        target.unlink(missing_ok=True)
                        raise
                    if isinstance(exc, urllib.error.HTTPError) and exc.code not in {408, 429, 500, 502, 503, 504}:
                        raise
                    if attempt == 4:
                        raise
                    delay = min(16, 2 ** attempt)
                    if isinstance(exc, urllib.error.HTTPError):
                        retry_after = exc.headers.get("Retry-After", "")
                        if retry_after.isdigit():
                            delay = min(30, max(delay, int(retry_after)))
                        if exc.code in {429, 503}:
                            self.hosts.penalize(source_url, delay)
                    if stop.wait(delay):
                        raise Paused() from exc
            raise OSError("Đã hết số lần thử tải khối từ các nguồn.")

        # Without a strong validator, multiple HTTP responses cannot prove identical content.
        workers = job["connections"] if info["ranged"] and strong_etag(info["etag"]) else 1
        self.store.update(job_id, worker_limit=workers, safety_note="Chờ kiểm tra")
        if info["ranged"] and not strong_etag(info["etag"]):
            self.store.set_chunks(job_id, [(0, info["total"]-1)])
            chunks = self.store.chunks(job_id)
            progress.clear()
            progress[0] = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(transfer, chunk) for chunk in chunks]
            try:
                for future in concurrent.futures.as_completed(futures):
                    future.result()
            except Exception:
                stop.set()
                for future in futures:
                    future.cancel()
                raise
        if stop.is_set():
            raise Paused()
        self.store.update(job_id, state="verifying", speed=0, downloaded=sum(progress.values()))
        assembled = staging / "assembled.tmp"
        digests = assemble_parts((staging / f"{idx}.part" for idx, *_ in chunks), assembled, stop)
        digest = digests["sha256"]
        if stop.is_set():
            raise Paused()
        if job["expected_sha256"] and digest != job["expected_sha256"] and len(sources) > 1:
            self.store.event(job_id, "mirror_integrity", "SHA-256 sai: tải lại các khối từ mirror, giữ khối đã lấy từ nguồn chính")
            self.store.update(job_id, mirror_fallback=True)
            with self.store.connect() as db:
                for idx, *_ in chunks:
                    if chunk_sources.get(str(idx)) != job["url"]:
                        db.execute("UPDATE chunks SET done=0 WHERE job=? AND idx=?", (job_id, idx))
                        (staging/f"{idx}.part").unlink(missing_ok=True)
            assembled.unlink()
            return self._download(job_id, stop)
        auto_scan = self.store.setting("auto_defender", False) and os.name == "nt"
        inspection = inspect_download(assembled, job["filename"],
            high_security=self.store.setting("high_security", False), antivirus=False)
        reasons = inspection["reasons"]
        if stop.is_set():
            raise Paused()
        if job["expected_sha256"] and digest != job["expected_sha256"]:
            reasons.append("SHA-256 không trùng mã băm mong đợi")
        for algorithm, expected in job.get("expected_hashes", {}).items():
            if digests[algorithm] != expected:
                reasons.append(f"{algorithm.upper()} không trùng mã băm mong đợi")
        suffix = ".chuakiemtra" if reasons else ""
        filename = job["filename"] + suffix
        candidate = deliver(assembled, folder, filename, stop)
        size = candidate.stat().st_size
        if os.name == "nt":
            try:
                Path(str(candidate) + ":Zone.Identifier").write_text("[ZoneTransfer]\nZoneId=3\n")
            except OSError:
                pass  # FAT/exFAT and some shares do not support alternate data streams.
        self.store.update(job_id, state="quarantined" if reasons else "complete", downloaded=size,
                          total=size, speed=0, sha256=digest, checksums=digests,
                          output=str(candidate), error="; ".join(reasons),
                          safety_note="Cách ly" if reasons else inspection["safety_note"],
                          safety_check={"provider": "defender", "status": "scanning"} if auto_scan else {})
        if auto_scan:
            self.safety_pool.submit(self._scan_completed, job_id, candidate, digest, bool(reasons))
        elif not reasons:
            self._extract_completed(job_id, candidate)
        for part in staging.glob("*.part"):
            part.unlink()
        try:
            staging.rmdir()
        except OSError:
            pass

    def _scan_completed(self, job_id, candidate, digest, quarantined):
        from .safety import scan_defender, sha256_file
        scan_risk = False
        try:
            result = scan_defender(candidate, stop=self.scheduler_stop)
            status = "clean" if result.returncode == 0 else "threat" if result.returncode == 2 else "error"
            detail = (result.stdout or "")+"\n"+(result.stderr or "")
            if self.closed:
                return
            scan_risk = result.returncode != 0
            if sha256_file(candidate) != digest:
                status, detail = "error", "Tệp thay đổi trong lúc kiểm tra; hãy quét lại."
                scan_risk = False
        except TransferCancelled:
            return
        except Exception as error:  # noqa: BLE001 -- A failed optional scan never becomes a clean result.
            status, detail = "error", str(error)
            scan_risk = False
        try:
            if self.closed:
                return
            job = self.store.get(job_id)
            if job.get("output") != str(candidate):
                return
            if scan_risk and not quarantined:
                candidate = deliver(candidate, candidate.parent, candidate.name+".chuakiemtra", self.scheduler_stop)
                self.store.update(job_id, state="quarantined", output=str(candidate), safety_note="Cách ly",
                                  error="Defender phát hiện rủi ro hoặc chưa hoàn tất quét; cần kiểm tra trước khi mở")
            self.store.update(job_id, safety_check={"provider": "defender", "status": status,
                "detail": detail, "checked_at": time.time()})
            if status == "clean" and not quarantined and not self.closed:
                self._extract_completed(job_id, candidate)
        except (KeyError, TransferCancelled):
            pass  # Removing a journal entry while its scan runs must not recreate it.
        except OSError as error:
            try:
                self.store.update(job_id, safety_check={"provider": "defender", "status": "error",
                    "detail": str(error), "checked_at": time.time()})
            except KeyError:
                pass

    def _extract_completed(self, job_id, candidate):
        if self.store.setting("auto_extract", False) and candidate.suffix.lower() == ".zip":
            from .extraction import extract_zip
            try:
                extracted = extract_zip(candidate, candidate.with_name(candidate.stem+"-extracted"))
                self.store.event(job_id, "extracted", str(extracted))
            except (OSError, ValueError) as exc:
                self.store.event(job_id, "extraction_error", str(exc))
