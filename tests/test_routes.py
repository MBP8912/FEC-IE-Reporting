"""Regression tests: NY-17 lives under its own race URL and is listed at the root."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from refresh import DATAFILE

class TestRaceRoutes(unittest.TestCase):
    def test_index_is_race_directory(self):
        root = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("Independent Expenditure Dashboards", root)
        self.assertIn('href="./NY-17/"', root)
        self.assertNotIn('id="groups-table"', root)

    def test_ny17_location_and_shared_assets(self):
        html = (ROOT / "NY-17" / "index.html").read_text(encoding="utf-8")
        self.assertIn('href="../assets/styles.css', html)
        self.assertIn('src="../assets/app.js', html)
        self.assertTrue((ROOT / "NY-17" / "data" / "data.json").is_file())
        self.assertEqual(DATAFILE, ROOT / "NY-17" / "data" / "data.json")

    def test_section_order_and_removed_labels(self):
        page = (ROOT / "NY-17" / "index.html").read_text(encoding="utf-8")
        self.assertLess(page.index('class="panel pivot-section"'),
                        page.index('class="panel group-section"'))
        self.assertIn("Spending by type and disposition", page)
        self.assertIn("Independent expenditures by group", page)
        self.assertNotIn("WHO IS SPENDING", page)
        self.assertNotIn("WHAT THE MONEY FUNDED", page)

    def test_workflow_places_data_in_new_path(self):
        workflow = (ROOT / ".github" / "workflows" / "refresh-and-publish.yml").read_text(encoding="utf-8")
        self.assertIn("cp NY-17/index.html _site/NY-17/", workflow)
        self.assertIn("cp NY-17/data/data.json _site/NY-17/data/data.json", workflow)
        self.assertIn("git add NY-17/data/data.json", workflow)

if __name__ == "__main__":
    unittest.main()
