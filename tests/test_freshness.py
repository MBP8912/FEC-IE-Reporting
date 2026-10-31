import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_freshness
import refresh_all


class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 31, 14, tzinfo=timezone.utc)
        self.data = {"status": "ok", "generated_at": "2026-10-31T13:00:00+00:00"}
        self.recent = {"status": "ok", "checked_at": self.data["generated_at"],
                       "source_data_generated_at": self.data["generated_at"]}

    def test_recent_completed_snapshot_is_fresh(self):
        self.assertEqual(check_freshness.problems(self.data, self.recent, self.now), [])

    def test_recent_receipt_check_does_not_hide_stale_source(self):
        self.data["generated_at"] = "2026-10-30T13:00:00+00:00"
        self.assertTrue(check_freshness.problems(self.data, self.recent, self.now))

    def test_old_or_unknown_scan_start_is_not_current(self):
        for start in (None, "2026-10-30T13:00:00+00:00"):
            self.data["fetch"] = {"scan_started_at": start}
            self.assertTrue(check_freshness.problems(self.data, self.recent, self.now))

    def test_partial_receipts_are_not_current(self):
        self.recent.update(status="partial", unresolved_recent_items=1)
        self.assertTrue(check_freshness.problems(self.data, self.recent, self.now))

    def test_incomplete_ingestion_exits_nonzero_and_keeps_checkpoint(self):
        state = refresh_all.new_state()
        with patch.object(refresh_all, "read_state", return_value=state), \
             patch.object(refresh_all, "capture_pages", return_value=False), \
             patch.object(refresh_all, "save_state") as save:
            self.assertEqual(refresh_all.main(), 2)
            save.assert_not_called()

    def test_rate_limit_preserves_buffer_and_does_not_publish(self):
        state = refresh_all.new_state()
        state["rows"] = [{"sub_id": "buffered"}]
        state["cursor"] = {"last_index": "123"}
        with patch.object(refresh_all.core, "request_json", side_effect=RuntimeError("FEC HTTP 429")), \
             patch.object(refresh_all, "save_state") as save, \
             patch.object(refresh_all, "finalize_one_race") as finalize:
            self.assertFalse(refresh_all.capture_pages(state, "DEMO_KEY", 22))
        self.assertEqual(state["rows"], [{"sub_id": "buffered"}])
        self.assertEqual(state["cursor"], {"last_index": "123"})
        finalize.assert_not_called()
        save.assert_called_once_with(state)
