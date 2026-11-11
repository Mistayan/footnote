# Multilingual question-conditioned support verification — bounded development result

## Decision

**Negative: do not advance this QA checkpoint/rule to a personal-store field trial.** Real inference completed on the OLD DEVELOPMENT 16 answerable + 5 no-answer questions, with the unchanged historical ordered 20-parent pools. This is neither a fresh 80% milestone nor a 90% result. No incumbent, runtime, vault, global environment, staging, or commit was changed.

The question-conditioned reader is technically runnable and source-anchored, but its null/span margin is a poor local support discriminator. The zero-margin QA gate refuses every baseline answer; reranking by QA margin selects unrelated passages and a wrong Python version. Development calibration cannot recover useful coverage while rejecting all five no-answer cases. Keep current mMARCO; do not call either its logits or QA margins confidence.

## Research question and primary evidence

Question: can a question-conditioned evidence answerability signal reject superficially topical candidates without losing useful multilingual answers? A declarative NLI task and an interrogative answerability task are not interchangeable. Never pass the raw question as an NLI hypothesis and interpret entailment as evidence that it has a complete answer.

| Theme / primary source | What was actually read | Mechanism and local implication | Costs / constraints |
|---|---|---|---|
| Rajpurkar, Jia, Liang, **Know What You Don’t Know: Unanswerable Questions for SQuAD**, ACL 2018 short paper | Official abstract and bibliographic record | Extractive QA must both locate answers and abstain when unsupported. This motivates explicit question/context null scoring, not similarity-as-confidence.[1] | This experiment uses one reader pass per parent. SQuAD task transfer to technical French/English and source markup remains unproven. |
| Conneau et al., **XNLI: Evaluating Cross-lingual Sentence Representations**, EMNLP 2018 | Official abstract and bibliographic record | Multilingual premise/hypothesis understanding benchmark; extending MultiNLI to additional languages does not define a question-answerability or complete-evidence test.[2] | Multilingual coverage does not establish technical QA support or version applicability. |
| Honovich et al., **Q2: Evaluating Factual Consistency in Knowledge-Grounded Dialogues via Question Generation and Question Answering**, EMNLP 2021 | Official abstract and bibliographic record; not full PDF | Uses question generation and answering, and compares answer spans with NLI. It is not raw-question-as-hypothesis NLI.[3] | Full Q2 needs additional generation and comparison passes; not implemented or measured here. No paper gains are projected onto this corpus. |
| deepset XLM-RoBERTa base SQuAD2 checkpoint card | Full pinned card | Multilingual base; downstream training SQuAD2; card reports German MLQA/XQuAD evaluation, not French technical completeness validation. Upstream model declares CC-BY-4.0.[4] | English training / extractive task and code-like source text are transfer risks. Attribution to deepset/Branden Chan, Timo Möller, Malte Pietsch, Tanay Soni retained. |
| holisticon ONNX conversion | Pinned file listing/API, config and tokenizer; no README/license in listing | Config names deepset/xlm-roberta-base-squad2, but conversion parity and exact derivative licensing are not independently established.[5] | **License/provenance qualification gap:** upstream license verified, exporter has no explicit license. Do not mark exact exported checkpoint license verified or approve distribution/production. |
| MoritzLaurer mDeBERTa-v3-base-mnli-xnli card | Full pinned card, no weights downloaded | MIT checkpoint trained on MNLI and XNLI; premise/hypothesis classifier, not direct complete-answer verifier. Card language coverage is not proof of QA quality.[6] | Alternative only for declarative candidate-answer claims plus question/coverage logic; no local gains claimed. |

No claim of full-paper review, independently verified published model performance, or public-to-private-vault generalization is made. Source bytes and readable primary abstracts are preserved task-locally; the source ledger includes literal evidence quotes.

## Frozen experiment and checkpoint

Run directory, relative to repository:

`tools/support_verification_probe/run-8723dcef55ce487ebf5a56187e2dab5a/`

- `execution-freeze.json` written before evaluation inference: input/code/model hashes, exact original query/body recipe, 20-parent order, variants and development-only calibration objective.
- Inputs: existing `development-judgments.json`, `corpus.json`, `source-receipts.json` under `artifacts/fresh-multilingual-evaluation/efa3665b07c14411bb371bc7983b4f1c/`; fixed pools replayed from historical development `full2`. No acquisition/model/corpus changes inside the comparison.
- Encoder/Qdrant retrieval not rerun: deliberately matched fixed-pool verification probe. This is not an agent-facing/live-Qdrant acceptance test.
- Baseline: actual pinned current mMARCO, original query/body, max512, original ordered cohorts of four; one resident session, **420 actual inference pairs**. Incumbent cutoff 2.5 retained as a separate control.
- Candidate: `holisticon/xlm-roberta-base-squad2-onnx`, exact revision `d1e22df603ee04f4e0ff540d0d3bce147586df78`; config identifies upstream `deepset/xlm-roberta-base-squad2`; upstream card pinned `a5fab9908c8d856e8c583fd41ba6d92444e46477`.[4][5]
- ONNX SHA-256: `b0694fd87735fb57ec96afb3f41198512eb304c61b02fc9ebedfe035d1d0d45e`; tokenizer SHA-256: `c564888dbafbfebcc7a62d2f4049afe83e6fb5acd50a97082a84407c77ddd8ff`.
- **1,127,185,960 model/tokenizer/config bytes downloaded**, below the 1,200,000,000-byte ceiling; all project-local in `tools/support_verification_probe/model/`. No install/shared-environment mutation. Existing ORT/tokenizers/numpy used directly; no torch or transformers required.
- Candidate question/context only, first384 tokens, `only_second` truncation, no title enrichment or translation. Best joint start/end restricted to context and ordered span, maximum48 answer tokens; CLS start+end minus best span is the recorded null margin. No softmax/confidence interpretation. One resident QA session, **420 actual inference pairs**.
- Calibration uses only these old development labels: reject all five no-answer, maximize selected-label correct accepted, then coverage, then stricter cutoff. It is an assistant-proposed experiment constraint, not a user-approved operational SLA.

### Host and bounded execution

Observed Intel Core Ultra 7 270K Plus, 24 logical CPUs, AMD Radeon RX 6800. `nvidia-smi` unavailable; ONNX Runtime 1.30.0 exposed CPUExecutionProvider and AzureExecutionProvider, not GPU execution. Actual run used CPU: QA four intra-op threads, mMARCO two; inter-op one. Measured baseline inference 29.375s, candidate inference 57.066s, complete probe wall89.279s, not resident end-to-end retrieval latency. No GPU speed claim.

## Raw development counts

“Correct” below means recovered frozen selected-positive **parent ID**, not independently adjudicated complete evidence or extracted-answer accuracy. Other parents are UNKNOWN, not necessarily irrelevant. P@1 denominator is **all16 answerable questions**; abstentions count as misses. Coverage is accepted answerable/16. No-answer false accepts are out of5.

| Rule | Selected-positive correct accepted /16 (P@1) | Answerable accepted /16 (coverage) | Answerable rejected /16 | No-answer false accepts /5 | Selected-label correct / all accepted |
|---|---:|---:|---:|---:|---:|
| mMARCO, unthresholded | 15/16 (93.75%) | 16/16 (100%) | 0/16 | 5/5 | 15/21 |
| mMARCO, incumbent cutoff2.5 | 12/16 (75%) | 13/16 (81.25%) | 3/16 | 0/5 | 12/13 |
| mMARCO top1 + QA margin≥0 | 0/16 (0%) | 0/16 (0%) | 16/16 | 0/5 | undefined, no accepted results |
| QA-margin rerank, margin≥0 | 0/16 (0%) | 2/16 (12.5%) | 14/16 | 1/5 | 0/3 |
| QA-margin rerank, unthresholded | 6/16 (37.5%) | 16/16 (100%) | 0/16 | 5/5 | 6/21 |
| Dev-calibrated baseline QA gate, margin≥0.2802557945 | 0/16 (0%) | 0/16 (0%) | 16/16 | 0/5 | undefined |
| Dev-calibrated QA rerank, margin≥3.1452529430 | 0/16 (0%) | 1/16 (6.25%) | 15/16 | 0/5 | 0/1 |

The superficially high unthresholded mMARCO point estimate is recycled old development with incomplete selected labels and all five no-answer false accepts. It cannot certify the user's personal multilingual 80% lower milestone or 90% stretch target.

### Parity and historical integrity

The initial pool source `diagnostic-3b7...` has original earlier batch-composition scores: current baseline exact scores/ranks are 0/21 against that receipt. This is recorded unchanged, not patched away. Read-only supplemental comparison against both later corrected original-order receipts `diagnostic-5d7...` and `diagnostic-75b...` verifies **21/21 exact score dictionaries and 21/21 exact rankings**, with identical pools. See `historical-parity-supplement.json`. Quantized batch composition matters; no fabricated tolerance or historical receipt regeneration was used. All four hashed initial historical input files remained byte-identical after the run; supplemental comparison files were only read.

## Actual support / complete-answer limitations

All420 pair rows retain original query ID, parent/source IDs, URL, raw-source and parent SHA-256, exact source offsets, extracted source span, null and best-span logits, mMARCO logit, token count, omitted-window count, and resident-session ID. **All420 spans were also programmatically checked against their normalized source `.txt` slice**; `source-span-verification.json` records those normalized-file SHA-256 values. Offsets are Unicode codepoints in normalized source text, not raw-source byte offsets; the raw-source hash is the upstream provenance link. `per-query.jsonl` contains every exact question and ordered QA top-five full parent excerpts with provenance; no-answer questions also retain best non-null span and null score even when refused.

**409/420 pairs omit at least one overflow window.** This is a bounded first-window experiment, not a whole-parent answerability assessment. The training card used shorter contexts too, but that does not excuse lost technical proof. A negative result here rejects this recipe, not all multilingual extractive QA.

`span-support-review.json` contains an exposed, executing-assistant review of each top QA span: only4/16 answerable spans conservatively judged complete; the rest partial or unsupported. This is not independent gold and does not rewrite selected-positive metrics. Candidate-parent complete support remains unjudged outside frozen positives.

Concrete failures:

- The Git --follow single-file limitation is correctly extracted, yet its best QA support margin is −3.4342 and a zero threshold refuses it.
- The relevant decoration parent is recovered for an exclusion question, but the extracted `log.excludeDecoration` configuration token is not the requested command-line exclusion option. Correct parent does not equal complete/correct extracted answer.
- French Python strict-version question promotes unrelated argparse **3.2**, margin+3.1453, instead of itertools **3.13**. This is the sole dev-calibrated accepted answer and is wrong.
- A French private-generator no-answer question promotes HTTP-cache `5.2.2.7`, margin+1.8199. Extractability does not establish applicability or private knowledge.
- combinations “by position” is a plausible supported extracted answer from a non-selected overlapping parent. This is logged as a selected-label limitation, not silently relabeled to improve P@1.
- A valid option name, brief answer or supporting fragment cannot establish complete why/multipart reasoning, both sides of a comparison, version correctness or exhaustive evidence coverage. No generated recommendation is evaluated here.

## Verification, artifacts and next decision

Four tests passed, including actual ONNX source-span smoke and the complete420+420 pair experiment. Decoder, all-answerable denominator, resident adapter and bounded runner were each tested RED before implementation, then GREEN. Terminal outputs showed intended missing-feature assertions; final replay evidence is `tools/support_verification_probe/test-execution.log` (4 tests, 91.230s, OK). These are scoped tests, not a claim that the entire unrelated repository suite was run.

Created only the owned report, `tools/support_verification_probe/` and `tests/test_support_verification_probe.py`; no existing partial files/report were present at resume. Primary fetch `web_extract` was search-only and could not fetch; direct public HTTPS primary sources succeeded. The guessed nonexistent onnx-community checkpoint returned401; a public pinned holisticon ONNX alternative actually ran. No simulated results.

Core receipts: `execution-freeze.json`, `frozen-questions.json`, `frozen-pools.json`, `pairs.jsonl`, `per-query.jsonl`, both calibration tables, `selection-freeze.json`, `report.json`, `historical-verification.json`, `artifact-sha256.json`, `historical-parity-supplement.json`, `span-support-review.json`. Root `delivery-sha256.json` covers supplemental receipts, source material, tests, code, report and final logs without mutating archived receipts.

Download and inference child processes exited0 and were explicitly waited/polled to completion. No Qdrant/server/translator launched, no ports opened by this probe; model sessions released on Python process exit. Retain downloaded model for reproducibility; no long-lived process or shared environment changes to clean up.

**Next justified step is not a field trial of this candidate.** If continuing later, first obtain an explicitly licensed/export-parity-qualified checkpoint and test a prespecified question-conditioned support/coverage formulation with token-safe evidence windows on old development, preserving identical pools and baselines. A declarative multilingual NLI checker may complement an explicit proposed answer and multipart coverage decomposition; it must not use the question alone as its hypothesis. Only a positive complete-evidence development result with acceptable coverage would justify freezing a new independently judged field test. Nothing was launched beyond this finite experiment.

## Sources

[1] https://aclanthology.org/P18-2124
[2] https://aclanthology.org/D18-1269
[3] https://aclanthology.org/2021.emnlp-main.619
[4] https://huggingface.co/deepset/xlm-roberta-base-squad2/blob/a5fab9908c8d856e8c583fd41ba6d92444e46477/README.md
[5] https://huggingface.co/holisticon/xlm-roberta-base-squad2-onnx/tree/d1e22df603ee04f4e0ff540d0d3bce147586df78
[6] https://huggingface.co/MoritzLaurer/mDeBERTa-v3-base-mnli-xnli/blob/8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c/README.md
