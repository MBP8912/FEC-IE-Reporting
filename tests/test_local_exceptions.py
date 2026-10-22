"""Regression tests for the two manually verified 2026 FEC filing exceptions."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import refresh as core
import refresh_all as all_races


def record(**changes):
    sample={
        "sub_id":"100", "committee_id":"C00489799",
        "committee_name":"PLANNED PARENTHOOD VOTES",
        "candidate_id":None, "candidate_name":"LAWLER, MICHAEL",
        "candidate_office":"H","candidate_office_state":"NY",
        "candidate_office_district":"17","election_type":"G2026",
        "expenditure_date":"2026-10-09","expenditure_amount":50000.0,
        "support_oppose_indicator":"O","is_notice":True,
        "filing_form":"F24","filing_date":"2026-10-11",
        "expenditure_description":"ESTIMATED COST OF PRODUCTION AND DISSEMINATION OF DIGITAL AD",
        "payee_name":"PLANNED PARENTHOOD ACTION FUND",
        "transaction_id":"500768900"
    }
    sample.update(changes)
    return sample


class TestFECExceptions(unittest.TestCase):
    def test_planned_parenthood_ny17_candidate_alias_only(self):
        with patch.object(core,"COMMITTEE_KEY","NY-17"):
            row,reason=core.normalize_row(record())
            self.assertIsNone(reason)
            self.assertEqual(row["candidate"],"lawler")
            self.assertEqual(row["candidate_id"],"H2NY17162")
            self.assertEqual(row["disposition"],"oppose_lawler")
            self.assertEqual(row["group_id"],"C00489799")
            self.assertEqual(row["type"],"Digital")
            self.assertEqual(row["amount_cents"],5000000)
            for changed in (
                {"committee_id":"C11111111"},
                {"candidate_office_district":"19"},
                {"candidate_office_state":"CA"},
                {"candidate_name":"LAWLER, DIFFERENT"},
                {"candidate_id":"H2NY99999"}
            ):
                with self.subTest(changes=changed):
                    self.assertEqual(core.normalize_row(record(**changed))[1],"other_candidate")
        with patch.object(core,"COMMITTEE_KEY","NY-19"):
            self.assertIsNone(core.nominee_key(record()))

    def test_ppv_repeated_regular_report_not_double_counted(self):
        with patch.object(core,"COMMITTEE_KEY","NY-17"):
            notice=record(
                sub_id="201", transaction_id="duplicate-1",
                expenditure_amount=101.65,expenditure_date="2026-06-03",
                expenditure_description="STAFF TIME FOR VOTER COMMUNICATIONS")
            monthly=record(
                sub_id="202",transaction_id="duplicate-1",
                candidate_id="H2NY17162",candidate_name="LAWLER, MIKE",
                expenditure_amount=101.65,expenditure_date="2026-06-03",
                expenditure_description="STAFF TIME FOR VOTER COMMUNICATIONS",
                is_notice=False,filing_form="F3X",filing_date="2026-07-20")
            digital=record(sub_id="203",transaction_id="fresh",expenditure_amount=50000)
            included,excluded=core.unique_rows([notice,monthly,digital])
            self.assertEqual(len(included),2)
            self.assertEqual(sum(x["amount_cents"] for x in included),5010165)
            self.assertEqual(len([x for x in included if x["transaction_id"]=="duplicate-1"]),1)
            self.assertTrue(excluded.get("repeated_transaction_or_amendment"))

    def test_targeted_co3_notice_search_accepts_only_real_co4_boebert_id_general(self):
        baseline=record(
            committee_id="C00552851",committee_name="FREEDOM CAUCUS FUND",
            candidate_id="H0CO03165",candidate_name="BOEBERT, LAUREN",
            candidate_office_state="CO",candidate_office_district="03",
            support_oppose_indicator="S",
            expenditure_amount=237083.20,expenditure_date="2026-09-22",
            filing_date="2026-09-23",
            transaction_id="EE125CCEF00774AB5ACF",
            expenditure_description="IE- BOEBERT- MEDIA BUY"
        )
        dataset=[baseline,
                 dict(baseline,sub_id="102",candidate_id="H0CO99999"),
                 dict(baseline,sub_id="103",committee_id="C99999999"),
                 dict(baseline,sub_id="104",election_type="P2026"),
                 dict(baseline,sub_id="105",candidate_office_state="TX"),
                 dict(baseline,sub_id="106",candidate_office_district="05")]
        urls=[]
        def request(url,attempts=1):
            urls.append(url)
            return {"results":dataset,"pagination":{"last_indexes":{}}}
        with patch.object(core,"request_json",side_effect=request):
            accepted,pages=all_races.fetch_co4_misfiled_boebert_notices("TEST_KEY")
        self.assertEqual(pages,1)
        self.assertEqual(len(accepted),1)
        self.assertEqual(accepted[0]["transaction_id"],"EE125CCEF00774AB5ACF")
        self.assertIn("candidate_id=H0CO03165",urls[0])
        self.assertIn("committee_id=C00552851",urls[0])
        self.assertIn("is_notice=true",urls[0])
        self.assertNotIn("candidate_office_district=",urls[0])

    def test_co4_supplement_integrated_before_finalization(self):
        st=all_races.new_state()
        st["batch"]=1 # CO-4 in the nine-race ordering
        source=record(
            committee_id="C00552851",candidate_id="H0CO03165",
            candidate_name="BOEBERT, LAUREN",
            candidate_office_state="CO",candidate_office_district="03",
            election_type="G2026",expenditure_amount=237083.20,
            expenditure_description="IE- BOEBERT- MEDIA BUY",
            support_oppose_indicator="S"
        )
        urls=[]
        def request(url,attempts=1):
            urls.append(url)
            if "committee_id=C00552851" in url:
                return {"results":[source],"pagination":{"last_indexes":{}}}
            return {"results":[],"pagination":{"last_indexes":{}}}
        with patch.object(core,"request_json",side_effect=request),\
             patch.object(all_races,"save_state"),\
             patch.object(all_races,"finalize_one_race") as finalize:
            self.assertFalse(all_races.capture_pages(st,"KEY",2))
        self.assertEqual(st["batch"],2)
        self.assertEqual(st["pages"],2)
        self.assertEqual(st["rows"],[])
        self.assertEqual(finalize.call_count,1)
        name,raw,pages=finalize.call_args.args
        self.assertEqual(name,"CO-4")
        self.assertEqual(pages,2)
        self.assertEqual(len(raw),1)
        self.assertEqual(raw[0]["candidate_office_district"],"03")

    def test_co4_supplement_failure_keeps_unverified_district_unpublished(self):
        st=all_races.new_state()
        st["batch"]=1
        def request(url,attempts=1):
            if "committee_id=C00552851" in url:
                raise RuntimeError("FEC temporary rate limit")
            return {"results":[],"pagination":{}}
        with patch.object(core,"request_json",side_effect=request),\
             patch.object(all_races,"save_state") as saved,\
             patch.object(all_races,"finalize_one_race") as finalized:
            self.assertFalse(all_races.capture_pages(st,"KEY",2))
        self.assertTrue(saved.called)
        self.assertFalse(finalized.called)
        self.assertEqual(st["batch"],1)
        self.assertEqual(st["rows"],[])

if __name__=="__main__":
    unittest.main()
