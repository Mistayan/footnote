import { useCallback, useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, ChevronRight as Chev, FolderTree, Heart, Layers, Lightbulb, MessagesSquare, Search, Wrench } from "lucide-react";
import { footnote, num } from "./data.js";
import { Select, Tip, Trash, Verdict, clip } from "./ui.jsx";

const KINDS = ["", "preference", "fact", "fix", "session"];
const PAGE = 50;
const KIND_ICON = { preference: Heart, fact: Lightbulb, fix: Wrench, session: MessagesSquare };

/** A memory's kind as a pictogram in its own colour; the word is in the tooltip and for screen readers. */
export function KindIcon({ kind, small }) {
  const Icon = KIND_ICON[kind] ?? Layers;
  return (
    <Tip tip={kind}>
      <span className={`kind-ic ${kind}`} role="img" aria-label={kind} style={small ? { width: 20, height: 20 } : undefined}>
        <Icon size={small ? 11 : 13} strokeWidth={2} />
      </span>
    </Tip>
  );
}

/** A memory has no title: its first sentence, cut to one line, stands for it. */
const nameOf = (text) => clip(String(text).split(/(?<=[.!?])\s|\n/)[0], 140);

export default function Memory({ refresh }) {
  const [project, setProject] = useState("");
  const [kind, setKind] = useState("");
  const [filter, setFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const [round, setRound] = useState(0);
  const [state, setState] = useState({ loading: true });
  const [busyId, setBusyId] = useState(null);
  const [open, setOpen] = useState(() => new Set());

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
      setRound((r) => r + 1);
      refresh?.();
    } catch (e) {
      setState((s) => ({ ...s, error: String(e) }));
    } finally {
      setBusyId(null);
    }
  };
  const flip = (id) => setOpen((o) => {
    const n = new Set(o);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  const data = state.data;
  const q = filter.trim().toLowerCase();
  const memories = (data?.memories ?? []).filter(
    (m) => !q || m.text.toLowerCase().includes(q) || (m.scope ?? "").toLowerCase().includes(q) || (m.tags ?? []).some((t) => t.toLowerCase().includes(q)),
  );
  const total = data?.total ?? 0;
  const scopes = [{ value: "", label: "All scopes", hint: num(total) }, ...(data?.scopes ?? []).map((s) => ({ value: s.scope, label: s.scope, hint: num(s.memories) }))];
  const kinds = KINDS.map((k) => ({ value: k, label: k || "All kinds" }));

  return (
    <div className="body">
      <div className="toolbar">
        <label className="search-box">
          <Search size={14} strokeWidth={1.9} aria-hidden="true" />
          <input className="input" placeholder="Filter this page" value={filter} onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter the memories on this page" />
        </label>
        <Select value={project} options={scopes} onChange={(v) => { setProject(v); setOffset(0); }} label="Scope" icon={FolderTree} />
        <Select value={kind} options={kinds} onChange={(v) => { setKind(v); setOffset(0); }} label="Kind" icon={Layers} />
        <span className="count">{data ? `${num(memories.length)} of ${num(total)}` : ""}</span>
        {total > PAGE && (
          <span className="pager">
            <Tip tip="Previous page">
              <button type="button" className="ic-btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))} aria-label="Previous page">
                <ChevronLeft size={15} strokeWidth={1.9} />
              </button>
            </Tip>
            <span className="dimmed small mono">{offset + 1}–{Math.min(offset + PAGE, total)}</span>
            <Tip tip="Next page">
              <button type="button" className="ic-btn" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)} aria-label="Next page">
                <ChevronRight size={15} strokeWidth={1.9} />
              </button>
            </Tip>
          </span>
        )}
      </div>

      {pending.length > 0 && (
        <section className="group sub" aria-labelledby="review-title" style={{ marginTop: 0 }}>
          <h2 id="review-title" className="heading">
            Waiting for your review<span className="count">{pending.length}</span>
          </h2>
          <p className="dimmed small">Global preferences an agent saved. None is used until you approve it.</p>
          <ul className="memos">
            {pending.map((m) => (
              <Row key={m.id} m={m} open={open.has(m.id)} flip={() => flip(m.id)} review>
                <Verdict what={`memory #${m.id}`} busy={busyId === m.id} approveTip="Approve: agents may use it"
                  rejectTip="Reject: forget it" onApprove={() => forget(m.id, "memory-restore")} onReject={() => forget(m.id)} />
              </Row>
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
        <ul className="memos" aria-label="Memories">
          {memories.map((m) => (
            <Row key={m.id} m={m} open={open.has(m.id)} flip={() => flip(m.id)}
              trash={<Trash what={`memory #${m.id}`} busy={busyId === m.id} onConfirm={() => forget(m.id)} />} />
          ))}
        </ul>
      )}
    </div>
  );
}

/** One memory: chevron, id, kind, its name, scope, date and the trash; a click opens the full text below. */
function Row({ m, open, flip, review, trash, children }) {
  const body = `memo-${m.id}`;
  return (
    <li className={`memo surface sq lit${review ? " review" : ""}`} data-open={open}>
      <div className="memo-head" onClick={flip}>
        <Chev size={14} strokeWidth={2} className="memo-chev" aria-hidden="true" />
        <span className="memo-id">#{m.id}</span>
        <KindIcon kind={m.kind} />
        <button type="button" className="memo-name" aria-expanded={open} aria-controls={body}
          onClick={(e) => { e.stopPropagation(); flip(); }}>
          {nameOf(m.text)}
        </button>
        <Tip tip={m.scope.length > 22 ? m.scope : null}><span className="chip memo-scope">{clip(m.scope, 22)}</span></Tip>
        <span className="memo-date">{m.observed_at}</span>
        <span className="memo-actions" onClick={(e) => e.stopPropagation()}>{review ? children : trash}</span>
      </div>
      <div className="memo-body" id={body} role="region" aria-label={`Memory #${m.id}`} inert={!open}>
        <div>
          <p className="memo-text">{m.text}</p>
          <div className="memo-meta">
            <span>{m.kind}</span>
            <span>{m.scope}</span>
            {m.origin && <span>from {m.origin}</span>}
            {m.tags?.map((t) => <span key={t} className="mono">#{t}</span>)}
          </div>
        </div>
      </div>
    </li>
  );
}
