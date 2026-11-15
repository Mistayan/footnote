# Footnote backlog

Last updated 15 November 2026. One prioritised list; Beads stays the authority for tracked tasks. Order inside a tier is the order
of work. "Johan" marks items waiting for his go.

## Recently done

- Test 5 (llama.cpp models, [rule and results](../../bench/experiments/LLAMACPP-MODELS.md)): no model adopted through an HTTP server.
- Test 6 ([results](../../bench/experiments/LLAMACPP-INPROCESS.md)): Jina v5 nano in-process, wired into the product
  (`--features llama`), held-out quality passes on the product: Alloprof +0.103 [+0.090, +0.115], mix-fr-en +0.083 [+0.074, +0.093].
- Audit-chain fork fixed (two concurrent MCP sessions); Rust-encoder build with metrics installed (15 Nov).

## P0: protect and finish what exists (small, this week)

1. **Commit and push** everything since the last push (two days of work, uncommitted). Johan.
2. **Make memory work visible** (Johan's first-week feedback): the hook asks agents to say in a few words when a recalled memory
   shapes the answer, and to give a short receipt after each save.
3. **Zero retention in the hook:** per-session journals under `memory-hook/` keep conversation text; keep only what the hook needs,
   then delete the old journals (Johan).
4. **`bk-gsh`, hybrid recall on each prompt:** the memory baseline gave hybrid any@5 0.504 against keyword 0.384.
5. **Jina nano latency on an idle machine** (Johan says when), then ship it as the opt-in French/mixed profile.
6. **Memory review** around 21 November (baseline: memory 134).

## P1: product structure (next)

7. **Separate products, features on or off:** Library, Memory, Code, Alias enabled independently; nothing loaded that is not used.
8. **Embedding model manager:** install, switch, remove; recommend from the detected hardware (GPU, VRAM, CPU, RAM) and corpus language,
   from Footnote's own results (the model matrix: licence × hardware × language). Today: the pair by default, nano for French/mixed,
   EmbeddingGemma 1 on a GPU.
9. **Hook in Rust** (`footnote hook`), then delete `tools/embed.py`: no Python left on the memory path (hook p95 225 ms today). Johan.
10. **Icons:** one family, one icon per product.

## P2: new products

11. **Footnote Alias** (pseudonymisation before the LLM): desk study first (Presidio, LLM Guard, GLiNER PII, French accuracy), then a
    French + English prototype with underline-and-explain. Design notes below.
12. **Footnote Code:** code-graph study ([plan](../research/CODE-GRAPH-STUDY.md)); hands-on after Johan's go.

## P3: benchmarks, when a decision needs them

- Model matrix and setup playbook (feeds item 8).
- Test 5 stage A3 (Octen-4B, F2LLM-v2-1.7B, harrier-oss-v1) and the llama.cpp speed grid (`-fa`, `-ub`, runtime versions).
- Storage backends: SQLite + Tantivy against Postgres + pgvector, LanceDB, HelixDB, Omnigraph; Qdrant for large companies only.
  Ask before installing Postgres or Docker.
- Memory rematch (mem0, Cognee graph, Hindsight, Graphiti, OpenViking, EverOS), after the review.

## Later: company deployment (not urgent, Johan 15 Nov)

**Access control and data tiers**, before the first company deployment:
1. Every document and memory carries a scope (owner, team, department) and a classification tier, on the client's own grid.
2. Filtering happens in the engine before ranking, never by dropping hits from a top-k afterwards.
3. A memory inherits the highest tier of its sources; some tiers never enter agent memory.
4. An agent session carries the clearance of its user, never more.

Advice for every company: classify data before connecting agents; adding it later means re-tagging everything and auditing memory.

**Compliance kit**, to bring the French approval path (about a year) down to four to six months:

| Reviewer | What they get |
|---|---|
| DPO | Record of processing (purpose, data, no retention beyond the index), data-flow diagram, DPIA inputs, Alias and the CJEU SRB argument |
| IT security (SSI) | Architecture (local, no outbound network), hash-chained audit log, threat model, dependencies, vulnerability audit (not run yet) |
| Compliance | AI Act position, licences of every model and dependency, what the tool cannot do |
| CSE / CSEC | No per-employee monitoring; usage statistics aggregated and off by default |

## Ideas, unranked

- UI study of T3 Code (https://github.com/pingdotgg/t3code): rounded look, typography, links in chat; check the licence; take
  structure, layout and motion.
- Footnote Roadmap (visual roadmap from memories and Beads) and the project node map.
- Baseline audit across projects: AI contracts and rules, security-reviewed skills, projects behind on push.
- Progressive context levels (summary, overview, full on demand), after OpenViking.
- Verify the DeepSeek memory hook. Product page v2 (`site/index.html`): QLoop review before commit.

## Footnote Alias, design notes

- **Legal anchor** (verified 15 Nov): CJEU C-413/23 P EDPS v SRB, 4 Sept 2025, para 86: pseudonymised data is not personal data for a
  recipient with no reasonable means to re-identify. The client still names the LLM provider as a recipient (para 112) and signs a
  no-re-identification clause. EDPB guidelines 01/2025 (consultation) still disagree; national regulators may be stricter.
- **Johan's principle:** processing is justified by its purpose; the AI tool must not identify the person, the business application
  may. The identity link stays in the client file; Footnote and the LLM see stable pseudonyms keyed with the company's secret (statistics
  and history still work, access and erasure requests stay answerable). The mapping never leaves the machine or enters a log.
- **Product:** optional module, France first (French + English), plug and play in host apps; runs before any text reaches an AI; a very
  good detection rate, never promised as 100 %.
- **UX leaning:** underline while typing; hovering explains the type, the GDPR rule and what to write instead, in plain French,
  editable by the company's DPO. One engine serves live warning, on-demand check and save-time review.
