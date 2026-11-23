// The Models screen's data (#556): what Footnote measured for each model, and the cards in ranked order. Plain
// JavaScript so `npm test` can check it.

// The ranking: what the benchmarks measured, each number opening its report. nDCG@10 on held-out
// splits, each difference against the default pair in the same run. Order: the active models, the default pair (shipped,
// fastest), the best measured alternatives, the earlier models, then imported models nobody measured.
const FINAL = "bench/experiments/FINAL-RANKING.md";
const INPROC = "bench/experiments/LLAMACPP-INPROCESS.md";
const CONFIRM = "bench/experiments/LLAMACPP-CONFIRMATION.md";
const COSTS = "bench/experiments/LLAMACPP-MODELS.md";
const PAIR = {
  tag: "Default · fastest",
  best: true,
  stats: [
    { label: "Mixed", value: "0.489", vs: "the reference", receipt: FINAL },
    { label: "English", value: "0.747", vs: "the reference", receipt: FINAL },
    { label: "Search p95", value: "42 ms", vs: "the reference", receipt: INPROC },
  ],
};
const MEASURED = {
  "bekko-a8m": PAIR,
  "gte-small": PAIR,
  "jina-v5-nano": {
    tag: "Recommended for French or mixed",
    best: true,
    stats: [
      { label: "Mixed", value: "0.572", vs: "+0.083 vs pair", good: true, receipt: INPROC },
      { label: "French", value: "0.578", vs: "+0.103 vs pair", good: true, receipt: INPROC },
      { label: "Search p95", value: "69 ms", vs: "pair 42 ms", receipt: INPROC },
    ],
  },
  "jina-v5-small": {
    tag: "Highest French score, slowest",
    best: true,
    repo: "jinaai/jina-embeddings-v5-text-small-retrieval-GGUF",
    measuredOn: "the Q8_0 file",
    bytes: 639e6,
    stats: [
      { label: "Mixed", value: "0.579", vs: "+0.080 vs pair", good: true, receipt: CONFIRM },
      { label: "French", value: "0.589", vs: "+0.100 vs pair", good: true, receipt: CONFIRM },
      { label: "Encoding p95", value: "98 ms", vs: "pair 17 ms", receipt: COSTS },
    ],
  },
  "embeddinggemma-300m": {
    tag: "Best English score",
    best: true,
    repo: "ggml-org/embeddinggemma-300M-GGUF",
    measuredOn: "the Q8_0 file",
    bytes: 334e6,
    stats: [
      { label: "Mixed", value: "0.560", vs: "+0.061 vs pair", good: true, receipt: CONFIRM },
      { label: "English", value: "0.786", vs: "+0.040 vs pair", good: true, receipt: CONFIRM },
      { label: "Encoding p95", value: "61 ms", vs: "pair 17 ms", receipt: COSTS },
      { label: "Mixed, ONNX", value: "0.562", vs: "+0.063 vs pair", good: true, receipt: "bench/experiments/MODEL-CONFIRMATION.md" },
    ],
  },
  "e5-small": { tag: "Not better than the default", verdict: "Did not beat the default pair when added to it.", receipt: "bench/experiments/RESULTS.md" },
  minilm: { tag: "Not better than the default", verdict: "Did not beat the default pair when added to it.", receipt: "bench/experiments/RESULTS.md" },
};
const RANK = ["bekko-a8m", "gte-small", "jina-v5-nano", "jina-v5-small", "embeddinggemma-300m", "e5-small", "minilm"];
const GGUF = new Set(["jina-v5-nano"]);
/** Measured GGUF models outside the catalogue: a card offers to import them, and an imported file of the family takes
 * the card's place with its measurements. */
const CANDIDATES = [
  { name: "jina-v5-small", role: "Jina v5 text small retrieval", match: (m) => m.family === "jina-v5" && /small/.test(m.name),
    license: "CC-BY-NC-4.0 (no commercial use)" },
  { name: "embeddinggemma-300m", role: "EmbeddingGemma 300M", match: (m) => m.family === "embeddinggemma", license: null },
];

/** The cards in ranked order: catalogue models, measured candidates (imported or not) and other imported models. */
export function modelCards(models) {
  const taken = new Set();
  const cards = [];
  for (const cand of CANDIDATES) {
    const m = models.find((x) => x.imported && !taken.has(x.name) && cand.match(x));
    if (m) taken.add(m.name);
    cards.push({ key: cand.name, rankAs: cand.name, name: m?.name ?? cand.name, model: m, candidate: !m, gguf: true,
      role: m ? `Imported · ${cand.role}` : cand.role, license: m ? m.license ?? cand.license : cand.license, facts: MEASURED[cand.name] });
  }
  for (const m of models) {
    if (taken.has(m.name)) continue;
    cards.push({ key: m.name, rankAs: m.name, name: m.name, model: m, gguf: !!m.imported || GGUF.has(m.name),
      role: m.imported ? "Imported GGUF" : m.role, license: m.license, facts: m.imported ? null : MEASURED[m.name] });
  }
  const rank = (c) => (c.model?.used_by_memory ? -1 : RANK.indexOf(c.rankAs) < 0 ? RANK.length : RANK.indexOf(c.rankAs));
  return cards.sort((a, b) => rank(a) - rank(b));
}

