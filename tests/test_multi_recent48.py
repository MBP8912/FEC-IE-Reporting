"""Cross-race tests of FEC expedited-notice 48-hour feeds and candidate labels."""
import sys
import unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import update_recent_all as multi
import update_ny17_recent as notice
from races import RACES,RACE_CODES

NOW=datetime(2026,10,22,15,0,tzinfo=timezone.utc)
RECEIVED="2026-10-22T14:00:00Z"

def sample(district):
    cfg=RACES[district]
    return {
        "district":district,"status":"ok","generated_at":"2026-10-22T10:30:00-04:00",
        "disposition_labels":{
            "support_lawler":"Support "+cfg["republican"]["short"],
            "oppose_conley":"Oppose "+cfg["democratic"]["short"],
            "support_conley":"Support "+cfg["democratic"]["short"],
            "oppose_lawler":"Oppose "+cfg["republican"]["short"],
        },
        "transactions":[
            {"source_id":district+"-f24","file_number":12345,
             "filing_date":"2026-10-22","date":"2026-10-20",
             "group":"New IE Fund","description":"MEDIA BUY","type":"TV",
             "disposition":"oppose_conley","notice":True,"filing_form":"F24",
             "amount_cents":105000,"pdf_url":"https://docquery.fec.gov/cgi-bin/fecimg/?123"},
            {"source_id":district+"-f5","file_number":12346,
             "filing_date":"2026-10-22","date":"2026-10-20",
             "group":"Noncommittee","description":"DIGITAL","type":"Digital",
             "disposition":"support_conley","notice":True,"filing_form":"F5",
             "amount_cents":95000,"pdf_url":"https://docquery.fec.gov/cgi-bin/fecimg/?124"},
            {"source_id":district+"-monthly","file_number":999999,
             "filing_date":"2026-10-22","date":"2026-10-20",
             "group":"HMP","description":"REPORTED PREVIOUSLY","type":"TV",
             "disposition":"oppose_conley","notice":False,"filing_form":"F3X",
             "amount_cents":90000000,"pdf_url":"https://docquery.fec.gov/cgi-bin/fecimg/?125"},
        ],
    }


class MultiRecentTests(unittest.TestCase):
    def test_all_nine_pages_have_matching_collapsible_notice_panels(self):
        for district in RACE_CODES:
            page=(ROOT/district/"index.html").read_text(encoding="utf-8")
            with self.subTest(race=district):
                self.assertIn('id="recent48-groups"',page)
                self.assertIn('src="../assets/recent48.js',page)
                self.assertLess(page.index('id="recent48-groups"'),
                                page.index('class="panel chart-section"'))
        self.assertTrue((ROOT/"assets"/"recent48.js").is_file())


    def test_all_races_preserve_correct_candidate_names_and_exclude_monthly_reports(self):
        sources={district:sample(district) for district in RACE_CODES}
        result=multi.create_reports(sources,{"12345":RECEIVED,"12346":RECEIVED},NOW)
        self.assertEqual(set(result),set(RACE_CODES))
        for district,report in result.items():
            with self.subTest(district=district):
                cfg=RACES[district]
                self.assertEqual(report["district"],district)
                self.assertEqual(report["candidate_names"],{
                    "lawler":cfg["republican"]["short"],"conley":cfg["democratic"]["short"]})
                self.assertEqual(report["disposition_labels"]["oppose_conley"],
                                 "Oppose "+cfg["democratic"]["short"])
                self.assertTrue(report["notice_only"])
                self.assertEqual(report["status"],"ok")
                self.assertEqual({t["filing_form"] for t in report["items"]},{"F24","F5"})
                self.assertEqual(sum(t["amount_cents"] for t in report["items"]),200000)
                self.assertNotIn("HMP",[t["spender"] for t in report["items"]])

    def test_unverified_dataset_is_pending_not_an_invented_zero(self):
        sources={district:sample(district) for district in RACE_CODES}
        sources["CA-13"]={"district":"CA-13","status":"not_initialized","transactions":[]}
        result=multi.create_reports(sources,{"12345":RECEIVED,"12346":RECEIVED},NOW)
        self.assertEqual(result["CA-13"]["status"],"pending")
        self.assertTrue(result["CA-13"]["notice_only"])
        self.assertEqual(result["CA-13"]["items"],[])

    def test_receipt_cache_requires_original_verified_notice_with_matching_race(self):
        good=notice.build_payload(sample("CO-5"),{"12345":RECEIVED},NOW)
        other={"district":"IA-1","status":"ok","notice_only":False,
               "items":[{"file_number":"999999","reported_at":RECEIVED,
                         "filing_form":"F3X","notice":False}]}
        found=multi.valid_cache({"CO-5":good,"IA-1":other})
        self.assertEqual(found,{"12345":"2026-10-22T14:00:00+00:00"})
        self.assertNotIn("999999",found)

if __name__=="__main__":
    unittest.main()
