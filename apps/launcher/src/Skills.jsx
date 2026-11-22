import { useEffect, useRef, useState } from "react";
import { footnote, openReceipt, openSkillFolder, shortDate } from "./data.js";

// Skills: whether agents may change the skills they use (`memory.skill_rewrite`, #457), and the changes to skill scripts that
// wait for the user. The switch's gain and cost are the engine's own catalogue text (`footnote options`), never a copy here.
// Approving serves a change; nothing in the window or the engine runs the scripts it holds. The review happens here: each
// change shows its line diff (`footnote skills diff`, #472) and opens its folder.

const OPTION = "memory.skill_rewrite";
const NAME = "Agents may change skills";

function useReads(round) {
  const [state, setState] = useState({ loading: true });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    Promise.all([footnote("options"), footnote("memory-review")]).then(
      ([options, review]) =>
        live && setState({ option: options.options.find((o) => o.key === OPTION), pending: review.skills_pending ?? [] }),
      (error) => live && setState({ error: String(error) }),
    );
    return () => { live = false; };
  }, [round]);
  return state;
}

/** A measurement report in this repository, which the window can open on the project's site. */
const RECEIPT = /^bench\/experiments\/[A-Za-z0-9._-]+\.md$/;

/** Catalogue text, with its `command` spans shown as code (a measurement report opens), ending with one full stop. */
const Text = ({ children }) =>
  String(children)
    .replace(/\.?$/, ".")
    .split("`")
    .map((part, i) =>
      i % 2 === 0 ? part
      : RECEIPT.test(part) ? (
        <button key={i} type="button" className="receipt" onClick={() => openReceipt(part)}
          aria-label={`Open the measurement ${part.split("/").pop()}`}>
          the measurement <span aria-hidden="true">↗</span>
        </button>
      ) : <code key={i} className="mono">{part}</code>);

const Failed = ({ error }) => (
  <p className="empty warn" role="alert">{error === "ENGINE_MISSING" ? "The Footnote engine was not found." : error}</p>
);

/** The screen's shape while it reads: the option card, the heading and one change. */
const Loading = () => (
  <div className="body skills" aria-busy="true">
    <span className="sr-only" role="status">Reading skills…</span>
    <div className="card setting skel-card">
      <span className="skel w30" />
      {["w70", "w70", "w70", "w40", "w70", "w70", "w70", "w40"].map((w, i) => <span key={i} className={`skel prose ${w}`} />)}
    </div>
    <div className="group"><span className="skel line w30" /><span className="skel-para"><span className="skel w70" /><span className="skel w40" /></span><div className="change skel-card"><span className="skel w30" /><span className="skel" /></div></div>
  </div>
);

export default function Skills({ onChange }) {
  const [round, setRound] = useState(0);
  const { option, pending, error, loading } = useReads(round);
  const reread = () => {
    setRound((r) => r + 1);
    onChange?.();
  };
  if (error) return <div className="body skills"><Failed error={error} /></div>;
  if (loading && !option && !pending) return <Loading />;
  return (
    <div className="body skills">
      {option ? <Rewrite option={option} done={reread} /> : (
        <p className="empty">This engine cannot let agents change skills. Update Footnote to get it.</p>
      )}
      <section className="group" aria-labelledby="pending-title">
        <h2 id="pending-title" className="heading">
          Changes waiting for you{pending?.length ? <span className="count">{pending.length}</span> : null}
          {pending?.length > 0 && option && option.value !== true && (
            <span className="note">proposed while agents could change skills</span>
          )}
        </h2>
        <Pending list={pending} option={option} done={reread} />
      </section>
    </div>
  );
}

/** The switch. Turning it on asks once, with the cost; turning it off is immediate. A company policy can lock it. */
function Rewrite({ option, done }) {
  const on = option.value === true;
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const toggle = useRef(null);
  const cancel = () => {
    setAsking(false);
    requestAnimationFrame(() => toggle.current?.focus());
  };
  const set = async (value) => {
    setBusy(true);
    setError(null);
    try {
      await footnote("config", "set", OPTION, String(value));
      setAsking(false);
      done();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="card setting" aria-labelledby="rewrite-title">
      <div className="title">
        <h2 id="rewrite-title">{NAME}</h2>
        {option.locked ? (
          <span className="locked">
            <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12"><rect x="2" y="5.5" width="8" height="5.5" rx="1.5" fill="currentColor" /><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5" fill="none" stroke="currentColor" strokeWidth="1.3" /></svg>
            {on ? "On" : "Off"}, set by your company
          </span>
        ) : (
          <span className="toggle">
            <span aria-hidden="true">{on ? "On" : "Off"}</span>
            <button ref={toggle} type="button" role="switch" aria-checked={on} aria-labelledby="rewrite-title" className="switch"
              disabled={busy || asking} onClick={() => (on ? set(false) : setAsking(true))}>
              <span aria-hidden="true" />
            </button>
          </span>
        )}
      </div>
      {option.locked && option.reason && (
        <p className="policy"><strong>Your company's policy:</strong> <Text>{option.reason}</Text></p>
      )}
      <p className="copy"><Text>{option.gain}</Text></p>
      <p className="copy cost"><strong>Cost.</strong> <Text>{option.cost}</Text></p>
      {asking && (
        <div className="confirm" role="group" aria-labelledby="confirm-title" aria-describedby="confirm-cost"
          onKeyDown={(e) => e.key === "Escape" && cancel()}>
          <p id="confirm-title"><strong>Let agents change skills?</strong></p>
          <p id="confirm-cost">
            Each change request costs one more agent turn (the cost above), at most once a session and only after a skill's script fails. You can
            turn this off here at any time.
          </p>
          <div className="actions">
            <button type="button" className="btn primary" disabled={busy} onClick={() => set(true)} autoFocus>
              Turn on
            </button>
            <button type="button" className="btn" disabled={busy} onClick={cancel}>Cancel</button>
          </div>
        </div>
      )}
      {error && <p className="copy warn" role="alert">{error}</p>}
    </section>
  );
}

/** What fills an empty list depends on whether agents can propose changes at all. */
function nothing(option) {
  if (option?.locked && option.value !== true) return "Your company keeps this off, so no agent change can arrive here.";
  if (option && option.value !== true) return "No change is waiting. Once agents may change skills, a change to a skill's scripts waits here for you.";
  return "No change is waiting. When an agent changes a skill's scripts, the change waits here until you approve or reject it.";
}

/** Agents' changes to skill scripts, held until the user serves or refuses each one. */
function Pending({ list, option, done }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  if (!list) return null;
  if (list.length === 0) return <p className="empty"><span>{nothing(option)}</span></p>;
  const act = async (verb, s) => {
    setBusy(`${s.name}@${s.scope}`);
    setError(null);
    try {
      await footnote(...args(verb, s));
      done();
    } catch (e) {
      setError(`${s.name}: ${e}`);
    } finally {
      setBusy(null);
    }
  };
  return (
    <>
      <p className="copy">
        Approving serves the change to every later session in its scope. Read what it changes first: Footnote never runs a
        skill's scripts itself.
      </p>
      <ul className="changes">
        {list.map((s) => (
          <Change key={`${s.name}@${s.scope}`} s={s} busy={busy} act={act} />
        ))}
      </ul>
      {error && <p className="empty warn" role="alert">{error}</p>}
    </>
  );
}

const args = (verb, s) => ["skills", verb, s.name, ...(s.scope === "global" ? [] : ["--project", s.scope])];

/** One pending change: why, what, the diff on demand, and the decision. */
function Change({ s, busy, act }) {
  const key = `${s.name}@${s.scope}`;
  const [open, setOpen] = useState(false);
  const [diff, setDiff] = useState(null);
  const [note, setNote] = useState(null);
  const show = async () => {
    setOpen((o) => !o);
    if (diff) return;
    try {
      setDiff(await footnote(...args("diff", s)));
    } catch (e) {
      setDiff({ error: String(e) });
    }
  };
  const folder = () => openSkillFolder(s.name, s.scope).catch((e) => setNote(String(e)));
  const id = `diff-${key.replace(/[^a-z0-9]/gi, "-")}`;
  return (
    <li className="change">
      <div className="head">
        <span className="mono name">{s.name}</span>
        <span>
          {s.scope === "global" ? "every project" : `project ${s.scope}`} · revision {s.revision}
          {s.at && <> · proposed by an agent on {shortDate(s.at.slice(0, 10))}</>}
        </span>
      </div>
      <p>{s.reason}</p>
      <p className="files">Changes {(s.changed ?? []).map((f, i) => <code key={f} className="mono">{i ? `, ${f}` : f}</code>)}</p>
      {open && <Diff id={id} diff={diff} folder={folder} />}
      {note && <p className="warn" role="alert">{note}</p>}
      <div className="actions">
        <button type="button" className="btn wide" aria-expanded={open} aria-controls={id} onClick={show}
          aria-label={`${open ? "Hide" : "Show"} the changes to ${s.name}`}>
          {open ? "Hide the changes" : "Show the changes"}
        </button>
        <button type="button" className="btn" onClick={folder} title={s.files} aria-label={`Open folder of ${s.name}`}>
          Open folder
        </button>
        <span className="gap" />
        <button type="button" className="btn primary" disabled={busy !== null} onClick={() => act("approve", s)}
          aria-label={`Approve the change to ${s.name}`}>
          {busy === key ? "Working…" : "Approve"}
        </button>
        <button type="button" className="btn" disabled={busy !== null} onClick={() => act("reject", s)}
          aria-label={`Reject the change to ${s.name}`}>
          Reject
        </button>
      </div>
    </li>
  );
}

/** The line diff of each changed file: removed lines marked −, added lines +, folded runs of unchanged lines …. */
function Diff({ id, diff, folder }) {
  if (!diff) return <div id={id} className="diff" aria-busy="true"><span className="skel" /></div>;
  if (diff.error) return <p id={id} className="warn" role="alert">{diff.error}</p>;
  return (
    <div id={id} className="diff">
      {diff.files.map((f) => <File key={f.file} f={f} folder={folder} />)}
    </div>
  );
}

const MARK = { "-": "−", "+": "+", " ": " " };

/** One line of a diff: both line numbers, the mark, the text. */
const Line = ({ l, from }) => (
  <span className={{ "-": "del", "+": "add" }[l.op] ?? ""} {...(from !== undefined && { "data-from": from, tabIndex: -1 })}>
    <i aria-hidden="true">{l.old ?? ""}</i>
    <i aria-hidden="true">{l.new ?? ""}</i>
    <b aria-hidden="true">{MARK[l.op] ?? " "}</b>
    <span className="t">
      {l.op === "-" && <span className="sr-only">removed: </span>}
      {l.op === "+" && <span className="sr-only">added: </span>}
      {l.text}{"\n"}
    </span>
  </span>
);

/** A changed file. A folded run of unchanged lines opens in place when the engine sent its lines. */
function File({ f, folder }) {
  const [unfolded, setUnfolded] = useState(() => new Set());
  const pre = useRef(null);
  // Unfolding removes the button that had focus: hand focus to the first revealed line.
  const unfold = (i) => {
    setUnfolded((s) => new Set(s).add(i));
    requestAnimationFrame(() => pre.current?.querySelector(`[data-from="${i}"]`)?.focus());
  };
  return (
    <figure>
      <figcaption><code className="mono">{f.file}</code> · {f.status}</figcaption>
      {f.note ? <p>{f.note}</p> : (
        <pre className="mono" ref={pre}>
          {f.lines.map((l, i) =>
            l.op !== "…" ? <Line key={i} l={l} />
            : unfolded.has(i) ? l.lines.map((h, j) => <Line key={`${i}.${j}`} l={h} from={j === 0 ? i : undefined} />)
            : (
              <span key={i} className="fold">
                {/* A run over the engine's cap comes without its lines: the folder has them. */}
                <button type="button" onClick={() => (l.lines ? unfold(i) : folder())}>
                  <span aria-hidden="true">⋯</span> {l.lines ? `Show ${l.text}` : `${l.text.replace(/ \(.*\)$/, "")}: open the folder`}{"\n"}
                </button>
              </span>
            ),
          )}
        </pre>
      )}
    </figure>
  );
}
