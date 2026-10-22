#!/usr/bin/env python3
"""Resumable FEC Schedule E refresh for nine separate 2026 House districts.

Some valid Schedule E transactions omit candidate IDs. We fetch nine full
House districts so those transactions can be matched by candidate name,
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
BATCHES = [{"district": name, "state": cfg["state"], "number": cfg["district"]}
           for name, cfg in RACES.items()]
PAGE_SIZE = 100
VERSION = 2
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
        "districts": BATCHES, "cycle": 2026,
        "include_idless_candidates": True,
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
        "race_pages": 0,
        "completed_races": [],
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


def next_query(key,batch,cursor):
    cfg=BATCHES[batch]
    params={
        "api_key":key,"cycle":2026,"candidate_office":"H",
        "candidate_office_state":cfg["state"],
        "candidate_office_district":cfg["number"],
        "min_date":core.DATA_START.isoformat(),
        "max_date":core.DATA_END.isoformat(),
        "most_recent":"true","per_page":PAGE_SIZE,"sort":"-expenditure_date",
    }
    params.update(cursor)
    return core.API_URL+"?"+urlencode(params,doseq=True)


def capture_pages(state,key,maximum_pages):
    """Publish a race only when its entire district query is complete."""
    requests=0
    while state["batch"]<len(BATCHES):
        name=BATCHES[state["batch"]]["district"]
        if requests>=maximum_pages:
            save_state(state)
            print("IN PROGRESS: "+name+"; rate-budget checkpoint saved.",flush=True)
            return False
        try:
            response=core.request_json(next_query(key,state["batch"],state["cursor"]),
                                       attempts=1 if key=="DEMO_KEY" else 3)
        except Exception as exc:
            save_state(state)
            print("IN PROGRESS: "+name+"; FEC unavailable ("+str(exc)+")",flush=True)
            return False
        rows=response.get("results")
        if not isinstance(rows,list):
            raise RuntimeError("FEC returned no results list; not publishing")
        # Keep original candidate ID (even when blank), name and expenditure.
        state["rows"].extend(compact(row) for row in rows)
        state["pages"]+=1
        state["race_pages"]+=1
        requests+=1
        if len(rows)<PAGE_SIZE:
            finalize_one_race(name,state["rows"],state["race_pages"])
            state["completed_races"].append(name)
            state["batch"]+=1
            state["rows"]=[]
            state["race_pages"]=0
            state["cursor"]={}
            state["cursor_history"]=[]
        else:
            last=(response.get("pagination") or {}).get("last_indexes") or {}
            cursor={str(k):str(v) for k,v in last.items() if v is not None and str(v)}
            if "last_index" not in cursor:
                raise RuntimeError("FEC full page lacked seek cursor")
            marker=json.dumps([state["batch"],cursor],sort_keys=True)
            if marker in state["cursor_history"]:
                raise RuntimeError("FEC repeated seek cursor")
            state["cursor_history"].append(marker)
            state["cursor"]=cursor
        save_state(state)
        print("FEC pages: "+str(state["pages"])+"; completed districts: "+
              str(len(state["completed_races"]))+"/9; buffered rows: "+
              str(len(state["rows"])),flush=True)
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


def finalize_one_race(district,raw,pages):
    """Count unique expenditures for both nominees, including ID-less FEC rows."""
    set_race(district)
    entries,excluded=core.unique_rows(raw)
    data=core.summarize(entries,excluded,len(raw),pages)
    data["fetch"]={
        "source":"FEC processed Schedule E: complete House district",
        "all_district_pages_complete":True,
        "includes_missing_candidate_id_records":True,
        "source_pages_this_district":pages,
    }
    path=DATA_PATHS[district]
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    tmp.replace(path)
    print(f"VERIFIED {district}: {len(raw)} source rows, {len(entries)} unique, "
          f"${data['totals']['all']/100:,.2f}",flush=True)


def main():
    key=os.environ.get("FEC_API_KEY") or "DEMO_KEY"
    budget=22 if key=="DEMO_KEY" else 250
    state=read_state()
    if capture_pages(state,key,budget):
        save_state({
            "schema_version":VERSION,"query_fingerprint":QUERY_FINGERPRINT,
            "status":"complete","completed_at":datetime.now(timezone.utc).isoformat(),
            "pages":state["pages"],"completed_races":RACE_CODES,
            "rows":[],"batch":0,"cursor":{},
        })
        print("VERIFIED: all nine complete House district searches.",flush=True)
    else:
        print("CHECKPOINT SAVED; only complete district totals are published.",flush=True)


if __name__ == "__main__":
    main()
