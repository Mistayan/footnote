import { useCallback, useEffect, useRef, useState } from "react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import {
  Activity as ActivityIcon,
  BarChart3,
  BookOpen,
  Brain,
  Building2,
  Check,
  Copy,
  Cpu,
  FolderGit2,
  GitFork,
  LayoutDashboard,
  Minimize2,
  Minus,
  Palette,
  Plug,
  RefreshCw,
  Search as SearchIcon,
  Sparkles,
  Square,
  Webhook,
  X,
} from "lucide-react";
import Code from "./Code.jsx";
import Library from "./Library.jsx";
import Memory from "./Memory.jsx";
import Search from "./Search.jsx";
import Skills from "./Skills.jsx";
import Usage from "./Usage.jsx";
import { switchTo } from "./Mini.jsx";
import { Activity as ActivityScreen, Models, ProjectCard, Projects as ProjectsScreen } from "./Screens.jsx";
import { AGENTS, footnote, inApp, load, mb, num, openSupport, shortDate } from "./data.js";
import { PALETTES, Scroll, Switch, Tip, Toasts, usePalette, useSpotlight } from "./ui.jsx";

const SCREENS = {
  overview: { title: "Overview", note: "this week" },
  search: { title: "Search", note: "Memory, Library and Code" },
  memory: { title: "Memory", note: "review and manage saved memories" },
  library: { title: "Library", note: "indexed document corpora" },
  code: { title: "Code" },
  projects: { title: "Projects" },
  models: { title: "Models" },
  activity: { title: "Activity", note: "what Memory did" },
  usage: { title: "Usage", note: "tokens your agents used" },
  skills: { title: "Skills", note: "agents' changes, and your review" },
  enterprise: { title: "Footnote Enterprise" },
};

const HOTKEY_SCREENS = ["overview", "search", "memory", "library", "code", "projects", "models", "activity", "usage"];

/** `#/code/symbol?mock=1` -> ["code", "symbol"]. */
const route = () => {
  const [name, view] = location.hash.replace(/^#\/?/, "").split("?")[0].split("/");
  return name in SCREENS ? [name, view] : ["overview"];
};

/** Start native window drag when clicking empty titlebar space (buttons/inputs keep their own clicks). */
function onDragMouseDown(e) {
  if (!inApp || e.button !== 0) return;
  if (e.target.closest("button, a, input, select, textarea, [role='button']")) return;
  getCurrentWindow().startDragging().catch(() => {});
}

function onTitleDoubleClick(e) {
  if (!inApp) return;
  if (e.target.closest("button, a, input, select, textarea, [role='button']")) return;
  getCurrentWindow().toggleMaximize().catch(() => {});
}

export default function App() {
  const [[screen, view], setScreen] = useState(route);
  const [state, setState] = useState({ loading: true });
  const [maximized, setMaximized] = useState(false);

  const refresh = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }));
    const r = await load([["status"], ["projects"], ["activity"]]);
    setState({ loading: false, ...r });
  }, []);
  useEffect(() => {
    refresh();
  }, [refresh]);
  useEffect(() => {
    const on = () => setScreen(route());
    addEventListener("hashchange", on);
    return () => removeEventListener("hashchange", on);
  }, []);
  useEffect(() => {
    if (!inApp) return;
    const win = getCurrentWindow();
    win.isMaximized().then(setMaximized).catch(() => {});
    const unlisten = win.onResized(() => {
      win.isMaximized().then(setMaximized).catch(() => {});
    });
    return () => { unlisten.then((fn) => fn()).catch(() => {}); };
  }, []);

  const go = useCallback((name) => {
    const query = location.hash.includes("?") ? "?" + location.hash.split("?")[1] : "";
    location.hash = `/${name}${query}`;
  }, []);

  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.altKey || e.shiftKey) return;
      if (e.key.toLowerCase() === "k") {
        e.preventDefault();
        go("search");
      } else if (e.key >= "1" && e.key <= "9") {
        const target = HOTKEY_SCREENS[Number(e.key) - 1];
        if (target) {
          e.preventDefault();
          go(target);
        }
      }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [go]);

  const [status, projects, activity] = state.data ?? [];
  const meta = SCREENS[screen];
  useSpotlight();

  return (
    <div className={screen === "overview" ? "app" : "app no-feed"}>
      <Sidebar status={status} projects={projects} screen={screen} go={go} />
      <main>
        <header className="top" data-tauri-drag-region onMouseDown={onDragMouseDown} onDoubleClick={onTitleDoubleClick}>
          <h1>{meta.title}</h1>
          {meta.note && <span className="top-note">· {meta.note}</span>}
          <div className="end">
            <Appearance />
            <Tip tip="Mini window" side="bottom">
              <button type="button" className="ic-btn" onClick={() => switchTo("mini")} aria-label="Switch to the mini window">
                <Minimize2 size={15} strokeWidth={1.75} />
              </button>
            </Tip>
            <Tip tip={state.loading ? "Reading…" : "Refresh"} side="bottom">
              <button type="button" className="ic-btn" onClick={refresh} disabled={state.loading} aria-label="Refresh data">
                <RefreshCw size={15} strokeWidth={1.75} className={state.loading ? "spin" : ""} />
              </button>
            </Tip>
            <WindowControls maximized={maximized} />
          </div>
        </header>
        <Scroll label={meta.title} key={screen}>
        {screen === "enterprise" ? (
          <Enterprise />
        ) : state.error ? (
          <Problem error={state.error} retry={refresh} />
        ) : screen === "projects" ? (
          <ProjectsScreen projects={projects} refresh={refresh} />
        ) : screen === "models" ? (
          <Models refresh={refresh} />
        ) : screen === "memory" ? (
          <Memory refresh={refresh} />
        ) : screen === "library" ? (
          <Library refresh={refresh} />
        ) : screen === "activity" ? (
          <ActivityScreen />
        ) : screen === "search" ? (
          <Search />
        ) : screen === "usage" ? (
          <Usage />
        ) : screen === "skills" ? (
          <Skills />
        ) : screen === "code" ? (
          <Code projects={projects} view={["symbol", "layers"].includes(view) ? view : "map"} go={(v) => go(`code/${v}`)} />
        ) : (
          <Overview status={status} projects={projects} refresh={refresh} go={go} />
        )}
        </Scroll>
      </main>
      {screen === "overview" && !state.error && <Activity activity={activity} />}
      <Toasts />
    </div>
  );
}

/** The palette menu (T3 Code's theme picker): five palettes, the choice kept in this window's storage. */
function Appearance() {
  const [palette, choose] = usePalette();
  const menu = useRef(null);
  const onKey = (e) => {
    const list = [...(menu.current?.querySelectorAll("[role='menuitemradio']") ?? [])];
    const at = list.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      list[(at + (e.key === "ArrowDown" ? 1 : list.length - 1)) % list.length]?.focus();
    }
  };
  return (
    <>
      <Tip tip="Appearance" side="bottom">
        <button type="button" className="ic-btn anchor-self" popoverTarget="appearance" aria-label="Appearance"
          aria-haspopup="menu" style={{ "--anchor": "--appearance" }}>
          <Palette size={15} strokeWidth={1.75} />
        </button>
      </Tip>
      <div ref={menu} id="appearance" popover="auto" role="menu" aria-label="Palette" className="menu right lglass"
        style={{ "--anchor": "--appearance" }} onKeyDown={onKey}
        onToggle={(e) => e.newState === "open" && requestAnimationFrame(() => menu.current?.querySelector("[aria-checked='true']")?.focus())}>
        <div className="menu-title">Palette</div>
        <div className="palettes">
          {PALETTES.map((p) => (
            <button key={p.id} type="button" role="menuitemradio" aria-checked={palette === p.id} className="pal"
              onClick={() => choose(p.id)}>
              <i style={{ background: `linear-gradient(135deg, ${p.sw[0]} 52%, ${p.sw[1]} 52%)` }} />
              <span>{p.name}</span>
              <Check size={14} strokeWidth={2} aria-hidden="true" />
            </button>
          ))}
        </div>
      </div>
    </>
  );
}

function WindowControls({ maximized }) {
  const minimize = () => inApp && getCurrentWindow().minimize().catch(() => {});
  const toggleMax = () => inApp && getCurrentWindow().toggleMaximize().catch(() => {});
  const close = () => inApp && getCurrentWindow().hide().catch(() => {});
  return (
    <div className="win-ctls" aria-label="Window controls">
      <button type="button" className="win-btn" onClick={minimize} aria-label="Minimize" title="Minimize">
        <Minus size={14} strokeWidth={1.75} />
      </button>
      <button type="button" className="win-btn" onClick={toggleMax} aria-label={maximized ? "Restore" : "Maximize"} title={maximized ? "Restore" : "Maximize"}>
        {maximized ? <Copy size={12} strokeWidth={1.75} /> : <Square size={12} strokeWidth={1.75} />}
      </button>
      <button type="button" className="win-btn close" onClick={close} aria-label="Hide to tray" title="Hide to tray">
        <X size={14} strokeWidth={1.75} />
      </button>
    </div>
  );
}

function Sidebar({ status, projects, screen, go }) {
  const memory = status?.products?.memory;
  const library = status?.products?.library;
  const code = status?.products?.code;
  const models = status?.models?.models ?? [];
  const onDisk = models.reduce((sum, m) => sum + (m.installed ? m.bytes ?? 0 : 0), 0);
  const item = (name, Icon, label, extra) => (
    <button className="item" aria-current={screen === name ? "page" : undefined} onClick={() => go(name)}>
      <Icon size={15} strokeWidth={1.75} className="nav-ic" aria-hidden="true" />
      <span className="nav-lbl">{label}</span>
      {extra}
    </button>
  );
  const badge = (text, product) => (
    <span className="n">
      {text}
      {product !== undefined && <span className={live(product) ? "dot" : "dot off"} />}
    </span>
  );
  return (
    <aside className="side">
      <div className="brand" data-tauri-drag-region onMouseDown={onDragMouseDown} onDoubleClick={onTitleDoubleClick}>
        <span className="lens" aria-hidden="true">1</span>
        Footnote
        {status && <span className="ver mono">One {status.version.split("-")[0]}</span>}
      </div>
      <h2 className="grp">Products</h2>
      <nav className="nav" aria-label="Products">
        {item("overview", LayoutDashboard, "Overview")}
        {item("search", SearchIcon, "Search", <span className="n kbd">Ctrl K</span>)}
        {item("memory", Brain, "Memory", badge(memory ? num(memory.memories) : "", memory))}
        {item("library", BookOpen, "Library", badge(library?.corpora ? num(library.corpora.length) : "", library))}
        {item("code", GitFork, "Code", badge(graphs(code?.graphs), code))}
      </nav>
      <h2 className="grp">Workspace</h2>
      <nav className="nav" aria-label="Workspace">
        {item("projects", FolderGit2, "Projects", <span className="n">{projects ? num(projects.projects.length) : ""}</span>)}
        {item("models", Cpu, "Models",
          <span className="n">{status ? `${models.filter((m) => m.installed).length} / ${models.length}` : ""}</span>)}
        {item("activity", ActivityIcon, "Activity")}
        {item("usage", BarChart3, "Usage")}
        {item("skills", Sparkles, "Skills")}
      </nav>
      <h2 className="grp">Footnote Enterprise</h2>
      <nav className="nav" aria-label="Footnote Enterprise">
        {item("enterprise", Building2, "Alias, sign-on…", <span className="n">Learn more</span>)}
      </nav>
      <div className="foot">
        <span>Free and open source</span>
        {onDisk > 0 && <span className="mono">{mb(onDisk)} models</span>}
        <span className="help">
          Help: <button type="button" className="help-link" onClick={() => openSupport("issues")}>report an issue</button>
          {" · "}
          <button type="button" className="help-link" onClick={() => openSupport("email")}>email</button>
        </span>
      </div>
    </aside>
  );
}

/** A product is live when it is in this build and switched on (the dot beside its name). */
const live = (p) => p !== undefined && p.built !== false && p.enabled !== false;

const graphs = (n) => (n === undefined ? "" : n === 1 ? "1 graph" : `${num(n)} graphs`);

function Overview({ status, projects, refresh, go }) {
  const p = status?.products;
  const memory = p?.memory;
  const code = p?.code;
  const sw = (key, title) => ({ product: key, title, built: p?.[key]?.built, enabled: p?.[key]?.enabled !== false, refresh });
  const recent = (projects?.projects ?? []).filter((x) => x.exists).slice(0, 6);
  return (
    <div className="body">
      <div className="row">
        <Card {...sw("memory", "Memory")} big={memory && (memory.built === false ? "–" : num(memory.memories))}
          sub={memory && (memory.built === false ? "" : `${num(memory.saved_last_7_days)} saved · ${num(memory.recalls_last_7_days)} recalls in 7 days`)} />
        <Card {...sw("library", "Library")} big={p && (p.library?.built ? (p.library.enabled === false ? "Off" : "On") : "–")}
          sub={p && (p.library?.built ? "Your folders and docs, searched by any agent" : "")} />
        <Card {...sw("code", "Code")} big={code && (code.built ? num(code.graphs) : "–")}
          sub={code && (!code.built ? "" : `project ${code.graphs === 1 ? "graph" : "graphs"}${code.rust_indexer ? " · rust-analyzer found" : ""}`)} />
      </div>
      <div className="bar">
        <h2 className="section">Projects agents worked in</h2>
        {projects?.projects?.length > recent.length && (
          <button type="button" className="help-link" style={{ marginLeft: "auto" }} onClick={() => go("projects")}>
            All {num(projects.projects.length)} projects
          </button>
        )}
      </div>
      {!projects ? <span className="skel" /> : recent.length === 0 ? (
        <p className="empty">No project yet. A project appears here when an agent starts a session in it.</p>
      ) : (
        <div className="mini-projects">
          {recent.map((x) => <ProjectCard key={x.path} p={x} refresh={refresh} />)}
        </div>
      )}
      <h2 className="section">Agents</h2>
      <Agents list={memory?.agents} loading={!status} />
    </div>
  );
}

/** A product card. Its switch is the product's on/off setting (`footnote config set <product>.enabled`): off, agents lose its
 * tools at once and Memory's hook goes quiet; nothing is deleted. A company policy can refuse the change; its reason is shown. */
function Card({ product, title, built, enabled, refresh, big, sub }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const known = built !== undefined;
  const flip = async () => {
    setBusy(true);
    setError(null);
    try {
      await footnote("config", "set", `${product}.enabled`, String(!enabled));
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className={`card sq lit${known && (!built || !enabled) ? " muted" : ""}`}>
      <h2>
        <span className={known && built && enabled ? "dot" : "dot off"} />
        {title}
        {known && (built ? (
          <Switch checked={enabled} label={`${title} on`} onChange={flip} disabled={busy} />
        ) : (
          <span className="state">Not in this build</span>
        ))}
      </h2>
      {big === undefined ? <span className="skel big" /> : <div className="big">{big}</div>}
      {sub === undefined ? <span className="skel" /> : (
        <div className="sub">{known && built && !enabled ? "Off: agents get none of its tools. Nothing is deleted." : sub}</div>
      )}
      {error && <div className="sub warn" role="alert">{error}</div>}
    </section>
  );
}

/** Each connected agent as a glass chip: its name, then two pictograms (Memory hooks, MCP server), lit when on. */
function Agents({ list, loading }) {
  if (loading) return <span className="skel" />;
  if (!list?.length)
    return (
      <p className="empty">
        No agent connected. Run <code>footnote install --memory</code> to connect Claude Code, Codex and others.
      </p>
    );
  const pict = (on, Icon, what) => (
    <Tip tip={`${what}: ${on ? "on" : "off"}`}>
      <span className={`stat idle${on ? " on" : " warn"}`} role="img" aria-label={`${what} ${on ? "on" : "off"}`} tabIndex={0}>
        <span className="stat-ic"><Icon size={13} strokeWidth={1.9} /></span>
      </span>
    </Tip>
  );
  return (
    <div className="agents">
      {list.map((a) => (
        <div key={a.agent} className="agent surface sq lit">
          <b>{AGENTS[a.agent] ?? a.agent}</b>
          {pict(a.hooks, Webhook, "Memory hooks")}
          {pict(a.mcp_server, Plug, "MCP server")}
        </div>
      ))}
    </div>
  );
}

function Activity({ activity }) {
  const days = (activity?.days ?? []).filter((d) => d.saved || d.prompts_given_memories || d.sessions).reverse();
  return (
    <aside className="feed" aria-label="Activity">
      <h2 className="section">Activity</h2>
      {!activity ? (
        <span className="skel" />
      ) : days.length === 0 ? (
        <p className="dimmed">Nothing yet this week.</p>
      ) : (
        <table className="tbl days">
          <thead>
            <tr>
              <th scope="col">Day</th>
              <th scope="col" className="num">Saved</th>
              <th scope="col" className="num" title="Prompts that were given memories">Recalls</th>
              <th scope="col" className="num">Sessions</th>
            </tr>
          </thead>
          <tbody>
            {days.map((d) => (
              <tr key={d.date}>
                <td className="mono"><time dateTime={d.date}>{shortDate(d.date)}</time></td>
                <td className="num">{num(d.saved)}</td>
                <td className="num">{num(d.prompts_given_memories)}</td>
                <td className="num">{num(d.sessions)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {activity?.most_used?.length > 0 && (
        <>
          <h2 className="section" style={{ marginTop: 8 }}>Most recalled</h2>
          {activity.most_used.slice(0, 6).map((m) => (
            <div className="ev" key={m.id}>
              <span className="mono id">#{m.id}</span>
              <div title={m.memory?.text ?? ""}>
                {m.memory ? <span className="clamp">{m.memory.text}</span> : <span className="dimmed">no longer in memory</span>}
                <span className="dimmed">{num(m.times)} times{m.memory?.scope ? ` · ${m.memory.scope}` : ""}</span>
              </div>
            </div>
          ))}
        </>
      )}
    </aside>
  );
}

function Problem({ error, retry }) {
  const missing = error === "ENGINE_MISSING";
  return (
    <div className="body">
      <div className="msg" role="alert">
        <h2>{missing ? "The Footnote engine was not found" : "Footnote could not read its data"}</h2>
        {missing ? (
          <p>
            Install <code>footnote</code>, or set <code>FOOTNOTE_BIN</code> to its path, then try again.
          </p>
        ) : (
          <p className="mono">{error}</p>
        )}
        <div className="actions">
          {missing && (
            <button className="btn primary" onClick={() => openSupport("install")}>Get Footnote</button>
          )}
          <button className="btn" onClick={retry}>Try again</button>
        </div>
      </div>
    </div>
  );
}

function Enterprise() {
  return (
    <div className="body">
      <div className="prose">
        <h2>For teams and companies</h2>
        <p>
          Footnote One stays free and complete for one person or a small team. Footnote Enterprise is a separate build of the
          same engine for companies that need:
        </p>
        <ul>
          <li><b>Alias</b>: names and personal details replaced before text reaches a model.</li>
          <li><b>Company sign-on and rights</b>: who sees which project, from your own directory.</li>
          <li><b>Portfolio</b>: projects across teams in one view, with usage roll-ups.</li>
          <li><b>Curated skills and a compliance kit</b> for regulated work.</li>
        </ul>
        <p>Nothing here is locked in Footnote One, and Footnote One never asks you to upgrade.</p>
      </div>
    </div>
  );
}
