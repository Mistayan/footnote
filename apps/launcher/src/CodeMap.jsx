import { useEffect, useRef, useState } from "react";
import "./codemap.css";
import { footnote, num } from "./data.js";
import { closure, engineLevel, filesLevel } from "./layout.js";

// The architecture map by zoom level (#360; the mockup of 22 Nov 2026 approved in chat): the project's blocks, then the
// files of one block. ELK lays it out left to right (callers left of what they call) with orthogonal routes. Selecting a
// box lights what a change to it affects (amber) and what it relies on (teal). Drag pans, the wheel zooms, Fit shows all.
// Cards are HTML in foreignObject so they can wrap a description; the SVG around them is built here, not by React, because
// ELK's coordinates arrive after an async layout and every selection restyles every path.

const NS = "http://www.w3.org/2000/svg";
const WIDTH = { block: 248, file: 236, outside: 224, actor: 204 };
let layoutEngine;
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
const KIND = { block: "Block", file: "File", outside: "Calls out", actor: "Calls in" };
const statsText = (s) => (!s ? "" : s.lines ? `${num(s.lines)} lines` : `${num(s.files)} files · ${num(s.symbols)} symbols`);
const el = (tag, attrs, parent) => {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  parent?.appendChild(e);
  return e;
};

function cardHTML(n, maxLines) {
  const mem = n.memoryCount ? `<span class="mem" title="${n.memoryCount} memories anchored here">${n.memoryCount}</span>`
    : n.drill ? `<span class="c-open">open ↗</span>` : "";
  return `<div xmlns="http://www.w3.org/1999/xhtml" class="card k-${n.kind}" data-id="${esc(n.id)}" tabindex="0" role="button"
      aria-pressed="false" aria-label="${esc(n.title)}${n.drill ? ", can open" : ""}">
    <div class="c-top"><span class="eyebrow">${KIND[n.kind]}</span>${mem}</div>
    <div class="c-title">${esc(n.title)}</div>
    ${n.path && n.path !== n.title ? `<div class="c-path">${esc(n.path)}</div>` : ""}
    ${n.packages ? `<ul class="c-pk">${n.packages.map((p) => `<li><span>${esc(p.name)}</span><span>${num(p.refs)}</span></li>`).join("")}</ul>`
      : n.desc ? `<p class="c-desc">${esc(n.desc)}</p>` : n.kind === "file" ? `<p class="c-desc none">No module doc yet</p>` : ""}
    ${n.stats ? `<div class="c-meta">${statsText(n.stats)}</div>` : ""}
    ${n.stats?.lines ? `<div class="c-bar"><i style="width:${Math.max(4, Math.round((100 * n.stats.lines) / maxLines))}%"></i></div>` : ""}
    ${n.badges?.length ? `<div class="c-badges">${n.badges.map((b) => `<span>${esc(b)}</span>`).join("")}</div>` : ""}
  </div>`;
}

const zoneOf = (engine, n) => (!engine ? null : n.kind === "actor" ? "in" : n.kind === "outside" ? "out" : "code");

const canvas = typeof document !== "undefined" ? document.createElement("canvas").getContext("2d") : null;
function textWidth(t) {
  if (!canvas) return t.length * 7;
  canvas.font = "11px 'JetBrains Mono', monospace";
  return Math.ceil(canvas.measureText(t).width);
}

async function layout(L, engine, measure) {
  const maxLines = Math.max(1, ...L.nodes.map((n) => n.stats?.lines ?? 0));
  measure.innerHTML = L.nodes.map((n) => `<div style="width:${WIDTH[n.kind]}px">${cardHTML(n, maxLines)}</div>`).join("");
  const size = {};
  [...measure.children].forEach((e, i) => {
    size[L.nodes[i].id] = { w: WIDTH[L.nodes[i].kind], h: Math.ceil(e.firstElementChild.getBoundingClientRect().height) };
  });
  measure.innerHTML = "";
  const root = { id: "root", children: [], edges: [], layoutOptions: {
    "elk.algorithm": "layered", "elk.direction": "RIGHT", "elk.edgeRouting": "ORTHOGONAL", "elk.hierarchyHandling": "INCLUDE_CHILDREN",
    "elk.layered.spacing.nodeNodeBetweenLayers": "56", "elk.spacing.nodeNode": "26", "elk.layered.spacing.edgeNodeBetweenLayers": "16",
    "elk.spacing.edgeEdge": "11", "elk.spacing.edgeLabel": "4", "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
    "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES", "elk.padding": "[top=24,left=24,bottom=24,right=24]",
    // Files inside a block are dense: bundle parallel links into shared trunks.
    ...(engine ? {} : { "elk.layered.mergeEdges": "true", "elk.spacing.nodeNode": "20" }) } };
  const parent = {}, holder = { root };
  for (const n of L.nodes) {
    const z = zoneOf(engine, n), child = { id: n.id, width: size[n.id].w, height: size[n.id].h };
    if (!z) { root.children.push(child); parent[n.id] = "root"; continue; }
    const gid = `g:${z}`;
    if (!holder[gid]) {
      holder[gid] = { id: gid, children: [], edges: [], layoutOptions: { "elk.padding": "[top=40,left=17,bottom=17,right=17]" } };
      root.children.push(holder[gid]);
    }
    holder[gid].children.push(child);
    parent[n.id] = gid;
  }
  // One line joins the code zone to "Calls out"; which block uses which package shows on selection.
  if (holder["g:out"] && holder["g:code"]) root.edges.push({ id: "ez", sources: ["g:code"], targets: ["g:out"] });
  const place = {};
  L.edges.forEach((e, i) => {
    if (engine && e.outside) return;
    const c = parent[e.from] === parent[e.to] ? parent[e.from] : "root";
    holder[c].edges.push({ id: `e${i}`, sources: [e.from], targets: [e.to],
      labels: engine && !e.outside ? [{ text: e.label, width: textWidth(e.label) + 14, height: 19 }] : [] });
    place[i] = c;
  });
  layoutEngine ??= import("elkjs/lib/elk.bundled.js").then(({ default: ELK }) => new ELK());
  const out = await (await layoutEngine).layout(root);
  const at = { root: { x: 0, y: 0 } }, groups = [], boxes = {};
  for (const c of out.children) {
    if (c.children) {
      at[c.id] = { x: c.x, y: c.y };
      groups.push(c);
      for (const k of c.children) boxes[k.id] = { x: c.x + k.x, y: c.y + k.y, w: k.width, h: k.height };
    } else boxes[c.id] = { x: c.x, y: c.y, w: c.width, h: c.height };
  }
  const edgeOut = {};
  for (const h of [out, ...out.children]) for (const e of h.edges ?? []) edgeOut[e.id] = e;
  return { boxes, groups, edgeOut, at, place, width: out.width, height: out.height, maxLines };
}

function roundPath(pts, r = 9) {
  let d = `M${pts[0].x},${pts[0].y}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const p = pts[i - 1], c = pts[i], n = pts[i + 1], d1 = Math.hypot(c.x - p.x, c.y - p.y), d2 = Math.hypot(n.x - c.x, n.y - c.y);
    if (!d1 || !d2) continue;
    const rr = Math.min(r, d1 / 2, d2 / 2);
    d += ` L${c.x + ((p.x - c.x) * rr) / d1},${c.y + ((p.y - c.y) * rr) / d1} Q${c.x},${c.y} ${c.x + ((n.x - c.x) * rr) / d2},${c.y + ((n.y - c.y) * rr) / d2}`;
  }
  const l = pts[pts.length - 1];
  return `${d} L${l.x},${l.y}`;
}

/** Draw a laid-out level into `vp`; returns the cards and paths that selection restyles. */
function render(vp, L, G, engine, zoneTitle) {
  vp.innerHTML = "";
  const gGroups = el("g", {}, vp), gEdges = el("g", {}, vp), gFlow = el("g", {}, vp), gLabels = el("g", {}, vp), gNodes = el("g", {}, vp);
  const ZONES = { in: ["Calls in", true], code: [zoneTitle, false], out: ["Calls out", true] };
  for (const g of G.groups) {
    const [title, dashed] = ZONES[g.id.slice(2)];
    const grp = el("g", { class: `grp${dashed ? " dashed" : ""}` }, gGroups);
    el("rect", { x: g.x, y: g.y, width: g.width, height: g.height, rx: 16 }, grp);
    el("text", { x: g.x + 17, y: g.y + 24 }, grp).textContent = title;
  }
  const maxRefs = Math.max(1, ...L.edges.map((e) => e.refs ?? 0));
  const edges = L.edges.map((e, i) => {
    const o = G.edgeOut[`e${i}`], off = G.at[G.place[i]], sec = o?.sections?.[0];
    if (!sec || !off) return null;
    const pts = [sec.startPoint, ...(sec.bendPoints ?? []), sec.endPoint].map((p) => ({ x: p.x + off.x, y: p.y + off.y }));
    const kind = e.boundary ? "boundary" : e.outside ? "outside" : "base";
    const d = roundPath(pts);
    const path = el("path", { d, class: `edge ${kind === "base" ? "" : kind}`, "stroke-width": e.refs ? (1.2 + 3.2 * Math.sqrt(e.refs / maxRefs)).toFixed(2) : 1.5,
      "marker-end": `url(#cm-${kind})` }, gEdges);
    el("title", {}, path).textContent = `${e.from} → ${e.to}${e.refs ? `: ${num(e.refs)} references` : ""}${e.names ? ` (${e.names})` : ""}`;
    let label = null;
    const lo = o.labels?.[0];
    if (lo) {
      label = el("g", { class: `lbl ${kind}` }, gLabels);
      const x = lo.x + off.x, y = lo.y + off.y;
      el("rect", { x, y, width: lo.width, height: lo.height, rx: 9.5 }, label);
      el("text", { x: x + lo.width / 2, y: y + 13, "text-anchor": "middle" }, label).textContent = e.label;
    }
    return { e, kind, d, path, label };
  }).filter(Boolean);
  const ez = G.edgeOut.ez?.sections?.[0];
  if (ez) el("path", { d: roundPath([ez.startPoint, ...(ez.bendPoints ?? []), ez.endPoint]), class: "edge outside", "stroke-width": 1.5, "marker-end": "url(#cm-outside)" }, gEdges);
  const cards = {};
  for (const n of L.nodes) {
    const b = G.boxes[n.id];
    if (!b) continue;
    const fo = el("foreignObject", { x: b.x, y: b.y, width: b.w, height: b.h + 2 }, gNodes);
    fo.innerHTML = cardHTML(n, G.maxLines);
    cards[n.id] = fo.firstElementChild;
  }
  return { cards, edges, flow: gFlow };
}

export default function CodeMap({ root, project }) {
  const stage = useRef(null), vp = useRef(null), measure = useRef(null);
  const drawn = useRef(null);
  const view = useRef({ x: 0, y: 0, k: 1 });
  const [trail, setTrail] = useState(["engine"]);
  const [level, setLevel] = useState({ loading: true });
  const [sel, setSel] = useState(null);
  const at = trail[trail.length - 1];
  const engine = at === "engine";
  const reduced = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;

  const apply = () => {
    const { x, y, k } = view.current;
    vp.current?.setAttribute("transform", `translate(${x},${y}) scale(${k})`);
    if (stage.current) {
      stage.current.style.backgroundSize = `${24 * k}px ${24 * k}px`;
      stage.current.style.backgroundPosition = `${x}px ${y}px`;
    }
  };
  // The whole level, centred below the caption and above the legend.
  const fit = () => {
    const G = level.G, s = stage.current;
    if (!G || !s) return;
    const r = s.getBoundingClientRect(), top = 76, bottom = 64;
    const k = Math.min((r.width - 48) / G.width, (r.height - top - bottom) / G.height, 1.1);
    view.current = { k, x: (r.width - G.width * k) / 2, y: top + (r.height - top - bottom - G.height * k) / 2 };
    apply();
  };
  const zoomAt = (f, px, py) => {
    const v = view.current, k = Math.min(2.5, Math.max(0.25, v.k * f)), r = k / v.k;
    view.current = { k, x: px - (px - v.x) * r, y: py - (py - v.y) * r };
    apply();
  };

  // Read the level, lay it out, draw it.
  useEffect(() => {
    let live = true;
    setLevel((l) => ({ ...l, loading: true }));
    setSel(null);
    const args = engine ? ["code-map", "--root", root] : ["code-map", "--root", root, "--block", at.slice(6)];
    footnote(...args)
      .then(async (data) => {
        const L = engine ? engineLevel(data) : filesLevel(data, at.slice(6));
        await document.fonts?.ready;
        const G = await layout(L, engine, measure.current);
        if (!live) return;
        drawn.current = render(vp.current, L, G, engine, project);
        setLevel({ L, G, data });
      })
      .catch((err) => live && setLevel({ error: String(err) }));
    return () => { live = false; };
  }, [root, at]);

  useEffect(() => { if (level.G) fit(); }, [level.G]);
  useEffect(() => {
    const on = () => level.G && fit();
    addEventListener("resize", on);
    return () => removeEventListener("resize", on);
  });

  // Selection: everything that reaches the box (affected if it changes) and everything it reaches (it relies on). Files
  // inside a block form cycles through hub files, so there it stops at direct neighbours.
  const hops = engine ? Infinity : 1;
  const edges = level.L?.edges ?? [];
  const up = sel ? closure(edges, sel, "up", hops) : new Set();
  const down = sel ? closure(edges, sel, "down", hops) : new Set();
  useEffect(() => {
    const D = drawn.current;
    if (!D || !level.G) return;
    stage.current?.classList.toggle("quiet", !engine && !sel);
    for (const [id, card] of Object.entries(D.cards)) {
      const st = !sel ? "" : id === sel ? "is-sel" : up.has(id) && down.has(id) ? "is-both" : up.has(id) ? "is-up" : down.has(id) ? "is-down" : "is-dim";
      card.className = card.className.replace(/\s?is-\w+/g, "") + (st ? ` ${st}` : "");
      card.setAttribute("aria-pressed", String(id === sel));
    }
    D.flow.innerHTML = "";
    for (const x of D.edges) {
      const inUp = (v) => v === sel || up.has(v), inDown = (v) => v === sel || down.has(v);
      const hot = !sel ? null : hops === 1 ? (x.e.from === sel ? "down" : x.e.to === sel ? "up" : null)
        : inDown(x.e.from) && inDown(x.e.to) ? "down" : inUp(x.e.from) && inUp(x.e.to) ? "up" : null;
      x.path.classList.remove("up", "down", "dim");
      x.label?.classList.remove("dim", "hot");
      if (sel && !hot) { x.path.classList.add("dim"); x.label?.classList.add("dim"); }
      if (hot) {
        x.path.classList.add(hot);
        x.label?.classList.add("hot");
        x.path.setAttribute("marker-end", `url(#cm-${hot})`);
        el("path", { d: x.d, class: "flow" }, D.flow);
      } else x.path.setAttribute("marker-end", `url(#cm-${x.kind})`);
    }
  });

  const go = (to) => setTrail((t) => [...t, to]);
  const upLevel = () => setTrail((t) => (t.length > 1 ? t.slice(0, -1) : t));
  useEffect(() => {
    const key = (e) => {
      if (e.key !== "Escape" || e.target.closest?.("input, select, textarea, [role='listbox']")) return;
      if (sel) { const id = sel; setSel(null); drawn.current?.cards[id]?.focus({ preventScroll: true }); } else upLevel();
    };
    addEventListener("keydown", key);
    return () => removeEventListener("keydown", key);
  });

  // Input: click selects, double-click or Open goes down, drag pans, the wheel zooms.
  const drag = useRef(null);
  const nodeOf = (t) => {
    const c = t.closest?.(".card");
    return c && level.L?.nodes.find((n) => n.id === c.dataset.id);
  };
  useEffect(() => {
    const s = stage.current;
    const wheel = (ev) => {
      ev.preventDefault();
      const r = s.getBoundingClientRect();
      zoomAt(Math.exp(-ev.deltaY * 0.0015), ev.clientX - r.left, ev.clientY - r.top);
    };
    s.addEventListener("wheel", wheel, { passive: false });
    return () => s.removeEventListener("wheel", wheel);
  }, []);
  const center = () => { const r = stage.current.getBoundingClientRect(); return [r.width / 2, r.height / 2]; };

  const L = level.L;
  const node = sel && L?.nodes.find((n) => n.id === sel);
  const edgeTo = (id) => edges.find((x) => (x.from === sel && x.to === id) || (x.to === sel && x.from === id));
  const rows = (ids, color) =>
    ids.length === 0 ? <p className="hint">None.</p> : (
      <ul className="rows">
        {ids.map((id) => {
          const n = L.nodes.find((x) => x.id === id), e = edgeTo(id);
          return (
            <li key={id}>
              <button type="button" onClick={() => { setSel(id); drawn.current?.cards[id]?.focus({ preventScroll: true }); }}>
                <span className="d" style={{ background: color }} />
                <span className="n">
                  {n?.path || n?.title || id}
                  {e?.names && <small>{e.names}</small>}
                </span>
                <span className="v">{e ? (e.refs ? `${num(e.refs)} ref${e.refs === 1 ? "" : "s"}` : "direct") : "via"}</span>
              </button>
            </li>
          );
        })}
      </ul>
    );
  const how = (
    <>
      <h3>How this map was made</h3>
      <ul className="how">
        <li><span className="fn">1</span> Boxes and links: <code>footnote code-map{engine ? "" : ` --block ${at.slice(6)}`}</code> · {level.data?.origin === "compiler" ? "the compiler's index" : "the parser's graph"}</li>
        <li><span className="fn">2</span> Descriptions: {engine ? <>each block&apos;s <code>Cargo.toml</code> or <code>package.json</code></> : <>each file&apos;s leading module doc</>}, as written</li>
        <li><span className="fn">3</span> Layout: ELK layered, callers left of what they call</li>
        <li>No model was called to draw or describe this map.</li>
      </ul>
    </>
  );

  return (
    <div className="cmap">
      <div className="cmap-bar">
        <nav className="crumbs" aria-label="Zoom level">
          {trail.map((t, i) => (
            <span key={t}>
              {i > 0 && <span className="sep" aria-hidden="true">›</span>}
              <button type="button" aria-current={i === trail.length - 1 ? "page" : undefined}
                onClick={() => i < trail.length - 1 && setTrail(trail.slice(0, i + 1))}>
                {t === "engine" ? project : t.slice(6)}
              </button>
            </span>
          ))}
        </nav>
        <div className="levels" aria-hidden="true">
          <span className={engine ? "on" : ""}>1 blocks</span><span className={engine ? "" : "on"}>2 files</span>
        </div>
      </div>
      <div className="cmap-main">
        <div className="stage" ref={stage} aria-label={engine ? "Architecture map" : `Files of ${at.slice(6)}`} role="group"
          onPointerDown={(ev) => {
            if (ev.target.closest(".card, .zoom")) return;
            drag.current = { x: ev.clientX, y: ev.clientY, vx: view.current.x, vy: view.current.y, moved: false };
            ev.currentTarget.setPointerCapture(ev.pointerId);
          }}
          onPointerMove={(ev) => {
            const d = drag.current;
            if (!d) return;
            const dx = ev.clientX - d.x, dy = ev.clientY - d.y;
            if (!d.moved && Math.hypot(dx, dy) < 4) return;
            d.moved = true;
            stage.current.classList.add("panning");
            view.current = { ...view.current, x: d.vx + dx, y: d.vy + dy };
            apply();
          }}
          onPointerUp={() => { if (drag.current && !drag.current.moved) setSel(null); drag.current = null; stage.current.classList.remove("panning"); }}
          onClick={(ev) => { const n = nodeOf(ev.target); if (n) setSel(n.id); }}
          onDoubleClick={(ev) => { const n = nodeOf(ev.target); if (n?.drill) go(n.drill); }}
          onKeyDown={(ev) => {
            const n = nodeOf(ev.target);
            if (!n || (ev.key !== "Enter" && ev.key !== " ")) return;
            ev.preventDefault();
            if (sel === n.id && n.drill && ev.key === "Enter") go(n.drill); else setSel(n.id);
          }}>
          <svg xmlns={NS}>
            <defs>
              {["base", "boundary", "outside", "up", "down"].map((id) => (
                <marker key={id} id={`cm-${id}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto-start-reverse">
                  <path d="M0,1 L9,5 L0,9 z" className={`mk-${id}`} />
                </marker>
              ))}
            </defs>
            <g ref={vp} className={level.loading && !reduced ? "swap" : ""} />
          </svg>
          <div className="overlay caption">
            <b>{engine ? project : at.slice(6)}</b>
            <span>{engine ? "Left to right: who calls whom. Line width is the number of code references."
              : "Files of this block, linked by the code they use from each other. Select one to see its direct links."}</span>
          </div>
          <div className="overlay legend">
            <span><i className="ln" />code reference, width = count</span>
            {engine && <span><i className="ln b" />serves a protocol</span>}
            {engine && <span><i className="ln o" />calls out</span>}
            <span><i className="dot up" />affected if it changes</span>
            <span><i className="dot down" />it relies on</span>
          </div>
          <div className="overlay zoom">
            <button type="button" aria-label="Zoom out" onClick={() => zoomAt(1 / 1.2, ...center())}>−</button>
            <button type="button" aria-label="Zoom in" onClick={() => zoomAt(1.2, ...center())}>+</button>
            <button type="button" onClick={fit}>Fit</button>
          </div>
          {level.loading && <div className="overlay loading">Laying out…</div>}
          {level.error && <div className="overlay loading warn" role="alert">{level.error === "ENGINE_MISSING" ? "The Footnote engine was not found." : level.error}</div>}
        </div>
        <aside className="cmap-panel" aria-label="Details">
          {!L ? null : !node ? (
            <>
              <span className="eyebrow">{engine ? "Level 1 · blocks" : "Level 2 · files"}</span>
              <h2>{engine ? project : at.slice(6)}</h2>
              {engine ? (
                <>
                  <p>{L.nodes.filter((n) => n.kind === "block").length} blocks of code and what they call out to.</p>
                  {L.hidden.length > 0 && (
                    <p className="hint">{L.hidden.length} more blocks link to nothing here and are left out: {L.hidden.slice(0, 12).map((h) => <span key={h} className="chip">{h}</span>)}{L.hidden.length > 12 ? " …" : ""}</p>
                  )}
                </>
              ) : (
                <p>{L.nodes.length} files of <code>{at.slice(6)}</code>. {L.nodes.filter((n) => !n.desc).length} have no module doc yet.</p>
              )}
              <h3>Try</h3>
              <p className="hint">Select a box to light up what it reaches. Double-click a box marked <span className="c-open">open ↗</span>, or use its Open button, to go one level down. Esc goes back up.</p>
              {how}
            </>
          ) : (
            <>
              <span className="eyebrow">{KIND[node.kind]}</span>
              <h2>{node.title}</h2>
              {node.path && node.path !== node.title && <div className="path">{node.path}</div>}
              {node.desc ? (
                <>
                  <p>{node.desc}<span className="fn">2</span></p>
                  {node.descSource && <div className="src">from <code>{node.descSource}</code></div>}
                </>
              ) : node.kind === "file" ? (
                <p className="hint">No module doc. A one-line doc at the top of the file would describe this box without any model.</p>
              ) : null}
              {node.stats && (
                <div className="stats">{Object.entries(node.stats).map(([k, v]) => <div key={k}>{num(v)}<small>{k}</small></div>)}</div>
              )}
              {node.drill && <button type="button" className="primary" onClick={() => go(node.drill)}>Open its files ↗</button>}
              {node.memories?.length > 0 && (
                <>
                  <h3>Memories anchored here · {node.memoryCount}</h3>
                  {node.memories.map((m) => (
                    <div key={m.id} className="memo"><b>#{m.id} · {m.kind} · {m.observed_at}</b><span>{m.text}</span></div>
                  ))}
                </>
              )}
              {node.packages && (
                <>
                  <h3>Packages</h3>
                  <ul className="rows">
                    {node.packages.map((k) => (
                      <li key={k.name}><span className="pk"><span className="n">{k.name} <span className="v">{k.version}</span></span><span className="v">{num(k.refs)} refs</span></span></li>
                    ))}
                  </ul>
                </>
              )}
              <h3>Affected if it changes · {up.size}</h3>
              {rows([...up], "var(--warn)")}
              <h3>It relies on · {down.size}</h3>
              {rows([...down], "var(--acc)")}
              {how}
            </>
          )}
        </aside>
      </div>
      <div ref={measure} className="cmap-measure" aria-hidden="true" />
      <div className="sr-only" aria-live="polite">{node ? `${node.title} selected. ${up.size} affected if it changes, relies on ${down.size}.` : ""}</div>
    </div>
  );
}
