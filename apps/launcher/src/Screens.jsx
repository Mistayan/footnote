import { useEffect, useState } from "react";
import { cancelInstall, footnote, mb, num, seen, shortDate } from "./data.js";

// The workspace screens: Projects, Models, Activity and Usage. Each reads its own engine command; nothing is written.

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

function Range({ days, setDays, options = [7, 30, 90] }) {
  return (
    <div className="tabs" role="tablist" aria-label="Period">
      {options.map((d) => (
        <button key={d} role="tab" aria-selected={days === d} className="tab" onClick={() => setDays(d)}>
          {d === 1 ? "1 day" : `${d} days`}
        </button>
      ))}
    </div>
  );
}

const Failed = ({ error }) => (
  <p className="empty warn" role="alert">{error === "ENGINE_MISSING" ? "The Footnote engine was not found." : error}</p>
);

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
  const todo = (list ?? []).filter((p) => p.exists && !p.code_graph).map((p) => p.path);
  if (!list) return <div className="body"><span className="skel" /></div>;
  return (
    <div className="body">
      <p className="dimmed">
        Every folder where an agent started a session with Footnote Memory on. Git counts are read when this screen opens.
      </p>
      {todo.length > 0 && (
        <p>
          <button className="btn" disabled={busy !== null} onClick={() => index(todo)}>
            {busy ? "Indexing…" : `Index ${todo.length} project${todo.length === 1 ? "" : "s"} without a code graph`}
          </button>
        </p>
      )}
      {error && <p className="empty warn" role="alert">{error}</p>}
      {list.length === 0 ? (
        <p className="empty">No project yet. A project appears here when an agent starts a session in it.</p>
      ) : (
        <table className="tbl">
          <thead>
            <tr>
              <th scope="col">Project</th>
              <th scope="col">Folder</th>
              <th scope="col">First seen</th>
              <th scope="col">Last seen</th>
              <th scope="col" className="num">Memories</th>
              <th scope="col">Code graph</th>
              <th scope="col" className="num">Uncommitted</th>
              <th scope="col" className="num">Unpushed</th>
            </tr>
          </thead>
          <tbody>
            {list.map((p) => (
              <tr key={p.path}>
                <td>{p.name}</td>
                <td className="mono" title={p.path}>{p.exists ? p.path : <span className="warn">{p.path} (missing)</span>}</td>
                <td>{shortDate(p.first_seen)}</td>
                <td>{seen(p.last_seen)}</td>
                <td className="num">{num(p.memories)}</td>
                <td className={p.code_graph ? "ok" : ""}>
                  {p.code_graph ? "built" : busy === p.path ? "indexing…" : p.exists ? (
                    <button className="btn" disabled={busy !== null} onClick={() => index([p.path])}>Index</button>
                  ) : "–"}
                </td>
                <td className={p.git?.uncommitted > 0 ? "num warn" : "num"}>{p.git ? num(p.git.uncommitted) : "–"}</td>
                <td className={p.git?.unpushed > 0 ? "num warn" : "num"}>{p.git ? num(p.git.unpushed) : "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
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
    const key = names.join("+");
    setSwitching(key);
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
  if (!data) return <div className="body"><span className="skel" /></div>;
  const active = data.models.filter((m) => m.used_by_memory).map((m) => m.name);
  const defaultPairInstalled = ["bekko-a8m", "gte-small"].every((n) => data.models.some((m) => m.name === n && m.installed));
  const isDefaultPair = active.length === 2 && active.includes("bekko-a8m") && active.includes("gte-small");
  return (
    <div className="body">
      <div className="bar wrap">
        <p className="dimmed" style={{ flex: 1, minWidth: 260 }}>
          Embedding models run locally on this computer. Active for Memory:{" "}
          <b style={{ color: "var(--text)" }}>{active.length ? active.join(" + ") : "none"}</b>.
        </p>
        {defaultPairInstalled && !isDefaultPair && (
          <button type="button" className="btn" disabled={!!switching} onClick={() => useModels(["bekko-a8m", "gte-small"])}>
            {switching === "bekko-a8m+gte-small" ? "Switching…" : "Use default pair (bekko-a8m + gte-small)"}
          </button>
        )}
      </div>
      {switchNote && <p className={switchNote.startsWith("Error:") ? "warn small" : "ok small"}>{switchNote}</p>}
      <table className="tbl">
        <thead>
          <tr>
            <th scope="col">Model</th>
            <th scope="col">Role</th>
            <th scope="col">Licence</th>
            <th scope="col">State</th>
            <th scope="col" className="num">Size</th>
          </tr>
        </thead>
        <tbody>
          {data.models.map((m) => (
            <tr key={m.name}>
              <td className="mono">{m.name}</td>
              <td>{m.role}</td>
              <td className={/no commercial/i.test(m.license) ? "warn" : ""}>{m.license}</td>
              <td>
                {m.installed ? (
                  m.used_by_memory ? (
                    <span className="pill-ok">Active · used by Memory</span>
                  ) : (
                    <span className="model-actions">
                      <span className="dimmed small">installed</span>
                      <button
                        className="btn"
                        type="button"
                        disabled={!!switching}
                        onClick={() => useModels([m.name])}
                      >
                        {switching === m.name ? "Switching…" : "Use for Memory"}
                      </button>
                    </span>
                  )
                ) : busy?.name === m.name ? (
                  <Download busy={busy} total={m.download_bytes} cancel={cancel} retry={() => install(m.name)} />
                ) : (
                  <button className="btn" type="button" disabled={!!busy && !busy.error && !busy.cancelled}
                    onClick={() => install(m.name)} aria-label={`Install ${m.name}, ${m.download_bytes ? mb(m.download_bytes) : "size unknown"}`}>
                    Install{m.download_bytes ? ` · ${mb(m.download_bytes)}` : ""}
                  </button>
                )}
              </td>
              <td className="num">{m.installed && m.bytes ? mb(m.bytes) : m.download_bytes ? <span className="dimmed">{mb(m.download_bytes)}</span> : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="dimmed mono">{data.folder}</p>
    </div>
  );
}

/** One model's download: progress of the file being fetched, then the outcome. A cancelled or failed install leaves no model
 * behind (the engine renames each file only once it is complete and its hash checked). */
function Download({ busy, total, cancel, retry }) {
  if (busy.cancelled) return <span className="dimmed">Cancelled. Nothing was installed. <button className="btn" type="button" onClick={retry}>Install again</button></span>;
  if (busy.error) return <span className="warn" role="alert">{busy.error} <button className="btn" type="button" onClick={retry}>Try again</button></span>;
  const p = busy.progress;
  const pct = p?.total ? Math.min(100, Math.round((100 * p.done) / p.total)) : null;
  return (
    <span className="dl">
      <progress max={100} value={pct ?? undefined} aria-label={`Downloading ${busy.name}`} />
      <span className="mono dimmed">{p ? `${mb(p.done)}${p.total ? ` of ${mb(p.total)}` : ""}` : total ? `starting · ${mb(total)}` : "starting"}</span>
      <button className="btn" type="button" onClick={cancel}>Cancel</button>
    </span>
  );
}

export function Activity() {
  const [days, setDays] = useState(30);
  const { data, error } = useRead(["activity", "--days", String(days)]);
  const rows = (data?.days ?? []).slice().reverse();
  return (
    <div className="body">
      <div className="bar">
        <Range days={days} setDays={setDays} />
        {data?.note && <span className="dimmed">{data.note}</span>}
      </div>
      {error ? <Failed error={error} /> : !data ? <span className="skel" /> : (
        <div className="split">
          <table className="tbl">
            <thead>
              <tr>
                <th scope="col">Day</th>
                <th scope="col" className="num">Memories saved</th>
                <th scope="col" className="num">Prompts given memories</th>
                <th scope="col" className="num">Sessions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.date}>
                  <td className="mono">{shortDate(d.date)}</td>
                  <td className="num">{num(d.saved)}</td>
                  <td className="num">{num(d.prompts_given_memories)}</td>
                  <td className="num">{num(d.sessions)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <aside className="panel">
            <h2 className="title">Most recalled</h2>
            {data.most_used.length === 0 ? <p className="dimmed">No memory recalled yet.</p> : (
              <ul className="plain">
                {data.most_used.map((m) => (
                  <li key={m.id} className="place" title={m.memory?.text ?? ""}>
                    <span><span className="mono id">#{m.id}</span> {m.memory ? m.memory.text : <span className="dimmed">no longer in memory</span>}</span>
                    <span className="dimmed">{num(m.times)} times{m.memory ? ` · ${m.memory.kind} · ${m.memory.scope}` : ""}</span>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </div>
      )}
      {data?.recent?.length > 0 && (
        <>
          <h2 className="section">Recent recalls</h2>
          <ul className="hits" aria-label="Recent recalls, newest first">
            {data.recent.map((r) => (
              <li key={`${r.t}-${r.event}`}>
                <span className="dimmed small">
                  {new Date(r.t).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                  {" · "}{r.event === "pack" ? "session start" : "prompt"}{r.project ? ` · ${r.project}` : ""}
                </span>
                {r.memories.map((m) => (
                  <span key={m.id} className="t">
                    <span className="mono id">#{m.id}</span>{" "}
                    {m.gone ? <span className="dimmed">no longer in memory</span> : <>{m.text} <span className="dimmed small">{m.kind} · {m.scope} · {m.observed_at}</span></>}
                  </span>
                ))}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
