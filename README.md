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

**WI-1 and NE-2 freshness priority:** Each hourly job attempts a *complete* WI-1 scan followed by a *complete* NE-2 scan before the shared nine-race ingestion. Interrupted/rate-limited scans preserve previously verified data; successfully completed priority scans are skipped by the subsequent resumable pass to avoid duplicate API requests. The full-cycle timestamp shows the last **completed** FEC scan, not merely the last GitHub Pages deployment.

**48-hour feed consistency:** The 48-hour receipt feed is generated once after the priority scans (for early receipt lookups) and again **after** the shared full-cycle scan, so newly downloaded FEC notices do not remain invisible until the following refresh. If receipt timestamps are rate-limited, the notice feed marks potentially recent unresolved items as partial rather than reporting a misleading zero. The live deployment verifier rejects a feed built from an older full-cycle dataset.

## Verified FEC record-inclusion exceptions

Two locally scoped 2026 general-election exceptions are applied **during every FEC refresh**, not simply patched into the browser:

- **NY-17 / Planned Parenthood Votes (C00489799):** The FEC's October 1 and 11 Form 24 notices identify the candidate as `LAWLER, MICHAEL` and omit `candidate_id`. Only when the spender is C00489799 and the candidate is explicitly reported as Michael Lawler in NY-17 does `scripts/refresh.py` resolve the name to Mike Lawler's official ID `H2NY17162`. The expenditures oppose Lawler.
- **CO-4 / Freedom Caucus Fund (C00552851):** Certain Form 24 notices support Lauren Boebert (`H0CO03165`) but retain the older district code `CO-03`. `scripts/refresh_all.py` queries that exact committee/candidate pair independently and includes only 2026 general-election notices reported as CO-03/04. It combines them with the regular CO-4 search, deduplicating overlapping notices, repeat filings, and monthly-report disclosures. This is **not** a rule that transfers other CO-3 spending to CO-4.

The original FEC descriptions, filing-image links, spending dates and filer identifications are retained. The standalone 48-hour boxes still include only notices **actually received in the rolling 48-hour window**; historical filings from September/early October do not appear there simply because they have been newly incorporated into the full-cycle dataset.

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


## All nine races: expedited independent expenditures received in the last 48 hours

Each individual race URL has an identical compact 48-hour panel **above the daily expenditure timeline**. The initial view shows the two candidate-benefit totals, ordered largest first; a single accessible down-arrow expands both itemized tables and collapses them again. Each new expenditure lists **Spender, Disposition, Purpose, Amount, Date** and links to its FEC filing.

Only original 24/48-hour independent-expenditure notices are counted: Schedule E entries with `is_notice=true` and filing type `F24` (committees) or expedited `F5` (noncommittees). Monthly/quarterly Form 3X reports and repeat disclosures are excluded. The FEC e-file `receipt_date` determines the rolling 48-hour window; spending dates remain available as supplemental context. Electronic timestamps without a timezone are interpreted as America/New_York.

The `scripts/update_recent_all.py` updater uses the nine verified district datasets and deduplicates receipt-number lookups across races, writes `<district>/data/recent48.json` per race, and runs **before** the more expensive full-cycle FEC API update. Missing recent receipt timestamps are marked as partial, never silently treated as zero; processed FEC notices can lag filing time. Each box's data is validated before deployment. These additions do not change any full-cycle totals or any of the race-specific spending-type corrections. The browser applies the rolling cutoff at page load, including between hourly refreshes.

## Spiros Consulting branding

The same approved Spiros Consulting logo from the CA-13 Form 6 fundraising pilot is also used on **all nine independent-expenditure dashboards**. Each race header now displays the PNG at `assets/spiros-consulting-logo.png` beside its existing district badge, with responsive desktop/mobile sizing. The source logo matches the original PNG byte-for-byte. The chart, latest-48-hour notice section, classification overrides, data refresh and direct district URLs are unchanged. `scripts/verify_site.py` checks that the logo and correct header are deployed to each district.
