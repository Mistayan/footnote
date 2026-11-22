import { useEffect, useRef, useState } from "react";
import { Bot, Brain, ChevronLeft, ChevronRight, Coins, GitCommitHorizontal, Library as LibraryIcon, Maximize2, Minus, X } from "lucide-react";
import { emitTo } from "@tauri-apps/api/event";
import { AGENTS, footnote, inApp, num } from "./data.js";

// Mini window (DESIGN.md section 11, reworked 22 Nov 2026): the tray's quick look. One squircle widget, no OS frame; a
// slider of single-KPI cards (Memory, today's usage, work to commit, agents, Library and Code). Its own controls: minimize,
// open the full window, close (to the tray). Anything to act on opens the full window.

/** Swap between the full window and mini mode. Outside the app (screenshots), the page just changes route. */
export async function switchTo(target, route = "overview") {
  if (!inApp) {
    const q = location.hash.includes("?") ? "?" + location.hash.split("?")[1] : "";
    location.hash = `/${target === "mini" ? "mini" : route}${q}`;
    return;
  }
  const { Window, getCurrentWindow } = await import("@tauri-apps/api/window");
  const other = await Window.getByLabel(target === "mini" ? "mini" : "main");
  if (target !== "mini") await emitTo("main", "footnote-go", route).catch(() => {});
  await other?.unminimize().catch(() => {});
  await other?.show();
  await other?.setFocus();
  await getCurrentWindow().hide();
}

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const tokens = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)}B` : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : num(n));
const sumTokens = (t) => (t ? (t.input ?? 0) + (t.output ?? 0) + (t.cache_read ?? 0) + (t.cache_write_5m ?? 0) + (t.cache_write_1h ?? 0) : 0);
const KEY = "footnote.mini.slide";
const readSlide = () => {
  try { return Number(localStorage.getItem(KEY)) || 0; } catch { return 0; }
};

function useEngine(args, every) {
  const [v, setV] = useState({});
  const key = args.join(" ");
  useEffect(() => {
    let live = true;
    const read = () => footnote(...args).then((data) => live && setV({ data }), (error) => live && setV({ error: String(error) }));
    read();
    const t = setInterval(read, every);
    return () => { live = false; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, every]);
  return v;
}

export default function Mini() {
  const status = useEngine(["status"], 30_000);
  const usage = useEngine(["usage", "--days", "1"], 60_000);
  const projects = useEngine(["projects"], 60_000);
  const track = useRef(null);
  const [at, setAt] = useState(readSlide);

  const p = status.data?.products;
  const memory = p?.memory;
  const agents = memory?.agents ?? [];
  const broken = agents.filter((a) => !a.hooks || !a.mcp_server);
  const dirty = (projects.data?.projects ?? []).filter((x) => x.git?.uncommitted > 0);
  const t = usage.data?.totals;

  const slides = [
    { id: "memory", Icon: Brain, label: "Memory", go: "memory", open: "Memory",
      big: memory ? num(memory.memories) : "–",
      sub: memory ? `${num(memory.saved_last_7_days)} saved · ${num(memory.recalls_last_7_days)} recalls this week` : "" },
    { id: "usage", Icon: Coins, label: "Today", go: "usage", open: "Usage",
      big: t ? tokens(sumTokens(t)) : "–",
      sub: t ? `${usd.format(t.api_price_usd ?? 0)} at list prices · ${num(t.requests)} requests` : "" },
    { id: "commit", Icon: GitCommitHorizontal, label: "To commit", go: "projects", open: "Projects", tone: dirty.length ? "bad" : "ok",
      big: projects.data ? (dirty.length ? num(dirty.length) : "None") : "–",
      sub: dirty.length ? dirty.slice(0, 3).map((x) => `${x.name} ${x.git.uncommitted}`).join(" · ") : "Every project is committed" },
    { id: "agents", Icon: Bot, label: "Agents", go: "overview", open: "Overview", tone: broken.length ? "warn" : "ok",
      big: agents.length ? `${agents.length - broken.length}/${agents.length}` : "–",
      sub: broken.length ? `Needs repair: ${broken.map((a) => AGENTS[a.agent] ?? a.agent).join(", ")}` : "Hooks and MCP connected" },
    { id: "library", Icon: LibraryIcon, label: "Library · Code", go: "library", open: "Library",
      big: p ? `${p.library?.built && p.library.enabled !== false ? "On" : "Off"} · ${num(p.code?.graphs ?? 0)}` : "–",
      sub: p ? `Docs search ${p.library?.enabled === false ? "off" : "on"} · ${num(p.code?.graphs ?? 0)} code graphs` : "" },
  ];
  const n = slides.length;

  const to = (i, smooth = true) => {
    const k = ((i % n) + n) % n;
    setAt(k);
    try { localStorage.setItem(KEY, String(k)); } catch { /* the slide is a convenience */ }
    track.current?.scrollTo({ left: k * track.current.clientWidth, behavior: smooth ? "smooth" : "instant" });
  };
  useEffect(() => { to(at, false); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const onScroll = (e) => {
    const k = Math.round(e.currentTarget.scrollLeft / e.currentTarget.clientWidth);
    if (k !== at) {
      setAt(k);
      try { localStorage.setItem(KEY, String(k)); } catch { /* convenience */ }
    }
  };
  const win = async (what) => {
    if (!inApp) return what === "full" && switchTo("main");
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    const w = getCurrentWindow();
    if (what === "min") w.minimize();
    else if (what === "close") w.hide();
    else switchTo("main");
  };

  return (
    <div className="mw" onKeyDown={(e) => {
      if (e.key === "ArrowRight") to(at + 1);
      else if (e.key === "ArrowLeft") to(at - 1);
    }}>
      <header className="mw-top" data-tauri-drag-region>
        <span className="lens" aria-hidden="true">1</span>
        <span className="mw-title" data-tauri-drag-region>Footnote</span>
        {status.error && <span className="warn small">{status.error === "ENGINE_MISSING" ? "Engine not found" : "Engine error"}</span>}
        <span className="mw-ctl">
          <button type="button" className="mw-btn" onClick={() => win("min")} aria-label="Minimize" title="Minimize"><Minus size={13} strokeWidth={2} /></button>
          <button type="button" className="mw-btn" onClick={() => win("full")} aria-label="Open the full window" title="Open the full window"><Maximize2 size={12} strokeWidth={2} /></button>
          <button type="button" className="mw-btn close" onClick={() => win("close")} aria-label="Close to the tray" title="Close to the tray"><X size={13} strokeWidth={2} /></button>
        </span>
      </header>
      <div className="mw-track" ref={track} onScroll={onScroll} role="region" aria-roledescription="carousel" aria-label="Quick look">
        {slides.map((s, i) => (
          <section key={s.id} className={`mw-card${s.tone ? ` ${s.tone}` : ""}`} aria-roledescription="slide"
            aria-label={`${i + 1} of ${n}: ${s.label}`} aria-hidden={i !== at}>
            <span className="mw-kicker"><span className="mw-ic"><s.Icon size={13} strokeWidth={2} /></span>{s.label}</span>
            <b className="mw-big">{s.big}</b>
            <span className="mw-sub">{s.sub}</span>
            <button type="button" className="mw-open" tabIndex={i === at ? 0 : -1} onClick={() => switchTo("main", s.go)}>
              Open {s.open}
              <ChevronRight size={12} strokeWidth={2} />
            </button>
          </section>
        ))}
      </div>
      <footer className="mw-foot">
        <button type="button" className="mw-btn" onClick={() => to(at - 1)} aria-label="Previous"><ChevronLeft size={14} strokeWidth={2} /></button>
        <span className="mw-dots" role="tablist" aria-label="Cards">
          {slides.map((s, i) => (
            <button key={s.id} type="button" role="tab" aria-selected={i === at} aria-label={s.label} onClick={() => to(i)} />
          ))}
        </span>
        <button type="button" className="mw-btn" onClick={() => to(at + 1)} aria-label="Next"><ChevronRight size={14} strokeWidth={2} /></button>
      </footer>
    </div>
  );
}
