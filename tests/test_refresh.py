import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from refresh import as_cents, classify, normalize_row, unique_rows, summarize, is_2026_general

def record(**changes):
    base = {
        "sub_id": "10001", "original_sub_id": None,
        "committee_id": "C00111111",
        "committee_name": "Example Voter PAC",
        "candidate_id": "H2NY17162",
        "candidate_name": "LAWLER, MIKE",
        "candidate_office": "H", "candidate_office_state": "NY",
        "candidate_office_district": "17",
        "election_type": "G2026",
        "expenditure_date": "2026-10-17",
        "expenditure_amount": 2500.0,
        "support_oppose_indicator": "S",
        "is_notice": True,
        "expenditure_description": "Digital ad buy",
        "payee_name": "Vendor",
        "filing_date": "2026-10-18",
        "transaction_id": "ABC",
        "filing_form": "F24",
    }
    base.update(changes)
    return base

class TestIE(unittest.TestCase):
    def test_general_only(self):
        self.assertTrue(is_2026_general(record()))
        self.assertFalse(is_2026_general(record(election_type="P2026")))
        self.assertFalse(is_2026_general(record(election_type="G2024")))
    def test_amount(self):
        self.assertEqual(as_cents(1000.015), 100002)
        self.assertIsNone(as_cents("NaN"))
    def test_categories(self):
        self.assertEqual(classify("DIRECT MAIL PRINTING"), "Mail")
        self.assertEqual(classify("SMS Voter Contact"), "Text")
        self.assertEqual(classify("Digital Streaming TV Ads"), "Digital")
        self.assertEqual(classify("Television cable ads"), "TV")
        self.assertEqual(classify("TV ad production"), "TV")
        self.assertEqual(classify("MEDIA PLACEMENT"), "Media (unspecified)")
        self.assertEqual(classify("AD BUY"), "Media (unspecified)")
        self.assertEqual(classify("TEXT BANK"), "Text")
        self.assertEqual(classify("EMAIL SERVICES"), "Digital")
        self.assertEqual(classify("VOTER DATA"), "Research")
        self.assertEqual(classify("Miscellaneous services"), "Other / Unclassified")
    def test_nominees_and_2026_general(self):
        x, err = normalize_row(record(candidate_id="H6NY17171", support_oppose_indicator="O"))
        self.assertIsNone(err)
        self.assertEqual(x["disposition"], "oppose_conley")
        self.assertEqual(normalize_row(record(election_type="P2026"))[1], "other_election")
        self.assertEqual(normalize_row(record(candidate_id="H2NY17001"))[1], "other_candidate")
        self.assertEqual(normalize_row(record(memo_code="X"))[1], "memo_item")
    def test_notice_and_regular_duplicate(self):
        a=record(sub_id="11",transaction_id="NOTICE1",is_notice=True,filing_form="F24")
        b=record(sub_id="12",transaction_id="REGULAR2",is_notice=False,filing_form="F3X",
                 filing_date="2026-10-22")
        rows,counters=unique_rows([a,b])
        self.assertEqual(len(rows),1)
        self.assertFalse(rows[0]["notice"])
        self.assertEqual(counters["notice_regular_duplicates"],1)
    def test_amendment_with_changed_amount(self):
        a=record(sub_id="11",transaction_id="SAME",expenditure_amount=200)
        b=record(sub_id="12",transaction_id="SAME",expenditure_amount=350,
                 filing_date="2026-10-19")
        rows,ct=unique_rows([a,b])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["amount_cents"],35000)
        self.assertEqual(ct["repeated_transaction_or_amendment"],1)
    def test_two_legitimate_similar_notice_rows_preserved(self):
        a=record(sub_id="11",transaction_id="EXP1")
        b=record(sub_id="12",transaction_id="EXP2")
        rows,ct=unique_rows([a,b])
        self.assertEqual(len(rows),2)
    def test_fingerprint_does_not_merge_two_regular_rows(self):
        a=record(sub_id="11",transaction_id="EXP1",is_notice=False)
        b=record(sub_id="12",transaction_id="EXP2",is_notice=False)
        rows,ct=unique_rows([a,b])
        self.assertEqual(len(rows),2)
    def test_sums_reconcile(self):
        a=record(sub_id="11",transaction_id="A",expenditure_amount=2000)
        b=record(sub_id="12",transaction_id="B",candidate_id="H6NY17171",support_oppose_indicator="O")
        rows,exclusions=unique_rows([a,b])
        d=summarize(rows,exclusions,2,1)
        self.assertEqual(d["totals"]["benefit_lawler"],450000)
        self.assertEqual(d["totals"]["benefit_conley"],0)
        self.assertEqual(d["totals"]["all"],450000)
        self.assertEqual(sum(x["total"] for x in d["pivot"]),450000)

if __name__=="__main__":
    unittest.main()
