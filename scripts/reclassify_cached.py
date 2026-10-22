#!/usr/bin/env python3
"""Apply narrowly scoped type overrides to already verified FEC datasets.

This step runs before any network refresh, so rate-limited FEC requests cannot
delay these presentation-only corrections. All financial totals, source links,
original descriptions, and data-collection timestamps are preserved.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import refresh as core
import refresh_all as multi
from races import RACES

ROOT = Path(__file__).resolve().parents[1]


def apply_cached_overrides():
    changes = {}
    for district in RACES:
        path = multi.DATA_PATHS[district]
        if not path.exists():
            raise RuntimeError(f"Missing dashboard data file for {district}: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "not_initialized":
            continue
        if data.get("status") != "ok" or not isinstance(data.get("transactions"), list):
            raise RuntimeError(f"Unexpected archived data format: {district}")
        multi.set_race(district)
        count = 0
        spent_cents = 0
        for item in data["transactions"]:
            corrected = core.manual_spend_category(
                item.get("group_id"), item.get("candidate_id"),
                item.get("date"), item.get("description"))
            if corrected and item.get("type") != corrected:
                item["type"] = corrected
                count += 1
                spent_cents += item["amount_cents"]
        if not count:
            continue
        regenerated = core.summarize(
            data["transactions"], data["counts"].get("excluded", {}),
            data["counts"]["api_rows"], data["counts"]["pages"])
        # Category moves MUST be presentation-only.
        for field in ("totals", "daily", "groups"):
            if regenerated[field] != data[field]:
                raise RuntimeError(f"Unexpected financial changes in {district}: {field}")
        if sum(p["total"] for p in regenerated["pivot"]) != data["totals"]["all"]:
            raise RuntimeError(f"Category totals no longer reconcile in {district}")
        data["pivot"] = regenerated["pivot"]
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
        temp.replace(path)
        changes[district] = {"records": count, "amount_cents": spent_cents}
        print(f"UPDATED {district}: {count} category correction(s), "
              f"${spent_cents / 100:,.2f} reclassified; dollar totals unchanged.",
              flush=True)
    return changes


if __name__ == "__main__":
    apply_cached_overrides()
