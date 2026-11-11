"""Bounded, standalone document-intelligence experiment (not production runtime)."""
import re
import hashlib
import json
from pathlib import Path


def verify_frozen(root):
    """Fail closed on any changed source, gold or protocol byte."""
    files = json.loads((root / "freeze.json").read_text())["files"]
    for name, expected in files.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"frozen input changed: {name}")
    return files


def extract_native(path):
    """Native PDF tables or static HTML diagnostic; no remote resources."""
    if path.suffix.lower() == ".pdf":
        import pymupdf
        cells, pages, regions, raw_tables = [], [], [], []
        with pymupdf.open(path) as pdf:
            for pi, page in enumerate(pdf):
                pages.append(page.get_text(sort=True))
                regions.append({"page": pi + 1, "coordinate_system": "PDF points, top-left", "dict": page.get_text("dict")})
                for table in page.find_tables().tables:
                    matrix = table.extract()
                    raw_tables.append({"page": pi + 1, "grid": matrix, "bbox": list(table.bbox), "header": table.header.names})
                    for ri, row in enumerate(matrix[1:], 1):
                        for ci, value in enumerate(row[1:], 1):
                            box = table.rows[ri].cells[ci]
                            cells.append({"text": value or "", "row_headers": [row[0] or ""],
                                          "column_headers": [table.header.names[ci] or ""],
                                          "anchor": {"page": pi + 1, "bbox": [box[0]/page.rect.width, box[1]/page.rect.height, box[2]/page.rect.width, box[3]/page.rect.height]} if box else None})
        return {"status": "ok" if any(pages) else "empty", "text": "\n".join(pages), "cells": cells,
                "native_regions": regions, "raw_tables": raw_tables, "policy": "find_tables native text; detected column names; first-column row label heuristic; no OCR"}
    if path.suffix.lower() not in {".html", ".htm"}:
        return {"status": "unsupported", "text": "", "cells": []}
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(path.read_bytes(), "html.parser")
    cells = []
    for ti, table in enumerate(soup.find_all("table")):
        rows = table.find_all("tr")
        headers = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"], recursive=False)] if rows else []
        for ri, row in enumerate(rows):
            values = row.find_all(["th", "td"], recursive=False)
            for ci, cell in enumerate(values):
                if ri == 0 or ci == 0:
                    continue
                cells.append({"text": cell.get_text(" ", strip=True),
                              "row_headers": [values[0].get_text(" ", strip=True)],
                              "column_headers": [headers[ci]] if ci < len(headers) else [],
                              "anchor": {"dom": f"table:{ti}/row:{ri}/cell:{ci}"}})
    return {"status": "ok", "text": soup.get_text(" ", strip=True), "cells": cells,
            "policy": "first row column headers; first column row label heuristic; simple grids only"}


def extract_candidate(candidate, path, model_dir):
    """Adapt outputs without gold; baseline remains an unchanged imported helper."""
    from pathlib import Path
    if candidate == "native":
        return extract_native(path)
    if candidate == "baseline":
        if path.suffix.lower() != ".pdf":
            return {"status": "unsupported", "text": "", "cells": []}
        import importlib.util
        spec = importlib.util.spec_from_file_location("existing_extract", Path(__file__).with_name("extract.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        raw = module.extract(path)
        return {"status": "ok" if raw["status"] == "indexed" else raw["status"],
                "text": "\n".join(p["text"] for p in raw["pages"]), "cells": [], "raw": raw,
                "anchor_limit": "existing helper exposes page text only, no table cells or region boxes"}
    if candidate != "docling":
        raise ValueError("unknown candidate")
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions, TableFormerMode
    from docling.datamodel.accelerator_options import AcceleratorOptions
    import rapidocr_onnxruntime
    ocr_dir = Path(rapidocr_onnxruntime.__file__).parent / "models"
    options = PdfPipelineOptions(artifacts_path=model_dir, do_ocr=True, do_table_structure=True,
                                 enable_remote_services=False, allow_external_plugins=False,
                                 document_timeout=120, accelerator_options=AcceleratorOptions(device="cpu", num_threads=2))
    options.table_structure_options.mode = TableFormerMode.FAST
    options.ocr_options = RapidOcrOptions(lang=["en"], scale=2,
        det_model_path=str(ocr_dir / "ch_PP-OCRv4_det_infer.onnx"),
        rec_model_path=str(ocr_dir / "ch_PP-OCRv4_rec_infer.onnx"),
        cls_model_path=str(ocr_dir / "ch_ppocr_mobile_v2.0_cls_infer.onnx"))
    converter = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.HTML],
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    converted = converter.convert(path, max_num_pages=1, max_file_size=3000000)
    doc = converted.document
    cells = []
    for table in doc.tables:
        items = table.data.table_cells
        for item in items:
            if item.column_header or item.start_col_offset_idx == 0:
                continue
            columns = [c.text for c in items if c.column_header and
                       c.start_col_offset_idx <= item.start_col_offset_idx < c.end_col_offset_idx]
            rows = [c.text for c in items if c.start_col_offset_idx == 0 and not c.column_header and
                    c.start_row_offset_idx <= item.start_row_offset_idx < c.end_row_offset_idx]
            anchor = {"docling_ref": table.self_ref}
            if table.prov and item.bbox:
                page_no = table.prov[0].page_no
                page_size = doc.pages[page_no].size
                box = item.bbox.to_top_left_origin(page_size.height)
                anchor.update(page=page_no, bbox=[box.l/page_size.width, box.t/page_size.height, box.r/page_size.width, box.b/page_size.height])
            cells.append({"text": item.text, "row_headers": list(dict.fromkeys(rows)),
                          "column_headers": list(dict.fromkeys(columns)), "anchor": anchor})
    return {"status": "ok" if str(converted.status.value) == "success" else str(converted.status.value),
            "text": doc.export_to_markdown(), "cells": cells, "raw": doc.export_to_dict(),
            "policy": "Fast TableFormer CPU; existing wheel OCR checkpoints, first-column row labels; HTML Docling refs are NOT source DOM anchors"}


def run_measured(command, prefix, timeout_seconds, rss_limit, env=None):
    """Fresh process, bounded wall/RSS, sampled process-tree memory; reap only owned PIDs."""
    import subprocess
    import time
    import psutil
    start = time.perf_counter()
    peak, reason, owned = 0, None, {}
    with prefix.with_suffix(".stdout.txt").open("x", encoding="utf-8") as stdout, prefix.with_suffix(".stderr.txt").open("x", encoding="utf-8") as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env)
        root_process = psutil.Process(process.pid)
        owned[process.pid] = root_process
        try:
            while process.poll() is None:
                try:
                    tree = [root_process] + root_process.children(recursive=True)
                    rss = 0
                    for item in tree:
                        owned[item.pid] = item
                        try:
                            rss += item.memory_info().rss
                        except psutil.NoSuchProcess:
                            pass
                    peak = max(peak, rss)
                except psutil.NoSuchProcess:
                    pass
                if time.perf_counter() - start > timeout_seconds:
                    reason = "timeout"
                    break
                if peak > rss_limit:
                    reason = "rss_limit"
                    break
                time.sleep(0.02)
        finally:
            # Reap sampled descendants even when the parent has already exited.
            # psutil.Process retains creation identity, avoiding PID-reuse kills.
            for item in reversed(list(owned.values())):
                try:
                    if item.is_running():
                        item.kill()
                except psutil.NoSuchProcess:
                    pass
            process.wait(timeout=10)
            for item in owned.values():
                if item.pid != process.pid:
                    try:
                        item.wait(timeout=5)
                    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                        pass
    survivors = [item.pid for item in owned.values() if item.is_running()]
    return {"command": command, "pid": process.pid, "elapsed_seconds": time.perf_counter()-start,
            "peak_tree_rss_bytes": peak, "returncode": process.returncode, "error": reason,
            "surviving_owned_pids": survivors, "rss_sampling_seconds": 0.02}


def score_document(document, gold):
    """Score exact number presence and value-with-unit presence, never retrieval."""
    numbers = set(re.findall(r"(?<![\w.])-?\d+(?:[.,]\d+)?(?![\w.])", document.get("text", "")))
    text = " ".join(document.get("text", "").split())
    facts = gold["facts"]
    units = [f for f in facts if f.get("unit")]
    def anchor_matches(cell, fact):
        anchor = cell.get("anchor") or {}
        if "dom" in fact:
            return anchor.get("dom") == fact["dom"]
        if anchor.get("page") != fact.get("page") or not anchor.get("bbox"):
            return False
        a, b = anchor["bbox"], fact["bbox"]
        intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
        union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - intersection
        return union > 0 and intersection / union >= 0.5

    matches = [[c for c in document.get("cells", []) if f["raw"] in " ".join(c["text"].split())] for f in facts]
    return {
        "content_presence": {"correct": sum(f["raw"] in text for f in facts), "total": len(facts)},
        "header_associations": {"correct": sum(any(c.get("row_headers") == f["row_headers"] and c.get("column_headers") == f["column_headers"] for c in cells) for f, cells in zip(facts, matches)), "total": len(facts)},
        "region_anchors": {"correct": sum(any(anchor_matches(c, f) for c in cells) for f, cells in zip(facts, matches)), "total": len(facts)},
        "numbers": {"correct": sum(f["number"] in numbers for f in facts if f.get("number")),
                    "total": sum(bool(f.get("number")) for f in facts)},
        "units": {"correct": sum(f["raw"] in text for f in units), "total": len(units)},
    }


def run_benchmark(root, output, candidates=("baseline", "docling", "native")):
    """Execute the fixed three-variant pilot, never discover or ingest other files."""
    import datetime
    import importlib.metadata
    import os
    import platform
    import sys
    import psutil
    root = root.resolve()
    frozen = verify_frozen(root)
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads((root / "protocol.json").read_text())
    gold = json.loads((root / "gold.json").read_text())
    env = os.environ.copy()
    env.update(HF_HOME=str(root / "hf-cache"), HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               HF_HUB_DISABLE_XET="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", DOCLING_NUM_THREADS="2",
               TORCH_HOME=str(root / "torch-cache"), XDG_CACHE_HOME=str(root / "cache"),
               PYTHONIOENCODING="utf-8")
    report = {"started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
              "frozen_inputs": frozen, "freeze_sha256": hashlib.sha256((root / "freeze.json").read_bytes()).hexdigest(),
              "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "baseline_sha256": hashlib.sha256(Path(__file__).with_name("extract.py").read_bytes()).hexdigest(),
              "environment": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                              "logical_cpus": psutil.cpu_count(), "physical_cpus": psutil.cpu_count(logical=False),
                              "physical_memory_bytes": psutil.virtual_memory().total,
                              "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
                              "inference": "CPU, 2 requested threads; baseline OCR helper fixes its ONNX threads to 1"},
              "results": []}
    cases = [("native-pdf", "sources/table.pdf", "pdf"), ("scan-pdf", "sources/table-scan.pdf", "pdf"),
             ("html", "sources/one-header.html", "html")]
    for case, source, gold_key in cases:
        for candidate in candidates:
            name = f"{case}-{candidate}"
            result_path = output / f"{name}.json"
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", candidate,
                       "--source", str(root / source), "--models", str(root / "models"), "--result", str(result_path)]
            measurement = run_measured(command, output / name,
                protocol["budgets"]["worker_timeout_seconds"], protocol["budgets"]["worker_rss_limit_bytes"], env)
            if result_path.exists():
                document = json.loads(result_path.read_text(encoding="utf-8"))
            else:
                document = {"status": "failed", "error": measurement["error"] or f"worker exit {measurement['returncode']}", "text": "", "cells": []}
                result_path.write_text(json.dumps(document, indent=2), encoding="utf-8")
            report["results"].append({"case": case, "source": source, "candidate": candidate,
                "status": document["status"], "error": document.get("error"), "measurements": measurement,
                "metrics": score_document(document, gold[gold_key]), "cells_emitted": len(document.get("cells", [])),
                "output_file": result_path.name, "output_bytes": result_path.stat().st_size,
                "output_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest()})
    verify_frozen(root)
    report["integrity_verified_after"] = True
    report["finished_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    (output / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=True), encoding="utf-8")
    return report


def main():
    import argparse
    import datetime
    import traceback
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, help="Frozen pilot directory; writes a unique executions subdirectory")
    parser.add_argument("--worker", choices=["baseline", "docling", "native"])
    parser.add_argument("--source", type=Path)
    parser.add_argument("--models", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    if args.worker:
        try:
            document = extract_candidate(args.worker, args.source, args.models)
        except Exception as exc:
            traceback.print_exc()
            document = {"status": "failed", "error": f"{type(exc).__name__}: {exc}", "text": "", "cells": []}
        with args.result.open("x", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2, ensure_ascii=True, default=str)
        return
    if not args.run:
        parser.error("--run or --worker is required")
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.run / "executions" / stamp
    report = run_benchmark(args.run, output)
    print(json.dumps({"report": str(output / "report.json"), "pairs": len(report["results"]),
                      "statuses": [r["status"] for r in report["results"]]}))


if __name__ == "__main__":
    main()
