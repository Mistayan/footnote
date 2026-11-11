"""Standalone pilot tests; controlled fixtures are NOT public-source gold."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pilot", ROOT / "tools/document_intelligence_benchmark.py")
pilot = importlib.util.module_from_spec(spec)
if spec.loader and (ROOT / "tools/document_intelligence_benchmark.py").exists():
    spec.loader.exec_module(pilot)


class ScoringTests(unittest.TestCase):
    def test_number_matching_never_counts_substrings_or_missing_units(self):
        gold = {"facts": [{"number": "5", "raw": "5%", "unit": "%",
                           "row_headers": ["A"], "column_headers": ["Rate"],
                           "page": 1, "bbox": [0, 0, 1, 1]}]}
        score = pilot.score_document({"text": "15 and 5", "cells": []}, gold)
        self.assertEqual(score["numbers"], {"correct": 1, "total": 1})
        self.assertEqual(score["units"], {"correct": 0, "total": 1})
        self.assertEqual(pilot.score_document({"text": "15", "cells": []}, gold)["numbers"]["correct"], 0)

    def test_associations_and_region_anchors_are_separate_from_text_presence(self):
        fact = {"raw": "5%", "number": "5", "unit": "%", "row_headers": ["A"],
                "column_headers": ["Results", "Rate"], "page": 1, "bbox": [0.1, 0.1, 0.2, 0.2]}
        cell = {"text": "5%", "row_headers": ["B"], "column_headers": ["Results", "Rate"],
                "anchor": {"page": 1, "bbox": [0.1, 0.1, 0.2, 0.2]}}
        score = pilot.score_document({"text": "5%", "cells": [cell]}, {"facts": [fact]})
        self.assertEqual(score["header_associations"]["correct"], 0)
        self.assertEqual(score["region_anchors"]["correct"], 1)
        cell["row_headers"] = ["A"]
        cell["anchor"]["page"] = 2
        score = pilot.score_document({"text": "5%", "cells": [cell]}, {"facts": [fact]})
        self.assertEqual(score["header_associations"]["correct"], 1)
        self.assertEqual(score["region_anchors"]["correct"], 0)
        cell["anchor"] = {"dom": "table:0/row:1/cell:1"}
        fact.pop("page"); fact.pop("bbox"); fact["dom"] = "table:0/row:1/cell:1"
        self.assertEqual(pilot.score_document({"text": "5%", "cells": [cell]}, {"facts": [fact]})["region_anchors"]["correct"], 1)


class NativeAdapterTests(unittest.TestCase):
    def test_pdf_native_table_retains_regions_but_scan_stays_empty(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "fixture.pdf"
            doc = pymupdf.open(); page = doc.new_page(width=300, height=200)
            for x in [20, 120, 250]:
                page.draw_line((x, 20), (x, 120))
            for y in [20, 50, 85, 120]:
                page.draw_line((20, y), (250, y))
            for x, y, text in [(25, 40, "Group"), (125, 40, "Rate"), (25, 75, "A"), (125, 75, "5%"), (25, 110, "B"), (125, 110, "6%")]:
                page.insert_text((x, y), text)
            doc.save(source)
            result = pilot.extract_native(source)
            cell = next(c for c in result["cells"] if c["text"] == "5%")
            self.assertEqual(cell["row_headers"], ["A"])
            self.assertEqual(cell["column_headers"], ["Rate"])
            self.assertEqual(cell["anchor"]["page"], 1)
            self.assertTrue(result["native_regions"])
            scan = pymupdf.open(); out = scan.new_page(width=300, height=200)
            out.insert_image(out.rect, stream=page.get_pixmap().tobytes("png"))
            scan.save(Path(temp) / "scan.pdf")
            scanned = pilot.extract_native(Path(temp) / "scan.pdf")
            self.assertEqual(scanned["text"], "")
            self.assertEqual(scanned["cells"], [])

    def test_static_html_cells_have_header_paths_and_snapshot_anchors(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "fixture.html"
            source.write_text('<table><tr><th>Group</th><th>Rate</th></tr><tr><td>A</td><td>5%</td></tr></table>')
            result = pilot.extract_native(source)
            cell = next(c for c in result["cells"] if c["text"] == "5%")
            self.assertEqual(cell["row_headers"], ["A"])
            self.assertEqual(cell["column_headers"], ["Rate"])
            self.assertEqual(cell["anchor"], {"dom": "table:0/row:1/cell:1"})
            self.assertIn("5%", result["text"])
            self.assertEqual(pilot.extract_native(source.with_suffix(".xlsx"))["status"], "unsupported")


class CandidateAdapterTests(unittest.TestCase):
    def test_docling_html_keeps_raw_structure_without_fabricating_dom(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "fixture.html"
            source.write_text('<html><body><table><tr><th>Group</th><th>Rate</th></tr><tr><td>A</td><td>5%</td></tr></table></body></html>')
            result = pilot.extract_candidate("docling", source, ROOT / "tools/artifacts/docintel-pilot-20261017/models")
            self.assertEqual(result["status"], "ok")
            self.assertIn("5%", result["text"])
            self.assertTrue(result["raw"]["tables"])
            cell = next(c for c in result["cells"] if c["text"] == "5%")
            self.assertEqual(cell["row_headers"], ["A"])
            self.assertEqual(cell["column_headers"], ["Rate"])
            self.assertNotIn("dom", cell.get("anchor") or {})
            self.assertEqual(pilot.extract_candidate("baseline", source, Path(temp))["status"], "unsupported")


class RunnerTests(unittest.TestCase):
    def test_pipeline_executes_three_frozen_fixture_variants_and_writes_receipts(self):
        import hashlib
        import json
        import pymupdf
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); (root / "sources").mkdir()
            doc = pymupdf.open(); page = doc.new_page(); page.insert_text((30, 30), "5%")
            doc.save(root / "sources/table.pdf"); doc.save(root / "sources/table-scan.pdf")
            (root / "sources/one-header.html").write_text('<table><tr><th>A</th></tr><tr><td>5%</td></tr></table>')
            (root / "gold.json").write_text(json.dumps({"pdf": {"facts": []}, "html": {"facts": []}}))
            (root / "protocol.json").write_text(json.dumps({"budgets": {"worker_timeout_seconds": 10, "worker_rss_limit_bytes": 3000000000}}))
            files = ["sources/table.pdf", "sources/table-scan.pdf", "sources/one-header.html", "gold.json", "protocol.json"]
            (root / "freeze.json").write_text(json.dumps({"files": {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in files}}))
            report = pilot.run_benchmark(root, root / "execution", candidates=["native"])
            self.assertEqual(len(report["results"]), 3)
            self.assertTrue(report["integrity_verified_after"])
            self.assertTrue(all(r["status"] == "ok" for r in report["results"]))
            self.assertTrue(all(r["measurements"]["peak_tree_rss_bytes"] > 0 for r in report["results"]))
            self.assertTrue((root / "execution/report.json").exists())
            for result in report["results"]:
                self.assertEqual(hashlib.sha256((root / "execution" / result["output_file"]).read_bytes()).hexdigest(), result["output_sha256"])
            with self.assertRaises(FileExistsError):
                pilot.run_benchmark(root, root / "execution", candidates=["native"])

    def test_descendant_is_reaped_even_after_its_parent_exits_normally(self):
        import sys
        import psutil
        with tempfile.TemporaryDirectory() as temp:
            script = "import subprocess,sys,time; subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); time.sleep(0.3)"
            result = pilot.run_measured([sys.executable, "-c", script], Path(temp) / "child", 2, 3000000000)
            try:
                self.assertEqual(result["surviving_owned_pids"], [])
                self.assertEqual(result["returncode"], 0)
            finally:
                for pid in result["surviving_owned_pids"]:
                    try:
                        proc = psutil.Process(pid); proc.kill(); proc.wait(timeout=5)
                    except psutil.NoSuchProcess:
                        pass

    def test_measured_subprocess_times_out_and_is_reaped(self):
        import sys
        import psutil
        with tempfile.TemporaryDirectory() as temp:
            result = pilot.run_measured([sys.executable, "-c", "import time; time.sleep(10)"], Path(temp) / "timeout", 0.2, 3000000000)
            self.assertEqual(result["error"], "timeout")
            self.assertGreater(result["elapsed_seconds"], 0)
            self.assertGreater(result["peak_tree_rss_bytes"], 0)
            self.assertFalse(psutil.pid_exists(result["pid"]))
            self.assertEqual(result["surviving_owned_pids"], [])

    def test_frozen_inputs_refuse_tampering(self):
        import hashlib
        import json
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "gold.json").write_text('{"facts": []}')
            digest = hashlib.sha256((root / "gold.json").read_bytes()).hexdigest()
            (root / "freeze.json").write_text(json.dumps({"files": {"gold.json": digest}}))
            self.assertEqual(pilot.verify_frozen(root)["gold.json"], digest)
            (root / "gold.json").write_text('{"facts": [1]}')
            with self.assertRaisesRegex(ValueError, "frozen input changed"):
                pilot.verify_frozen(root)


if __name__ == "__main__":
    unittest.main()
