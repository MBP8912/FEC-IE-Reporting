#!/usr/bin/env python3
"""Report stale live snapshots independently of safe deployment/archiving."""
import json
import sys
from datetime import datetime, timedelta, timezone

from races import RACE_CODES
from verify_site import read


def problems(data, recent, now, max_age_hours=3):
    errors = []
    stamps = {"completed scan": data.get("generated_at"),
              "receipt check": recent.get("checked_at")}
    fetch = data.get("fetch", {})
    if "scan_started_at" in fetch:
        stamps["scan start"] = fetch["scan_started_at"]
    for label, value in stamps.items():
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("missing timezone")
            age = now - stamp
            if age > timedelta(hours=max_age_hours) or age < -timedelta(minutes=5):
                errors.append(f"{label} outside freshness window: {value}")
        except (AttributeError, TypeError, ValueError):
            errors.append(f"{label} timestamp unknown or invalid")
    if data.get("status") != "ok" or recent.get("status") != "ok":
        errors.append("source or receipt feed is not complete")
    if recent.get("unresolved_recent_items", 0):
        errors.append("unresolved recent receipt timestamps")
    if recent.get("source_data_generated_at") != data.get("generated_at"):
        errors.append("receipt feed uses a different source snapshot")
    return errors


def main():
    now = datetime.now(timezone.utc)
    failures = []
    for race in RACE_CODES:
        data = json.loads(read(f"{race}/data/data.json"))
        recent = json.loads(read(f"{race}/data/recent48.json"))
        issues = problems(data, recent, now)
        if issues:
            failures.append(race)
            print(f"::error::{race}: " + "; ".join(issues), flush=True)
        else:
            print(f"FRESH {race}: {data['generated_at']}", flush=True)
    if failures:
        print("Last verified totals retained; freshness not established for: " + ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
