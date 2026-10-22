# 2026 Independent Expenditure Dashboards

The root URL redirects directly to **NY-17**, not a race selection page.

| District | Republican | Democrat / DFL | Dashboard |
|---|---|---|---|
| NY-17 | Mike Lawler | Cait Conley | [NY-17](https://mbp8912.github.io/FEC-IE-Reporting/NY-17/) |
| CO-4 | Lauren Boebert | Eileen Laubacher | [CO-4](https://mbp8912.github.io/FEC-IE-Reporting/CO-4/) |
| CO-5 | Jeff Crank | Jessica Killin | [CO-5](https://mbp8912.github.io/FEC-IE-Reporting/CO-5/) |
| IA-1 | Mariannette Miller-Meeks | Christina Bohannan | [IA-1](https://mbp8912.github.io/FEC-IE-Reporting/IA-1/) |
| MN-1 | Brad Finstad | Jake Johnson | [MN-1](https://mbp8912.github.io/FEC-IE-Reporting/MN-1/) |
| NE-2 | Brinker Harding | Denise Powell | [NE-2](https://mbp8912.github.io/FEC-IE-Reporting/NE-2/) |
| WI-1 | Bryan Steil | Mitchell Berman | [WI-1](https://mbp8912.github.io/FEC-IE-Reporting/WI-1/) |
| NY-19 | Peter Oberacker | Josh Riley | [NY-19](https://mbp8912.github.io/FEC-IE-Reporting/NY-19/) |
| CA-13 | Kevin Lincoln | Adam Gray | [CA-13](https://mbp8912.github.io/FEC-IE-Reporting/CA-13/) |

Each race uses the completed NY-17 layout: candidate totals with support/oppose subtotals, daily stacked spending chart (click a colored segment for spender, category and amount), an expandable disposition → spending type → group table, and an independently sortable group table. The latter two appear **type first, group second**. The former “Who Is Spending,” “What the Money Funded,” extra spending disclaimer, and entire “About these figures” section are absent.

**Data:** FEC processed Schedule E; 2026-cycle general election expenditures dated January 1, 2025 through November 3, 2026. Expedited 24/48-hour notices and periodic reports are reconciled using identifiers and conservative duplicate matching. All monetary totals use integer cents. This is third-party independent expenditure spending, not candidate fundraising.

**Automatic refresh:** Nine candidate-specific datasets live at `<district>/data/data.json`. GitHub Actions queries the FEC for both nominees in each race (up to ten IDs per API request). Since the FEC caps pages at 100 results and the shared DEMO_KEY is rate-limited, collection saves verified pagination progress in `data/ingest_checkpoint.json` and resumes on its next scheduled hourly run. A district only displays verified complete totals; until then, it shows a clearly marked pending status. For more efficient refreshes, register a free [OpenFEC API key](https://api.open.fec.gov/developers/) and add it as a GitHub Actions secret named `FEC_API_KEY`.

## Narrow, race-specific spending type corrections

The dashboard owner's classifications apply **only to the named filer and spending description in the indicated race**. They are implemented in `scripts/refresh.py`, tested by `tests/test_manual_categories.py`, and applied to archived data by `scripts/reclassify_cached.py` even during FEC API rate limits.

| District | Spender (FEC committee) | Original FEC description | Display category |
|---|---|---|---|
| NY-17 | LCV Victory Fund (C00486845), Sept. 11 only | AD BUY | Digital |
| NY-17 | CLF (C00504530) | MEDIA PLACEMENT | TV |
| CO-5 | No Going Back PAC (C00960435) | PLACED MEDIA: TV AND CONNECTED TV | TV |
| CO-5 | Women Vote (C00473918) | MAILHOUSE | Mail |
| IA-1 | CLF (C00504530) | MEDIA PLACEMENT | TV |
| IA-1 | LCV Victory Fund (C00486845) | AD BUY | TV |
| MN-1 | LCV Victory Fund (C00486845) | AD BUY | TV |
| NE-2 | CLF (C00504530) | MEDIA PLACEMENT | TV |
| WI-1 | Fairshake (C00835959) | IE-STEIL-MEDIA BUY | TV |
| WI-1 | CLF (C00504530) | MEDIA PLACEMENT | TV |
| WI-1 | End Citizens United (C00573261) | MEDIA BUY | Digital |
| WI-1 | AB PAC (C00492140) | BILLBOARD ADVERTISING (estimated/actual cost) | Billboard |
| CA-13 | CLF (C00504530) | MEDIA PLACEMENT | TV |
| CA-13 | AB PAC (C00492140) | BILLBOARD ADVERTISING (estimated/actual cost) | Billboard |

This does **not** change a race's dollar totals or original FEC text. Other descriptions (e.g., CLF DIGITAL PLACEMENT and MEDIA PRODUCTION), groups, and races retain their general categories. The new Billboard category is deliberately limited to AB PAC's specified WI-1 and CA-13 expenditures.

This is an independent display of [FEC data](https://www.fec.gov/data/independent-expenditures/), not affiliated with the FEC, nominees, or spending groups.


## NY-17 pilot: independent expenditures reported in the last 48 hours

Only the [NY-17 dashboard](https://mbp8912.github.io/FEC-IE-Reporting/NY-17/) has a panel **above** the daily expenditure timeline. It shows both candidate-benefit totals together in one compact panel, larger first. Individual spending tables are **collapsed by default**; the single down-arrow opens the details for both candidates (and can collapse them again). Expanded items retain the order **Spender, Disposition, Purpose, Amount, Date**. The Date cell shows **FEC receipt time (Eastern)**, with the expenditure date separately indicated.

**Important distinction:** The original daily timeline groups spending by **expenditure date**. The new panel uses the FEC electronic filing system's **receipt_date timestamp**, resolved via `/efile/filings/` by filing number. Schedule E's `filing_date` alone has only day precision and cannot define an exact rolling 48-hour window. If OpenFEC omits a timezone from the e-filing receipt timestamp, the dashboard interprets it as America/New_York. The panel only counts unique processed, general-election expenditures present in the verified NY-17 dataset; processed data can lag newly submitted notices. Missing receipt times are disclosed rather than treated as zero.

The hourly workflow checks source receipt times in `scripts/update_ny17_recent.py` **before** the multi-race API refresh can exhaust the shared DEMO_KEY limit. It stores the small, independent `NY-17/data/recent48.json` file and retains previously verified data if receipt metadata is temporarily unavailable. The browser applies a fresh 48-hour cutoff whenever the page loads, so older records automatically age out even between updates. This feature is NY-17-only pending user review.
