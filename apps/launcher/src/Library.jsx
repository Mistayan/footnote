import { useEffect, useState } from "react";
import { BookOpen, Globe } from "lucide-react";
import { footnote, mb, num, shortDate } from "./data.js";
import { PathPill, Tip, Trash, clip } from "./ui.jsx";
import { UNUSED, groupDocs } from "./docGroups.js";

function corpusName(path) {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  const file = parts[parts.length - 1] ?? path;
  const parent = parts[parts.length - 2];
  return parent && (file === "latest.db" || /^\d/.test(file)) ? `${parent} (${file.replace(/\.db$/, "")})` : file.replace(/\.db$/, "");
}

const samePath = (p) => p.replace(/\\/g, "/").toLowerCase();
const pct = (d) => (d.total ? Math.floor((100 * d.done) / d.total) : null);

function DocState({ d }) {
  const p = pct(d);
  if (d.state === "ready") return <span className="state-dot">Ready</span>;
  if (d.state === "queued") return <span className="state-dot idle">Queued</span>;
  if (d.state === "embedding" || String(d.state).startsWith("embedding "))
    return (
      <span className="doc-progress">
        <span className="shimmer">{p != null ? `${p} %` : "Embedding"}</span>
        {p != null && <progress value={d.done} max={d.total} aria-label={`${d.site} embedding ${p} %`} />}
      </span>
    );
  return <span className="state-dot idle">{p != null ? `Paused at ${p} %` : "Keyword only"}</span>;
}

function DocRow({ d }) {
  const users = d.used_by ?? [];
  return (
    <li className="line-row surface sq lit">
      <span className="cell-name">{d.site}</span>
      <span className="cell-dim mono">{clip(d.version, 12)}</span>
      <DocState d={d} />
      {d.used_by && (
        <Tip tip={users.length ? users.join(", ") : null}>
          <span className="cell-dim">{users.length ? `${users.length} ${users.length === 1 ? "project" : "projects"}` : "–"}</span>
        </Tip>
      )}
      <span className="num-r mono small">{d.pages != null ? num(d.pages) : "–"}</span>
      <span className="num-r mono small">{d.bytes != null ? mb(d.bytes) : "–"}</span>
      <span className="num-r mono small dimmed">
        {d.modified_unix ? shortDate(new Date(d.modified_unix * 1000).toISOString().slice(0, 10)) : "–"}
      </span>
    </li>
  );
}

export default function Library({ refresh }) {
  const [round, setRound] = useState(0);
  const [state, setState] = useState({ loading: true });
  const [busyPath, setBusyPath] = useState(null);

  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    Promise.all([footnote("corpora"), footnote("docs", "list").catch(() => ({ docs: [] }))]).then(
      ([data, docs]) => live && setState({ loading: false, data, docs: docs.docs ?? [] }),
      (error) => live && setState({ loading: false, error: String(error) }),
    );
    return () => { live = false; };
  }, [round]);

  // Re-read while a site embeds, so its percentage moves.
  const embedding = (state.docs ?? []).some(
    (d) => d.state === "embedding" || d.state === "queued" || String(d.state).startsWith("embedding "),
  );
  useEffect(() => {
    if (!embedding) return;
    const t = setTimeout(() => setRound((r) => r + 1), 5000);
    return () => clearTimeout(t);
  }, [embedding, round]);

  const remove = async (path) => {
    setBusyPath(path);
    try {
      await footnote("corpora", "remove", path);
      setRound((r) => r + 1);
      refresh?.();
    } catch (e) {
      setState((s) => ({ ...s, error: String(e) }));
    } finally {
      setBusyPath(null);
    }
  };

  const docs = state.docs ?? [];
  // `docs add` also registers each site as a corpus: list it once, as a doc site.
  const docPaths = new Set(docs.map((d) => samePath(String(d.db ?? ""))));
  const own = (state.data?.corpora ?? []).filter((c) => !docPaths.has(samePath(c.path)));
  const ready = docs.filter((d) => d.state === "ready").length;
  const pages = docs.reduce((n, d) => n + (d.pages ?? 0), 0);
  const usage = docs.some((d) => Array.isArray(d.used_by));
  const groups = groupDocs(docs);

  return (
    <div className="body library">
      {state.error ? (
        <p className="empty warn" role="alert">{state.error}</p>
      ) : state.loading && !state.data ? (
        <span className="skel big" />
      ) : (
        <>
          <section className="hero lglass sq">
            <div>
              <div className="kicker">Library</div>
              <div className="big">{num(docs.length)} <span className="dimmed" style={{ fontSize: 18, fontWeight: 600 }}>{docs.length === 1 ? "doc site" : "doc sites"}</span></div>
              <div className="sub">Indexed once per machine with <code>footnote docs add</code> and searched by every project.</div>
            </div>
            <div className="kpis">
              <div className="kpi"><span><Globe size={12} strokeWidth={1.9} /> Ready</span><b className={ready === docs.length ? "ok" : "warn"}>{num(ready)}<span className="dimmed"> / {num(docs.length)}</span></b></div>
              <div className="kpi"><span>Pages cached</span><b>{num(pages)}</b></div>
              {own.length > 0 && <div className="kpi"><span><BookOpen size={12} strokeWidth={1.9} /> Your corpora</span><b>{num(own.length)}</b></div>}
            </div>
          </section>

          {docs.length === 0 && own.length === 0 && (
            <p className="empty">
              Nothing in the Library yet. Add a docs site with <code>footnote docs add</code> or index a folder with <code>footnote index</code>.
            </p>
          )}

          {groups.map((g) => {
            const rows = (
              <div className={`docs${usage ? " used" : ""}`}>
                <div className="row-head" aria-hidden="true">
                  <span>Site</span><span>Version</span><span>State</span>{usage && <span>Used by</span>}
                  <span className="num-r">Pages</span><span className="num-r">Size</span><span className="num-r">Updated</span>
                </div>
                <ul className="rows" aria-label={g.name ?? "Doc sites"}>
                  {g.docs.map((d) => <DocRow key={`${d.site}@${d.version}`} d={d} />)}
                </ul>
              </div>
            );
            const heading = <>{g.name ?? "Doc sites"}<span className="count">{g.docs.length}</span></>;
            return g.name === UNUSED ? (
              <details key={g.name} className="group sub lib-group">
                <summary className="heading">{heading}</summary>
                <p className="dimmed small">No registered project's manifest names these. Remove old versions with <code>footnote docs prune</code>.</p>
                {rows}
              </details>
            ) : (
              <section key={g.name ?? "docs"} className="group sub lib-group" aria-label={g.name ?? "Doc sites"}>
                <h2 className="heading">{heading}</h2>
                {rows}
              </section>
            );
          })}

          {own.length > 0 && (
            <section className="group sub lib-group" aria-labelledby="own-title">
              <h2 id="own-title" className="heading">Your corpora<span className="count">{own.length}</span></h2>
              <p className="dimmed small">Folders and sites you indexed yourself. Removing one unregisters it; the file stays on disk.</p>
              <div className="corpora">
                <div className="row-head" aria-hidden="true"><span>Corpus</span><span>Database</span><span>State</span><span /></div>
                <ul className="rows" aria-label="Your corpora">
                  {own.map((c) => {
                    const name = corpusName(c.path);
                    return (
                      <li key={c.path} className="line-row surface sq lit">
                        <Tip tip={name.length > 32 ? name : null}><span className="cell-name">{clip(name, 32)}</span></Tip>
                        <span><PathPill path={c.path} keep={2} missing={!c.exists} /></span>
                        <span className={`state-dot${c.exists ? "" : " warn"}`}>{c.exists ? "On disk" : "Missing"}</span>
                        <Trash what={name} busy={busyPath === c.path} onConfirm={() => remove(c.path)} />
                      </li>
                    );
                  })}
                </ul>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
