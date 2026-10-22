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

**NY-17 exceptions remain NY-17 only:** The September 11, 2026 LCV Victory Fund AD BUY is labeled Digital; CLF's NY-17 MEDIA PLACEMENT records are labeled TV. No other race inherits these classifications. Original FEC descriptions and source links remain unchanged.

This is an independent display of [FEC data](https://www.fec.gov/data/independent-expenditures/), not affiliated with the FEC, nominees, or spending groups.
