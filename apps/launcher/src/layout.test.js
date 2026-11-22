// npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { closure, engineLevel, filesLevel, linkNames } from "./layout.js";

const map = {
  blocks: [
    { name: "src", files: 9, symbols: 120, entry: true, description: "The CLI", described_in: "Cargo.toml" },
    { name: "crates/core", files: 4, symbols: 40, entry: false },
    { name: "scripts", files: 2, symbols: 5, entry: true },
    { name: "tests", files: 3, symbols: 20, entry: true },
  ],
  links: [
    { from: "src", to: "crates/core", references: 12, symbols: [{ name: "state_dir" }], other_symbols: 3 },
    { from: "tests", to: "src", references: 4 },
  ],
  outside: [
    { package: "axum", version: "0.8", references: 9, class: "server", used_by: ["src"] },
    { package: "rusqlite", version: "0.37", references: 30, class: "database", used_by: ["crates/core"] },
    { package: "rusqlite", version: "0.32", references: 2, class: "database", used_by: ["crates/core"] },
    { package: "anyhow", version: "1", references: 50, class: null, used_by: ["src"] },
  ],
};

test("level 1 draws linked blocks, lists the rest, and adds calls in and calls out", () => {
  const L = engineLevel(map);
  assert.deepEqual(L.nodes.map((n) => n.id), ["in:axum", "src", "crates/core", "out:database"]);
  assert.deepEqual(L.hidden, ["scripts", "tests"]);
  assert.deepEqual(L.nodes.at(-1).packages.map((p) => p.name), ["rusqlite"]);
  const src = L.nodes.find((n) => n.id === "src");
  assert.equal(src.desc, "The CLI");
  assert.equal(src.drill, "files:src");
  assert.deepEqual(L.edges.map((e) => [e.from, e.to, e.label]), [
    ["src", "crates/core", "12"], ["in:axum", "src", "HTTP"], ["crates/core", "out:database", "rusqlite"],
  ]);
  assert.equal(L.edges[0].names, "state_dir +3");
});

test("a project with one block still draws it", () => {
  const L = engineLevel({ blocks: [{ name: ".", files: 1, symbols: 3 }], links: [], outside: [] });
  assert.deepEqual(L.nodes.map((n) => [n.id, n.drill]), [[".", null]]);
});

test("level 2 names files inside the block and keeps their docs", () => {
  const L = filesLevel({ blocks: [{ name: "src/app.rs", files: 1, symbols: 9, lines: 40, description: "The app." }], links: [] }, "src");
  assert.deepEqual([L.nodes[0].title, L.nodes[0].desc, L.nodes[0].stats.lines], ["app.rs", "The app.", 40]);
});

test("impact goes up to what a change affects and down to what it relies on", () => {
  const edges = [{ from: "a", to: "b" }, { from: "b", to: "c" }, { from: "c", to: "a" }, { from: "d", to: "b" }];
  assert.deepEqual([...closure(edges, "b", "down")].sort(), ["a", "c"]);
  assert.deepEqual([...closure(edges, "b", "up")].sort(), ["a", "c", "d"]);
  assert.deepEqual([...closure(edges, "b", "up", 1)].sort(), ["a", "d"]);
});

test("link names list the top names and count the rest", () => {
  assert.equal(linkNames({ symbols: [{ name: "a" }, { name: "b" }], other_symbols: 28 }), "a, b +28");
  assert.equal(linkNames({ references: 4 }), "");
});
