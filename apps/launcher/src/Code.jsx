import { useEffect, useState } from "react";
import { footnote, num } from "./data.js";
import CodeMap from "./CodeMap.jsx";
import { Select, Tabs } from "./ui.jsx";
import { Boxes, ChevronLeft, ChevronRight, FileCode2, FolderGit2, GitFork, Waypoints } from "lucide-react";

// Code, by zoom level (DESIGN.md section 11): the architecture map of a project and its blocks' files (CodeMap.jsx), then
// one symbol's callers and callees.
// Never the whole graph at once.
export default function Code({ projects, view, go }) {
  const graphs = (projects?.projects ?? []).filter((p) => p.code_graph && p.exists);
  const [root, setRoot] = useState(null);
  // With several graphs the screen opens on all of them; one graph opens straight on its map.
  const project = graphs.find((p) => p.path === root) ?? (graphs.length === 1 ? graphs[0] : null);

  if (!projects) return <div className="body"><span className="skel" /></div>;
  if (graphs.length > 1 && !project) return <Graphs graphs={graphs} open={setRoot} />;
  if (!project)
    return (
      <div className="body">
        <p className="empty">
          No code graph yet. In a project folder, run <code>footnote code-index</code>; its map and symbols then show here.
        </p>
      </div>
    );
  return (
    <div className="body">
      <div className="bar">
        {graphs.length > 1 && (
          <button type="button" className="btn back-btn" onClick={() => setRoot(null)}><ChevronLeft size={14} strokeWidth={2} /> All graphs</button>
        )}
        {graphs.length > 1 ? (
          <Select value={project.path} options={graphs.map((p) => ({ value: p.path, label: p.name }))} onChange={setRoot}
            label="Project" icon={FolderGit2} />
        ) : (
          <b>{project.name}</b>
        )}
        <Tabs value={view} options={[["map", "Architecture"], ["layers", "Layers"], ["symbol", "Symbol"]]} onChange={go} label="Code view" />
      </div>
      {view === "symbol" ? <Symbol root={project.path} key={project.path} /> : view === "layers" ? <Layers root={project.path} key={project.path} /> : <CodeMap root={project.path} project={project.name} key={project.path} />}
    </div>
  );
}

/** Every registered code graph as a card with its size; a card opens that project's map. */
function Graphs({ graphs, open }) {
  return (
    <div className="body">
      <div className="graph-grid">
        {graphs.map((p, i) => <GraphCard key={p.path} p={p} i={i} open={() => open(p.path)} />)}
      </div>
    </div>
  );
}

// The rim light follows a fine pointer in the card's own coordinates (design-bank "bordure éclairée").
const spot = (e) => {
  const r = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty("--x", `${e.clientX - r.left}px`);
  e.currentTarget.style.setProperty("--y", `${e.clientY - r.top}px`);
};

function GraphCard({ p, i, open }) {
  const { data, error } = useRead(["code-map", "--root", p.path]);
  const blocks = data?.blocks.filter((b) => b.symbols > 0) ?? [];
  const sum = (k) => blocks.reduce((n, b) => n + (b[k] ?? 0), 0);
  const kpis = [
    [Boxes, "blocks", blocks.length],
    [FileCode2, "files", sum("files")],
    [GitFork, "symbols", sum("symbols")],
    [Waypoints, "links", data?.links.length ?? 0],
  ];
  return (
    <button type="button" className="graph-card surface sq" style={{ "--i": i }} onClick={open} onPointerMove={spot}
      aria-label={`Open the code map of ${p.name}`}>
      <span className="gc-head">
        <span className="gc-glyph" aria-hidden="true"><FolderGit2 size={16} strokeWidth={1.9} /></span>
        <span className="gc-id">
          <b>{p.name}</b>
          <span className="path mono" title={p.path}>{p.path}</span>
        </span>
        <ChevronRight className="gc-go" size={16} strokeWidth={2} aria-hidden="true" />
      </span>
      {error ? <span className="warn small">{clipErr(error)}</span> : (
          <span className="gc-kpis">
            {kpis.map(([Icon, label, v]) => (
              <span key={label}>
                <b>{data ? num(v) : "–"}</b>
                <small><Icon size={12} strokeWidth={1.9} aria-hidden="true" />{label}</small>
              </span>
            ))}
          </span>
      )}
    </button>
  );
}

const clipErr = (e) => (e === "ENGINE_MISSING" ? "Engine not found" : String(e).slice(0, 80));

function useRead(args) {
  const [state, setState] = useState({});
  const key = args?.join(" ");
  useEffect(() => {
    if (!args) return;
    let live = true;
    setState({ loading: true });
    footnote(...args).then(
      (data) => live && setState({ data }),
      (error) => live && setState({ error: String(error) }),
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}

// What the project calls out to, grouped by kind (DESIGN.md section 11, blueprint map of 17 Nov 2026). `server` and `mcp`
// packages mean the project is called in, so they sit on the "calls in" side.
const KINDS = [
  ["database", "Databases"],
  ["model", "Model runtimes"],
  ["network", "Network and APIs"],
  ["system", "Files and system"],
];

const short = (n) => n.split("/").pop();

/** Layers (the Strata direction, 17 Nov 2026): the same map read top to bottom. Entry blocks (nothing calls them), base blocks
 *  (they call no other block), features between, then the outside packages by kind. Under each layer, its links down. */
function Layers({ root }) {
  const { data, error, loading } = useRead(["code-map", "--root", root]);
  if (error) return <Failed error={error} />;
  if (loading || !data) return <span className="skel" />;
  const blocks = data.blocks.filter((b) => b.symbols > 0);
  const links = data.links.filter((l) => blocks.some((b) => b.name === l.from) && blocks.some((b) => b.name === l.to));
  const calls = (b) => links.some((l) => l.from === b.name);
  const entry = blocks.filter((b) => b.entry);
  const base = blocks.filter((b) => !b.entry && !calls(b));
  const features = blocks.filter((b) => !entry.includes(b) && !base.includes(b));
  const max = Math.max(1, ...links.map((l) => l.references));
  const strata = [
    ["Entry", "Where a run starts: nothing else in the project calls these.", entry],
    ["Features", "What the project does.", features],
    ["Base", "Shared by everything: calls no other block.", base],
  ].filter(([, , list]) => list.length);
  const down = (list) => links.filter((l) => list.some((b) => b.name === l.from)).sort((a, b) => b.references - a.references);
  const kinds = KINDS.map(([k, label]) => [label, data.outside.filter((o) => o.class === k)]).filter(([, l]) => l.length);
  return (
    <div className="layers">
      {strata.map(([title, note, list]) => (
        <section key={title} className="stratum" aria-label={title}>
          <div><h2 className="title">{title}</h2><p className="dimmed">{note}</p></div>
          <div className="cells">
            {list.map((b) => (
              <div key={b.name} className="cell">
                <b className="mono">{b.name}</b>
                <span className="dimmed">{num(b.symbols)} symbols · {num(b.files)} files</span>
                {b.memories?.count > 0 && <span className="mems">{b.memories.count === 1 ? "1 memory" : `${b.memories.count} memories`}</span>}
              </div>
            ))}
          </div>
          {down(list).length > 0 && (
            <ul className="down">
              {down(list).map((l) => (
                <li key={l.from + l.to} className={l.references / max > 0.5 ? "heavy" : ""}>
                  {short(l.from)} → <b>{short(l.to)}</b> {num(l.references)}
                  <i style={{ width: Math.max(4, 90 * (l.references / max)) }} />
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
      {kinds.length > 0 && (
        <section className="stratum" aria-label="Outside">
          <div><h2 className="title">Outside</h2><p className="dimmed">Services and runtimes the project calls out to.</p></div>
          <div className="cells">
            {kinds.flatMap(([label, list]) => list.map((o) => (
              <div key={o.package} className="cell">
                <b className="mono">{o.package}</b>
                <span className="dimmed">{label.toLowerCase()} · {num(o.references)} refs · {o.used_by.map(short).join(", ")}</span>
              </div>
            )))}
          </div>
        </section>
      )}
      <p className="dimmed">Read top to bottom: each layer calls the ones below it. The longest bars are the heaviest links.</p>
    </div>
  );
}

function Symbol({ root }) {
  const [name, setName] = useState("");
  const [asked, setAsked] = useState(null);
  const { data, error, loading } = useRead(asked && ["code", asked, "--root", root]);
  const [i, setI] = useState(0);
  const [side, setSide] = useState("both");
  const found = data?.symbols ?? [];
  const s = found[Math.min(i, found.length - 1)];
  return (
    <div className="split">
      <div className="map">
        <form className="ask" onSubmit={(e) => { e.preventDefault(); const n = name.trim(); if (n) { setI(0); setAsked(n); } }}>
          <label htmlFor="sym" className="sr-only">Symbol name</label>
          <input id="sym" className="input mono" placeholder="A function or type, e.g. lookup" value={name}
            onChange={(e) => setName(e.target.value)} autoComplete="off" spellCheck="false" />
          <button className="btn" type="submit" disabled={!name.trim()}>Find</button>
        </form>
        {error ? <Failed error={error} /> : loading ? <span className="skel" /> : !asked ? (
          <p className="dimmed">Type an exact name. Footnote shows where it is defined, who calls it and what it calls.</p>
        ) : !s ? (
          <p className="empty">Nothing named <code>{asked}</code> in this project&apos;s graph.</p>
        ) : (
          <>
            <Tabs value={side} options={SIDES} onChange={setSide} label="Which side" />
            {side === "up" ? <Radius s={s} root={root} key={s.name} /> : <Ego s={side === "down" ? { ...s, callers: [] } : s} />}
          </>
        )}
      </div>
      <aside className="panel">
        {s && (
          <>
            {found.length > 1 && (
              <span className="dimmed bar">
                {found.length} definitions
                <Select value={i} options={found.map((f, k) => ({ value: k, label: `${f.path}:${f.lines[0]}` }))} onChange={setI}
                  label="Definition" />
              </span>
            )}
            <h2 className="title mono">{s.name}</h2>
            <p className="mono sig">{s.signature || s.kind}</p>
            <p className="mono dimmed">{s.path}:{s.lines[0]}–{s.lines[1]}</p>
            {data.stale?.length > 0 && (
              <p className="warn">Changed since indexing: {data.stale.join(", ")}. Run <code>footnote code-index</code>.</p>
            )}
            <Places label={`Called by · ${s.callers.length}`} items={s.callers} />
            <Places label={`Calls · ${s.callees.length} in project`} items={s.callees} />
          </>
        )}
      </aside>
    </div>
  );
}

function Places({ label, items }) {
  return (
    <>
      <h3 className="section">{label}</h3>
      {items.length === 0 ? <p className="dimmed">None.</p> : (
        <ul className="plain">
          {items.map((c) => (
            <li key={c.name + c.path} className="place">
              <span>{c.name}</span>
              <span className="mono dimmed">{c.path}:{c.lines[0]}</span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

const SIDES = [["both", "Both sides"], ["up", "Affected if it changes"], ["down", "It relies on"]];

/** The blast radius upstream (#360): callers by level from `code-impact`, the farthest on the left, the symbol on the right.
 *  The index records levels, not which caller calls which, so one arrow joins each pair of columns. */
function Radius({ s, root }) {
  const { data, error, loading } = useRead(["code-impact", s.name, "--root", root]);
  if (error) return <Failed error={error} />;
  if (loading || !data) return <span className="skel" />;
  const levels = [...new Set(data.callers.map((c) => c.level))].sort((a, b) => b - a);
  if (!levels.length) return <p className="dimmed">Nothing in the project calls <code>{s.name}</code>, so a change stays inside it.</p>;
  const show = 7, cw = 176, gx = 56, rowH = 44, top = 34;
  const cols = [...levels.map((l) => data.callers.filter((c) => c.level === l)), null];
  const tall = Math.max(...cols.map((c) => (c ? Math.min(show, c.length) + (c.length > show ? 1 : 0) : 1)));
  const H = top + tall * rowH + 8, W = cols.length * (cw + gx) - gx;
  const mid = top + (tall * rowH) / 2;
  return (
    <figure className="ego">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }} role="img"
        aria-label={`${s.name}: ${data.counts.callers} callers over ${levels.length} levels, ${data.counts.tests} tests`}>
        <defs>
          <marker id="arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" orient="auto">
            <path d="M0 0 L8 4 L0 8 z" className="arrowhead" />
          </marker>
        </defs>
        {cols.map((list, i) => {
          const x = i * (cw + gx);
          const items = list ? list.slice(0, show) : [{ name: s.name }];
          const y0 = mid - (Math.min(show, items.length + (list?.length > show ? 1 : 0)) * rowH) / 2;
          return (
            <g key={i}>
              <text x={x} y={14} className="zone-t">{list ? `Level ${levels[i]} · ${list.length}` : "The symbol"}</text>
              {i < cols.length - 1 && <path className="link on" markerEnd="url(#arrow)" d={`M${x + cw + 6} ${mid} L${x + cw + gx - 6} ${mid}`} />}
              {items.map((c, k) => (
                <g key={c.name + (c.path ?? "") + k} className={list ? "block" : "block on"}>
                  <rect x={x} y={y0 + k * rowH} width={cw} height={36} rx="8" />
                  <text x={x + 12} y={y0 + k * rowH + 23}>{c.name.length > 19 ? c.name.slice(0, 18) + "…" : c.name}
                    <title>{c.path ? `${c.name} · ${c.path}:${c.line}` : c.name}</title></text>
                </g>
              ))}
              {list?.length > show && <text x={x + 12} y={y0 + show * rowH + 20} className="link-t">+ {list.length - show} more</text>}
            </g>
          );
        })}
      </svg>
      <figcaption className="dimmed">
        A change to <code>{s.name}</code> reaches {num(data.counts.callers)} callers and {num(data.counts.tests)} tests in{" "}
        {num(data.counts.files)} files, up to {data.depth} levels. Arrows point from callers to what they call.
      </figcaption>
    </figure>
  );
}

/** Callers on the left, the symbol in the middle, callees on the right. */
function Ego({ s }) {
  const W = 760, rowH = 52, show = 8;
  const left = s.callers.slice(0, show), right = s.callees.slice(0, show);
  const H = Math.max(3, left.length, right.length) * rowH + 32;
  const ys = (n) => Array.from({ length: n }, (_, k) => H / 2 + (k - (n - 1) / 2) * rowH);
  const box = (x, y, label, cls, key) => (
    <g key={key} className={cls}>
      <rect x={x} y={y - 18} width="170" height="36" rx="8" />
      <text x={x + 12} y={y + 5}>{label.length > 20 ? label.slice(0, 19) + "…" : label}<title>{label}</title></text>
    </g>
  );
  return (
    <figure className="ego">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W }} role="img"
        aria-label={`${s.name}: ${s.callers.length} callers, ${s.callees.length} callees`}>
        {ys(left.length).map((y, k) => <path key={"l" + k} className="link on" d={`M190 ${y} C260 ${y}, 240 ${H / 2}, 295 ${H / 2}`} />)}
        {ys(right.length).map((y, k) => <path key={"r" + k} className="link on" d={`M465 ${H / 2} C520 ${H / 2}, 500 ${y}, 570 ${y}`} />)}
        {left.map((c, k) => box(20, ys(left.length)[k], c.name, "block", "lb" + k))}
        {box(295, H / 2, s.name, "block on", "me")}
        {right.map((c, k) => box(570, ys(right.length)[k], c.name, "block", "rb" + k))}
      </svg>
      {(s.callers.length > show || s.callees.length > show) && (
        <figcaption className="dimmed">Showing the first {show} on each side; the full lists are on the right.</figcaption>
      )}
    </figure>
  );
}

function Failed({ error }) {
  return <p className="empty warn" role="alert">{error === "ENGINE_MISSING" ? "The Footnote engine was not found." : error}</p>;
}
