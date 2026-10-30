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

    def test_priority_wi_fetches_all_pages_before_publishing(self):
        first={"results":[{"sub_id":str(i)} for i in range(100)],
               "pagination":{"last_indexes":{"last_index":"100","last_expenditure_date":"2026-10-28"}}}
        second={"results":[{"sub_id":str(i)} for i in range(100,200)],
                "pagination":{"last_indexes":{"last_index":"200","last_expenditure_date":"2026-10-20"}}}
        third={"results":[{"sub_id":"200"}],"pagination":{}}
        with patch.object(core,"request_json",side_effect=[first,second,third]) as query, \
             patch.object(multi,"finalize_one_race") as finalize:
            self.assertTrue(multi.refresh_priority_race("WI-1","TEST"))
        self.assertEqual(query.call_count,3)
        for call in query.call_args_list:
            self.assertIn("candidate_office_state=WI",call.args[0])
            self.assertIn("candidate_office_district=01",call.args[0])
        self.assertEqual(finalize.call_count,1)
        self.assertEqual(finalize.call_args.args[0],"WI-1")
        self.assertEqual(len(finalize.call_args.args[1]),201)
        self.assertEqual(finalize.call_args.args[2],3)

    def test_priority_ne_fetches_all_pages_before_publishing(self):
        first={"results":[{"sub_id":str(i)} for i in range(100)],
               "pagination":{"last_indexes":{"last_index":"100","last_expenditure_date":"2026-10-28"}}}
        last={"results":[{"sub_id":"100"}],"pagination":{}}
        with patch.object(core,"request_json",side_effect=[first,last]) as query, \
             patch.object(multi,"finalize_one_race") as finalize:
            self.assertTrue(multi.refresh_priority_race("NE-2","TEST"))
        self.assertEqual(query.call_count,2)
        for call in query.call_args_list:
            self.assertIn("candidate_office_state=NE",call.args[0])
            self.assertIn("candidate_office_district=02",call.args[0])
        finalize.assert_called_once()
        self.assertEqual(finalize.call_args.args[0],"NE-2")
        self.assertEqual(len(finalize.call_args.args[1]),101)

    def test_priority_wi_rate_limit_preserves_existing_snapshot(self):
        first={"results":[{"sub_id":str(i)} for i in range(100)],
               "pagination":{"last_indexes":{"last_index":"100","last_expenditure_date":"2026-10-28"}}}
        with patch.object(core,"request_json",side_effect=[first,RuntimeError("FEC HTTP 429")]), \
             patch.object(multi,"finalize_one_race") as finalize:
            self.assertFalse(multi.refresh_priority_race("WI-1","TEST"))
        finalize.assert_not_called()

    def test_priority_ne_rate_limit_preserves_existing_snapshot(self):
        first={"results":[{"sub_id":str(i)} for i in range(100)],
               "pagination":{"last_indexes":{"last_index":"100","last_expenditure_date":"2026-10-28"}}}
        with patch.object(core,"request_json",side_effect=[first,RuntimeError("FEC HTTP 429")]), \
             patch.object(multi,"finalize_one_race") as finalize:
            self.assertFalse(multi.refresh_priority_race("NE-2","TEST"))
        finalize.assert_not_called()

    def test_bulk_scan_skips_wi_if_priority_scan_finished(self):
        state=multi.new_state()
        idx=next(i for i,b in enumerate(multi.BATCHES) if b["district"]=="WI-1")
        state["batch"]=idx
        state["rows"]=[{"sub_id":"old-checkpointed-row"}]
        state["cursor"]={"last_index":"old"}
        with patch.object(multi,"save_state") as save, \
             patch.object(core,"request_json") as query:
            self.assertFalse(multi.capture_pages(state,"TEST",0,fresh_races={"WI-1"}))
        self.assertEqual(state["batch"],idx+1)
        self.assertEqual(state["rows"],[])
        self.assertEqual(state["cursor"],{})
        self.assertIn("WI-1",state["completed_races"])
        query.assert_not_called()
        self.assertTrue(save.called)

    def test_bulk_scan_skips_ne_if_priority_scan_finished(self):
        state=multi.new_state()
        idx=next(i for i,b in enumerate(multi.BATCHES) if b["district"]=="NE-2")
        state["batch"]=idx
        state["rows"]=[{"sub_id":"old-checkpointed-row"}]
        state["cursor"]={"last_index":"old"}
        with patch.object(multi,"save_state") as save, \
             patch.object(core,"request_json") as query:
            self.assertFalse(multi.capture_pages(state,"TEST",0,fresh_races={"WI-1","NE-2"}))
        # The next race in the established ordering is WI-1, also marked
        # as freshly verified, so the cursor should skip both districts.
        self.assertEqual(state["batch"],idx+2)
        self.assertEqual(state["rows"],[])
        self.assertEqual(state["cursor"],{})
        self.assertIn("NE-2",state["completed_races"])
        self.assertIn("WI-1",state["completed_races"])
        query.assert_not_called()
        self.assertTrue(save.called)

if __name__=="__main__":unittest.main()
