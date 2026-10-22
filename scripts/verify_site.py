#!/usr/bin/env python3
"""Validate nine publicly deployed IE dashboards and the no-directory root."""
import json,sys,time
from urllib.request import Request,urlopen
from races import RACES
BASE="https://mbp8912.github.io/FEC-IE-Reporting/"
def read(path):
    with urlopen(Request(BASE+path,headers={"User-Agent":"FEC-IE-Reporting-live-check/2.0"}),timeout=24) as res:
        if res.status != 200: raise RuntimeError(str(res.status)+" "+path)
        return res.read()
def verify():
    index=read("").decode("utf-8")
    if 'url=./NY-17/' not in index or 'window.location.replace("./NY-17/")' not in index or "directory-card" in index:
        raise RuntimeError("Main URL is not the required NY-17 redirect")
    js=read("assets/app.js").decode("utf-8")
    for name in ["function drawChart","function groupTable","function makePivot","function openDetails"]:
        if name not in js: raise RuntimeError("Missing shared script method "+name)
    css=read("assets/styles.css").decode("utf-8")
    if ".headline-metrics" not in css: raise RuntimeError("Missing CSS")
    done=[];pending=[]
    for district,config in RACES.items():
        page=read(district+"/").decode("utf-8")
        if "<title>"+district+" • 2026 Independent Expenditure Reporting</title>" not in page:
            raise RuntimeError("Wrong dashboard title "+district)
        a=page.index('class="panel pivot-section"')
        b=page.index('class="panel group-section"')
        if a>b: raise RuntimeError("Pivot below group in "+district)
        for unwanted in ["WHO IS SPENDING","WHAT THE MONEY FUNDED","About these figures",
                         "Four dispositions shown separately","Numbers are independent expenditure amounts, not contributions to campaigns"]:
            if unwanted in page: raise RuntimeError("Unwanted text in "+district+": "+unwanted)
        if '../assets/app.js' not in page or '../assets/styles.css' not in page:
            raise RuntimeError("Wrong relative asset URL in "+district)
        data=json.loads(read(district+"/data/data.json"))
        if data.get("district")!=district: raise RuntimeError("Misassigned FEC data in "+district)
        if data.get("status")=="ok":
            entries=data["transactions"]
            money=sum(int(item["amount_cents"]) for item in entries)
            if money!=data["totals"]["all"] or money!=sum(g["total"] for g in data["groups"]):
                raise RuntimeError("Financial values do not reconcile in "+district)
            allowed={config["republican"]["id"],config["democratic"]["id"]}
            if any(item["candidate_id"] not in allowed for item in entries):
                raise RuntimeError("Incorrect nominee ID in "+district)
            # The displayed type and pivot must reflect every documented,
            # narrowly scoped manual correction, even if the FEC API was rate-limited.
            import refresh as core
            import refresh_all as multi
            multi.set_race(district)
            for item in entries:
                category = core.manual_spend_category(
                    item.get("group_id"), item.get("candidate_id"),
                    item.get("date"), item.get("description"))
                if category and item.get("type") != category:
                    raise RuntimeError("Unapplied classification override: "+district+
                                       " / "+str(item.get("source_id")))
            for section in obj["pivot"]:
                if section["total"] != sum(cat["total"] for cat in section["categories"]):
                    raise RuntimeError("Pivot type totals mismatch in "+district)
            done.append((district,len(entries),money))
        elif data.get("status")=="not_initialized": pending.append(district)
        else: raise RuntimeError("Unknown data state for "+district)
    print("VERIFIED: Root redirect, shared JS/CSS, nine individual race pages; type section above group section.",flush=True)
    for district,n,amt in done:
        print(f"DATA VERIFIED {district}: {n} unique expenditures, ${amt/100:,.2f}",flush=True)
    if pending:
        print("AWAITING COMPLETE FEC PAGINATION (no invented amounts): "+", ".join(pending),flush=True)
    print(BASE+"NY-17/")
if __name__=="__main__":
    for n in range(4):
        try:
            verify();sys.exit(0)
        except Exception as exc:
            print("Site check "+str(n+1)+"/4: "+str(exc),file=sys.stderr,flush=True)
            if n==3:sys.exit(1)
            time.sleep(8)
