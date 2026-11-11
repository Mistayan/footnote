# Evidence completion — diagnostic 2×2 intervention, not acceptance

## Outcome

Actual resident Qdrant retrieval and pinned resident mMARCO completed **52 old v2 diagnostic requests** in **76.59 seconds**, with **52/52 exact original pool/ranking/logit parity**. Four separately declared factors yield **208 presentation records**. This does not claim fresh ≥80% or ≥90% multilingual accuracy. Expanded text is **new intervention evidence version2**, never retroactive support for originally presented evidence.

Unique run: `artifacts/evidence-completion/diagnostic-4d656d0e6d954964aadbf9deb9478a2b/`.

**Integrity incident after successful run:** an existing regression test calls the historical v2 audit writer. Running `test_accuracy_validation_v2*.py` regenerated the historical `artifacts/accuracy-validation-v2/run-9090a031e1014818b42a6df066b68eb1/independent-audit.json`. Its original SHA256 was `21908211fe907f885cbcac5c4ee1b1be657a931e65adb66a4bd4b6c710c18c3f`; its regenerated SHA256 is `497542903b01f1f1dd4d78d47be58c90a735b6de13d639d8409fb750dbf9a6c3`. The pre/post live-run receipt correctly verified97 historical files unchanged **at run completion**, but final historical immutability is no longer true:96 match, this one does not. Source bytes, original results, gold and method hashes still match. Original audit bytes were not backed up, so no guessed timestamp or fabricated restoration was attempted. Restore this auxiliary audit from an actual external backup if available. See `final-integrity-incident.json`. This is a scope violation, not a successful all-files-immutable handoff.

## Frozen mechanism and controls

Read `BILINGUAL-EVIDENCE-AUDIT.md` and actual saved v2 evidence before intervention. Hypothesis: cut proof spans explain three uncertainties; an explicitly requested French source is a distinct applicability failure.

- Actual Qdrant770 slice96 vectors, point budget400 / dense parent100, original FTS top10, RRF60, final pool20, unchanged original parent text to pinned mMARCO512. Existing sources/models only; no downloads or runtime edits.
- **Completion** alone changes only presentation: uniformly choose outer sentence/paragraph/fenced-code/recognized REPL boundaries in pinned normalized source, bounded2500 Unicode characters. Exact substring, end-exclusive Unicode offsets and SHA256; no generation, label anchors, query input or query-specific completion branches. Overbudget returns untouched original and an explicit incomplete flag.
- **Constraint** alone applies authoritative source-receipt language before Qdrant point budget (server-side has_id filter), dense-parent budget, FTS10, fused pool20, and again in presentation/get. Unknown source language is excluded when constrained.
- Request metadata is frozen in `requests.json`. A tested narrow generic grammar recognizes “According to the French/English … documentation” or “Selon la documentation française/anglaise”; it does not infer source language from query language. Exactly one old request carries `source_language=fr`. Callers should normally provide explicit metadata. This grammar is intentionally incomplete, not a universal natural-language constraint parser.
- Factor labels: `completion0_constraint0`, `completion1_constraint0`, `completion0_constraint1`, `completion1_constraint1`. Unconstrained live acquisition is reused for identical unconstrained requests;53 live retrieval/ranker requests total, not208 independently timed pipelines.
- Original refusal remains **max candidate logit≥2.5**. Neither cutoff nor ranking inputs are refitted. Completion cannot alter ranking/logits/acceptance.

## Historical-ID scoring, never semantic acceptance

Expected IDs and historical denominators remain unchanged. ID membership does **not** award credit merely because the expanded source contains a quote.

| Completion | Source constraint | Historical selected-ID hit@1 / all40 answerable | Accepted answerable | No-answer false acceptance |
|---|---|---:|---:|---:|
| off | off |19/40 (47.5%)|39/40|0/12|
| on | off |19/40 (47.5%)|39/40|0/12|
| off | on |20/40 (50%)|39/40|0/12|
| on | on |20/40 (50%)|39/40|0/12|

Every factor rejects the same `v2-016-fr` answerable request;20/20 English and19/20 French answerables are accepted. All12 no-answer requests remain rejected. Precision among all39 accepted, under the incomplete historical selected-ID labels, is19/39 or20/39 respectively. These are not complete semantic precision estimates. The earlier baseline20/40 and selected19/40 files are not relabeled.

## Structural crossing-boundary checks

All three previously cut support spans are absent in full from original top1, present in full in the version2 excerpt, and independently verified as exact substrings of the pinned normalized source. This is a structural result, **not three automatically granted semantic passes**.

| Old query | Original offsets | Version2 offsets | Whole diagnostic support span |
|---|---|---|---|
|`v2-006-en`|`pathlib-en[13500:15300]`|`[13365:15330]`|`[13414:13461]`: `>>> PurePath('a/b.py').full_match('*.py')` followed by `False`|
|`v2-013-en`|`contextlib-en[9900:11700]`|`[9360:11703]`|`[9792:9995]`: global-side-effect suitability sentence plus no-subprocess-effect sentence|
|`v2-020-en`|`transactions-en[3600:5400]`|`[3381:5419]`|`[5249:5419]`: complete commit/rolled-back-actions-never-visible sentence|

Constraint-only changes `v2-011-en` top1 from `contextlib-en-0002` (logit5.318718433380127) to `contextlib-fr-0002` (2.8980460166931152), still above2.5. Completion alone does not repair source-language applicability. `structural-diagnosis-DO-NOT-SEND.json` preserves full originals, exact new text, original/new hashes and probe source offsets, separate from blind review material.

## Cost and residual risks

- With constraints on, top1 total chars90587→101158 (**+11.67%**); top5 chars461114→510443 (**+10.70%**). Equivalent intervention envelopes1188742→1270309 bytes (**+6.86%**). These envelopes deliberately retain original AND new evidence; this is not an optimized transport measurement.
- Completion-only changes48/52 top1 hashes and246/260 top5 hashes. With constraints,48/52 top1 hashes and245/260 top5 hashes change. Original records remain attached unchanged.
- **4/52 top1** and **15/260 top5** constrained-completion excerpts exceed the boundary-expansion budget and therefore retain incomplete original spans. Completion-only has14/260 overbudget top5 fallbacks. Do not label all returned evidence complete.
- Normalization strips HTML pre/paragraph semantics. Recognized sentence/fenced-code/REPL boundaries are heuristic; arbitrary output, unfenced code, abbreviations, malformed/unclosed fences and multilingual punctuation need further independent fixtures. A structural flag is not a semantic proof checker.
- Bound is2500 characters, not512 rank tokens. New presentation is never sent back through the ranker, so no claim is made about model token cost or ranking improvement. Larger excerpts can introduce distractions, competing scope/version statements, and higher reader/agent costs.
- Sampled harness peak RSS1159311360 bytes; server56922112 bytes. Sampled CPU time177.46875s harness and0.140625s server. Whole live experiment76.59s; these are not separate-factor latency estimates.
- Owned server PID4644/port50852 exited and closed; returncode1 is the recorded forced terminate/wait shutdown, not graceful-exit proof. No other PID stopped. No private/vault/global/environment mutations, staging or commits were requested/performed; the historical auxiliary audit write incident above is explicitly disclosed.

## Review packet and next fresh configuration

**Send ONLY these two files to an independent semantic reviewer:**

- `blind-packet.json`:102 unique query/full-presented-text/provenance pairs, shuffled, no pipeline/score/acceptance/labels/query IDs. SHA256 `34f0ac2852336ce3a8972552d8269888e15e28deb8af145aadd3e2d0ee70d755`.
- `RUBRIC.json`: written before live inference. SHA256 `a4ca2ee42af4dfed980cf2c7fc44c650b6d8ffcd9fb81ad2d3e80e71a47e9ff9`.

There are208 separate mapping rows. **Do not send this report, results, structural diagnosis, expected IDs or `mapping-DO-NOT-SEND.json` before reviewer verdict freeze.** The packet is presentation-blinded; the implementing agent was already exposed. No second reviewer has yet scored it.

`next-fresh-candidate-config.json` freezes the candidate hypothesis/source hashes/cutoff and requires NEW independently judged facts/questions with corpus-wide bilingual/applicability coverage, controls and reporting rules frozen before inference. This is a declaration, not a new selected winner or a completed fresh corpus-binding runner. The existing standalone diagnostic constructor is intentionally bound to old v2. Acceptance remains pending independent review and a genuinely new evaluation; all-answerable P@1 goals remain80% then90%, never inflated by refusals or old-test selection.

## Reproduction and verification

```bash
python -m unittest discover -s tests -p 'test_evidence_completion*.py' -v
python -m tools.evidence_completion.experiment  # creates a NEW unique diagnostic run
```

Five focused tests were developed through observed missing-feature/assertion RED→GREEN cycles: sentence offsets, fenced/REPL blocks, bounds/Unicode, request filtering/get/presentation and explicit metadata grammar. Three additional read-only artifact tests verify208 factor rows, frozen ranking/refusal parity, source gating, packet separation and every manifest hash; these were added after execution and are not claimed test-first. Final new suite8/8 passes. Related v2 suite7 passes/5 opt-in skips; semantic audit suite5 passes. **Do not rerun the old v2 audit tests on immutable evidence without isolating its writer**: they caused the disclosed incident.

`artifact-sha256.json` verifies the live evidence bundle; `supplement-sha256.json` binds structural analysis and next-candidate declaration. The final integrity receipt supersedes the earlier run-completion historical-unchanged receipt. New files are confined to `tools/evidence_completion/*`, `tests/test_evidence_completion*.py`, this report and the unique evidence directory, except the disclosed existing auxiliary audit regeneration.
