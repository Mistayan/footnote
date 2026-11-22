// Data for the architecture map (CodeMap.jsx, #360): `footnote code-map` output turned into the boxes and links of one
// zoom level, and the impact of a selection. Pure functions, so they are tested without a browser.

const KINDS = { database: "Databases", model: "Model runtimes", network: "Network and APIs", system: "Files and system" };
// `server` and `mcp` packages mean the project is called in, so they sit on the "calls in" side.
const INBOUND = { server: ["Serves HTTP", "HTTP"], mcp: ["Serves MCP", "MCP"] };

/** The names a link uses most, as one line: `state_dir, product_settings, ensure_private_dir +28`. */
export function linkNames(l) {
  const s = (l.symbols ?? []).map((x) => x.name).join(", ");
  return s && l.other_symbols ? `${s} +${l.other_symbols}` : s;
}

const last = (p) => p.split("/").pop();
const edge = (l) => ({ from: l.from, to: l.to, refs: l.references, label: `${l.references}`, names: linkNames(l) });

/** Level 1: the project's blocks that link to another block (the rest are listed, not drawn), what calls in, and what they
 *  call out to, grouped by kind. */
export function engineLevel(map) {
  // Tests, benchmarks and examples call the product, nothing calls them: listed, not drawn, as in the approved mockup.
  const aside = (n) => /^(tests?|benches|bench|examples?|e2e|fixtures)(\/|$)/.test(n);
  const linked = new Set(map.links.flatMap((l) => (l.from === l.to || aside(l.from) || aside(l.to) ? [] : [l.from, l.to])));
  const real = map.blocks.filter((b) => b.symbols > 0);
  const shown = linked.size ? real.filter((b) => linked.has(b.name)) : real;
  const ids = new Set(shown.map((b) => b.name));
  const pkgs = (b) => map.outside.filter((o) => o.used_by.includes(b) && o.class && !INBOUND[o.class] && o.class !== "standard library")
    .slice(0, 3).map((o) => o.package);
  const nodes = shown.map((b) => ({
    id: b.name, kind: "block", title: last(b.name), path: b.name, desc: b.description ?? null, descSource: b.described_in ?? null,
    stats: { files: b.files, symbols: b.symbols }, badges: pkgs(b.name), memories: b.memories?.recent ?? [],
    memoryCount: b.memories?.count ?? 0, drill: b.files > 1 && b.name !== "." ? `files:${b.name}` : null,
  }));
  const edges = map.links.filter((l) => l.from !== l.to && ids.has(l.from) && ids.has(l.to)).map(edge);
  for (const o of map.outside.filter((x) => INBOUND[x.class])) {
    const users = o.used_by.filter((u) => ids.has(u));
    if (!users.length) continue;
    const id = `in:${o.package}`;
    nodes.unshift({ id, kind: "actor", title: o.package, desc: INBOUND[o.class][0] });
    for (const u of users) edges.push({ from: id, to: u, label: INBOUND[o.class][1], boundary: true });
  }
  for (const [cls, title] of Object.entries(KINDS)) {
    // One row per package, even when two versions of it are in the lock file.
    const pk = map.outside.filter((o, i, all) => o.class === cls && o.used_by.some((u) => ids.has(u))
      && all.findIndex((x) => x.package === o.package && x.class === cls) === i);
    if (!pk.length) continue;
    const id = `out:${cls}`;
    nodes.push({ id, kind: "outside", title, packages: pk.slice(0, 4).map((o) => ({ name: o.package, refs: o.references, version: o.version })) });
    for (const u of new Set(pk.flatMap((o) => o.used_by.filter((x) => ids.has(x))))) {
      edges.push({ from: u, to: id, outside: true, label: pk.filter((o) => o.used_by.includes(u)).map((o) => o.package).join(", ") });
    }
  }
  return { nodes, edges, hidden: real.filter((b) => !ids.has(b.name)).map((b) => b.name) };
}

/** Level 2: the files of one block (`code-map --block`), each with its leading doc and size. */
export function filesLevel(map, block) {
  const nodes = map.blocks.map((b) => ({
    id: b.name, kind: "file", title: b.name.startsWith(block + "/") ? b.name.slice(block.length + 1) : b.name, path: b.name,
    desc: b.description ?? null, descSource: b.description ? "its leading module doc" : null, stats: { lines: b.lines ?? 0 },
    memories: b.memories?.recent ?? [], memoryCount: b.memories?.count ?? 0,
  }));
  return { nodes, edges: map.links.filter((l) => l.from !== l.to).map(edge), hidden: [] };
}

/** Everything `id` reaches going down links ("down": what it relies on) or up them ("up": what a change to it affects),
 *  at most `hops` links away. */
export function closure(edges, id, dir, hops = Infinity) {
  const seen = new Set();
  let frontier = [id];
  for (let h = 0; h < hops && frontier.length; h++) {
    const next = [];
    for (const c of frontier) {
      for (const e of edges) {
        const [a, b] = dir === "up" ? [e.to, e.from] : [e.from, e.to];
        if (a === c && b !== id && !seen.has(b)) { seen.add(b); next.push(b); }
      }
    }
    frontier = next;
  }
  return seen;
}
