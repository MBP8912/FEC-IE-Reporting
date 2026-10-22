import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from refresh import (
    as_cents, classify, classify_ny17_override, normalize_row,
    unique_rows, summarize, is_2026_general,
)

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
    def test_ny17_lcv_ad_buy_digital_only_on_september_11(self):
        base = record(
            committee_id="C00486845", committee_name="LCV VICTORY FUND",
            expenditure_date="2026-09-11", expenditure_description="AD BUY",
            candidate_id="H2NY17162", support_oppose_indicator="O",
            expenditure_amount=457000,
        )
        normalized, error = normalize_row(base)
        self.assertIsNone(error)
        self.assertEqual(normalized["type"], "Digital")
        self.assertEqual(normalized["amount_cents"], 45700000)
        self.assertEqual(normalized["description"], "AD BUY")

        other_date, _ = normalize_row(dict(base, expenditure_date="2026-09-12"))
        self.assertEqual(other_date["type"], "Media (unspecified)")
        other_filer, _ = normalize_row(dict(base, committee_id="C99999999"))
        self.assertEqual(other_filer["type"], "Media (unspecified)")
        other_description, _ = normalize_row(dict(base, expenditure_description="MEDIA PRODUCTION"))
        self.assertEqual(other_description["type"], "Production")

    def test_ny17_clf_media_placement_tv_but_no_general_relabeling(self):
        base = record(
            committee_id="C00504530", committee_name="CLF",
            candidate_id="H6NY17171", support_oppose_indicator="O",
            expenditure_date="2026-09-21", expenditure_description="MEDIA PLACEMENT",
            expenditure_amount=928807.13,
        )
        normalized, error = normalize_row(base)
        self.assertIsNone(error)
        self.assertEqual(normalized["type"], "TV")
        self.assertEqual(normalized["amount_cents"], 92880713)
        self.assertEqual(normalized["description"], "MEDIA PLACEMENT")

        clf_digital, _ = normalize_row(dict(base, expenditure_description="DIGITAL PLACEMENT"))
        self.assertEqual(clf_digital["type"], "Digital")
        clf_production, _ = normalize_row(dict(base, expenditure_description="MEDIA PRODUCTION"))
        self.assertEqual(clf_production["type"], "Production")
        another_filer, _ = normalize_row(dict(base, committee_id="C99999999"))
        self.assertEqual(another_filer["type"], "Media (unspecified)")
        self.assertEqual(classify("MEDIA PLACEMENT"), "Media (unspecified)")
        self.assertEqual(classify("AD BUY"), "Media (unspecified)")

        import refresh
        from unittest.mock import patch
        with patch.object(refresh, "COMMITTEE_KEY", "CO-5"):
            self.assertEqual(
                classify_ny17_override(
                    "C00504530", "H6NY17171", "2026-09-21", "MEDIA PLACEMENT"),
                "Media (unspecified)",
            )

    def test_ny17_overrides_reconcile_category_pivot_without_changing_amounts(self):
        rows = [
            record(sub_id="lc", transaction_id="lc", committee_id="C00486845",
                   committee_name="LCV VICTORY FUND", candidate_id="H2NY17162",
                   support_oppose_indicator="O", expenditure_date="2026-09-11",
                   expenditure_description="AD BUY", expenditure_amount=457000),
        ]
        clf_amounts = [928807.13, 1001426.33, 1469743.44, 1430008.55]
        clf_dates = ["2026-09-21", "2026-09-28", "2026-10-05", "2026-10-09"]
        for i, (amount, date_str) in enumerate(zip(clf_amounts, clf_dates)):
            rows.append(record(
                sub_id="clf" + str(i), transaction_id="clf" + str(i),
                committee_id="C00504530", committee_name="CLF",
                candidate_id="H6NY17171", support_oppose_indicator="O",
                expenditure_date=date_str, expenditure_description="MEDIA PLACEMENT",
                expenditure_amount=amount,
            ))
        unique, excluded = unique_rows(rows)
        result = summarize(unique, excluded, len(rows), 1)
        self.assertEqual(len(unique), 5)
        self.assertEqual(result["totals"]["oppose_lawler"], 45700000)
        self.assertEqual(result["totals"]["oppose_conley"], 482998545)
        self.assertEqual(result["totals"]["all"], 528698545)
        for key, category, value in [
            ("oppose_lawler", "Digital", 45700000),
            ("oppose_conley", "TV", 482998545),
        ]:
            pivot = next(p for p in result["pivot"] if p["key"] == key)
            category_row = next(p for p in pivot["categories"] if p["name"] == category)
            self.assertEqual(category_row["total"], value)
        self.assertTrue(all(x["description"] in ("AD BUY", "MEDIA PLACEMENT") for x in unique))

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
    def test_daily_drilldown_matches_stacked_bar_and_category_totals(self):
        sample = [
            record(sub_id="11", transaction_id="ONE", expenditure_amount=100, expenditure_description="DIRECT MAIL", committee_name="Spender A"),
            record(sub_id="12", transaction_id="TWO", expenditure_amount=250, expenditure_description="DIRECT MAIL", committee_name="Spender A"),
            record(sub_id="13", transaction_id="THREE", expenditure_amount=30, expenditure_description="DIGITAL ADS", committee_name="Spender B"),
            record(sub_id="14", transaction_id="FOUR", candidate_id="H6NY17171", support_oppose_indicator="O", expenditure_amount=70),
            record(sub_id="15", transaction_id="FIVE", expenditure_date="2026-10-18", expenditure_amount=120),
        ]
        rows, excluded = unique_rows(sample)
        result = summarize(rows, excluded, len(sample), 1)
        day = next(row for row in result["daily"] if row["date"] == "2026-10-17")
        segment = [row for row in result["transactions"]
                   if row["date"] == "2026-10-17" and row["disposition"] == "support_lawler"]
        self.assertEqual(day["support_lawler"], sum(row["amount_cents"] for row in segment))
        totals_by_spender_category = {}
        for item in segment:
            key = (item["group"], item["type"])
            totals_by_spender_category[key] = totals_by_spender_category.get(key, 0) + item["amount_cents"]
        self.assertEqual(totals_by_spender_category[("Spender A", "Mail")], 35000)
        self.assertEqual(totals_by_spender_category[("Spender B", "Digital")], 3000)
        self.assertEqual(sum(totals_by_spender_category.values()), day["support_lawler"])
        self.assertEqual(len([row for row in result["transactions"] if row["date"] == "2026-10-17" and row["disposition"] == "oppose_conley"]), 1)

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
