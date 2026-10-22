#!/usr/bin/env python3
"""Smoke-check publicly served GitHub Pages files after a deployment."""
from __future__ import annotations

import json
import sys
import time
from urllib.request import Request, urlopen

ROOT = "https://mbp8912.github.io/FEC-IE-Reporting/"
HEADERS = {"User-Agent": "FEC-IE-Reporting-Pages-Verification/1.0"}


def read(path):
    url = ROOT + path
    with urlopen(Request(url, headers=HEADERS), timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f"Unexpected HTTP {response.status}: {url}")
        if not response.geturl().lower().startswith(ROOT.lower()):
            raise RuntimeError(f"Unexpected redirect: {url} to {response.geturl()}")
        return response.read()


def verify():
    page = read("").decode("utf-8")
    if "NY-17 • 2026 Independent Expenditure Reporting" not in page:
        raise RuntimeError("Public HTML does not contain expected NY-17 title")
    for expected in ('id="groups-table"', 'id="pivot"', 'id="chart"', 'id="detail-dialog"',
                     'id="daily-breakdown"', 'id="daily-breakdown-rows"',
                     'Category of spend', 'v=20261021-clickable-bars-v1'):
        if expected not in page:
            raise RuntimeError(f"Missing dashboard element: {expected}")
    script = read("assets/app.js").decode("utf-8")
    if not all(x in script for x in ("function drawChart", "function groupTable", "function makePivot",
                                     "function openDetails", "function showChartBreakdown",
                                     'openDetails({date:day.date,disposition:d})',
                                     't.date===criteria.date')):
        raise RuntimeError("Frontend script does not contain the expected chart and drilldowns")
    styles = read("assets/styles.css").decode("utf-8")
    if ".headline-metrics" not in styles:
        raise RuntimeError("Dashboard stylesheet is incomplete")
    data = json.loads(read("data/data.json"))
    if data.get("status") != "ok":
        raise RuntimeError("Public JSON is not verified")
    transactions = data.get("transactions") or []
    groups = data.get("groups") or []
    if not transactions or not groups:
        raise RuntimeError("Published dataset is empty")
    total = sum(int(row["amount_cents"]) for row in transactions)
    if total != data["totals"]["all"]:
        raise RuntimeError("Published dashboard totals do not reconcile")
    if total != sum(g["total"] for g in groups):
        raise RuntimeError("Published group totals do not reconcile")
    print(f"VERIFIED NY-17 public Pages: HTTP 200, charts, pivot, source drilldowns, "
          f"{len(transactions)} transactions, {len(groups)} groups, ${total / 100:,.2f}.")
    print(ROOT)


if __name__ == "__main__":
    for attempt in range(1, 7):
        try:
            verify()
            sys.exit(0)
        except Exception as exc:
            print(f"Public Pages verification attempt {attempt}/6: {exc}", file=sys.stderr, flush=True)
            if attempt == 6:
                sys.exit(1)
            time.sleep(8)
