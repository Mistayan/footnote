import { useEffect, useState } from "react";
import { footnote } from "./data.js";

// Skills: whether agents may change the skills they use (`memory.skill_rewrite`, #457), and the changes to skill scripts that
// wait for the user. The switch's gain and cost are the engine's own catalogue text (`footnote options`), never a copy here.
// Approving serves a change; nothing in the window or the engine runs the scripts it holds.

const OPTION = "memory.skill_rewrite";

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

/** Catalogue text, with its `command` spans shown as code. */
const Text = ({ children }) =>
  String(children)
    .split("`")
    .map((part, i) => (i % 2 ? <code key={i} className="mono">{part}</code> : part));

const Failed = ({ error }) => (
  <p className="empty warn" role="alert">{error === "ENGINE_MISSING" ? "The Footnote engine was not found." : error}</p>
);

export default function Skills({ onChange }) {
  const [round, setRound] = useState(0);
  const { option, pending, error, loading } = useReads(round);
  const reread = () => {
    setRound((r) => r + 1);
    onChange?.();
  };
  if (error) return <div className="body"><Failed error={error} /></div>;
  if (loading && !option && !pending) return <div className="body"><span className="skel" /><span className="skel" /></div>;
  return (
    <div className="body">
      {option ? <Rewrite option={option} done={reread} /> : (
        <p className="empty">This engine has no skill rewriting. Update Footnote to get it.</p>
      )}
      <h2 className="section">Changes waiting for you</h2>
      <Pending list={pending} done={reread} />
    </div>
  );
}

/** The switch. Turning it on asks once, with the cost; turning it off is immediate. A company policy can lock it. */
function Rewrite({ option, done }) {
  const on = option.value === true;
  const [asking, setAsking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
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
    <section className={on ? "card setting" : "card setting muted"} aria-labelledby="rewrite-title">
      <h2 id="rewrite-title">
        <span className={on ? "dot" : "dot off"} />
        Agents may change skills
        {option.locked ? (
          <span className="state">Set by your company</span>
        ) : (
          <button type="button" role="switch" aria-checked={on} aria-label="Agents may change skills" className="switch"
            disabled={busy || asking} onClick={() => (on ? set(false) : setAsking(true))}>
            <span aria-hidden="true" />
          </button>
        )}
      </h2>
      <p className="sub"><Text>{option.gain}</Text>.</p>
      <p className="sub"><strong>Cost.</strong> <Text>{option.cost}</Text>.</p>
      {option.locked && option.reason && <p className="sub">Policy: {option.reason}</p>}
      {asking && (
        <div className="confirm" role="group" aria-labelledby="confirm-title" aria-describedby="confirm-cost">
          <p id="confirm-title"><strong>Turn on skill rewriting?</strong></p>
          <p id="confirm-cost" className="sub"><Text>{option.cost}</Text>.</p>
          <div className="actions">
            <button type="button" className="btn primary" disabled={busy} onClick={() => set(true)} autoFocus>
              Turn on
            </button>
            <button type="button" className="btn" disabled={busy} onClick={() => setAsking(false)}>Cancel</button>
          </div>
        </div>
      )}
      {error && <p className="sub warn" role="alert">{error}</p>}
    </section>
  );
}

/** Agents' changes to skill scripts, held until the user serves or refuses each one. */
function Pending({ list, done }) {
  const [busy, setBusy] = useState(null);
  const [error, setError] = useState(null);
  if (!list) return <span className="skel" />;
  if (list.length === 0)
    return (
      <p className="empty">
        No change is waiting. When an agent changes a skill's scripts, the change waits here until you approve or reject it.
      </p>
    );
  const act = async (verb, s) => {
    const key = `${s.name}@${s.scope}`;
    setBusy(key);
    setError(null);
    try {
      const args = ["skills", verb, s.name];
      if (s.scope !== "global") args.push("--project", s.scope);
      await footnote(...args);
      done();
    } catch (e) {
      setError(`${s.name}: ${e}`);
    } finally {
      setBusy(null);
    }
  };
  return (
    <>
      <p className="dimmed">
        Read the files in the folder before you approve: approving serves the change to every later session in its scope.
        Footnote never runs a skill's scripts itself.
      </p>
      <ul className="changes">
        {list.map((s) => {
          const key = `${s.name}@${s.scope}`;
          return (
            <li key={key} className="change">
              <div className="head">
                <span className="mono">{s.name}</span>
                <span className="dimmed">{s.scope === "global" ? "every project" : s.scope} · revision {s.revision}</span>
              </div>
              <p>{s.reason}</p>
              <div className="dimmed">Changes <span className="mono">{(s.changed ?? []).join(", ")}</span></div>
              <div className="dimmed">Folder <span className="mono path">{s.files}</span></div>
              <div className="actions">
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
        })}
      </ul>
      {error && <p className="empty warn" role="alert">{error}</p>}
    </>
  );
}
