"""Adaptive scheduling preserves durable byte ownership across tail splits."""

import tempfile
import unittest
from itertools import pairwise
from pathlib import Path

from hngoos_dm.store import Store


class ScheduleTests(unittest.TestCase):
    def test_initial_ranges_bound_request_count_and_preserve_every_byte(self):
        from hngoos_dm.transfer_schedule import initial_ranges

        for total in (1, 1048576, 134217728, 8589934593):
            for connections in (1, 2, 16, 32):
                with self.subTest(total=total, connections=connections):
                    ranges = initial_ranges(total, connections)
                    self.assertLessEqual(len(ranges), connections*2)
                    self.assertEqual(ranges[0][0], 0)
                    self.assertEqual(ranges[-1][1], total-1)
                    self.assertEqual(sum(end-start+1 for start, end in ranges), total)
                    self.assertTrue(all(first[1]+1 == second[0] for first, second in pairwise(ranges)))

    def test_adopted_prefix_planning_keeps_the_remaining_byte_offset(self):
        from hngoos_dm.transfer_schedule import initial_ranges

        ranges = initial_ranges(134217728, 16, start=1048577)
        self.assertEqual(ranges[0][0], 1048577)
        self.assertEqual(ranges[-1][1], 134217727)
        self.assertEqual(sum(end-start+1 for start, end in ranges), 134217728-1048577)
        self.assertEqual(initial_ranges(100, 16, start=100), [])

    def test_split_preserves_stable_ids_and_complete_ordered_coverage(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory)/"db")
            row = store.create("https://example.com/data", directory, "data")
            store.set_chunks(row["id"], [(0, 99), (100, 199)])
            child = store.split_chunk(row["id"], 0, 60)
            self.assertEqual(child, (2, 60, 99, 0))
            self.assertEqual(sorted(store.chunks(row["id"]), key=lambda item: item[1]),
                             [(0, 0, 59, 0), (2, 60, 99, 0), (1, 100, 199, 0)])
            with self.assertRaises(ValueError):
                store.split_chunk(row["id"], 0, 100)
            self.assertEqual(len(store.chunks(row["id"])), 3)

    def test_speed_probe_retains_useful_connections_and_rejects_flat_throughput(self):
        from hngoos_dm.transfer_schedule import AdaptiveConnections
        policy = AdaptiveConnections(32, now=0)
        self.assertEqual(policy.target, 4)
        self.assertEqual(policy.sample(1, 1000), 8)
        self.assertEqual(policy.sample(2, 3000), 16)
        self.assertEqual(policy.sample(3, 5000), 8)
        self.assertEqual(policy.sample(3.1, 5200), 8)

    def test_zero_byte_source_can_probe_up_to_its_connection_limit(self):
        from hngoos_dm.transfer_schedule import AdaptiveConnections
        policy = AdaptiveConnections(32, now=0)
        for second in (1, 2, 3):
            policy.sample(second, 0)
        self.assertEqual(policy.target, 32)
        self.assertEqual(policy.sample(4, 1024, cap=2), 2)
