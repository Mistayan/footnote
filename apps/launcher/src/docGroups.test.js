// npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { UNUSED, groupDocs } from "./docGroups.js";

const doc = (site, ecosystem, used_by, state = "ready") => ({ site, ecosystem, used_by, state });

test("doc sites group by language, unused last, embedding first inside a group", () => {
  const groups = groupDocs([
    doc("numpy", "pypi", ["data"]),
    doc("pandas", "pypi", ["data", "lab"]),
    doc("python", "pypi", ["data"], "embedding"),
    doc("docsrs-numpy", "cargo", []),
    doc("pyo3-guide", "cargo", ["tool"]),
    doc("duckdb", null, []),
  ]);
  assert.deepEqual(groups.map((g) => g.name), ["Python", "Rust", UNUSED]);
  assert.deepEqual(groups[0].docs.map((d) => d.site), ["python", "pandas", "numpy"]);
  assert.deepEqual(groups.at(-1).docs.map((d) => d.site), ["docsrs-numpy", "duckdb"]);
});

test("without usage data the list stays one ungrouped list", () => {
  const groups = groupDocs([{ site: "b", state: "ready" }, { site: "a", state: "ready" }]);
  assert.deepEqual(groups, [{ name: null, docs: [{ site: "a", state: "ready" }, { site: "b", state: "ready" }] }]);
});
