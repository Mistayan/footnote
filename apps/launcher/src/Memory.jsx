import { useCallback, useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { footnote, num } from "./data.js";

const KINDS = ["", "preference", "fact", "fix", "session"];
const PAGE = 50;

export default function Memory({ refresh }) {
  const [project, setProject] = useState("");
  const [kind, setKind] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [round, setRound] = useState(0);
  const [state, setState] = useState({ loading: true });
  const [confirmId, setConfirmId] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const loadList = useCallback(() => {
    const args = ["memory-list"];
    if (project) args.push("--project", project);
    if (kind) args.push("--kind", kind);
    args.push("--limit", String(PAGE), "--offset", String(offset));
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    footnote(...args).then(
      (data) => live && setState({ loading: false, data }),
      (error) => live && setState({ loading: false, error: String(error) }),
    );
    return () => { live = false; };
  }, [project, kind, offset]);

  useEffect(() => loadList(), [loadList, round]);

  // Global preferences agents saved wait here until the user approves (memory-restore) or rejects (forget) them (#207).
  const [pending, setPending] = useState([]);
  useEffect(() => {
    let live = true;
    footnote("memory-review").then((r) => live && setPending(r.pending ?? []), () => live && setPending([]));
    return () => { live = false; };
  }, [round]);

  const forget = async (id, cmd = "forget") => {
    setBusyId(id);
    try {
      await footnote(cmd, String(id));
      setConfirmId(null);
      setRound((r) => r + 1);
      refresh?.();
    } catch (e) {
      setState((s) => ({ ...s, error: String(e) }));
    } finally {
      setBusyId(null);
    }
  };

  const data = state.data;
  const q = filter.trim().toLowerCase();
  const memories = (data?.memories ?? []).filter(
    (m) => !q || m.text.toLowerCase().includes(q) || (m.scope ?? "").toLowerCase().includes(q) || (m.tags ?? []).some((t) => t.toLowerCase().includes(q)),
  );
  const total = data?.total ?? 0;

  return (
    <div className="body">
      <div className="bar wrap">
        <input
          className="input"
          style={{ maxWidth: 300 }}
          placeholder="Filter visible memories…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          aria-label="Filter memories"
        />
        <select
          className="btn"
          value={project}
          onChange={(e) => { setProject(e.target.value); setOffset(0); }}
          aria-label="Filter by scope"
        >
          <option value="">All scopes ({num(total)})</option>
          {(data?.scopes ?? []).map((s) => (
            <option key={s.scope} value={s.scope}>{s.scope} ({num(s.memories)})</option>
          ))}
        </select>
        <select
          className="btn"
          value={kind}
          onChange={(e) => { setKind(e.target.value); setOffset(0); }}
          aria-label="Filter by kind"
        >
          {KINDS.map((k) => (
            <option key={k || "all"} value={k}>{k ? k : "All kinds"}</option>
          ))}
        </select>
        <span className="dimmed small" style={{ marginLeft: "auto" }}>
          {data ? `Showing ${memories.length} of ${num(total)}` : ""}
        </span>
      </div>

      {pending.length > 0 && (
        <section className="group sub" aria-labelledby="review-title">
          <h2 id="review-title" className="heading">
            Waiting for your review<span className="count">{pending.length}</span>
          </h2>
          <p className="dimmed small">Global preferences an agent saved. None is used until you approve it.</p>
          <ul className="hits mem-list review-list">
            {pending.map((m) => (
              <li key={m.id} className="mem-row">
                <div className="mem-head">
                  <span className="mono id">#{m.id}</span>
                  <span className="chip">{m.kind}</span>
                  <span className="dimmed mono small">{m.observed_at}</span>
                  <div className="mem-actions">
                    <button type="button" className="btn primary" disabled={busyId === m.id} onClick={() => forget(m.id, "memory-restore")}>
                      Approve
                    </button>
                    <button type="button" className="btn" disabled={busyId === m.id} onClick={() => forget(m.id)}>
                      Reject
                    </button>
                  </div>
                </div>
                <p className="mem-text">{m.text}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {state.error ? (
        <p className="empty warn" role="alert">{state.error}</p>
      ) : state.loading && !data ? (
        <span className="skel" />
      ) : memories.length === 0 ? (
        <p className="empty">No memories match this filter.</p>
      ) : (
        <ul className="hits mem-list">
          {memories.map((m) => (
            <li key={m.id} className="mem-row">
              <div className="mem-head">
                <span className="mono id">#{m.id}</span>
                <span className="chip">{m.kind}</span>
                <span className="chip">{m.scope}</span>
                <span className="dimmed mono small">{m.observed_at}</span>
                {m.origin && <span className="dimmed small">· {m.origin}</span>}
                <div className="mem-actions">
                  {confirmId === m.id ? (
                    <>
                      <button
                        type="button"
                        className="btn warn-btn"
                        disabled={busyId === m.id}
                        onClick={() => forget(m.id)}
                      >
                        {busyId === m.id ? "Forgetting…" : "Confirm forget"}
                      </button>
                      <button type="button" className="btn" onClick={() => setConfirmId(null)}>Cancel</button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className="btn icon-btn"
                      title="Forget this memory"
                      onClick={() => setConfirmId(m.id)}
                    >
                      <Trash2 size={13} strokeWidth={1.75} />
                      Forget
                    </button>
                  )}
                </div>
              </div>
              <p className="mem-text">{m.text}</p>
              {m.tags?.length > 0 && (
                <div className="mem-tags">
                  {m.tags.map((t) => <span key={t} className="dimmed mono small">#{t}</span>)}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {total > PAGE && (
        <div className="bar">
          <button type="button" className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            Previous
          </button>
          <span className="dimmed small">
            {offset + 1}–{Math.min(offset + PAGE, total)} of {num(total)}
          </span>
          <button type="button" className="btn" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}
