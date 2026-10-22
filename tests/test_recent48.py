"""NY-17 last-48-hours feed uses exact FEC receipt times, not expenditure dates."""
import sys,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from update_ny17_recent import parse_receipt,build_payload

NOW=datetime(2026,10,22,13,15,tzinfo=timezone.utc)

def row(fid,filing,spending,disposition,amount):
    return dict(source_id=str(fid),file_number=fid,filing_date=filing,
                date=spending,disposition=disposition,amount_cents=amount,
                group="Example PAC",description="ADS",type="Digital",
                pdf_url="https://docquery.fec.gov/cgi-bin/fecimg/?1")
def dataset(rows):
    return dict(status="ok",district="NY-17",
                generated_at="2026-10-22T09:00:00-04:00",transactions=rows)

class RecentTests(unittest.TestCase):
    def test_datetime_parsing(self):
        self.assertIsNone(parse_receipt("2026-10-21"))
        self.assertEqual(parse_receipt("2026-10-21T13:00:00"),
                         datetime(2026,10,21,17,tzinfo=timezone.utc))
        self.assertEqual(parse_receipt("2026-10-21T17:00:00Z"),
                         datetime(2026,10,21,17,tzinfo=timezone.utc))
    def test_report_time_not_spending_time(self):
        rows=[row(1,"2026-10-21","2026-09-11","oppose_lawler",10000)]
        p=build_payload(dataset(rows),{"1":"2026-10-21T17:00:00Z"},NOW)
        self.assertEqual(p["status"],"ok")
        self.assertEqual(p["items"][0]["expenditure_date"],"2026-09-11")
        self.assertEqual(p["items"][0]["amount_cents"],10000)
    def test_rolling_exact_boundary(self):
        rows=[row(1,"2026-10-20","2026-10-19","oppose_lawler",100),
              row(2,"2026-10-20","2026-10-19","support_lawler",200)]
        p=build_payload(dataset(rows),
                        {"1":"2026-10-20T13:14:59Z","2":"2026-10-20T13:15:00Z"},NOW)
        included=[t for t in p["items"] if parse_receipt(t["reported_at"])>=NOW-timedelta(hours=48)]
        self.assertEqual(len(included),1)
        self.assertEqual(included[0]["amount_cents"],200)
    def test_missing_timestamp_never_counts_as_zero(self):
        p=build_payload(dataset([row(3,"2026-10-21","2026-10-20","support_lawler",15000)]),{},NOW)
        self.assertEqual(p["status"],"partial")
        self.assertEqual(p["unresolved_recent_items"],1)
        self.assertEqual(p["items"],[])
    def test_old_unmatched_not_in_recent_uncertainty(self):
        p=build_payload(dataset([row(4,"2026-10-18","2026-10-18","support_lawler",15000)]),{},NOW)
        self.assertEqual(p["status"],"ok")
        self.assertEqual(p["unresolved_recent_items"],0)
if __name__=="__main__": unittest.main()
