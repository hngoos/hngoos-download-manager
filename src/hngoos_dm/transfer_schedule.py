"""Throughput probes and work stealing for validated, durable HTTP ranges."""

import concurrent.futures
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from .policy import TransferCancelled


def initial_ranges(total, connections, start=0):
    """Keep request overhead bounded; idle workers can split remaining tails later."""
    remaining = total-start
    if remaining <= 0:
        return []
    size = max(1024*1024, (remaining+connections*2-1)//(connections*2))
    return [(offset, min(offset+size, total)-1) for offset in range(start, total, size)]


class AdaptiveConnections:
    def __init__(self, maximum, now=None):
        self.maximum, self.target = maximum, min(4, maximum)
        self.time = time.monotonic() if now is None else now
        self.bytes, self.rate, self.hold_until = 0, 0, 0
        self.probing = False

    def sample(self, now, downloaded, cap=None):
        cap = min(self.maximum, cap if cap is not None else self.maximum)
        self.target = max(1, min(self.target, cap))
        elapsed = now-self.time
        if elapsed < 1:
            return self.target
        rate = max(0, downloaded-self.bytes)/elapsed
        if self.probing and self.rate and rate < self.rate*1.1:
            self.target = max(1, self.target//2)
            self.hold_until = now+5
            self.probing = False
        elif now >= self.hold_until and self.target < cap:
            self.target = min(cap, self.target*2)
            self.probing = True
        self.time, self.bytes, self.rate = now, downloaded, rate
        return self.target


@dataclass
class Range:
    idx: int
    start: int
    end: int
    done: int = 0
    committed: int = 0
    lock: object = field(default_factory=threading.RLock)

    def remaining(self):
        with self.lock:
            return max(0, self.end-self.start+1-self.committed)


def run_ranges(tasks, transfer, stop, maximum, split, downloaded, cap):
    pending, active = deque(tasks), {}
    policy = AdaptiveConnections(maximum)
    with concurrent.futures.ThreadPoolExecutor(max_workers=maximum) as pool:
        try:
            while pending or active:
                if stop.is_set():
                    raise TransferCancelled()
                target = policy.sample(time.monotonic(), downloaded(), cap())
                while pending and len(active) < target:
                    task = pending.popleft()
                    active[pool.submit(transfer, task)] = task
                if not pending and len(active) < target and maximum > 1:
                    for task in sorted(active.values(), key=lambda task: task.remaining(), reverse=True):
                        child = split(task)
                        if child is not None:
                            pending.append(child)
                            break
                if pending and len(active) < target:
                    continue
                done, _ = concurrent.futures.wait(active, timeout=.1, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    active.pop(future)
                    future.result()
        except Exception:
            stop.set()
            for future in active:
                future.cancel()
            raise
