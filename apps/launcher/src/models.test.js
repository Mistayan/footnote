import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { modelCards } from "./models.js";

const catalogue = [
  { name: "minilm", installed: false, license: "Apache-2.0" },
  { name: "jina-v5-nano", installed: false, license: "CC-BY-NC-4.0 (no commercial use)" },
  { name: "gte-small", installed: true, used_by_memory: true, license: "MIT" },
  { name: "bekko-a8m", installed: true, used_by_memory: true, license: "MIT" },
  { name: "e5-small", installed: false, license: "MIT" },
];

test("cards follow the measured ranking, active models first", () => {
  const names = modelCards(catalogue).map((c) => c.name);
  assert.deepEqual(names, ["gte-small", "bekko-a8m", "jina-v5-nano", "jina-v5-small", "embeddinggemma-300m", "e5-small", "minilm"]);
});

test("a measured model outside the catalogue is an import card until a file of its family is imported", () => {
  let cards = modelCards(catalogue);
  const gemma = cards.find((c) => c.key === "embeddinggemma-300m");
  assert.equal(gemma.candidate, true);
  assert.equal(gemma.license, null);
  cards = modelCards([...catalogue,
    { name: "embeddinggemma-300m-q8_0", installed: true, imported: true, family: "embeddinggemma", license: null },
    { name: "my-embed", installed: true, imported: true, family: null, license: "apache-2.0" }]);
  const taken = cards.find((c) => c.key === "embeddinggemma-300m");
  assert.equal(taken.name, "embeddinggemma-300m-q8_0");
  assert.equal(taken.candidate, false);
  assert.ok(taken.facts.stats.length > 0, "the imported file shows the family's measurements");
  const other = cards.find((c) => c.name === "my-embed");
  assert.equal(other.facts, null, "an unmeasured import shows no numbers");
  assert.equal(cards.at(-1).name, "my-embed", "unmeasured imports come last");
});

test("every number links to a report that exists in bench/experiments", () => {
  for (const c of modelCards(catalogue)) {
    const links = [...(c.facts?.stats ?? []).map((s) => s.receipt), c.facts?.receipt, c.facts?.note?.receipt].filter(Boolean);
    for (const path of links) {
      assert.match(path, /^bench\/experiments\/[A-Z0-9-]+\.md$/);
      assert.ok(readFileSync(new URL(`../../../${path}`, import.meta.url), "utf8").length > 0, path);
    }
  }
});

/** Whether the report gives `quoted` (as written on a card, rounded) among its numbers: 0.572 matches 0.5720, 69 ms 68.8. */
function inReport(text, quoted) {
  const m = quoted.match(/\d+(?:\.(\d+))?/);
  const value = Number(m[0]);
  const half = 0.5 * 10 ** -(m[1]?.length ?? 0) + 1e-9;
  return (text.match(/\d+\.?\d*/g) ?? []).some((x) => Math.abs(Number(x) - value) <= half);
}

test("every quoted score and difference appears in its report", () => {
  for (const c of modelCards(catalogue)) {
    for (const s of c.facts?.stats ?? []) {
      const text = readFileSync(new URL(`../../../${s.receipt}`, import.meta.url), "utf8");
      assert.ok(inReport(text, s.value), `${c.name}: ${s.label} ${s.value} not in ${s.receipt}`);
      if (/\d/.test(s.vs)) assert.ok(inReport(text, s.vs), `${c.name}: ${s.label} ${s.vs} not in ${s.receipt}`);
    }
  }
});
