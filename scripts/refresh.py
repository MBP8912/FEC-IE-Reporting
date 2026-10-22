#!/usr/bin/env python3
"""Independent-expenditure dashboard from FEC Schedule E, including notices.

Scope: 2026-cycle general-election expenditures concerning NY-17's nominees.
No fabricated figures; failed or incomplete queries do not replace good data.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATAFILE = ROOT / "NY-17" / "data" / "data.json"
DATA_START = date(2025, 1, 1)
DATA_END = date(2026, 11, 3)
COMMITTEE_KEY = "NY-17"
CANDIDATES = {
    "lawler": {"name": "Mike Lawler", "id": "H2NY17162", "party": "Republican"},
    "conley": {"name": "Cait Conley", "id": "H6NY17171", "party": "Democratic"},
}
ORDER = ["support_lawler", "oppose_conley", "support_conley", "oppose_lawler"]
DISPOSITIONS = {
    "support_lawler": "Support Lawler",
    "oppose_conley": "Oppose Conley",
    "support_conley": "Support Conley",
    "oppose_lawler": "Oppose Lawler",
}
COLORS = {
    "support_lawler": "#C85553",
    "oppose_conley": "#EBA59A",
    "support_conley": "#396BBA",
    "oppose_lawler": "#8EB4ED",
}
CATEGORIES = [
    "TV", "Digital", "Billboard", "Media (unspecified)", "Mail", "Text", "Field / Canvassing",
    "Polling", "Radio", "Production", "Print", "Research",
    "Consulting", "Events", "Other / Unclassified",
]
API_URL = "https://api.open.fec.gov/v1/schedules/schedule_e/"
AGENT = "NY17-independent-expenditure-dashboard/1.0 (public FEC data analysis)"
PER_PAGE = 100


def request_json(url: str, attempts: int = 3):
    target = urlparse(url)
    if target.scheme != "https" or target.hostname != "api.open.fec.gov":
        raise ValueError("Unexpected source URL " + url)
    for n in range(attempts):
        try:
            with urlopen(Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"}),
                         timeout=50) as response:
                return json.load(response)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or n == attempts - 1:
                raise RuntimeError("FEC HTTP " + str(exc.code) + " (" + target.path + ")") from exc
            delay = exc.headers.get("Retry-After", "")
            time.sleep(min(40, int(delay)) if delay.isdigit() else 4 * (n + 1))
        except (URLError, TimeoutError, ConnectionError) as exc:
            if n == attempts - 1:
                raise RuntimeError("FEC data fetch failed: " + str(exc)) from exc
            time.sleep(2 * (n + 1))


def fetch_rows(api_key):
    """Seek-paginate all processed Schedule E rows, including expedited notices.

    Use NY-17 office/district filters, not just candidate IDs; candidate IDs
    can be omitted in some reports. Later processing requires exact nominee ID
    or an unambiguous nominee name.
    """
    base = {
        "api_key": api_key,
        "cycle": 2026,
        "candidate_office": "H",
        "candidate_office_state": "NY",
        "candidate_office_district": "17",
        "min_date": DATA_START.isoformat(),
        "max_date": DATA_END.isoformat(),
        "most_recent": "true",
        "per_page": PER_PAGE,
        "sort": "-expenditure_date",
    }
    seen_pages = set()
    all_rows = []
    cursor = {}
    pages_read = 0
    for _ in range(350):
        params = dict(base, **cursor)
        url = API_URL + "?" + urlencode(params)
        page = request_json(url)
        rows = page.get("results")
        if not isinstance(rows, list):
            raise RuntimeError("FEC API did not return transaction rows")
        all_rows.extend(rows)
        pages_read += 1
        pagination = page.get("pagination") or {}
        last = pagination.get("last_indexes") or {}
        if len(rows) < PER_PAGE:
            print("Fetched " + str(len(all_rows)) + " Schedule E rows in " + str(pages_read) + " page(s)", flush=True)
            return all_rows, pages_read
        # A full page requires a next-page cursor; never silently truncate.
        candidate_cursor = {str(k): str(v) for k, v in last.items() if v is not None and str(v)}
        if not candidate_cursor or "last_index" not in candidate_cursor:
            raise RuntimeError("FEC pagination returned a full page but no seek cursor")
        mark = tuple(sorted(candidate_cursor.items()))
        if mark in seen_pages:
            raise RuntimeError("FEC pagination repeated a cursor; refusing incomplete data")
        seen_pages.add(mark)
        cursor = candidate_cursor
    raise RuntimeError("Exceeded 350 FEC pages; refusing truncated results")


def as_cents(number):
    if number is None or number == "":
        return None
    try:
        d = Decimal(str(number).replace(",", ""))
        if not d.is_finite():
            return None
        return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return None


def norm(value):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").lower())).strip()


def parse_day(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def nominee_key(row):
    """Match an official FEC candidate ID first; use an unambiguous name only
    where the underlying Schedule E record lacks a candidate ID entirely.
    """
    cid = str(row.get("candidate_id") or "").strip().upper()
    for key, cand in CANDIDATES.items():
        if cid == cand["id"]:
            return key
    if cid:  # Never silently equate an independently identified third candidate.
        return None
    name = norm(row.get("candidate_name"))
    if not name:
        return None
    matches = []
    for key, cand in CANDIDATES.items():
        family = norm(cand.get("surname") or cand["name"].split()[-1])
        given = norm(cand.get("given") or cand["name"].split()[0])
        # A surname alone is insufficient for an ID-less report.
        if family and family in name and given and given in name:
            matches.append(key)
    return matches[0] if len(matches) == 1 else None


def is_2026_general(row):
    raw = norm(row.get("election_type")).replace(" ", "")
    full = norm(row.get("election_type_full"))
    if raw.startswith("g"):
        suffix = raw[1:]
        return not suffix or suffix in ("26", "2026")
    return "general" in full and "primary" not in full and "special" not in full


def spender(row):
    committee = row.get("committee") or {}
    if isinstance(committee, dict):
        name = committee.get("name")
    else:
        name = None
    name = row.get("committee_name") or name
    if not name:
        parts = [row.get("filer_first_name"), row.get("filer_last_name")]
        name = " ".join(str(p).strip() for p in parts if p)
    return re.sub(r"\s+", " ", str(name or "Unidentified filer (see FEC filing)").strip())


def classify(description, category_description=""):
    txt = norm(description + " " + category_description)
    def has(*terms):
        return any(re.search(r"\b" + re.escape(term) + r"\b", txt) for term in terms)
    # Order matters. An expense for mail printing belongs with mail, not Print.
    if has("sms", "texting", "texts", "text message", "text messages", "p2p texting", "peer to peer text", "peer to peer texting", "text bank", "text bank calls"):
        return "Text"
    if has("direct mail", "mailing", "mailers", "mailer", "postage", "postal", "mail", "letter mailing", "postcards", "postcard"):
        return "Mail"
    if has("polling", "poll", "survey", "surveys", "focus group", "focus groups"):
        return "Polling"
    if has("canvass", "canvassing", "canvas", "field", "door knocking", "door to door", "gotv", "voter contact", "phone banking", "phonebank", "message phone calls", "voter outreach", "outreach", "staff time for voter communications", "phone calls"):
        return "Field / Canvassing"
    if has("digital", "online", "internet", "facebook", "instagram", "social media", "streaming", "programmatic", "pre roll", "preroll", "youtube", "connected tv", "ctv", "ott", "web ads", "website advertising", "google ads", "display ads", "email services", "email marketing", "email ads"):
        return "Digital"
    if has("television", "tv", "broadcast", "cable", "airtime", "television ads", "television advertising"):
        return "TV"
    if has("media placement", "media buy", "ad buy", "advertising buy", "media spending"):
        return "Media (unspecified)"
    if has("radio", "fm radio", "am radio"):
        return "Radio"
    if has("creative", "production", "video editing", "design", "editing", "photography", "graphics", "copywriting"):
        return "Production"
    if has("printing", "print", "newspaper", "billboard", "billboards", "yard signs", "yard sign", "signs", "signage", "literature", "flyers"):
        return "Print"
    if has("research", "opposition research", "data analysis", "modeling", "data services", "voter data"):
        return "Research"
    if has("consulting", "consultant", "strategy", "compliance", "professional fees"):
        return "Consulting"
    if has("events", "event", "rally"):
        return "Events"
    return "Other / Unclassified"


# These are manually reviewed, per-race category corrections — not general
# description matching rules. Keys contain the actual FEC spending committee ID
# and the normalized, ORIGINAL Schedule E expenditure description.
RACE_CATEGORY_OVERRIDES = {
    "CO-5": {
        ("C00960435", "placed media tv and connected tv"): "TV",  # No Going Back PAC
        ("C00473918", "mailhouse"): "Mail",                      # Women Vote
    },
    "IA-1": {
        ("C00504530", "media placement"): "TV",                 # CLF
        ("C00486845", "ad buy"): "TV",                          # LCV Victory Fund
    },
    "MN-1": {
        ("C00486845", "ad buy"): "TV",                          # LCV Victory Fund
    },
    "NE-2": {
        ("C00504530", "media placement"): "TV",                 # CLF
    },
    "WI-1": {
        ("C00835959", "ie steil media buy"): "TV",               # Fairshake
        ("C00504530", "media placement"): "TV",                 # CLF
        ("C00573261", "media buy"): "Digital",                  # End Citizens United
    },
    "CA-13": {
        ("C00504530", "media placement"): "TV",                 # CLF
    },
}
BILLBOARD_OVERRIDE_RACES = frozenset({"WI-1", "CA-13"})
AB_PAC_COMMITTEE_ID = "C00492140"


def manual_spend_category(committee_id, candidate_id, expenditure_date, description):
    """Return a manual category only for the precise race, filer and description.

    Original descriptions, cents, dates, filing links, and dispositions must
    remain untouched. For nonmatches, return None: let the standard classifier
    (or existing archived label) decide.
    """
    filer = str(committee_id or "").strip().upper()
    candidate = str(candidate_id or "").strip().upper()
    date_str = str(expenditure_date or "")[:10]
    text = norm(description)

    # Prior NY-17 user-reviewed exceptions must not leak to other districts.
    if COMMITTEE_KEY == "NY-17":
        if (filer == "C00486845" and candidate == "H2NY17162"
                and date_str == "2026-09-11" and text == "ad buy"):
            return "Digital"
        if (filer == "C00504530" and candidate == "H6NY17171"
                and text == "media placement"):
            return "TV"

    # AB PAC's two specifically requested races get a separate Billboard
    # category for billed/estimated billboard advertising, not all print ads.
    if (COMMITTEE_KEY in BILLBOARD_OVERRIDE_RACES
            and filer == AB_PAC_COMMITTEE_ID
            and (text == "billboard advertising" or
                 text.startswith("billboard advertising "))):
        return "Billboard"

    return RACE_CATEGORY_OVERRIDES.get(COMMITTEE_KEY, {}).get((filer, text))


def classify_for_race(committee_id, candidate_id, expenditure_date, description,
                      category_description=""):
    """Classify using a specific override when present, otherwise generic rules."""
    return (manual_spend_category(committee_id, candidate_id, expenditure_date, description)
            or classify(description, category_description))


def classify_ny17_override(committee_id, candidate_id, expenditure_date, description,
                           category_description=""):
    """Backward-compatible interface for the initial NY-17 regression tests."""
    return classify_for_race(committee_id, candidate_id, expenditure_date,
                             description, category_description)


def source_url(row):
    pdf = str(row.get("pdf_url") or "")
    if pdf.startswith("https://docquery.fec.gov/") or pdf.startswith("https://www.fec.gov/"):
        return pdf
    image = str(row.get("image_number") or "").strip()
    if image.isdigit():
        return "https://docquery.fec.gov/cgi-bin/fecimg/?" + image
    return ""


def normalize_row(row):
    if nominee_key(row) not in ("lawler", "conley"):
        return None, "other_candidate"
    if not is_2026_general(row):
        return None, "other_election"
    day = parse_day(row.get("expenditure_date"))
    if not day or not DATA_START <= day <= DATA_END:
        return None, "out_of_range"
    so = str(row.get("support_oppose_indicator") or "").strip().upper()
    if so not in ("S", "O"):
        return None, "missing_disposition"
    amount = as_cents(row.get("expenditure_amount"))
    if amount is None:
        return None, "invalid_amount"
    # A memo item is not counted again as a separate payment/disbursement.
    if str(row.get("memo_code") or "").strip().upper() in ("X", "M"):
        return None, "memo_item"
    person = nominee_key(row)
    disposition = ("support_" if so == "S" else "oppose_") + person
    description = str(row.get("expenditure_description") or "").strip()
    group_name = spender(row)
    item = {
        "source_id": str(row.get("sub_id") or "").strip(),
        "original_sub_id": str(row.get("original_sub_id") or "").strip(),
        "transaction_id": str(row.get("transaction_id") or "").strip(),
        "candidate": person,
        "candidate_id": CANDIDATES[person]["id"],
        "disposition": disposition,
        "date": day.isoformat(),
        "amount_cents": amount,
        "group": group_name,
        "group_id": str(row.get("committee_id") or "").upper().strip(),
        "payee": str(row.get("payee_name") or "").strip(),
        "description": description or "Description not reported",
        "type": classify_for_race(
            row.get("committee_id"), CANDIDATES[person]["id"],
            day.isoformat(), description, str(row.get("category_code_full") or "")),

        "notice": bool(row.get("is_notice")),
        "filing_form": str(row.get("filing_form") or ""),
        "filing_date": str(row.get("filing_date") or "")[:10],
        "file_number": row.get("file_number"),
        "pdf_url": source_url(row),
        "election_type": str(row.get("election_type") or row.get("election_type_full") or ""),
        "original_category_code": str(row.get("category_code") or ""),
        "amendment_indicator": str(row.get("amendment_indicator") or ""),
    }
    return item, None


def prefer(record):
    # Prefer the processed regular filing, when an IE appeared in a 24/48-hour
    # notice and subsequently in the monthly/quarterly form; then newest report.
    return (not record["notice"], record.get("filing_date") or "", str(record.get("file_number") or ""))


def unique_rows(rows):
    """Conservative two-stage dedup, retaining audit counts.

    1. Explicit original_sub_id or same spender/target/transaction ID.
    2. Cross-report exact transaction fingerprint when an expedited IE notice
       duplicates a regular filing, even if the filing assigned a new ID.
    Identical-looking independent entries *within the same report class*
    are not collapsed solely based on amount/date.
    """
    counters = defaultdict(int)
    normalized = []
    for row in rows:
        item, excluded = normalize_row(row)
        if excluded:
            counters[excluded] += 1
        else:
            normalized.append(item)
    # Exact sub_id repeats across returned pages shouldn't count twice.
    by_source = {}
    no_source = []
    for item in normalized:
        sid = item["source_id"]
        if sid:
            if sid in by_source:
                counters["duplicate_source_id"] += 1
                if prefer(item) > prefer(by_source[sid]):
                    by_source[sid] = item
            else:
                by_source[sid] = item
        else:
            no_source.append(item)
    normalized = list(by_source.values()) + no_source
    # Match explicit persistent transaction IDs across reports, or amendment
    # original_sub_id. Composite includes candidate and spending direction.
    first = {}
    for item in normalized:
        keys = []
        group_key = item["group_id"] or norm(item["group"])
        basis = (group_key, item["candidate_id"], item["disposition"])
        if item["original_sub_id"] not in ("", "0", "None", "null"):
            keys.append(("orig",) + basis + (item["original_sub_id"],))
        if item["transaction_id"]:
            keys.append(("tx",) + basis + (norm(item["transaction_id"]),))
        matches = [first[k] for k in keys if k in first]
        if matches:
            current = max(matches, key=prefer)
            winner = max([current, item], key=prefer)
            for k, v in list(first.items()):
                if any(v is m for m in matches):
                    first[k] = winner
            for k in keys:
                first[k] = winner
            counters["repeated_transaction_or_amendment"] += 1
        else:
            for k in keys:
                first[k] = item
    referenced = {id(v) for v in first.values()}
    initial = [i for i in normalized if not (i["original_sub_id"] or i["transaction_id"])]
    initial += [v for v in normalized if id(v) in referenced]
    # To avoid losing rows with an ID but no index conflicts, each record
    # is indexed by a unique stable source key as well.
    identity = {id(x): x for x in initial}
    stage1 = list(identity.values())

    fingerprint = lambda x: (
        x["group_id"] or norm(x["group"]), x["candidate_id"],
        x["disposition"], x["date"], x["amount_cents"],
        norm(x["payee"]), norm(x["description"])
    )
    pools = defaultdict(lambda: {True: [], False: []})
    for item in stage1:
        pools[fingerprint(item)][item["notice"]].append(item)
    selected = []
    for sides in pools.values():
        reg, notice = sides[False], sides[True]
        # A notice and a regular filing that describe the *same* expenditure
        # should contribute only once. Preserve surplus identical transactions.
        reg.sort(key=prefer, reverse=True)
        notice.sort(key=prefer, reverse=True)
        duplicates = min(len(reg), len(notice))
        selected.extend(reg)
        selected.extend(notice[duplicates:])
        counters["notice_regular_duplicates"] += duplicates
    selected.sort(key=lambda x: (x["date"], x["disposition"], norm(x["group"]), x["source_id"]))
    return selected, dict(counters)


def summarize(rows, exclusions, raw_count, pages):
    # Financial amounts are integer cents throughout. Do not round in JS.
    disp_sums = {k: 0 for k in ORDER}
    daily = defaultdict(lambda: {k: 0 for k in ORDER})
    groups = {}
    pivot = {k: {} for k in ORDER}
    types = defaultdict(int)
    for item in rows:
        label = item["disposition"]
        disp_sums[label] += item["amount_cents"]
        daily[item["date"]][label] += item["amount_cents"]
        types[item["type"]] += item["amount_cents"]
        g = item["group"]
        if g not in groups:
            groups[g] = {"name": g, "total": 0, **{k: 0 for k in ORDER}}
        groups[g]["total"] += item["amount_cents"]
        groups[g][label] += item["amount_cents"]
        category = pivot[label].setdefault(item["type"], {})
        category[g] = category.get(g, 0) + item["amount_cents"]
    daily_rows = [{"date": d, **daily[d], "total": sum(daily[d].values())} for d in sorted(daily)]
    group_rows = sorted(groups.values(), key=lambda g: (-g["total"], norm(g["name"])))
    pivot_rows = []
    for key in ORDER:
        categories = []
        for name in CATEGORIES:
            spenders = pivot[key].get(name)
            if not spenders:
                continue
            group_detail = sorted(
                [{"name": g, "amount_cents": amt} for g, amt in spenders.items()],
                key=lambda x: (-x["amount_cents"], norm(x["name"])))
            categories.append({"name": name, "total": sum(spenders.values()), "groups": group_detail})
        pivot_rows.append({"key": key, "name": DISPOSITIONS[key], "total": disp_sums[key], "categories": categories})
    total = sum(disp_sums.values())
    assert total == sum(x["total"] for x in group_rows) == sum(x["total"] for x in daily_rows)
    assert total == sum(x["total"] for x in pivot_rows)
    ny_now = datetime.now(ZoneInfo("America/New_York"))
    return {
        "status": "ok",
        "generated_at": ny_now.isoformat(timespec="seconds"),
        "district": COMMITTEE_KEY,
        "period": {"cycle": 2026, "from": DATA_START.isoformat(), "to": DATA_END.isoformat(), "election": "2026 general"},
        "candidates": CANDIDATES,
        "disposition_order": ORDER,
        "disposition_labels": DISPOSITIONS,
        "colors": COLORS,
        "counts": {"api_rows": raw_count, "pages": pages, "included_rows": len(rows),
                   "excluded": exclusions},
        "totals": {
            "support_lawler": disp_sums["support_lawler"],
            "oppose_conley": disp_sums["oppose_conley"],
            "support_conley": disp_sums["support_conley"],
            "oppose_lawler": disp_sums["oppose_lawler"],
            "benefit_lawler": disp_sums["support_lawler"] + disp_sums["oppose_conley"],
            "benefit_conley": disp_sums["support_conley"] + disp_sums["oppose_lawler"],
            "all": total,
        },
        "daily": daily_rows,
        "groups": group_rows,
        "pivot": pivot_rows,
        "transactions": rows,
        "methodology": "FEC processed Schedule E (including 24/48-hour notices); 2026-cycle general election only; dates are reported expenditure dates; exact and cross-report duplicates suppressed.",
    }


def main():
    print("NY-17 IE: querying FEC processed Schedule E for 2026 general-election spending", flush=True)
    key = os.environ.get("FEC_API_KEY") or "DEMO_KEY"
    raw, pages = fetch_rows(key)
    records, exclusions = unique_rows(raw)
    data = summarize(records, exclusions, len(raw), pages)
    if not raw or not records:
        raise RuntimeError("FEC returned no qualifying rows; refusing to overwrite with zero without review")
    DATAFILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATAFILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(DATAFILE)
    print("VERIFIED " + str(len(records)) + " entries | " + str(pages) + " page(s) | " +
          str(data["totals"]["all"]) + " cents total | duplicates: " +
          str(exclusions.get("notice_regular_duplicates", 0) +
              exclusions.get("repeated_transaction_or_amendment", 0)), flush=True)


if __name__ == "__main__":
    main()
