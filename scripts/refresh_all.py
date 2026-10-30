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
        "verified_ny17_ppv_alias": "C00489799:LAWLER MICHAEL",
        "verified_co4_misfiled_expenditure": "C00552851:H0CO03165:CO03",
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


def fetch_co4_misfiled_boebert_notices(api_key):
    """Retrieve a user-verified CO-4 exception coded by the filer as CO-3.

    Freedom Caucus Fund's 2026 independent expenditures explicitly use
    Lauren Boebert's official candidate ID H0CO03165, but report district 03.
    Pull only that committee/candidate pair, not other CO-3 campaigns.
    Paginate every result and retain only 2026 GENERAL election items.
    """
    params={
        "api_key":api_key,"cycle":2026,
        "committee_id":"C00552851",
        "candidate_id":"H0CO03165",
        "is_notice":"true",
        "min_date":core.DATA_START.isoformat(),
        "max_date":core.DATA_END.isoformat(),
        "most_recent":"true","per_page":PAGE_SIZE,"sort":"-expenditure_date",
    }
    seen=set()
    cursor={}
    accepted=[]
    for page in range(30):
        payload=core.request_json(core.API_URL+"?"+urlencode(dict(params,**cursor)),
                                  attempts=1 if api_key=="DEMO_KEY" else 3)
        rows=payload.get("results")
        if not isinstance(rows,list):
            raise RuntimeError("FEC returned invalid Freedom Caucus Fund Schedule E page")
        for row in rows:
            filer=str(row.get("committee_id") or "").upper()
            candidate=str(row.get("candidate_id") or "").upper()
            state=core.norm(row.get("candidate_office_state"))
            reported_district=core.norm(row.get("candidate_office_district")).lstrip("0")
            if (filer=="C00552851" and candidate=="H0CO03165"
                    and state=="co" and reported_district in ("3","4")
                    and core.is_2026_general(row)):
                accepted.append(row)
        if len(rows)<PAGE_SIZE:
            print("CO-4 cross-district exception: "+str(len(accepted))+
                  " general-election Freedom Caucus Fund notices from "+
                  str(page+1)+" FEC API page(s).",flush=True)
            return accepted,page+1
        next_page=(payload.get("pagination") or {}).get("last_indexes") or {}
        cursor={str(k):str(v) for k,v in next_page.items() if v is not None and str(v)}
        if "last_index" not in cursor:
            raise RuntimeError("Incomplete FEC seek pagination for CO-4 exception")
        marker=tuple(sorted(cursor.items()))
        if marker in seen:
            raise RuntimeError("Repeated FEC seek cursor for CO-4 exception")
        seen.add(marker)
    raise RuntimeError("FEC CO-4 exception exceeded the safe pagination bound")


def refresh_priority_race(district, key, maximum_pages=20):
    """Rebuild a complete high-priority district before the shared rate budget runs out.

    Never merge a partial page into old financial totals or publish on FEC error.
    In the hourly workflow, this makes WI-1 independent of its late position
    in the nine-district resumable ingestion loop.
    """
    indexes=[i for i, batch in enumerate(BATCHES) if batch["district"]==district]
    if len(indexes)!=1:
        raise ValueError("Unknown priority district: "+str(district))
    index=indexes[0]
    rows=[]
    cursor={}
    seen=set()
    for page in range(1, maximum_pages+1):
        try:
            response=core.request_json(next_query(key,index,cursor),
                                       attempts=1 if key=="DEMO_KEY" else 3)
        except Exception as exc:
            print(f"PRIORITY {district} INCOMPLETE: FEC unavailable ({exc}); retaining verified snapshot.",flush=True)
            return False
        batch=response.get("results")
        if not isinstance(batch,list):
            print(f"PRIORITY {district} INCOMPLETE: invalid FEC results; retaining verified snapshot.",flush=True)
            return False
        rows.extend(compact(row) for row in batch)
        if len(batch)<PAGE_SIZE:
            if not rows:
                print(f"PRIORITY {district} INCOMPLETE: empty FEC response; retaining verified snapshot.",flush=True)
                return False
            finalize_one_race(district,rows,page)
            print(f"PRIORITY {district} COMPLETE: {page} pages, {len(rows)} source rows.",flush=True)
            return True
        last=(response.get("pagination") or {}).get("last_indexes") or {}
        next_cursor={str(k):str(v) for k,v in last.items() if v is not None and str(v)}
        marker=tuple(sorted(next_cursor.items()))
        if "last_index" not in next_cursor or marker in seen:
            print(f"PRIORITY {district} INCOMPLETE: invalid/repeated pagination cursor; retaining verified snapshot.",flush=True)
            return False
        seen.add(marker)
        cursor=next_cursor
    print(f"PRIORITY {district} INCOMPLETE: exceeded {maximum_pages} FEC pages; retaining verified snapshot.",flush=True)
    return False


def capture_pages(state,key,maximum_pages,fresh_races=frozenset()):
    """Publish a race only when its entire district query is complete."""
    requests=0
    while state["batch"]<len(BATCHES):
        name=BATCHES[state["batch"]]["district"]
        if name in fresh_races:
            # The separate priority scan completed after any checkpointed
            # partial pages; discard those stale buffered rows safely.
            state["completed_races"].append(name)
            state["batch"]+=1
            state["rows"]=[]
            state["race_pages"]=0
            state["cursor"]={}
            state["cursor_history"]=[]
            save_state(state)
            print(f"PRIORITY {name}: already fully refreshed; skipping duplicate full-cycle query.",flush=True)
            continue
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
        # Do not mark the base district complete if its one verified
        # out-of-district Boebert filing search fails: stale complete results
        # are safer than publishing a known-understated CO-4 total.
        supplemental=[]
        supplemental_pages=0
        if len(rows)<PAGE_SIZE and name=="CO-4":
            try:
                supplemental,supplemental_pages=fetch_co4_misfiled_boebert_notices(key)
            except Exception as exc:
                save_state(state)
                print("CO-4 supplementary FEC notices unavailable ("+str(exc)+
                      "); retaining last complete CO-4 figures until retry.",flush=True)
                return False
        # Keep original candidate ID (even when blank), name and expenditure.
        # The existing source/transaction deduplicator reconciles supplemental
        # notices against regular Form 3X items already in the base query.
        state["rows"].extend(compact(row) for row in rows)
        state["rows"].extend(compact(row) for row in supplemental)
        state["pages"]+=1+supplemental_pages
        state["race_pages"]+=1+supplemental_pages
        requests+=1+supplemental_pages
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
    freshly_verified={"WI-1"} if os.environ.get("WI1_PRIORITY_OK","").lower()=="true" else set()
    if capture_pages(state,key,budget,fresh_races=freshly_verified):
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
