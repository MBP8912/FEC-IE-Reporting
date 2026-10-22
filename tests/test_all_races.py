"""Network-free tests for the nine independent district pages and FEC snapshots."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import refresh as core
from races import RACES, RACE_CODES, ALL_CANDIDATE_IDS
import refresh_all as multi

class TestAllRaces(unittest.TestCase):
    def test_distinct_candidate_ids_and_max_ten_per_fec_request(self):
        self.assertEqual(len(RACE_CODES),9)
        self.assertEqual(len(ALL_CANDIDATE_IDS),18)
        self.assertEqual(len(set(ALL_CANDIDATE_IDS)),18)
        self.assertEqual(sum(map(len,multi.BATCHES)),18)
        self.assertTrue(all(len(b)<=10 for b in multi.BATCHES))
        for key,config in RACES.items():
            self.assertRegex(key,r"^[A-Z]{2}-\d{1,2}$")
            self.assertRegex(config["republican"]["id"],r"^H[0-9A-Z]{8}$")
            self.assertRegex(config["democratic"]["id"],r"^H[0-9A-Z]{8}$")

    def test_race_selection_changes_disposition_labels_and_identity(self):
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY), \
             patch.object(core,"CANDIDATES",core.CANDIDATES), \
             patch.object(core,"DISPOSITIONS",core.DISPOSITIONS):
            for name,config in RACES.items():
                multi.set_race(name)
                self.assertEqual(core.nominee_key({"candidate_id":config["republican"]["id"]}),"lawler")
                self.assertEqual(core.nominee_key({"candidate_id":config["democratic"]["id"]}),"conley")
                self.assertIsNone(core.nominee_key({"candidate_id":"H6ZZ99999"}))
                self.assertEqual(core.DISPOSITIONS["support_lawler"],"Support "+config["republican"]["short"])
                self.assertEqual(core.DISPOSITIONS["oppose_conley"],"Oppose "+config["democratic"]["short"])
                self.assertEqual(core.DATAFILE,ROOT/name/"data"/"data.json")

    def test_ny17_manual_spending_rule_is_not_carried_to_other_districts(self):
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY), \
             patch.object(core,"CANDIDATES",core.CANDIDATES), \
             patch.object(core,"DISPOSITIONS",core.DISPOSITIONS):
            multi.set_race("NY-17")
            self.assertEqual(core.classify_ny17_override("C00504530","H6NY17171",
                               "2026-09-28","MEDIA PLACEMENT"),"TV")
            multi.set_race("CO-5")
            self.assertEqual(core.classify_ny17_override("C00504530","H6NY17171",
                               "2026-09-28","MEDIA PLACEMENT"),"Media (unspecified)")

    def test_batched_query_filters_all_the_named_candidates(self):
        for index,batch in enumerate(multi.BATCHES):
            url = multi.next_query("FAKE_KEY",index,{})
            self.assertEqual(url.count("candidate_id="),len(batch))
            self.assertIn("cycle=2026",url)
            self.assertIn("most_recent=true",url)
            self.assertIn("per_page=100",url)
            self.assertIn("min_date=2025-01-01",url)

    def test_no_live_query_needed_to_generate_separate_zero_or_positive_datasets(self):
        base = multi.new_state()
        base["status"]="in_progress"
        base["batch"]=1
        base["rows"]=[
          {"sub_id":"200", "candidate_id":RACES["CO-4"]["republican"]["id"],
           "committee_id":"C00111111","committee_name":"Sample IE Group",
           "candidate_name":"LAUREN BOEBERT","election_type":"G2026",
           "expenditure_date":"2026-10-19","expenditure_amount":1000,
           "support_oppose_indicator":"S","is_notice":True,
           "transaction_id":"X1","expenditure_description":"DIGITAL ADS"},
          {"sub_id":"201","candidate_id":RACES["WI-1"]["democratic"]["id"],
           "committee_id":"C00111111","committee_name":"Sample IE Group",
           "candidate_name":"MITCHELL BERMAN","election_type":"G2026",
           "expenditure_date":"2026-10-19","expenditure_amount":2000,
           "support_oppose_indicator":"S","is_notice":True,
           "transaction_id":"X2","expenditure_description":"MAIL"},
        ]
        # Verify direct processing without writing live data into the test checkout.
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY), \
             patch.object(core,"CANDIDATES",core.CANDIDATES), \
             patch.object(core,"DISPOSITIONS",core.DISPOSITIONS):
            multi.set_race("CO-4")
            raw=[r for r in base["rows"] if r["candidate_id"] in
                 {RACES["CO-4"]["republican"]["id"],RACES["CO-4"]["democratic"]["id"]}]
            rows,excluded=core.unique_rows(raw)
            result=core.summarize(rows,excluded,len(raw),1)
            self.assertEqual(result["totals"]["support_lawler"],100000)
            self.assertEqual(result["totals"]["all"],100000)
            multi.set_race("WI-1")
            raw=[r for r in base["rows"] if r["candidate_id"] in
                 {RACES["WI-1"]["republican"]["id"],RACES["WI-1"]["democratic"]["id"]}]
            rows,excluded=core.unique_rows(raw)
            result=core.summarize(rows,excluded,len(raw),1)
            self.assertEqual(result["totals"]["support_conley"],200000)
            self.assertEqual(result["totals"]["all"],200000)

if __name__=="__main__":
    unittest.main()
