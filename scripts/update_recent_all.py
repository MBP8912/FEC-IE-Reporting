#!/usr/bin/env python3
"""Publish a notice-only, rolling 48-hour FEC IE feed for all nine House races.

Includes only expedited Schedule E reports F24 and F5 with is_notice=True.
The FEC electronic filing receipt timestamp, not expenditure date, determines
the exact rolling window. Missing receipt times are disclosed as partial.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import update_ny17_recent as notice
from races import RACE_CODES

ROOT=Path(__file__).resolve().parents[1]
LOOKUP_BATCH=30


def load_data(root=ROOT):
    output={}
    for district in RACE_CODES:
        value=json.loads((root/district/"data"/"data.json").read_text(encoding="utf-8"))
        if value.get("district")!=district:
            raise RuntimeError("Incorrect district in verified data: "+district)
        if value.get("status") not in ("ok","not_initialized"):
            raise RuntimeError("Unexpected expenditure dataset status: "+district)
        output[district]=value
    return output


def valid_cache(existing):
    """Reuse only previously verified expedited notices with complete timestamps."""
    cache={}
    for district,report in existing.items():
        if (not isinstance(report,dict)
            or report.get("district")!=district
            or report.get("notice_only") is not True
            or report.get("status") not in ("ok","partial")):
            continue
        for item in report.get("items",[]):
            if not notice.is_new_notice(item):
                continue
            number=notice.file_id(item)
            when=notice.parse_receipt(item.get("reported_at"))
            if number and when:
                stamp=when.isoformat(timespec="seconds")
                if number in cache and cache[number]!=stamp:
                    raise RuntimeError("Conflicting FEC receipt timestamps for "+number)
                cache[number]=stamp
    return cache


def create_reports(data_by_race,receipt_times,now):
    reports={}
    for district in RACE_CODES:
        data=data_by_race[district]
        if data.get("status")!="ok":
            reports[district]={
                "status":"pending","district":district,"window_hours":48,
                "notice_only":True,"checked_at":now.isoformat(timespec="seconds"),
                "source_data_generated_at":data.get("generated_at"),
                "unresolved_recent_items":0,"items":[],
            }
        else:
            reports[district]=notice.build_payload(data,receipt_times,now)
    return reports


def refresh_all(now=None,root=ROOT,key=None):
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Now requires a timezone")
    data=load_data(root)
    previous={}
    for district in RACE_CODES:
        file=root/district/"data"/"recent48.json"
        if file.exists():
            previous[district]=json.loads(file.read_text(encoding="utf-8"))
    receipts=valid_cache(previous)
    file_ids=sorted({
        number for src in data.values() if src.get("status")=="ok"
        for row in notice.recent_candidates(src,now)
        if (number:=notice.file_id(row))
    })
    missing=[fid for fid in file_ids if fid not in receipts]
    api_key=key or os.environ.get("FEC_API_KEY") or "DEMO_KEY"
    print("Recent IE: "+str(len(file_ids))+" verified notice filings across nine races; "
          +str(len(missing))+" need receipt timestamps.",flush=True)
    for start in range(0,len(missing),LOOKUP_BATCH):
        batch=missing[start:start+LOOKUP_BATCH]
        try:
            receipts.update(notice.fetch_file_receipts(batch,api_key))
        except Exception as exc:
            # FEC DEMO_KEY can return 429. Publish verified subset, with a
            # PARTIAL status and a warning, never pretend missing data is zero.
            print("FEC receipt lookup interrupted ("+str(exc)+
                  "); retaining verified receipts and marking unresolved notices.",flush=True)
            break
    results=create_reports(data,receipts,now)
    bodies={district:json.dumps(feed,indent=2,ensure_ascii=False)+"\n"
            for district,feed in results.items()}
    cutoff=now-timedelta(hours=48)
    for district,content in bodies.items():
        path=root/district/"data"/"recent48.json"
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix(".tmp")
        temporary.write_text(content,encoding="utf-8")
        temporary.replace(path)
        feed=results[district]
        latest=[r for r in feed["items"] if notice.parse_receipt(r["reported_at"])>=cutoff]
        dollars=sum(r["amount_cents"] for r in latest)/100
        print("NOTICE-ONLY "+district+": "+feed["status"]+"; "+
              str(len(latest))+" new items, USD "+format(dollars,",.2f")+
              "; unresolved="+str(feed.get("unresolved_recent_items",0)),flush=True)
    return results


if __name__=="__main__":
    refresh_all()
