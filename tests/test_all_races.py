"""Network-free checks that each district includes valid FEC reports lacking candidate IDs."""
import sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import refresh as core
import refresh_all as multi
from races import RACES,RACE_CODES,ALL_CANDIDATE_IDS

class TestAllRaces(unittest.TestCase):
    def test_searches_house_districts_not_only_nominee_ids(self):
        self.assertEqual(len(multi.BATCHES),9)
        self.assertEqual(len(ALL_CANDIDATE_IDS),18)
        self.assertEqual(len(set(ALL_CANDIDATE_IDS)),18)
        for i,cfg in enumerate(multi.BATCHES):
            url=multi.next_query("TEST",i,{})
            self.assertIn("candidate_office_state="+cfg["state"],url)
            self.assertIn("candidate_office_district="+cfg["number"],url)
            self.assertIn("candidate_office=H",url)
            self.assertNotIn("candidate_id=",url)
            self.assertIn("most_recent=true",url)

    def test_each_race_filters_to_official_nominees(self):
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY), \
             patch.object(core,"CANDIDATES",core.CANDIDATES), \
             patch.object(core,"DISPOSITIONS",core.DISPOSITIONS):
            for name,r in RACES.items():
                multi.set_race(name)
                self.assertEqual(core.nominee_key({"candidate_id":r["republican"]["id"]}),"lawler")
                self.assertEqual(core.nominee_key({"candidate_id":r["democratic"]["id"]}),"conley")
                self.assertIsNone(core.nominee_key({"candidate_id":"H6ZZ99999"}))

    def test_ny17_clf_missing_candidate_id_is_counted_as_tv(self):
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY), \
             patch.object(core,"CANDIDATES",core.CANDIDATES), \
             patch.object(core,"DISPOSITIONS",core.DISPOSITIONS):
            multi.set_race("NY-17")
            tx={"sub_id":"101","committee_id":"C00504530","committee_name":"CLF",
                "candidate_id":None,"candidate_name":"CONLEY, CAIT",
                "election_type":"G2026","expenditure_date":"2026-10-09",
                "expenditure_amount":1430008.55,"support_oppose_indicator":"O",
                "is_notice":True,"expenditure_description":"MEDIA PLACEMENT",
                "transaction_id":"SE24.6100"}
            row,error=core.normalize_row(tx)
            self.assertIsNone(error)
            self.assertEqual(row["candidate"],"conley")
            self.assertEqual(row["candidate_id"],"H6NY17171")
            self.assertEqual(row["type"],"TV")
            self.assertEqual(row["amount_cents"],143000855)

    def test_missing_id_matching_does_not_lose_unambiguous_other_nominees(self):
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY), \
             patch.object(core,"CANDIDATES",core.CANDIDATES), \
             patch.object(core,"DISPOSITIONS",core.DISPOSITIONS):
            multi.set_race("CO-4")
            self.assertEqual(core.nominee_key({"candidate_name":"BOEBERT, LAUREN"}),"lawler")
            self.assertEqual(core.nominee_key({"candidate_name":"LAUBACHER, EILEEN"}),"conley")
            self.assertIsNone(core.nominee_key({"candidate_name":"OTHER PERSON"}))
            self.assertEqual(core.classify_ny17_override(
                 "C00504530","H6NY17171","2026-10-09","MEDIA PLACEMENT"),
                 "Media (unspecified)")

    def test_partial_query_saves_checkpoint_without_publishing(self):
        st=multi.new_state()
        fake={"results":[{"sub_id":str(i),"candidate_id":None,
            "candidate_name":"CONLEY, CAIT"} for i in range(100)],
            "pagination":{"last_indexes":{"last_index":"100",
                                          "last_expenditure_date":"2026-10-09"}}}
        with patch.object(core,"request_json",return_value=fake), \
             patch.object(multi,"save_state") as saved, \
             patch.object(multi,"finalize_one_race") as finalized:
            self.assertFalse(multi.capture_pages(st,"TEST",1))
        self.assertEqual(st["batch"],0)
        self.assertEqual(st["race_pages"],1)
        self.assertEqual(len(st["rows"]),100)
        self.assertFalse(finalized.called)
        self.assertTrue(saved.called)

if __name__=="__main__":unittest.main()
