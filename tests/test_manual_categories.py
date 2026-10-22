"""User-requested per-race Schedule E categories must never leak across races."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import refresh as core
import refresh_all as multi
from races import RACES


EXPECTED = [
    ("CO-5", "C00960435", "PLACED MEDIA: TV AND CONNECTED TV", "TV"),
    ("CO-5", "C00473918", "MAILHOUSE", "Mail"),
    ("IA-1", "C00504530", "MEDIA PLACEMENT", "TV"),
    ("IA-1", "C00486845", "AD BUY", "TV"),
    ("MN-1", "C00486845", "AD BUY", "TV"),
    ("NE-2", "C00504530", "MEDIA PLACEMENT", "TV"),
    ("WI-1", "C00835959", "IE-STEIL-MEDIA BUY", "TV"),
    ("WI-1", "C00504530", "MEDIA PLACEMENT", "TV"),
    ("WI-1", "C00573261", "MEDIA BUY", "Digital"),
    ("WI-1", "C00492140", "BILLBOARD ADVERTISING- ESTIMATED COST", "Billboard"),
    ("CA-13", "C00504530", "MEDIA PLACEMENT", "TV"),
    ("CA-13", "C00492140", "BILLBOARD ADVERTISING- ESTIMATED COST", "Billboard"),
]


class TestManualClassifications(unittest.TestCase):
    def test_all_requested_classifications(self):
        with patch.object(core, "COMMITTEE_KEY", core.COMMITTEE_KEY), \
             patch.object(core, "CANDIDATES", core.CANDIDATES), \
             patch.object(core, "DISPOSITIONS", core.DISPOSITIONS):
            for district, committee, original, expected in EXPECTED:
                with self.subTest(race=district, committee=committee, description=original):
                    multi.set_race(district)
                    candidate = RACES[district]["republican"]["id"]
                    result = core.classify_for_race(
                        committee, candidate, "2026-10-05", original)
                    self.assertEqual(result, expected)
                    self.assertEqual(core.manual_spend_category(
                        committee, candidate, "2026-10-05", original), expected)

    def test_generic_classifier_and_other_races_are_unchanged(self):
        self.assertIn("Billboard", core.CATEGORIES)
        self.assertEqual(core.classify("MEDIA PLACEMENT"), "Media (unspecified)")
        self.assertEqual(core.classify("AD BUY"), "Media (unspecified)")
        self.assertEqual(core.classify("PLACED MEDIA: TV AND CONNECTED TV"), "Digital")
        self.assertEqual(core.classify("BILLBOARD ADVERTISING- ESTIMATED COST"), "Print")
        with patch.object(core, "COMMITTEE_KEY", core.COMMITTEE_KEY):
            for district, committee, original, expected in EXPECTED:
                others = next(name for name in RACES if name != district and
                              (name != "NY-17" or original != "MEDIA PLACEMENT"))
                with self.subTest(original_race=district, other_race=others, description=original):
                    core.COMMITTEE_KEY = others
                    if others == "NY-17":
                        candidate = "H2NY17162"
                    else:
                        candidate = RACES[others]["republican"]["id"]
                    self.assertIsNone(core.manual_spend_category(
                        committee, candidate, "2026-10-05", original))

    def test_neighboring_spend_descriptions_remain_their_original_types(self):
        examples = [
            ("CO-5","C00960435","DIRECT MAIL: PRINTING AND POSTAGE","Mail"),
            ("CO-5","C00473918","PRODUCTION AND DIGITAL MEDIA BUY","Digital"),
            ("IA-1","C00504530","DIGITAL PLACEMENT","Digital"),
            ("IA-1","C00504530","MEDIA PRODUCTION","Production"),
            ("MN-1","C00486845","IN-KIND: MEDIA PRODUCTION","Production"),
            ("WI-1","C00835959","IE-STEIL-MEDIA PRODUCTION","Production"),
            ("WI-1","C00573261","MEDIA PRODUCTION","Production"),
            ("CA-13","C00492140","PRODUCTION- ESTIMATED COST","Production"),
            ("CO-5","C00492140","BILLBOARD ADVERTISING- ESTIMATED COST","Print"),
            ("IA-1","C00492140","BILLBOARD ADVERTISING- ESTIMATED COST","Print"),
        ]
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY), \
             patch.object(core,"CANDIDATES",core.CANDIDATES), \
             patch.object(core,"DISPOSITIONS",core.DISPOSITIONS):
            for district,committee,desc,expected in examples:
                multi.set_race(district)
                with self.subTest(race=district,description=desc):
                    self.assertEqual(core.classify_for_race(
                        committee,RACES[district]["republican"]["id"],"2026-10-05",desc),expected)

    def test_existing_ny17_exceptions_are_preserved(self):
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY):
            core.COMMITTEE_KEY = "NY-17"
            self.assertEqual(core.classify_for_race(
                "C00486845","H2NY17162","2026-09-11","AD BUY"),"Digital")
            self.assertEqual(core.classify_for_race(
                "C00504530","H6NY17171","2026-10-05","MEDIA PLACEMENT"),"TV")
            self.assertEqual(core.classify_for_race(
                "C00486845","H2NY17162","2026-09-12","AD BUY"),"Media (unspecified)")

    def test_source_description_and_amount_unchanged_in_normalization(self):
        with patch.object(core,"COMMITTEE_KEY",core.COMMITTEE_KEY), \
             patch.object(core,"CANDIDATES",core.CANDIDATES), \
             patch.object(core,"DISPOSITIONS",core.DISPOSITIONS):
            for district,committee,description,expected in EXPECTED:
                multi.set_race(district)
                candidate=RACES[district]["republican"]["id"]
                raw={
                    "candidate_id":candidate,"committee_id":committee,
                    "committee_name":"Test spender","expenditure_date":"2026-10-05",
                    "expenditure_amount":1234.56,"expenditure_description":description,
                    "support_oppose_indicator":"S","election_type":"G2026",
                    "transaction_id":"TEST",
                }
                with self.subTest(district=district,description=description):
                    result,reason=core.normalize_row(raw)
                    self.assertIsNone(reason)
                    self.assertEqual(result["type"],expected)
                    self.assertEqual(result["description"],description)
                    self.assertEqual(result["amount_cents"],123456)


if __name__ == "__main__":
    unittest.main()
