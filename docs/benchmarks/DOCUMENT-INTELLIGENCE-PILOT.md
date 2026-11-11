# Document intelligence: executed public-document pilot

**17 October 2026 · experimental, local CPU only · not a banking/GED acceptance.**

The standalone pipeline now runs the unchanged extraction helper, Docling and a native structured diagnostic on a public PDF, an image-only derivative of that same page and a static HTML snapshot. **Docling executed successfully on all three final variants. Preserving the selected numbers did not preserve the PDF header hierarchy.** No retrieval, answer precision, production integration or 90% evidence-quality claim follows from this pilot.

This implements a finite first slice of E1–E3 in [the academic review](../research/ACADEMIC-DOCUMENT-INTELLIGENCE-BY-THEME.md) and the source-preservation contract in [the LAD/RAD study](../research/DOCUMENT-INTELLIGENCE-RESEARCH.md). It is not a reproduction of TableFormer, OmniDocBench, GriTS or TEDS.

## 1. Scope and evidence locations

Repository-relative evidence root, abbreviated **P** below:

`tools/artifacts/docintel-pilot-20261017/`

- Original protocol, gold and source freeze: `P/protocol.json`, `P/gold.json`, `P/freeze.json`.
- Final corpus/container amendment: `P/corpus-v2-lossless-scan/{protocol,gold,freeze}.json`.
- **Final machine-readable results:** `P/corpus-v2-lossless-scan/executions/20261017T163430107912Z/report.json`.
- Initial run retained, including the scan-size failure: `P/executions/20261017T162605027209Z/report.json`.
- Source HTTP receipts: `P/sources/receipts.json`; originals: `P/sources/{table.pdf,one-header.html}`.
- Exact dependency versions: `P/requirements-pilot.lock`; installation transcript: `P/provision.txt`.
- Model revisions, selected sizes and SHA-256: `P/model-{preflight,receipts}.json`; OCR weight hashes: `P/ocr-model-receipts.json`.
- Package license metadata and license-file hashes: `P/package-license-receipts.json`.
- Aggregate counts/directory sizes: `P/aggregate.json`; final generated result table: `P/results-table-final.md`.

Only the two standalone Python files, this document and unique experiment/test artifacts were authored. The existing helper and application source were not edited; no shared `.venv` installation, staging, commit, push, global configuration or production datastore changes were performed. Project instructions and Beads were inspected, without global initialization or changes to unrelated tasks. The finite acceptance ledger lives in the frozen protocol.

## 2. Corpus, rights and gold

**Two actual public source documents, three variants; not three independent documents.** Both sources are W3C educational examples, not operational financial or banking reports.

| Source | Bound and annotation |
|---|---|
| W3C “Example table” PDF | One original page, 66,887 bytes. Disability-category table with merged Results header, percentage accuracy, seconds and parenthesized secondary observations.[1] |
| Same PDF, image-only derivative | Original render at 144 dpi, 1224 × 1584 pixels. No native text layer. This is a clean derived scan, **not a physical scan or photograph**. |
| W3C one-header tutorial HTML | Static snapshot, 48,599 bytes, three source tables; six manually selected value/header/DOM facts across tables 0 and 2.[2] |

Original URL, final URL, HTTP status, MIME, capture UTC, byte length and SHA-256 are retained. Original bytes are never replaced. The W3C public-document license was retrieved and inspected; attribution, source URLs, status and license notice accompany the corpus.[3] Its derivative permission is limited to the stated implementation/supporting-material use; this pilot is supporting software evaluation, not a republished technical specification. No blanket commercial clearance is asserted. PDF metadata names author “Mary” and records creation in 2011; those metadata remain in the immutable PDF. Independent chain-of-title review was not performed.

Gold was manually authored **from the original rendered PDF and source HTML before any candidate output was inspected**. The freeze timestamp is `2026-10-17T16:21:26.353535+00:00`; the first candidate run began at `16:26:05 UTC`. Gold contains 12 PDF facts (four completed-ballot counts, four percentages, four times), eight with explicit units, and six HTML facts. Native and scan use the same gold. PDF cell rectangles were manually approximated on the original render; HTML anchors are source snapshot table/row/cell indices.

This is partial, single-annotator gold: not exhaustive transcription, independently adjudicated annotations or a holdout. It excludes secondary parenthesized observations and most of the tutorial. Unit tests create controlled fixtures in temporary directories; **none of those fixtures or their generated labels contributes to these public-source results**.

### Container correction, not a relabeling

The initial image-only PDF used an uncompressed raster and occupied **5,820,016 bytes**, exceeding Docling's frozen 3,000,000-byte input bound. That real error remains in the initial run. A separately frozen v1.1 corpus uses lossless PDF deflate, **65,640 bytes**; decoded 144-dpi pixel bytes were asserted equal. Original public sources and gold bytes are identical across freezes. The second freeze preceded the second run. No engine settings, labels or header paths were tuned to outputs. This transparent setup correction does not turn the pilot into a prospective independent evaluation.

## 3. Adapters and fidelity measures

- **baseline:** imports unchanged `tools/extract.py`: PyMuPDF native text plus RapidOCR for image-bearing/empty PDF pages. It exposes page text, not cell topology or region boxes. HTML is explicitly `unsupported`, rather than passed to the helper's image branch.
- **docling:** Docling **2.140.0**, CPU, two requested threads, local Heron layout and **Fast TableFormer**, no picture/formula enrichment. RapidOCR uses the three existing `rapidocr-onnxruntime` wheel checkpoints through explicitly pinned paths; this is **not default Docling OCR or the default accurate table model**. Both native and OCR-bearing Docling provenance remain in raw exported JSON.
- **native:** PyMuPDF **1.28.2** `find_tables()` plus native text regions for PDF; BeautifulSoup static table traversal for HTML. This diagnostic has **no OCR**. First-column row-label heuristics are explicit, not certified semantic row headers. The HTML adapter only targets simple grids; no general spans/complex-DOM claim.

All adapters preserve raw outputs separately from score interpretation. No adapter consumes gold. A Docling `self_ref` is an internal derivative reference, **not an original HTML DOM anchor**.

Frozen measures, reported independently:

1. **Numbers:** exact number-token presence in whole extracted text. Denominator is annotated numerical facts, including repeated values—not unique numbers or correct-cell accuracy.
2. **Units:** exact selected value-with-unit substring after whitespace collapse, only for eight unit-bearing facts. This does not test all unit/scale/sign conventions.
3. **Content presence:** selected raw-value substring in extracted text (12/12 for PDF-capable populated outputs; 6/6 for populated HTML outputs). Substring presence can match a number in an unrelated cell; it is deliberately **not precision**.
4. **Headers:** same candidate cell contains the raw value and exactly matches ordered row/column header paths. No semantic equivalence or gold-driven repair. Different header splitting/line breaks can therefore fail even when a human could reconstruct the association.
5. **Anchors:** same raw-value cell has the correct PDF page and normalized top-left box IoU ≥ 0.5 with the annotated **cell rectangle**, or the exact HTML source table/row/cell path. Missing capability scores zero; zero-denominator metrics are n/a.

**Important anchor caveat:** Docling exposes tight text-content boxes, whereas the gold and PyMuPDF table outputs use grid-cell rectangles. Low IoU is a failure of this frozen cell-extent contract, **not proof that text is on the wrong page or that the crop is unusable**. No posthoc containment metric was substituted. The baseline lacks region output altogether. These conventions must be harmonized prospectively before ranking anchor quality.

## 4. Actual final results

One fresh worker process per pair. Elapsed time includes imports, model load, extraction, adaptation and writing the raw output; it excludes dependency/model provisioning and initial corpus rendering. OS/disk caches may already be warm, so “fresh process” is not a cold-filesystem measurement. No warm throughput, GPU, per-stage timing, confidence intervals or statistical significance were measured.

RSS is sampled process-tree resident memory every 20 ms; peaks between samples can be missed, and summed RSS can double-count shared pages. Hard worker bounds were 150 seconds and 3,000,000,000 sampled RSS bytes. Baseline OCR fixes ONNX threads to one; other paths request two, so these are measured recipes, not a perfectly thread-matched performance contest.

| Variant | Candidate | Status | Numbers | Units | Headers | Cell-box / DOM anchors | s | RSS MiB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| native-pdf | baseline | ok | 12/12 | 8/8 | 0/12 | 0/12 | 0.297 | 62.4 |
| native-pdf | docling | ok | 12/12 | 8/8 | 0/12 | 2/12 | 11.032 | 1082.0 |
| native-pdf | native | ok | 12/12 | 8/8 | 0/12 | 12/12 | 0.199 | 52.0 |
| scan-pdf | baseline | ok | 12/12 | 8/8 | 0/12 | 0/12 | 4.059 | 403.6 |
| scan-pdf | docling | ok | 12/12 | 8/8 | 0/12 | 0/12 | 11.103 | 1098.8 |
| scan-pdf | native | empty | 0/12 | 0/8 | 0/12 | 0/12 | 0.198 | 66.9 |
| html | baseline | unsupported | n/a | n/a | 0/6 | 0/6 | 0.059 | 20.7 |
| html | docling | ok | n/a | n/a | 6/6 | 0/6 | 4.121 | 361.1 |
| html | native | ok | n/a | n/a | 6/6 | 6/6 | 0.141 | 32.9 |

Final coverage: **7/9 populated successful pairs, one empty native scan and one unsupported baseline HTML**. Docling populated 3/3 variants, baseline and native diagnostic 2/3 each. “ok” means extraction emitted content, not that structure passed acceptance. All final pairs completed without time/RSS-limit errors; every recorded owned-process survivor list is empty. No overall quality average is meaningful across these dependent variants and missing capabilities.

### Inspectable per-document examples

Use the final execution directory named in §1; each pair has `.json`, `.stdout.txt`, `.stderr.txt` files.

- **Native PDF:** gold `Blind → Results → Accuracy = 34.5%`. In `native-pdf-docling.json`, the value survives as `34.5%, n=1`, but the column path is `['Results Time to', 'Accuracy']`: an actual merged-header assignment defect. `Ballots Completed` is also split into two header levels, which the strict raw-path metric rejects. `native-pdf-native.json` retains the raw grid/header output and native text regions; this parser oversegments the merged header, so 12/12 boxes is not proof of correct table topology. `native-pdf-baseline.json` has no cell relations to evaluate.
- **Derived scan:** `scan-pdf-docling.json` retains `1672.1 sec,n=4` and OCR-derived page/box provenance but repeats the malformed Results path. `scan-pdf-baseline.json` retains its explicit OCR-transcription marker and page number; it has no region boxes. `scan-pdf-native.json` is honestly empty. The raster is retained independently in `sources/table-144dpi.png`; the manually annotated Blind accuracy crop is `P/blind-accuracy-gold-region.png`.
- **HTML:** `Imari` must be associated with row label `Phoenix` and column `First Name`, not guessed to be a city. Both populated adapters satisfy the six selected header relations. Only `html-native.json` emits source DOM indices such as `table:2/row:1/cell:1`; Docling exports internal table references instead. Neither parser ran JavaScript or followed linked resources.

## 5. Provisioning, licenses and reproducibility

The environment is experiment-local: **`P/venv/`**, Python **3.12.10**, Windows 11 build 28000. The measured host reported 24 logical/physical CPUs and 51,132,588,032 physical RAM bytes; no GPU was used or qualified. Runtime package versions are embedded in each report.

Exactly **317,129,717 selected Hugging Face bytes** were provisioned, below the 400,000,000-byte model bound. Revisions and weight hashes are in `model-receipts.json`: Heron `8f39ad3c0b4c58e9c2d2c84a38465abf757272d8` (model card: Apache-2.0) and Docling models `fc0f2d45e2218ea24bce5045f58a389aed16dc23` (model card: CDLA-Permissive-2.0). Only Fast TableFormer weights were selected; no VLM, training, EasyOCR download or accurate-table checkpoint was provisioned.

The installer logged approximately 398.9 MiB across its displayed large package downloads; that is **not an exact network-byte total**. `aggregate.json` records logical directory sizes, not additional downloads or exclusive physical storage: uv uses hardlinks. Package license receipts identify Docling components as MIT, RapidOCR as Apache-2.0 and **PyMuPDF as AGPL-3.0/commercial dual-licensed**. Embedded OCR checkpoint hashes are recorded, but their independent rights chain remains unqualified; wheel license is not blanket model clearance. Full transitive legal/SBOM acceptance remains open.

An MSYS/native-path mistake initially placed this pilot's private caches under `D:/d/Projets/...`. Only that unique cache directory was relocated into P, and the old path was verified absent; see `cache-path-correction.json`. Use native forward-slash paths below, not POSIX `$PWD`, in environment values passed to native Windows programs.

From `D:/Projets/BorgKnowledge`, Git Bash:

```bash
P='D:/Projets/BorgKnowledge/tools/artifacts/docintel-pilot-20261017'

# Reuse the already provisioned isolated environment; no shared .venv mutation.
rtk proxy "$P/venv/Scripts/python.exe" -m unittest discover \
  -s tests -p document_intelligence_benchmark_test.py -v

# A new unique execution directory is created; old results are not overwritten.
rtk proxy "$P/venv/Scripts/python.exe" tools/document_intelligence_benchmark.py \
  --run "$P/corpus-v2-lossless-scan"

# Clean-room dependency recreation, only if the existing environment is unavailable:
# choose a NEW project-local environment; never recreate over P/venv.
UV_CACHE_DIR="$P/uv-cache" rtk proxy uv venv --python 3.12 "$P/replay-venv"
UV_CACHE_DIR="$P/uv-cache" rtk proxy uv pip install \
  --python "$P/replay-venv/Scripts/python.exe" -r "$P/requirements-pilot.lock"
```

The final corpus's `models` link points to `P/models` to avoid duplicating weights. On another machine, recreate that link or copy the pinned model directory to `corpus-v2-lossless-scan/models`; verify receipts first. Do not update frozen gold or replace source bytes to make a score pass. For a new corpus/protocol, create and freeze a new version **before** running candidates.

Worker reports retain exact command arrays, elapsed/RSS measurements, status/errors, source/gold/protocol hashes, output hashes, package versions and code/helper hashes. Workers set Hugging Face/Transformers offline mode, disable remote services/plugins and use local weights. **This is not an operating-system network sandbox or an independently verified air-gap.**

## 6. Tests, boundaries and next evaluation

Nine vertical RED→GREEN cycles are retained as `P/tdd-01-*` through `P/tdd-09-*`: number boundaries, association vs geometry separation, HTML structure, PDF regions vs empty scan, actual Docling HTML, frozen-input tamper refusal, timeout/reaping, a three-variant subprocess pipeline with hash receipts and descendant cleanup after normal parent exit. The ninth adversarial test exposed surviving descendants; cleanup was corrected and the actual pipeline rerun with unchanged frozen inputs. Missing-function/key or behavioral failures were observed before each corresponding implementation; no public-source gold was generated from candidate output.

The new suite passed **9 tests**. Final full Python discovery passed **30 of 33 tests, with 3 explicitly skipped opt-in tests**; transcript: `P/python-regression-final.txt`. That existing suite also ran its own isolated Qdrant server integration, generating `artifacts/server-benchmark/179f87e3dc214a4e8b5c73f374c709df/`; its receipt records the owned server exited and port closed. An earlier full regression produced `artifacts/server-benchmark/f4081f44f70c4066a41e5372e01f82a6/`. These incidental regressions are **not** document-intelligence retrieval evidence. The final timed pilot was run after, not concurrently with, regression discovery. Rust/application behavior was not changed or newly accepted by this pilot.

**Not tested:** DOCX, PPTX, XLSX, legacy Office, Markdown, email, multilingual/French monetary formats, formula caches/macros/revisions/notes, rotated/noisy/mixed/physical scans, multipage tables, charts, equations, reading-order fidelity, malicious files, large batches or retrieval. Office libraries installed transitively do **not** count as Office support tested. No rights-reviewed public Office sample was selected within this finite slice.

Next useful frozen slice: independently annotate additional public reports, harmonize header/topology and cell-box versus text-box conventions **before** outputs, add French units/scales/signs and secondary notes, include explicit no-answer/inapplicable cases, then test downstream evidence completeness separately. Evaluate accurate TableFormer and a distinct OCR/layout challenger under an equal resource protocol rather than presenting this single fast configuration as the product's ceiling.

### Bank-group GED / agentic solution checklist — ALL NOT VALIDATED

- [ ] Tenant/entity/document ACLs enforced before retrieval and on parent/context/original expansion; negative cross-tenant tests including caches and logs.
- [ ] Business version/effective-date applicability and revocation propagated through indexes, expansions, caches, exported evidence and concurrent sessions.
- [ ] Tamper-evident audit of ingestion, correction, model/config version, access, abstention and human override; retained original versus derived history.
- [ ] Prompt-injection and malicious-document isolation: document text cannot authorize tool calls, network requests, filesystem access or policy changes; parsers sandboxed and resource limits independently challenged.
- [ ] Retention/deletion, backup expiry, legal hold, minimization, encryption/key ownership and lawful processing policies validated by the responsible group teams.
- [ ] On-prem deployment and egress controls, reproducible package/model provenance, full license/SBOM review and operational patching accepted; no automatic cloud fallback.
- [ ] Human review of critical amounts/units/header paths and auditable abstention; representative group-owned evaluation under explicit authorization.

This checklist is proposed acceptance work, **not a compliance, security, procurement or production-readiness assertion**.

## Sources

[1] https://www.w3.org/WAI/WCAG21/working-examples/pdf-table/table.pdf
[2] https://www.w3.org/WAI/tutorials/tables/one-header
[3] https://www.w3.org/copyright/document-license-2023
