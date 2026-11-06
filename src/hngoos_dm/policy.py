"""Shared bandwidth budget and persistent, conservative per-host concurrency."""

import threading
import time
from contextlib import contextmanager
from typing import ClassVar
from urllib.parse import urlsplit


class TransferCancelled(Exception):
    pass


class BandwidthBudget:
    MODES: ClassVar[dict] = {"maximum": 0, "medium": 4 * 1024 * 1024, "light": 512 * 1024}

    def __init__(self):
        self.lock = threading.Lock()
        self.rate = 0
        self.next_slot = time.monotonic()

    def configure(self, mode="maximum", bytes_per_second=None):
        with self.lock:
            self.rate = max(0, int(bytes_per_second if bytes_per_second is not None else self.MODES[mode]))
            self.next_slot = time.monotonic()

    def consume(self, amount, stop):
        with self.lock:
            if not self.rate:
                return
            now = time.monotonic()
            delay = max(0, self.next_slot - now)
            self.next_slot = max(now, self.next_slot) + amount / self.rate
        if stop.wait(delay):
            raise TransferCancelled()


class HostPolicy:
    def __init__(self, store, default_limit=32, recovery_seconds=300, recovery_successes=32):
        self.store = store
        self.condition = threading.Condition()
        self.limits = store.setting("host_limits", {})
        self.default_limit = default_limit
        self.in_use = {}
        self.cooldowns = {}
        self.recovery_seconds = recovery_seconds
        self.recovery_successes = recovery_successes
        self.recovery = store.setting("host_recovery", {})

    @staticmethod
    def key(url):
        parsed = urlsplit(url)
        return f"{parsed.hostname}:{parsed.port or (443 if parsed.scheme == 'https' else 80)}"

    def penalize(self, url, retry_after=1):
        host = self.key(url)
        with self.condition:
            self.limits[host] = max(1, self.limits.get(host, self.default_limit) // 2)
            self.cooldowns[host] = max(self.cooldowns.get(host, 0), time.monotonic() + retry_after)
            self.recovery[host] = {"since": time.time(), "successes": 0}
            self.store.set_setting("host_limits", dict(self.limits))
            self.store.set_setting("host_recovery", dict(self.recovery))
            self.condition.notify_all()

    def succeeded(self, url):
        """Recover one connection at a time, only after sustained successful transfers."""
        host = self.key(url)
        with self.condition:
            limit = self.limits.get(host, self.default_limit)
            if limit >= self.default_limit:
                return
            now = time.time()
            recovery = self.recovery.setdefault(host, {"since": now, "successes": 0})
            recovery["successes"] += 1
            # Restart the stability window if the machine clock moved backwards.
            recovery["since"] = min(recovery["since"], now)
            if now-recovery["since"] >= self.recovery_seconds and recovery["successes"] >= self.recovery_successes:
                self.limits[host] = min(self.default_limit, limit+1)
                self.recovery[host] = {"since": now, "successes": 0}
                self.store.set_setting("host_limits", dict(self.limits))
                self.condition.notify_all()
            self.store.set_setting("host_recovery", dict(self.recovery))

    @contextmanager
    def connection(self, url, stop):
        host = self.key(url)
        with self.condition:
            while (self.in_use.get(host, 0) >= self.limits.get(host, self.default_limit)
                   or self.cooldowns.get(host, 0) > time.monotonic()):
                if stop.is_set():
                    raise TransferCancelled()
                self.condition.wait(0.1)
            if stop.is_set():
                raise TransferCancelled()
            self.in_use[host] = self.in_use.get(host, 0) + 1
        try:
            yield
        finally:
            with self.condition:
                self.in_use[host] -= 1
                self.condition.notify_all()
