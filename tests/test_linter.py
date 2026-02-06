from dataclasses import dataclass
from datetime import datetime
import unittest

from lifeos.linter import check_overlaps


@dataclass
class EventPayload:
    id: str
    start_time: datetime
    end_time: datetime


def make_event(event_id: str, start_hour: int, start_minute: int, end_hour: int, end_minute: int) -> EventPayload:
    return EventPayload(
        id=event_id,
        start_time=datetime(2024, 1, 1, start_hour, start_minute),
        end_time=datetime(2024, 1, 1, end_hour, end_minute),
    )


class CheckOverlapsTests(unittest.TestCase):
    def test_adjacent_sorted_events_overlap_is_detected(self) -> None:
        event_a = make_event("A", 9, 0, 10, 0)
        event_b = make_event("B", 9, 30, 10, 30)

        diagnostics = check_overlaps([event_a, event_b])

        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].event_id, "B")
        self.assertEqual(diagnostics[0].start, datetime(2024, 1, 1, 9, 30))
        self.assertEqual(diagnostics[0].end, datetime(2024, 1, 1, 10, 0))

    def test_longest_active_interval_detects_late_overlap(self) -> None:
        event_a = make_event("A", 9, 0, 12, 0)
        event_b = make_event("B", 10, 0, 11, 0)
        event_c = make_event("C", 11, 30, 12, 30)

        diagnostics = check_overlaps([event_a, event_b, event_c])

        self.assertEqual(len(diagnostics), 2)
        self.assertEqual([diag.event_id for diag in diagnostics], ["B", "C"])
        self.assertEqual(diagnostics[1].start, datetime(2024, 1, 1, 11, 30))
        self.assertEqual(diagnostics[1].end, datetime(2024, 1, 1, 12, 0))

    def test_non_overlapping_chain_has_no_false_positives(self) -> None:
        event_a = make_event("A", 9, 0, 10, 0)
        event_b = make_event("B", 10, 0, 11, 0)
        event_c = make_event("C", 11, 0, 12, 0)

        diagnostics = check_overlaps([event_a, event_b, event_c])

        self.assertEqual(diagnostics, [])


if __name__ == "__main__":
    unittest.main()
