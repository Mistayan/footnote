import { useEffect, useId, useState } from "react";
import {
  Brain,
  Check,
  CircleAlert,
  ExternalLink,
  GitCommitHorizontal,
  GitFork,
  Loader2,
  MessageSquareText,
  PlayCircle,
  ScanSearch,
  Sparkle,
} from "lucide-react";
import { cancelInstall, footnote, mb, num, openLicense, openProjectFolder, seen, shortDate } from "./data.js";
import { KindIcon } from "./Memory.jsx";
import { PathPill, Tabs, Tip, clip, toast } from "./ui.jsx";

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

/** The request the commit pictogram copies for the agent working in that folder. */
const commitAsk = (p) =>
  `In ${p.path}: review the ${p.git.uncommitted} uncommitted change${p.git.uncommitted === 1 ? "" : "s"}, commit them in ` +
  "logical commits with clear messages, then push the branch. Ask me before anything destructive.";

/** One project as a glass card: name, folder (drive squircle + last folder, opens the folder), then pictograms for its
 * memories, code graph and uncommitted changes. Each pictogram explains itself on hover. */
export function ProjectCard({ p, busy, onIndex }) {
  const open = () => openProjectFolder(p.path).catch((e) => toast(String(e), "warn"));
  const copyAsk = async () => {
    try {
      await navigator.clipboard.writeText(commitAsk(p));
      toast(`Copied a commit-and-push request for ${p.name}. Paste it to your agent.`);
    } catch {
      toast("The clipboard is not available here.", "warn");
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
        {p.git && (dirty > 0 ? (
          <Tip tip={`${num(dirty)} uncommitted change${dirty === 1 ? "" : "s"}. Click to copy a commit-and-push request for your agent.`}>
            <button type="button" className="stat bad" onClick={copyAsk} aria-label={`${num(dirty)} uncommitted changes in ${p.name}: copy a commit request`}>
              <span className="stat-ic"><GitCommitHorizontal size={13} strokeWidth={2.2} /></span>{num(dirty)}
            </button>
          </Tip>
        ) : (
          <Tip tip="Everything is committed">
            <span className="stat idle on" tabIndex={0} role="img" aria-label="Everything is committed">
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
  const todo = list.filter((p) => p.exists && !p.code_graph).map((p) => p.path);
  const graphs = list.filter((p) => p.code_graph).length;
  const memories = list.reduce((n, p) => n + (p.memories ?? 0), 0);
  const dirty = list.filter((p) => p.git?.uncommitted > 0);
  return (
    <div className="body">
      <section className="hero lglass sq">
        <div>
          <div className="kicker">Projects</div>
          <div className="big">{num(list.length)}</div>
          <div className="sub">Every folder where an agent started a session with Memory on.</div>
        </div>
        <div className="kpis">
          <div className="kpi"><span><Brain size={12} strokeWidth={1.9} /> Memories</span><b>{num(memories)}</b></div>
          <div className="kpi"><span><GitFork size={12} strokeWidth={1.9} /> Code graphs</span><b>{num(graphs)}<span className="dimmed small"> / {num(list.length)}</span></b></div>
          <div className="kpi">
            <span><GitCommitHorizontal size={12} strokeWidth={1.9} /> To commit</span>
            <b className={dirty.length ? "bad" : "ok"}>{dirty.length ? num(dirty.length) : "None"}</b>
          </div>
          {todo.length > 0 && (
            <button type="button" className="btn primary" disabled={busy !== null} onClick={() => index(todo)} style={{ alignSelf: "center" }}>
              {busy ? "Indexing…" : `Index ${todo.length} without a graph`}
            </button>
          )}
        </div>
      </section>
      {error && <p className="empty warn" role="alert">{error}</p>}
      {list.length === 0 ? (
        <p className="empty">No project yet. A project appears here when an agent starts a session in it.</p>
      ) : (
        <div className="proj-grid">
          {list.map((p) => <ProjectCard key={p.path} p={p} busy={busy} onIndex={(path) => index([path])} />)}
        </div>
      )}
    </div>
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
          {defaultPairInstalled && !isDefaultPair && (
            <button type="button" className="btn primary" disabled={!!switching} onClick={() => useModels(["bekko-a8m", "gte-small"])}>
              {switching === "bekko-a8m+gte-small" ? "Switching…" : "Use the default pair"}
            </button>
          )}
        </div>
      </section>
      {switchNote && <p className={switchNote.startsWith("Error:") ? "warn small" : "ok small"} role="status">{switchNote}</p>}
      <div className="models">
        <div className="row-head" aria-hidden="true"><span>Model</span><span>Use</span><span>Licence</span><span>State</span><span className="num-r">Size</span></div>
        <ul className="rows" aria-label="Models">
          {data.models.map((m) => (
            <li key={m.name} className="line-row surface sq lit">
              <span className="cell-name mono">{m.name}</span>
              <Tip tip={m.role.length > 40 ? m.role : null}><span className="cell-dim">{m.role}</span></Tip>
              <span><License license={m.license} /></span>
              <span>
                {m.installed ? (
                  m.used_by_memory ? (
                    <span className="state-dot">Active</span>
                  ) : (
                    <span className="cell-end" style={{ justifySelf: "start" }}>
                      <span className="state-dot idle">Installed</span>
                      <button className="btn" type="button" disabled={!!switching} onClick={() => useModels([m.name])}>
                        {switching === m.name ? "Switching…" : "Use"}
                      </button>
                    </span>
                  )
                ) : busy?.name === m.name ? (
                  <Download busy={busy} total={m.download_bytes} cancel={cancel} retry={() => install(m.name)} />
                ) : (
                  <button className="btn" type="button" disabled={!!busy && !busy.error && !busy.cancelled}
                    onClick={() => install(m.name)} aria-label={`Install ${m.name}, ${m.download_bytes ? mb(m.download_bytes) : "size unknown"}`}>
                    Install
                  </button>
                )}
              </span>
              <span className="num-r mono small">
                {m.installed && m.bytes ? mb(m.bytes) : m.download_bytes ? <span className="dimmed">{mb(m.download_bytes)}</span> : "–"}
              </span>
            </li>
          ))}
        </ul>
      </div>
      <div className="bar">
        <PathPill path={data.folder} keep={2} />
        {onDisk > 0 && <span className="dimmed small" style={{ marginLeft: "auto" }}>{mb(onDisk)} on disk</span>}
      </div>
    </div>
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
