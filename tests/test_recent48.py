"""NY-17 last-48-hours feed uses exact FEC receipt times, not expenditure dates."""
import sys,unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from update_ny17_recent import parse_receipt,build_payload,is_new_notice,recent_candidates

NOW=datetime(2026,10,22,13,15,tzinfo=timezone.utc)

def row(fid,filing,spending,disposition,amount):
    return dict(source_id=str(fid),file_number=fid,filing_date=filing,
                date=spending,disposition=disposition,amount_cents=amount,
                group="Example PAC",description="ADS",type="Digital",
                notice=True,filing_form="F24",
                pdf_url="https://docquery.fec.gov/cgi-bin/fecimg/?1")
def dataset(rows):
    return dict(status="ok",district="NY-17",
                generated_at="2026-10-22T09:00:00-04:00",transactions=rows)

class RecentTests(unittest.TestCase):
    def test_pilot_only_and_placement_above_timeline(self):
        html=(ROOT/"NY-17"/"index.html").read_text(encoding="utf-8")
        self.assertLess(html.index('id="recent48-groups"'),
                        html.index('class="panel chart-section"'))
        self.assertIn('src="./recent48.js',html)
        self.assertIn('Spending reported in the last 48 hours',html)
        script=(ROOT/"NY-17"/"recent48.js").read_text(encoding="utf-8")
        self.assertIn('["Spender","Disposition","Purpose","Amount","Date"]',script)
        self.assertIn('48*60*60*1000',script)
        for race in ("CO-4","CO-5","IA-1","MN-1","NE-2","WI-1","NY-19","CA-13"):
            other=(ROOT/race/"index.html").read_text(encoding="utf-8")
            self.assertNotIn('id="recent48-groups"',other)

    def test_regular_monthly_filing_never_counts_as_new_notice(self):
        # HMP's Form 3X monthly report includes old, previously announced IEs.
        hmp=row(2033863,"2026-10-20","2026-09-29","oppose_lawler",47378256)
        hmp.update(group="HMP",notice=False,filing_form="F3X")
        other=row(2032459,"2026-10-20","2026-10-07","oppose_lawler",17496000)
        other.update(group="VOTEVETS",notice=False,filing_form="F3X")
        new=row(2035136,"2026-10-21","2026-10-21","oppose_conley",2000000)
        receipts={str(x["file_number"]):"2026-10-21T17:00:00Z" for x in (hmp,other,new)}
        self.assertFalse(is_new_notice(hmp))
        self.assertFalse(is_new_notice(other))
        self.assertTrue(is_new_notice(new))
        self.assertEqual(recent_candidates(dataset([hmp,other,new]),NOW),[new])
        payload=build_payload(dataset([hmp,other,new]),receipts,NOW)
        self.assertEqual(len(payload["items"]),1)
        self.assertEqual(payload["items"][0]["source_id"],str(new["file_number"]))
        self.assertEqual(payload["items"][0]["filing_form"],"F24")
        self.assertEqual(payload["items"][0]["notice"],True)
        self.assertEqual(payload["items"][0]["amount_cents"],2000000)
        self.assertTrue(payload["notice_only"])

    def test_noncommittee_form5_notice_is_valid_but_quarterly_repeats_are_not(self):
        fresh=row(2033828,"2026-10-21","2026-10-21","oppose_lawler",17500)
        fresh.update(group="FOOD AND WATER ACTION",notice=True,filing_form="F5")
        quarterly=dict(fresh,source_id="quarterly-duplicate",file_number=3000000,
                       notice=False)
        self.assertTrue(is_new_notice(fresh))
        self.assertFalse(is_new_notice(quarterly))
        p=build_payload(dataset([fresh,quarterly]),
                        {"2033828":"2026-10-21T17:00:00Z",
                         "3000000":"2026-10-21T17:00:00Z"},NOW)
        self.assertEqual(len(p["items"]),1)
        self.assertEqual(p["items"][0]["filing_form"],"F5")

    def test_missing_or_spoofed_notice_marker_is_not_accepted(self):
        regular=row(1,"2026-10-21","2026-10-21","support_lawler",100)
        regular["notice"]=False
        self.assertFalse(is_new_notice(regular))
        regular["notice"]=True
        regular["filing_form"]="F3X"
        self.assertFalse(is_new_notice(regular))
        regular["filing_form"]="F24"
        self.assertTrue(is_new_notice(regular))
        regular.pop("notice")
        self.assertFalse(is_new_notice(regular))

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
