// Layered layout for the architecture map: a block sits one row below the lowest block that uses it, so callers are above
// what they call (src above crates/search above crates/core). Cycles are cut by a bound on the passes.

/** Row of each block: 0 for blocks nothing uses, then one more than the deepest user. */
export function ranks(blocks, links) {
  const rank = Object.fromEntries(blocks.map((b) => [b, 0]));
  // Drop the links that close a cycle (DFS back edges), else ranks climb around the loop to the cap.
  const out = {};
  for (const l of links) if (l.from in rank && l.to in rank && l.from !== l.to) (out[l.from] ??= []).push(l);
  const state = {}, acyclic = [];
  const visit = (n) => {
    state[n] = 1;
    for (const l of out[n] ?? []) {
      if (state[l.to] === 1) continue;
      acyclic.push(l);
      if (!state[l.to]) visit(l.to);
    }
    state[n] = 2;
  };
  for (const b of blocks) if (!state[b]) visit(b);
  for (let pass = 0; pass < blocks.length; pass++) {
    let moved = false;
    for (const { from, to } of acyclic) {
      if (from in rank && to in rank && rank[to] < rank[from] + 1 && rank[from] + 1 < blocks.length) {
        rank[to] = rank[from] + 1;
        moved = true;
      }
    }
    if (!moved) break;
  }
  return rank;
}

/** Box positions: rows by rank, boxes centred in their row. The drawing is at least `minWidth` wide, wider if a row needs it. */
export function place(blocks, links, minWidth, box = { w: 168, h: 56, gapX: 28, gapY: 72 }) {
  const rank = ranks(blocks.map((b) => b.name), links);
  const sparse = [];
  for (const b of blocks) (sparse[rank[b.name]] ??= []).push(b);
  // No empty rows (`.map` skips holes, which made the width NaN), and a long rank wraps so the map stays readable.
  const perRow = Math.max(1, Math.floor((minWidth - 32 + box.gapX) / (box.w + box.gapX)));
  const rows = sparse.filter(Boolean).flatMap((r) => Array.from({ length: Math.ceil(r.length / perRow) }, (_, i) => r.slice(i * perRow, (i + 1) * perRow)));
  const widest = Math.max(0, ...rows.map((r) => r.length * box.w + (r.length - 1) * box.gapX));
  const width = Math.max(minWidth, widest + 32);
  const pos = {};
  rows.forEach((row, r) => {
    const total = row.length * box.w + (row.length - 1) * box.gapX;
    row.forEach((b, i) => {
      pos[b.name] = { x: (width - total) / 2 + i * (box.w + box.gapX), y: 16 + r * (box.h + box.gapY), ...box };
    });
  });
  const height = 16 + rows.length * (box.h + box.gapY) - box.gapY + 16;
  return { pos, height, width };
}
