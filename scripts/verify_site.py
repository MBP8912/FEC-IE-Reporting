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
    if ".spiros-ie-header" not in css or ".spiros-ie-logo" not in css:
        raise RuntimeError("Missing shared Spiros Consulting header styles")
    logo=read("assets/spiros-consulting-logo.png")
    if not logo.startswith(bytes.fromhex("89504e470d0a1a0a")) or len(logo)<1000:
        raise RuntimeError("Spiros Consulting PNG is missing or invalid")
    shared_recent=read("assets/recent48.js").decode("utf-8")
    if ("function view(payload)" not in shared_recent or
        'cell("details",null,"recent48-disclosure")' not in shared_recent or
        "48*60*60*1000" not in shared_recent or
        "candidate_names" not in shared_recent):
        raise RuntimeError("Shared collapsed notice-only 48-hour UI missing or incomplete")
    done=[];pending=[]
    for district,config in RACES.items():
        page=read(district+"/").decode("utf-8")
        if "<title>"+district+" • 2026 Independent Expenditure Reporting</title>" not in page:
            raise RuntimeError("Wrong dashboard title "+district)
        if ('class="topbar spiros-ie-header"' not in page or
            'class="spiros-ie-logo"' not in page or
            'src="../assets/spiros-consulting-logo.png"' not in page or
            'alt="Spiros Consulting"' not in page):
            raise RuntimeError("Spiros Consulting header missing from "+district)
        a=page.index('class="panel pivot-section"')
        b=page.index('class="panel group-section"')
        if a>b: raise RuntimeError("Pivot below group in "+district)
        for unwanted in ["WHO IS SPENDING","WHAT THE MONEY FUNDED","About these figures",
                         "Four dispositions shown separately","Numbers are independent expenditure amounts, not contributions to campaigns"]:
            if unwanted in page: raise RuntimeError("Unwanted text in "+district+": "+unwanted)
        if '../assets/app.js' not in page or '../assets/styles.css' not in page:
            raise RuntimeError("Wrong relative asset URL in "+district)
        if 'id="recent48-groups"' not in page or 'Spending reported in the last 48 hours' not in page:
            raise RuntimeError("Missing notice-only 48-hour panel: "+district)
        if page.index('id="recent48-groups"') > page.index('class="panel chart-section"'):
            raise RuntimeError("48-hour panel not above expenditure timeline: "+district)
        if 'src="../assets/recent48.js' not in page or 'v=20261022-recent48-nine-races-v1' not in page:
            raise RuntimeError("Shared recent 48-hour frontend missing or stale: "+district)
        recent=json.loads(read(district+"/data/recent48.json"))
        if recent.get("district")!=district or recent.get("status") not in ("ok","partial","pending"):
            raise RuntimeError("Unrecognized recent spending data for "+district)
        if recent.get("status") in ("ok","partial"):
            if recent.get("notice_only") is not True:
                raise RuntimeError("Recent feed includes monthly/quarterly filings in "+district)
            names=recent.get("candidate_names",{})
            if (names.get("lawler")!=config["republican"]["short"] or
                names.get("conley")!=config["democratic"]["short"]):
                raise RuntimeError("Wrong nominee names in 48-hour feed for "+district)
            keys=set()
            for item in recent.get("items",[]):
                if item.get("notice") is not True or str(item.get("filing_form") or "").upper() not in ("F24","F5"):
                    raise RuntimeError("Non-notice entry in new spending box: "+district)
                if not isinstance(item.get("amount_cents"),int) or not isinstance(item.get("reported_at"),str) or "T" not in item["reported_at"]:
                    raise RuntimeError("Invalid receipt time or amount in "+district)
                if item.get("source_id") in keys:
                    raise RuntimeError("Repeated independent expenditure in recent feed: "+district)
                keys.add(item.get("source_id"))
        data=json.loads(read(district+"/data/data.json"))
        if data.get("district")!=district: raise RuntimeError("Misassigned FEC data in "+district)
        # The 'checked' timestamp on the recent panel is not proof of freshness:
        # the feeder must actually use the same full-cycle dataset published
        # beside it. Without this guard, panels can silently omit new notices.
        if data.get("status")=="ok":
            if recent.get("source_data_generated_at")!=data.get("generated_at"):
                raise RuntimeError("Stale 48-hour feed in "+district+
                                   ": notice feed built from older Schedule E snapshot")
            if recent.get("status")=="pending":
                raise RuntimeError("Verified "+district+" dataset still has an uninitialized recent feed")
            entries=data["transactions"]
            # Exact known missing records must remain included across future
            # automatic district refreshes; reject stale incomplete backups.
            if district=="NY-17":
                matched=[x for x in entries if
                         x.get("group_id")=="C00489799" and
                         x.get("transaction_id")=="500768900" and
                         x.get("candidate_id")=="H2NY17162" and
                         x.get("disposition")=="oppose_lawler"]
                if len(matched)!=1:
                    raise RuntimeError("Missing/double-counted NY-17 Planned Parenthood Votes Michael Lawler notice")
            if district=="CO-4":
                matched=[x for x in entries if
                         x.get("group_id")=="C00552851" and
                         x.get("transaction_id")=="EE125CCEF00774AB5ACF" and
                         x.get("candidate_id")=="H0CO03165" and
                         x.get("disposition")=="support_lawler"]
                if len(matched)!=1:
                    raise RuntimeError("Missing/double-counted CO-3-coded Freedom Caucus Fund Boebert notice")
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
            for section in data["pivot"]:
                if section["total"] != sum(cat["total"] for cat in section["categories"]):
                    raise RuntimeError("Pivot type totals mismatch in "+district)
            done.append((district,len(entries),money))
        elif data.get("status")=="not_initialized": pending.append(district)
        else: raise RuntimeError("Unknown data state for "+district)
    print("VERIFIED: All nine direct IE dashboards have Spiros Consulting branding, notice-only 48h panels, and reconciled totals.",flush=True)
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
