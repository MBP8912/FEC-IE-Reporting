#!/usr/bin/env python3
"""Resumable FEC Schedule E refresh for nine separate 2026 House districts.

FEC processed Schedule E supports up to 10 candidate_id filters per query and
100 results per page. We fetch all 18 verified nominee IDs in two batches,
checkpointing between GitHub Actions runs if the DEMO_KEY hourly quota is hit.
Never publish partial-cycle totals under the label "verified".
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import refresh as core
from races import RACES, RACE_CODES, ALL_CANDIDATE_IDS

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "data" / "ingest_checkpoint.json"
BATCHES = [ALL_CANDIDATE_IDS[:10], ALL_CANDIDATE_IDS[10:]]
PAGE_SIZE = 100
VERSION = 1
FIELDS = (
    "sub_id", "original_sub_id", "transaction_id", "committee_id",
    "committee_name", "candidate_id", "candidate_name",
    "candidate_office", "candidate_office_state", "candidate_office_district",
    "election_type", "election_type_full",
    "expenditure_date", "expenditure_amount", "support_oppose_indicator",
    "memo_code", "expenditure_description", "category_code_full",
    "category_code", "payee_name", "is_notice", "filing_date",
    "file_number", "pdf_url", "image_number",
    "filing_form", "amendment_indicator",
)
QUERY_FINGERPRINT = hashlib.sha256(
    json.dumps({
        "ids": BATCHES, "cycle": 2026,
        "min": core.DATA_START.isoformat(), "max": core.DATA_END.isoformat(),
        "sort": "-expenditure_date",
    }, sort_keys=True).encode()
).hexdigest()
DATA_PATHS = {district: ROOT / district / "data" / "data.json" for district in RACE_CODES}


def compact(row):
    subset = {key: row[key] for key in FIELDS if key in row}
    committee = row.get("committee")
    if isinstance(committee, dict) and committee.get("name"):
        subset["committee"] = {"name": committee["name"]}
    return subset


def new_state():
    return {
        "schema_version": VERSION,
        "query_fingerprint": QUERY_FINGERPRINT,
        "status": "in_progress",
        "batch": 0,
        "cursor": {},
        "cursor_history": [],
        "rows": [],
        "pages": 0,
    }


def read_state():
    if not CHECKPOINT.exists():
        return new_state()
    state = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if state.get("query_fingerprint") != QUERY_FINGERPRINT or state.get("status") != "in_progress":
        return new_state()
    if (state.get("schema_version") != VERSION
        or not isinstance(state.get("rows"), list)
        or not isinstance(state.get("cursor"), dict)
        or not isinstance(state.get("batch"), int)
        or not 0 <= state["batch"] < len(BATCHES)):
        raise RuntimeError("Invalid FEC checkpoint; refusing to silently lose the cursor")
    return state


def save_state(state):
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    temporary = CHECKPOINT.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, separators=(",", ":"), ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(CHECKPOINT)


def next_query(key, batch, cursor):
    params = {
        "api_key": key,
        "cycle": 2026,
        "candidate_id": BATCHES[batch],
        "min_date": core.DATA_START.isoformat(),
        "max_date": core.DATA_END.isoformat(),
        "most_recent": "true",
        "per_page": PAGE_SIZE,
        "sort": "-expenditure_date",
    }
    params.update(cursor)
    return core.API_URL + "?" + urlencode(params, doseq=True)


def capture_pages(state, key, maximum_pages):
    """Return True only after ALL batches are fully paginated."""
    permitted = set(ALL_CANDIDATE_IDS)
    count = 0
    while state["batch"] < len(BATCHES):
        if count >= maximum_pages:
            save_state(state)
            print(f"IN PROGRESS: {len(state['rows'])} source rows / {state['pages']} pages; "
                  f"batch {state['batch']+1}/{len(BATCHES)}. Resuming next scheduled refresh.",
                  flush=True)
            return False
        url = next_query(key, state["batch"], state["cursor"])
        try:
            response = core.request_json(url, attempts=1 if key == "DEMO_KEY" else 3)
        except Exception as exc:
            save_state(state)
            print(f"IN PROGRESS: API unavailable ({exc}). Saved {state['pages']} pages "
                  "and the pagination cursor without publishing incomplete totals.", flush=True)
            return False
        rows = response.get("results")
        if not isinstance(rows, list):
            raise RuntimeError("Unexpected Schedule E API response format")
        for row in rows:
            candidate_id = str(row.get("candidate_id") or "").upper()
            if candidate_id in permitted:
                state["rows"].append(compact(row))
        state["pages"] += 1
        count += 1
        if len(rows) < PAGE_SIZE:
            state["batch"] += 1
            state["cursor"] = {}
            state["cursor_history"] = []
        else:
            last = (response.get("pagination") or {}).get("last_indexes") or {}
            cursor = {str(k): str(v) for k, v in last.items() if v is not None and str(v)}
            if "last_index" not in cursor:
                raise RuntimeError("Full FEC page without a seek cursor; data may be incomplete")
            signature = json.dumps([state["batch"], cursor], sort_keys=True)
            if signature in state["cursor_history"]:
                raise RuntimeError("Repeated pagination cursor; refusing to publish incomplete totals")
            state["cursor_history"].append(signature)
            state["cursor"] = cursor
        # Keep a durable copy after each verified page. GitHub archives the
        # checkpoint at the end of this scheduled Actions run.
        save_state(state)
        print(f"FEC batch {min(state['batch']+1,len(BATCHES))}/{len(BATCHES)}, "
              f"API pages: {state['pages']}, stored itemizations: {len(state['rows'])}", flush=True)
    return True


def set_race(district):
    config = RACES[district]
    rep = config["republican"]
    dem = config["democratic"]
    core.COMMITTEE_KEY = district
    core.CANDIDATES = {
        "lawler": dict(name=rep["name"], id=rep["id"], party="Republican",
                       surname=rep["surname"], given=rep.get("given",rep["name"].split()[0])),
        "conley": dict(name=dem["name"], id=dem["id"],
                       party="DFL" if district=="MN-1" else "Democratic",
                       surname=dem["surname"], given=dem.get("given",dem["name"].split()[0])),
    }
    core.DISPOSITIONS = {
        "support_lawler": "Support " + rep["short"],
        "oppose_conley": "Oppose " + dem["short"],
        "support_conley": "Support " + dem["short"],
        "oppose_lawler": "Oppose " + rep["short"],
    }
    core.DATAFILE = DATA_PATHS[district]
    return config


def generate_datasets(state):
    """Only called after all FEC search pages from BOTH batches are received."""
    results = {}
    for district in RACE_CODES:
        cfg = set_race(district)
        allowed = {cfg["republican"]["id"],cfg["democratic"]["id"]}
        subset = [row for row in state["rows"]
                  if str(row.get("candidate_id") or "").upper() in allowed]
        deduplicated, excluded = core.unique_rows(subset)
        output = core.summarize(deduplicated, excluded, len(subset), state["pages"])
        output["fetch"] = {
            "source": "FEC processed Schedule E",
            "scope": "Complete 2026 general election, original and regular IE notices deduplicated",
            "all_batches_complete": True,
            "source_pages_across_races": state["pages"],
            "race_raw_records": len(subset),
        }
        results[district] = output
        print(f"VERIFIED {district}: {len(subset)} raw, {len(deduplicated)} unique,"
              f" {len(output['groups'])} spenders, \${output['totals']['all']/100:,.2f}",
              flush=True)
    # Publish none of the new race totals until every dataset was successfully
    # calculated and reconciled. Then atomically replace each JSON file.
    for district, data in results.items():
        path = DATA_PATHS[district]
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
        temporary.replace(path)
    save_state({
        "schema_version": VERSION,
        "query_fingerprint": QUERY_FINGERPRINT,
        "status": "complete",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "pages": state["pages"],
        "rows": [], "batch": 0, "cursor": {},
    })
    return results


def main():
    key = os.environ.get("FEC_API_KEY") or "DEMO_KEY"
    # 22 requests/cycle provides headroom under DEMO_KEY's shared limit;
    # a personal key can handle more pages per run.
    budget = 22 if key == "DEMO_KEY" else 250
    state = read_state()
    if capture_pages(state, key, budget):
        generate_datasets(state)
        print("VERIFIED: all nine complete candidate-level IE datasets published.", flush=True)
    else:
        print("FEC source ingestion checkpoint archived. Existing published datasets "
              "remain unchanged pending a complete download.", flush=True)


if __name__ == "__main__":
    main()
