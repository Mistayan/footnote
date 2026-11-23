import { useEffect, useId, useState } from "react";
import {
  Brain,
  Check,
  CheckCheck,
  CircleAlert,
  Eye,
  EyeOff,
  ExternalLink,
  GitCommitHorizontal,
  GitFork,
  Loader2,
  MemoryStick,
  MessageSquareText,
  PlayCircle,
  ScanSearch,
  Send,
  Sparkle,
} from "lucide-react";
import { cancelInstall, footnote, mb, num, openLicense, openProjectFolder, openReceipt, seen, shortDate } from "./data.js";
import { sessionName, takenLine, waitingTip } from "./asks.js";
import AddProject, { ImportGguf } from "./Folders.jsx";
import { KindIcon } from "./Memory.jsx";
import { PathPill, Select, Tabs, Tip, clip, toast } from "./ui.jsx";

// The workspace screens: Projects, Models and Activity. Each reads its own engine command.

function useRead(args, round = 0) {
  const [state, setState] = useState({ loading: true });
  const key = args.join(" ");
  useEffect(() => {
    let live = true;
    setState({ loading: true });
    footnote(...args).then(
      (data) => live && setState({ data }),
      (error) => live && setState({ error: String(error) }),
    );
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, round]);
  return state;
}

const Failed = ({ error }) => (
  <p className="empty warn" role="alert">{error === "ENGINE_MISSING" ? "The Footnote engine was not found." : error}</p>
);

const NAME_MAX = 24;

/** Commits running now, by project: a run outlives the card that started it (another screen, a refresh). */
const running = new Set();
const announce = () => dispatchEvent(new Event("footnote-commit-run"));

/** One project as a glass card: name, folder (drive squircle + last folder, opens the folder), then pictograms for its
 * memories, code graph and uncommitted changes. Each pictogram explains itself on hover. The commit pictogram sends the
 * engine's commit-and-push request to the project's last agent session (`footnote agent-ask`); while it waits, a click
 * withdraws it, and once taken its tip says which session took it and when. */
export function ProjectCard({ p, busy, onIndex, refresh }) {
  const [asking, setAsking] = useState(false);
  const [ignoring, setIgnoring] = useState(false);
  const ignore = async () => {
    setIgnoring(true);
    try {
      await footnote("projects", "ignore", p.name);
      await refresh?.();
      toast(`Ignoring ${p.name}: it leaves the list and new sessions there are not recorded.`, "ok", {
        action: { label: "Undo", run: () => footnote("projects", "unignore", p.name).then(() => refresh?.(), (e) => toast(String(e), "warn")) },
      });
    } catch (e) {
      toast(String(e), "warn");
      setIgnoring(false);
    }
  };
  const open = () => openProjectFolder(p.path).catch((e) => toast(String(e), "warn"));
  const waiting = p.ask?.kind === "commit";
  const taken = waiting ? null : takenLine(p.ask_taken);
  const [, rerender] = useState(0);
  useEffect(() => {
    const on = () => rerender((n) => n + 1);
    addEventListener("footnote-commit-run", on);
    return () => removeEventListener("footnote-commit-run", on);
  }, []);
  const committing = running.has(p.name);
  // A click commits and pushes now: the agent last used here runs unattended (`footnote agent-commit`). With no agent
  // command line installed, the request waits for the next agent turn instead (`agent-ask`); a click withdraws that.
  const ask = async () => {
    if (waiting) {
      setAsking(true);
      try {
        await footnote("agent-ask", p.name, "--cancel");
        toast(`Withdrew the commit request for ${p.name}.`);
        await refresh?.();
      } catch (e) {
        toast(String(e), "warn");
      } finally {
        setAsking(false);
      }
      return;
    }
    running.add(p.name);
    announce();
    try {
      const r = await footnote("agent-commit", p.name);
      const left = r?.uncommitted ?? 0;
      toast(`${p.name}: ${clip(r?.said || "done", 220)}${left ? ` (${left} left uncommitted)` : ""}`, left ? "warn" : "ok", { sticky: true });
    } catch (e) {
      if (/is installed on PATH/.test(String(e))) {
        const q = await footnote("agent-ask", p.name).catch(() => null);
        const who = sessionName(q?.agent, q?.session);
        toast(who
          ? `No agent command line found: sent to ${who}. It commits and pushes at its next turn; while idle it cannot be reached.`
          : `No agent command line found: ${p.name}'s next agent turn commits and pushes instead.`);
      } else {
        toast(`${p.name}: ${clip(String(e), 200)}`, "warn", { sticky: true });
      }
    } finally {
      running.delete(p.name);
      announce();
      refresh?.();
    }
  };
  const name = clip(p.name, NAME_MAX);
  const dirty = p.git?.uncommitted ?? 0;
  return (
    <article className={`proj surface sq lit${p.exists ? "" : " gone"}`}>
      <div className="proj-head">
        <Tip tip={name !== p.name ? p.name : null}><h3 className="proj-name">{name}</h3></Tip>
        <Tip tip={`First seen ${shortDate(p.first_seen)} · last seen ${seen(p.last_seen)}`}>
          <span className="proj-when" tabIndex={0}>{seen(p.last_seen)}</span>
        </Tip>
      </div>
      <PathPill path={p.path} onOpen={p.exists ? open : undefined} missing={!p.exists} />
      <div className="stats">
        <Tip tip={`${num(p.memories)} ${p.memories === 1 ? "memory" : "memories"} saved in this project`}>
          <span className={`stat${p.memories > 0 ? " on" : ""}`} tabIndex={0} role="img" aria-label={`${num(p.memories)} memories`}>
            <span className="stat-ic"><Brain size={13} strokeWidth={1.9} /></span>{num(p.memories)}
          </span>
        </Tip>
        {p.code_graph ? (
          <Tip tip="Code graph built: agents can ask who calls what">
            <span className="stat idle on" tabIndex={0} role="img" aria-label="Code graph built">
              <span className="stat-ic"><GitFork size={13} strokeWidth={1.9} /></span>
            </span>
          </Tip>
        ) : p.exists && onIndex ? (
          <Tip tip={busy ? "Building the code graph…" : "Build the code graph. A parser reads the source; no project code runs."}>
            <button type="button" className="stat idle" disabled={busy !== null && busy !== undefined} onClick={() => onIndex(p.path)}
              aria-label={`Build the code graph of ${p.name}`}>
              <span className="stat-ic">
                {busy === p.path ? <Loader2 size={13} strokeWidth={1.9} className="spin" /> : <ScanSearch size={13} strokeWidth={1.9} />}
              </span>
            </button>
          </Tip>
        ) : null}
        {p.git && (dirty > 0 && waiting ? (
          <Tip tip={waitingTip(p.name, p.ask)}>
            <button type="button" className="stat sent" onClick={ask} disabled={asking}
              aria-label={`Commit request waiting for ${sessionName(p.ask?.agent, p.ask?.session) ?? "the agent"} in ${p.name}: withdraw it`}>
              <span className="stat-ic"><Send size={12} strokeWidth={2.2} /></span>{num(dirty)}
            </button>
          </Tip>
        ) : dirty > 0 && committing ? (
          <Tip tip={`The agent is committing and pushing ${p.name}…`}>
            <span className="stat sent" role="status" aria-label={`Committing and pushing ${p.name}`} tabIndex={0}>
              <span className="stat-ic"><Loader2 size={12} strokeWidth={2.2} className="spin" /></span>{num(dirty)}
            </span>
          </Tip>
        ) : dirty > 0 && taken ? (
          <Tip tip={`${taken} ${num(dirty)} change${dirty === 1 ? "" : "s"} still uncommitted. Click: the agent last used here commits and pushes now, in the background.`}>
            <button type="button" className="stat sent" onClick={ask} disabled={asking}
              aria-label={`${taken} ${num(dirty)} uncommitted changes in ${p.name}: commit and push now`}>
              <span className="stat-ic"><CheckCheck size={13} strokeWidth={2.2} /></span>{num(dirty)}
            </button>
          </Tip>
        ) : dirty > 0 ? (
          <Tip tip={`${num(dirty)} uncommitted change${dirty === 1 ? "" : "s"}. Click: the agent last used here commits and pushes now, in the background.`}>
            <button type="button" className="stat bad" onClick={ask} disabled={asking}
              aria-label={`${num(dirty)} uncommitted changes in ${p.name}: commit and push now`}>
              <span className="stat-ic"><GitCommitHorizontal size={13} strokeWidth={2.2} /></span>{num(dirty)}
            </button>
          </Tip>
        ) : (
          <Tip tip={taken ? `Everything is committed. ${taken}` : "Everything is committed"}>
            <span className="stat idle on" tabIndex={0} role="img" aria-label={taken ? `Everything is committed. ${taken}` : "Everything is committed"}>
              <span className="stat-ic"><Check size={13} strokeWidth={2.2} /></span>
            </span>
          </Tip>
        ))}
        {!p.exists && (
          <Tip tip="This folder no longer exists">
            <span className="stat warn idle" tabIndex={0} role="img" aria-label="Folder missing">
              <span className="stat-ic"><CircleAlert size={13} strokeWidth={1.9} /></span>
            </span>
          </Tip>
        )}
        <span className="stats-end">
          <Tip tip="Ignore: stop listing this project and recording new sessions in it. Its memories stay.">
            <button type="button" className="stat idle ignore" onClick={ignore} disabled={ignoring} aria-label={`Ignore ${p.name}`}>
              <span className="stat-ic"><EyeOff size={13} strokeWidth={1.9} /></span>
            </button>
          </Tip>
        </span>
      </div>
    </article>
  );
}

export function Projects({ projects, refresh }) {
  const list = projects?.projects;
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  // One at a time: indexing is heavy, and a failure names its project instead of stopping the rest.
  const index = async (paths) => {
    setError(null);
    for (const path of paths) {
      setBusy(path);
      try { await footnote("code-index", path); } catch (e) { setError(`${path}: ${e}`); }
    }
    setBusy(null);
    refresh?.();
  };
  if (!list) return <div className="body"><span className="skel" /></div>;
  // A project whose folder is gone is noise: it is not shown (its memories stay; a new session there lists it again).
  const shown = list.filter((p) => p.exists);
  const todo = shown.filter((p) => !p.code_graph).map((p) => p.path);
  const graphs = shown.filter((p) => p.code_graph).length;
  const memories = shown.reduce((n, p) => n + (p.memories ?? 0), 0);
  const dirty = shown.filter((p) => p.git?.uncommitted > 0);
  return (
    <div className="body">
      <section className="hero lglass sq">
        <div>
          <div className="kicker">Projects</div>
          <div className="big">{num(shown.length)}</div>
          <div className="sub">Every folder where an agent started a session with Memory on.</div>
        </div>
        <div className="kpis">
          <div className="kpi"><span><Brain size={12} strokeWidth={1.9} /> Memories</span><b>{num(memories)}</b></div>
          <div className="kpi"><span><GitFork size={12} strokeWidth={1.9} /> Code graphs</span><b>{num(graphs)}<span className="dimmed small"> / {num(shown.length)}</span></b></div>
          <div className="kpi">
            <span><GitCommitHorizontal size={12} strokeWidth={1.9} /> To commit</span>
            <b className={dirty.length ? "bad" : "ok"}>{dirty.length ? num(dirty.length) : "None"}</b>
          </div>
          <div className="hero-actions">
            {todo.length > 0 && (
              <button type="button" className="btn primary" disabled={busy !== null} onClick={() => index(todo)}>
                {busy ? "Indexing…" : `Index ${todo.length} without a graph`}
              </button>
            )}
            <AddProject refresh={refresh} />
          </div>
        </div>
      </section>
      {error && <p className="empty warn" role="alert">{error}</p>}
      {shown.length === 0 ? (
        <p className="empty">No project yet. A project appears here when an agent starts a session in it.</p>
      ) : (
        <div className="proj-grid">
          {shown.map((p) => <ProjectCard key={p.path} p={p} busy={busy} onIndex={(path) => index([path])} refresh={refresh} />)}
        </div>
      )}
      <Ignored names={projects.ignored ?? []} refresh={refresh} />
    </div>
  );
}

/** The projects the user ignored, each with a button that lists and records it again from its next session. */
function Ignored({ names, refresh }) {
  const [open, setOpen] = useState(false);
  if (names.length === 0) return null;
  const restore = (name) =>
    footnote("projects", "unignore", name).then(
      () => { toast(`${name} is listed again from its next session.`); refresh?.(); },
      (e) => toast(String(e), "warn"),
    );
  return (
    <section className="ignored">
      <button type="button" className="help-link small" aria-expanded={open} onClick={() => setOpen(!open)}>
        {names.length} ignored {names.length === 1 ? "project" : "projects"}
      </button>
      {open && (
        <div className="ignored-list">
          {names.map((n) => (
            <span key={n} className="chip ignored-chip">
              {clip(n, 32)}
              <Tip tip={`Stop ignoring ${n}`}>
                <button type="button" className="mw-btn" onClick={() => restore(n)} aria-label={`Stop ignoring ${n}`}>
                  <Eye size={13} strokeWidth={1.9} />
                </button>
              </Tip>
            </span>
          ))}
        </div>
      )}
    </section>
  );
}

/** What a licence allows, in plain words, and where its text is. */
const LICENSES = [
  { test: /no commercial|by-nc/i, id: "cc-by-nc-4.0", name: "CC BY-NC 4.0", nc: true,
    text: "Free for personal use and research, with credit to the authors. Not for commercial work: a company product or paid service needs another model." },
  { test: /apache/i, id: "apache-2.0", name: "Apache 2.0",
    text: "Permissive, with a patent grant. Free for any use, commercial included; keep the notice and say what you changed." },
  { test: /\bmit\b/i, id: "mit", name: "MIT",
    text: "Permissive. Free for any use, commercial included; keep the copyright notice." },
];

function License({ license }) {
  const raw = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const anchor = `--lic-${raw}`;
  const known = LICENSES.find((l) => l.test.test(license));
  return (
    <>
      <button type="button" className={`lic${known?.nc ? " nc" : ""}`} popoverTarget={`lic-${raw}`} style={{ "--anchor": anchor }}
        aria-label={`Licence ${license}: what it allows`}>
        <span>{known?.name ?? license}</span>
      </button>
      <div id={`lic-${raw}`} popover="auto" className="lic-pop lglass" style={{ "--anchor": anchor }}>
        <h3>{known?.name ?? license}</h3>
        <p>{known ? known.text : "See the model's card for its terms before using it at work."}</p>
        {known && (
          <button type="button" className="btn" onClick={() => openLicense(known.id)}>
            Read the licence <ExternalLink size={12} strokeWidth={1.75} />
          </button>
        )}
      </div>
    </>
  );
}

export function Models({ refresh }) {
  const [round, setRound] = useState(0);
  const { data, error } = useRead(["models", "list"], round);
  const [busy, setBusy] = useState(null); // { name, progress: {done, total}, error, cancelled }
  const [switching, setSwitching] = useState(null);
  const [switchNote, setSwitchNote] = useState(null);
  // While a download runs, read its progress from the engine's job list (the install itself answers only at the end).
  useEffect(() => {
    if (!busy?.name || busy.error || busy.cancelled) return;
    const timer = setInterval(() => {
      footnote("jobs").then((j) => {
        const job = j.jobs.find((x) => x.kind === "models.install" && x.state === "running" && x.label.startsWith(busy.name + " "));
        if (job) setBusy((b) => b && b.name === busy.name && { ...b, progress: { done: job.done, total: job.total, file: job.label } });
      }, () => {});
    }, 500);
    return () => clearInterval(timer);
  }, [busy?.name, busy?.error, busy?.cancelled]);
  const install = (name) => {
    setBusy({ name });
    setSwitchNote(null);
    footnote("models", "install", name).then(
      () => { setBusy(null); setRound((r) => r + 1); refresh?.(); },
      (e) => setBusy((b) => (b?.cancelled ? b : { name, error: String(e) })),
    );
  };
  const useModels = (names) => {
    setSwitching(names.join("+"));
    setSwitchNote(null);
    footnote("models", "use", ...names).then(
      (res) => {
        setSwitching(null);
        setSwitchNote(res?.note ?? "Active model updated.");
        setRound((r) => r + 1);
        refresh?.();
      },
      (e) => {
        setSwitching(null);
        setSwitchNote(`Error: ${e}`);
      },
    );
  };
  const cancel = () => {
    setBusy((b) => b && { ...b, cancelled: true });
    cancelInstall();
  };
  if (error) return <div className="body"><Failed error={error} /></div>;
  if (!data) return <div className="body"><span className="skel big" /><span className="skel" /></div>;
  const active = data.models.filter((m) => m.installed && m.used_by_memory);
  const defaultPairInstalled = ["bekko-a8m", "gte-small"].every((n) => data.models.some((m) => m.name === n && m.installed));
  const isDefaultPair = active.length === 2 && active.some((m) => m.name === "bekko-a8m") && active.some((m) => m.name === "gte-small");
  const onDisk = data.models.reduce((n, m) => n + (m.installed ? m.bytes ?? 0 : 0), 0);
  const rank = (m) => (m.used_by_memory ? -1 : RANK.indexOf(m.name) < 0 ? RANK.length : RANK.indexOf(m.name));
  const models = [...data.models].sort((a, b) => rank(a) - rank(b));
  return (
    <div className="body">
      <section className="hero solo lglass sq">
        <div>
          <div className="kicker">Active for Memory</div>
          <div className="big">
            {active.length ? active.map((m, i) => (
              <span key={m.name}>{i > 0 && <span className="plus">+</span>}{m.name}</span>
            )) : "None"}
          </div>
          <div className="sub">
            {active.length ? active.map((m) => m.role).join(" · ") : "Memory searches by keywords until a model is installed."}
          </div>
        </div>
        <div className="end">
          {active.length > 0 && <KeepInMemory />}
          {defaultPairInstalled && !isDefaultPair && (
            <button type="button" className="btn primary" disabled={!!switching} onClick={() => useModels(["bekko-a8m", "gte-small"])}>
              {switching === "bekko-a8m+gte-small" ? "Switching…" : "Use the default pair"}
            </button>
          )}
        </div>
      </section>
      {switchNote && <p className={switchNote.startsWith("Error:") ? "warn small" : "ok small"} role="status">{switchNote}</p>}
      {data.llama === false && (
        <p className="dimmed small">This build of Footnote has no llama.cpp, so it cannot run GGUF models (marked below). Release builds include it.</p>
      )}
      <ul className="model-grid" aria-label="Models">
        {models.map((m) => {
          const blocked = (m.imported || GGUF.has(m.name)) && data.llama === false;
          const facts = MEASURED[m.name];
          return (
            <li key={m.name} className={`model-card card sq lit${m.used_by_memory ? " on" : ""}`} aria-label={m.name}>
              <header className="mc-head">
                <h3 className="mono">{m.name}</h3>
                {m.installed ? (
                  m.used_by_memory ? <span className="state-dot">Active</span> : <span className="state-dot idle">Installed</span>
                ) : <span className="dimmed small">Not installed</span>}
              </header>
              <p className="mc-role">{m.imported ? "Imported GGUF" : m.role}</p>
              {facts?.verdict ? (
                <p className="small dimmed">
                  {facts.verdict}{" "}
                  <button type="button" className="receipt" onClick={() => openReceipt(facts.receipt)}
                    aria-label={`Open the measurement ${facts.receipt.split("/").pop()}`}>
                    the measurement <span aria-hidden="true">↗</span>
                  </button>
                </p>
              ) : facts ? (
                <dl className="mc-stats">
                  {facts.stats.map((st) => (
                    <div key={st.label}>
                      <dt>{st.label}</dt>
                      <dd>
                        <button type="button" className="receipt mono" onClick={() => openReceipt(st.receipt)}
                          aria-label={`${st.label} ${st.value}, ${st.vs}: open the measurement`}>
                          {st.value}
                        </button>
                        <span className={`small${st.good ? " ok" : " dimmed"}`}>{st.vs}</span>
                      </dd>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="small dimmed">Not measured by Footnote. No query or passage prefixes.</p>
              )}
              {blocked && <p className="warn small">Needs a build with llama.cpp.</p>}
              {m.installed && !m.used_by_memory && !blocked && <p className="dimmed small">Use re-embeds your memories in the background.</p>}
              <footer className="mc-foot">
                {m.license ? <License license={m.license} />
                  : <span className="dimmed small">Licence unknown: check the model card before use at work.</span>}
                <span className="mono small dimmed mc-size">
                  {m.installed && m.bytes ? mb(m.bytes) : m.download_bytes ? mb(m.download_bytes) : "–"}
                </span>
                {m.installed ? (
                  !m.used_by_memory && (
                    <button className="btn" type="button" disabled={!!switching || blocked} onClick={() => useModels([m.name])}
                      aria-label={`Use ${m.name} for Memory`}>
                      {switching === m.name ? "Switching…" : "Use"}
                    </button>
                  )
                ) : busy?.name === m.name ? (
                  <Download busy={busy} total={m.download_bytes} cancel={cancel} retry={() => install(m.name)} />
                ) : (
                  <button className="btn" type="button" disabled={blocked || (!!busy && !busy.error && !busy.cancelled)}
                    onClick={() => install(m.name)} aria-label={`Install ${m.name}, ${m.download_bytes ? mb(m.download_bytes) : "size unknown"}`}>
                    Install
                  </button>
                )}
              </footer>
            </li>
          );
        })}
      </ul>
      <div className="bar">
        <PathPill path={data.folder} keep={2} />
        <ImportGguf disabled={data.llama === false} done={() => { setRound((r) => r + 1); refresh?.(); }} />
        {onDisk > 0 && <span className="dimmed small" style={{ marginLeft: "auto" }}>{mb(onDisk)} on disk</span>}
      </div>
    </div>
  );
}

// The Models screen's ranking (#556): what the benchmarks measured, each number opening its report. nDCG@10 on held-out
// splits; search p95 is a whole search as an agent sees it, on an idle machine. Order: the active models, the default
// pair, the best measured alternative, the earlier models, then imported ones.
const RANK = ["bekko-a8m", "gte-small", "jina-v5-nano", "e5-small", "minilm"];
const GGUF = new Set(["jina-v5-nano"]);
const FINAL = "bench/experiments/FINAL-RANKING.md";
const NANO = "bench/experiments/LLAMACPP-INPROCESS.md";
const PAIR = {
  stats: [
    { label: "French or mixed", value: "0.489", vs: "nDCG@10, the reference", receipt: FINAL },
    { label: "English", value: "0.747", vs: "nDCG@10, the reference", receipt: FINAL },
    { label: "Search p95", value: "42 ms", vs: "the two together", receipt: NANO },
  ],
};
const MEASURED = {
  "bekko-a8m": PAIR,
  "gte-small": PAIR,
  "jina-v5-nano": {
    stats: [
      { label: "French or mixed", value: "0.572", vs: "+0.083 over the pair", good: true, receipt: NANO },
      { label: "Search p95", value: "69 ms", vs: "pair 42 ms", receipt: NANO },
    ],
  },
  "e5-small": { verdict: "Did not beat the default pair when added to it.", receipt: "bench/experiments/RESULTS.md" },
  minilm: { verdict: "Did not beat the default pair when added to it.", receipt: "bench/experiments/RESULTS.md" },
};

const KEEP = [[300, "5 min"], [1800, "30 min"], [7200, "2 hours"]];

/** How long the models stay in RAM after the last recall (`memory.resident`, `memory.idle_seconds`): a user's trade of RAM
 * against a reload of about a second. Off means recall by keyword only. A company policy can lock either option. */
function KeepInMemory() {
  const [round, setRound] = useState(0);
  const { data } = useRead(["options"], round);
  const [error, setError] = useState(null);
  const opt = (key) => data?.options.find((o) => o.key === key);
  const resident = opt("memory.resident");
  const idle = opt("memory.idle_seconds");
  if (!resident || !idle) return null;
  const value = resident.value === false ? "off" : idle.value;
  const choices = KEEP.some(([s]) => s === idle.value) ? KEEP : [...KEEP, [idle.value, `${Math.round(idle.value / 60)} min`]];
  const options = [
    { value: "off", label: "Off" },
    ...choices.sort((a, b) => a[0] - b[0]).map(([s, label]) => ({ value: s, label })),
  ];
  const locked = resident.locked || idle.locked;
  if (locked) {
    const shown = options.find((o) => o.value === value)?.label;
    return <span className="dimmed small">Keep in memory: {shown}, set by your company</span>;
  }
  const set = async (v) => {
    setError(null);
    try {
      if (v === "off") await footnote("config", "set", "memory.resident", "false");
      else {
        await footnote("config", "set", "memory.idle_seconds", String(v));
        if (resident.value === false) await footnote("config", "set", "memory.resident", "true");
      }
      setRound((r) => r + 1);
    } catch (e) {
      setError(String(e));
    }
  };
  return (
    <>
      <span className="dimmed small" aria-hidden="true">Keep in memory after use</span>
      <Select value={value} options={options} onChange={set} label="Keep models in memory after use" icon={MemoryStick} />
      {value === "off" && <span className="dimmed small">keyword recall only</span>}
      {error && <span className="warn small" role="alert">{clip(error, 60)}</span>}
    </>
  );
}

/** One model's download: progress of the file being fetched, then the outcome. A cancelled or failed install leaves no model
 * behind (the engine renames each file only once it is complete and its hash checked). */
function Download({ busy, total, cancel, retry }) {
  if (busy.cancelled) return <span className="dimmed small">Cancelled. <button className="btn" type="button" onClick={retry}>Install again</button></span>;
  if (busy.error) return <span className="warn small" role="alert">{clip(busy.error, 60)} <button className="btn" type="button" onClick={retry}>Try again</button></span>;
  const p = busy.progress;
  const pct = p?.total ? Math.min(100, Math.round((100 * p.done) / p.total)) : null;
  return (
    <span className="dl">
      <progress max={100} value={pct ?? undefined} aria-label={`Downloading ${busy.name}`} />
      <span className="mono dimmed small">{p ? `${mb(p.done)}${p.total ? ` / ${mb(p.total)}` : ""}` : total ? `0 / ${mb(total)}` : "starting"}</span>
      <button className="btn" type="button" onClick={cancel}>Cancel</button>
    </span>
  );
}

const PERIODS = [[7, "7 days"], [30, "30 days"], [90, "90 days"]];
const utcDay = (t) => new Date(t).toISOString().slice(0, 10);
const active = (d) => d.saved || d.prompts_given_memories || d.sessions;

export function Activity() {
  const [days, setDays] = useState(30);
  const { data, error } = useRead(["activity", "--days", String(days)]);
  const [picked, setPicked] = useState(null);
  const all = data?.days ?? [];
  const live = all.filter(active).slice().reverse();
  const day = picked && live.some((d) => d.date === picked) ? picked : live[0]?.date ?? null;
  const sum = (k) => all.reduce((n, d) => n + (d[k] ?? 0), 0);
  const peak = Math.max(1, ...all.map((d) => d.prompts_given_memories));
  const recalls = (data?.recent ?? []).filter((r) => utcDay(r.t) === day);
  const chosen = live.find((d) => d.date === day);
  return (
    <div className="body">
      <div className="toolbar">
        <Tabs value={days} options={PERIODS} onChange={setDays} label="Period" />
        {data?.note && <span className="count">{data.note}</span>}
      </div>
      {error ? <Failed error={error} /> : !data ? <span className="skel big" /> : (
        <>
          <section className="hero lglass sq">
            <div>
              <div className="kicker">Recalls · {days} days</div>
              <div className="big">{num(sum("prompts_given_memories"))}</div>
              <div className="sub">
                {num(sum("saved"))} memories saved · {num(sum("sessions"))} sessions · {num(live.length)} active {live.length === 1 ? "day" : "days"}
              </div>
            </div>
            <div>
              <div className="bars" role="group" aria-label="Recalls per day; pick a day to see what happened">
                {all.map((d) => (
                  <Tip key={d.date} tip={`${shortDate(d.date)} · ${num(d.prompts_given_memories)} recalls · ${num(d.saved)} saved`}>
                    <button type="button" aria-pressed={d.date === day} disabled={!active(d)} onClick={() => setPicked(d.date)}
                      aria-label={`${shortDate(d.date)}: ${num(d.prompts_given_memories)} recalls`} style={{ height: "100%", flex: 1 }}>
                      <span style={{ height: `${Math.max(2, (100 * d.prompts_given_memories) / peak)}%` }} />
                    </button>
                  </Tip>
                ))}
              </div>
              {all.length > 0 && (
                <div className="bars-axis"><span>{shortDate(all[0].date)}</span><span>{shortDate(all[all.length - 1].date)}</span></div>
              )}
            </div>
          </section>

          {live.length === 0 ? (
            <p className="empty">Nothing happened in this period. Memory logs a day once an agent saves or recalls.</p>
          ) : (
            <div className="act-split">
              <section className="surface sq" aria-label="Active days">
                <div className="days-head" aria-hidden="true"><span>Day</span><span>Recalls</span><span>Saved</span></div>
                <ul className="days-list">
                  {live.map((d) => (
                    <li key={d.date}>
                      <button type="button" aria-pressed={d.date === day} onClick={() => setPicked(d.date)}>
                        <b>{seen(d.date)}</b>
                        <span className="n">{num(d.prompts_given_memories)}</span>
                        <span className="n">{num(d.saved)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
              <section className="tbl-card surface sq" aria-labelledby="day-title">
                <h2 id="day-title">
                  {day && shortDate(day)}
                  {chosen && (
                    <span className="note">{num(chosen.prompts_given_memories)} recalls · {num(chosen.saved)} saved · {num(chosen.sessions)} sessions</span>
                  )}
                </h2>
                {recalls.length === 0 ? (
                  <p className="empty">The recall log keeps the latest recalls only; none of them is from this day.</p>
                ) : (
                  <table className="gtbl">
                    <colgroup><col style={{ width: 92 }} /><col style={{ width: 140 }} /><col style={{ width: 170 }} /><col /></colgroup>
                    <thead><tr><th scope="col">Time</th><th scope="col">Event</th><th scope="col">Project</th><th scope="col">Memories given</th></tr></thead>
                    <tbody>
                      {recalls.map((r) => (
                        <tr key={`${r.t}-${r.event}`}>
                          <td className="mono">{new Date(r.t).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</td>
                          <td>
                            <span className="ev-ic">
                              {r.event === "pack" ? <PlayCircle size={13} strokeWidth={1.9} /> : <MessageSquareText size={13} strokeWidth={1.9} />}
                              {r.event === "pack" ? "Session start" : "Prompt"}
                            </span>
                          </td>
                          <td><Tip tip={r.project && r.project.length > 20 ? r.project : null}><span className="t">{clip(r.project ?? "–", 20)}</span></Tip></td>
                          <td>
                            <div className="mem-refs">
                              {r.memories.map((m) => (
                                <div key={m.id} className="mem-ref">
                                  <span className="mono id">#{m.id}</span>
                                  {m.gone ? <span /> : <KindIcon kind={m.kind} small />}
                                  {m.gone ? <span className="dimmed">no longer in memory</span> : (
                                    <Tip tip={<>{m.text}<br /><span className="dimmed">{m.kind} · {m.scope} · {m.observed_at}</span></>}>
                                      <span className="t">{clip(m.text, 110)}</span>
                                    </Tip>
                                  )}
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </section>
            </div>
          )}

          {data.most_used?.length > 0 && (
            <section className="tbl-card surface sq" aria-labelledby="most-title">
              <h2 id="most-title"><Sparkle size={14} strokeWidth={1.9} className="ok" /> Most recalled</h2>
              <table className="gtbl">
                <colgroup><col style={{ width: 64 }} /><col style={{ width: 40 }} /><col /><col style={{ width: 160 }} /><col style={{ width: 80 }} /></colgroup>
                <thead><tr><th scope="col">#</th><th scope="col"><span className="sr-only">Kind</span></th><th scope="col">Memory</th><th scope="col">Scope</th><th scope="col" className="num">Times</th></tr></thead>
                <tbody>
                  {data.most_used.map((m) => (
                    <tr key={m.id}>
                      <td className="mono id">#{m.id}</td>
                      <td>{m.memory && <KindIcon kind={m.memory.kind} small />}</td>
                      <td>
                        {m.memory ? (
                          <Tip tip={m.memory.text.length > 120 ? m.memory.text : null}><span className="t">{clip(m.memory.text, 120)}</span></Tip>
                        ) : <span className="dimmed">no longer in memory</span>}
                      </td>
                      <td>{m.memory ? clip(m.memory.scope, 22) : "–"}</td>
                      <td className="num mono">{num(m.times)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </div>
  );
}
