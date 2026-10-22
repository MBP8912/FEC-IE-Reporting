# NY-17 Independent Expenditure Spending 2026

Public NY-17 pilot dashboard for spending in the 2026 general election, benefiting or opposing Mike Lawler (H2NY17162) and Cait Conley (H6NY17171).

**Main race directory:** https://mbp8912.github.io/FEC-IE-Reporting/

**NY-17 dashboard:** https://mbp8912.github.io/FEC-IE-Reporting/NY-17/

The repository is organized for separate race dashboards. NY-17 is in `NY-17/index.html`, its verified spending data is in `NY-17/data/data.json`, shared browser assets are in `assets/`, and the root `index.html` is the race-selection directory.

## Features

Two candidate-benefit headline totals, each broken into support and opposition spending; daily stacked chart separated into four dispositions; sortable spending-group table; expandable disposition / spending type / group pivot; original FEC expenditure descriptions and source-image links; transaction-level CSV export.

**Daily chart drilldown:** Click (or focus and press Enter on) a colored bar segment to open the underlying expenditures for that date and support/oppose disposition. The popup begins with subtotals by **spender × category of spend**, with the **amount** for each combination. Below that, individual FEC items retain their expenditure date, spender, normalized spending category, original description, payee, amount, and source-document link. The sum of the breakdown rows equals the selected colored bar segment.

## Data source and deduplication

Source: processed FEC Schedule E API, with cycle 2026, House NY-17, most_recent=true, expenditure dates from January 1, 2025 to November 3, 2026. **Both** periodic reports and 24/48-hour expedited notices are included. Only transactions explicitly designated for the 2026 general election and pertaining to the two nominees are counted. Daily values use the FEC expenditure date.

Data reconciliation:
1. Collapse identical FEC sub_id values.
2. Reconcile amended/duplicated records using original_sub_id or filer-candidate-direction-transaction identifiers, preferring newer reports.
3. If a 24/48-hour notice and periodic filing both describe the same expenditure, using identical filer, candidate, disposition, date, amount, payee and normalized description, count it once, preferring the periodic filing.
4. Preserve otherwise distinct identical-amount transactions within the same report class.
5. Exclude memo items, unrelated candidates, and primary/special/other-election records.

Classification standardizes reported descriptions conservatively. Generic MEDIA PLACEMENT is Media (unspecified), not automatically classified as TV. The original FEC description is always shown in transaction details. Unclassifiable descriptions are Other / Unclassified.

### NY-17-specific one-off category overrides (not general rules)

Per the dashboard owner's directions, the following **NY-17 only** records are manually classified in `scripts/refresh.py` by FEC committee ID, candidate, original description and (for LCV) expenditure date:

- **LCV VICTORY FUND (C00486845):** the September 11, 2026 `AD BUY` entry, $457,000.00, is **Digital**.
- **CLF (C00504530):** its NY-17 `MEDIA PLACEMENT` expenditure entries ($4,829,985.45 total in the verified October 21 dataset) are **TV**. This does **not** affect CLF's distinct `DIGITAL PLACEMENT` or `MEDIA PRODUCTION` expenditures.

These adjustments affect only the standardized display category, including the pivot table and clickable daily-chart breakdown. They do **not** change expenditures' amounts, support/oppose disposition, deduplication, dates, group names, or original FEC descriptions. The general classifier continues to categorize an unqualified `AD BUY` or `MEDIA PLACEMENT` as `Media (unspecified)` for other groups, records, or races.

All amounts are processed as integer cents. Spending benefiting a candidate equals expenditures reported to support them plus expenditures reported to oppose their opponent. These are NOT contributions to the candidate or proof of coordination.

## Update and hosting

A GitHub Actions workflow tests parsing, deduplication, frontend JavaScript and categories; fetches current FEC data; archives successfully verified JSON at `NY-17/data/data.json`; publishes the GitHub Pages race directory and NY-17 dashboard. Approximately hourly refreshes are scheduled. Failed API calls never overwrite an earlier verified dataset.

A free OpenFEC API key is recommended as a repository Actions secret named FEC_API_KEY. Without it the workflow uses the shared DEMO_KEY, which may be rate-limited.

References: https://www.fec.gov/help-candidates-and-committees/making-independent-expenditures/reporting-independent-expenditures-form-3x/ and https://www.fec.gov/campaign-finance-data/independent-expenditures-file-description/

This is an independent public-data presentation, unaffiliated with the FEC or candidates.
