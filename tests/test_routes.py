"""Frontend regression tests across all nine independently published pages."""
import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from races import RACES
from refresh_all import DATA_PATHS
class TestRaceRoutes(unittest.TestCase):
    def test_root_redirects_instead_of_showing_race_selector(self):
        text=(ROOT/"index.html").read_text()
        self.assertIn('url=./NY-17/',text)
        self.assertIn('window.location.replace("./NY-17/")',text)
        self.assertNotIn("directory-card",text)
    def test_all_nine_pages_share_finished_ny17_layout(self):
        for district,cfg in RACES.items():
            h=(ROOT/district/"index.html").read_text()
            self.assertIn(f"<title>{district} • 2026 Independent Expenditure Reporting</title>",h)
            self.assertIn(cfg["republican"]["short"],h)
            self.assertIn(cfg["democratic"]["short"],h)
            self.assertIn('src="../assets/app.js',h)
            self.assertIn('href="../assets/styles.css',h)
            self.assertLess(h.index('class="panel pivot-section"'),h.index('class="panel group-section"'))
            for unwanted in ("WHO IS SPENDING","WHAT THE MONEY FUNDED","About these figures",
                  "Four dispositions shown separately",
                  "Numbers are independent expenditure amounts, not contributions to campaigns"):
                self.assertNotIn(unwanted,h)
            self.assertEqual(DATA_PATHS[district],ROOT/district/"data"/"data.json")
            obj=json.loads(DATA_PATHS[district].read_text())
            self.assertEqual(obj["district"],district)
            self.assertIn(obj["status"],("ok","not_initialized"))
    def test_all_nine_pages_use_original_spiros_logo(self):
        logo=ROOT/"assets"/"spiros-consulting-logo.png"
        self.assertTrue(logo.exists())
        self.assertGreater(logo.stat().st_size,1000)
        self.assertTrue(logo.read_bytes().startswith(bytes.fromhex("89504e470d0a1a0a")))
        css=(ROOT/"assets"/"styles.css").read_text(encoding="utf-8")
        self.assertIn(".spiros-ie-header",css)
        self.assertIn(".spiros-ie-logo",css)
        self.assertIn("@media(max-width:670px)",css)
        self.assertIn("@media(max-width:400px)",css)
        for district in RACES:
            with self.subTest(district=district):
                html=(ROOT/district/"index.html").read_text(encoding="utf-8")
                self.assertEqual(html.count('class="spiros-ie-logo"'),1)
                self.assertIn('class="topbar spiros-ie-header"',html)
                self.assertIn('src="../assets/spiros-consulting-logo.png"',html)
                self.assertIn('alt="Spiros Consulting"',html)
                self.assertIn('styles.css?v=20261023-spiros-all-races-v1',html)
                self.assertLess(html.index('class="spiros-ie-logo"'),html.index("<main>"))

    def test_workflow_refreshes_and_archives_each_race(self):
        s=(ROOT/".github/workflows/refresh-and-publish.yml").read_text()
        self.assertIn("python scripts/refresh_all.py",s)
        self.assertIn("for race in NY-17 CO-4 CO-5 IA-1 MN-1 NE-2 WI-1 NY-19 CA-13",s)
        self.assertIn("git add -A NY-17/data",s)
        self.assertIn("cp assets/* _site/assets/",s)
if __name__=="__main__":unittest.main()
