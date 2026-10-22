#!/usr/bin/env python3
"""NY-17 pilot: rolling 48-hour FEC independent expenditure receipt times.

Schedule E's filing_date has day precision only. Match each verified Schedule E
transaction's file_number to /efile/filings/ receipt_date for exact timestamps.
Date-only values NEVER qualify as timestamps; unresolved filings are disclosed.
"""
from __future__ import annotations
import json,os,re
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo
import refresh as ie
from races import RACES

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"NY-17"/"data"/"data.json"
OUTPUT=ROOT/"NY-17"/"data"/"recent48.json"
EASTERN=ZoneInfo("America/New_York")
LOOKBACK_HOURS=120
EFILE_API="https://api.open.fec.gov/v1/efile/filings/"
# Political committees file expedited IE notices on F24; noncommittees
# file expedited 24/48-hour notices on Form 5. Form 3X monthly reports,
# and Form 5 periodic reports, are not NEW notices.
EXPEDITED_FORMS=frozenset(("F24","F5"))


def is_new_notice(row):
    """Include only original expedited notices, never periodic re-reporting."""
    return (row.get("notice") is True
            and str(row.get("filing_form") or "").strip().upper() in EXPEDITED_FORMS)


def parse_receipt(value):
    if not isinstance(value,str) or not re.search(r"\d\d:\d\d:\d\d",value):
        return None
    try: dt=datetime.fromisoformat(value.strip().replace("Z","+00:00"))
    except ValueError: return None
    if dt.tzinfo is None: dt=dt.replace(tzinfo=EASTERN)
    return dt.astimezone(timezone.utc)


def file_id(row):
    value=str(row.get("file_number") or "").strip()
    return value if value.isdigit() else None


def recent_candidates(data,now):
    start=(now.astimezone(EASTERN)-timedelta(hours=LOOKBACK_HOURS)).date().isoformat()
    return [r for r in data.get("transactions",[])
            if is_new_notice(r)
            and str(r.get("filing_date") or "")[:10]>=start]


def fetch_file_receipts(ids,key):
    mapping={}
    for start in range(0,len(ids),30):
        wanted=ids[start:start+30]
        params=[("api_key",key),("per_page","100")]
        params.extend(("file_number",i) for i in wanted)
        result=ie.request_json(EFILE_API+"?"+urlencode(params),
                               attempts=1 if key=="DEMO_KEY" else 3)
        entries=result.get("results")
        if not isinstance(entries,list) or len(entries)>=100:
            raise RuntimeError("FEC efiling receipt lookup missing or potentially truncated")
        for r in entries:
            ident=file_id(r)
            receipt=parse_receipt(r.get("receipt_date"))
            if ident in wanted and receipt:
                mapping[ident]=receipt.isoformat(timespec="seconds")
    return mapping


def build_payload(data,receipts,now):
    if now.tzinfo is None: raise ValueError("now must have a timezone")
    if data.get("status")!="ok" or data.get("district") not in RACES:
        raise RuntimeError("Cannot produce recent spending from an unverified district")
    district=data["district"]
    config=RACES[district]
    labels=data.get("disposition_labels") or {}
    pool=[]
    unknown=0
    unique=set()
    oldest=now-timedelta(hours=LOOKBACK_HOURS)
    possible_day=(now-timedelta(hours=48)).astimezone(EASTERN).date().isoformat()
    for r in recent_candidates(data,now):
        if not is_new_notice(r):
            raise RuntimeError("Periodic report cannot enter the 48-hour IE feed")
        number=file_id(r)
        at=parse_receipt(receipts.get(number)) if number else None
        if at is None:
            if str(r.get("filing_date") or "")[:10]>=possible_day:
                unknown+=1
            continue
        if not oldest <= at <= now+timedelta(minutes=5): continue
        uid=r.get("source_id") or (number,r["date"],r["amount_cents"])
        if uid in unique: raise RuntimeError("Duplicate verified source transaction")
        unique.add(uid)
        pool.append({
            "source_id":r.get("source_id"),"file_number":number,
            "reported_at":at.isoformat(timespec="seconds"),
            "expenditure_date":r["date"],
            "spender":r["group"],
            "disposition":r["disposition"],
            "notice":True,
            "filing_form":str(r["filing_form"]).upper(),
            "purpose":r["description"],
            "spend_type":r["type"],
            "amount_cents":r["amount_cents"],
            "fec_url":r.get("pdf_url") or "",
        })
    pool.sort(key=lambda x:(x["reported_at"],x["amount_cents"]),reverse=True)
    return {
        "status":"partial" if unknown else "ok",
        "district":district,"window_hours":48,
        "candidate_names":{
            "lawler":config["republican"]["short"],
            "conley":config["democratic"]["short"],
        },
        "disposition_labels":{
            "support_lawler":labels.get("support_lawler","Support "+config["republican"]["short"]),
            "oppose_conley":labels.get("oppose_conley","Oppose "+config["democratic"]["short"]),
            "support_conley":labels.get("support_conley","Support "+config["democratic"]["short"]),
            "oppose_lawler":labels.get("oppose_lawler","Oppose "+config["republican"]["short"]),
        },
        "notice_only":True,
        "selection":"original_expeditious_24_48_hour_IE_notices",
        "accepted_forms":sorted(EXPEDITED_FORMS),
        "checked_at":now.isoformat(timespec="seconds"),
        "source_data_generated_at":data.get("generated_at"),
        "unresolved_recent_items":unknown,
        "timestamp_note":"FEC efiling receipt time, Eastern when no offset is supplied",
        "items":pool,
    }


def main():
    now=datetime.now(timezone.utc)
    data=json.loads(DATA.read_text(encoding="utf-8"))
    if data.get("status")!="ok": raise RuntimeError("NY-17 source data not verified")
    # Do not even look up receipt timestamps for ordinary monthly/quarterly
    # filing numbers: they would otherwise appear to be newly reported spending.
    ids=sorted({i for r in recent_candidates(data,now) if (i:=file_id(r))})
    previous={}
    if OUTPUT.exists():
        previous=json.loads(OUTPUT.read_text(encoding="utf-8"))
    cache={}
    if previous.get("status") in ("ok","partial"):
        for r in previous.get("items",[]):
            number=file_id(r)
            at=parse_receipt(r.get("reported_at"))
            if number and at: cache[number]=at.isoformat(timespec="seconds")
    missing=[i for i in ids if i not in cache]
    if missing:
        cache.update(fetch_file_receipts(missing,os.environ.get("FEC_API_KEY") or "DEMO_KEY"))
    result=build_payload(data,cache,now)
    temp=OUTPUT.with_suffix(".tmp")
    temp.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    temp.replace(OUTPUT)
    latest=[r for r in result["items"]
            if parse_receipt(r["reported_at"])>=now-timedelta(hours=48)]
    total=sum(r["amount_cents"] for r in latest)
    print(f"NY-17 48h: {len(latest)} items, USD {total/100:,.2f}; "
          f"{result['unresolved_recent_items']} uncertain; status {result['status']}",flush=True)


if __name__=="__main__": main()
