import { useEffect, useState } from "react";
import { BookOpen, Globe } from "lucide-react";
import { footnote, mb, num, shortDate } from "./data.js";
import { PathPill, Tip, Trash, clip } from "./ui.jsx";

function corpusName(path) {
  const parts = path.replace(/\\/g, "/").split("/").filter(Boolean);
  const file = parts[parts.length - 1] ?? path;
  const parent = parts[parts.length - 2];
  return parent && (file === "latest.db" || /^\d/.test(file)) ? `${parent} (${file.replace(/\.db$/, "")})` : file.replace(/\.db$/, "");
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

  const corpora = state.data?.corpora ?? [];
  const docs = state.docs ?? [];
  const ready = corpora.filter((c) => c.exists).length;
  const pages = docs.reduce((n, d) => n + (d.pages ?? 0), 0);

  return (
    <div className="body">
      {state.error ? (
        <p className="empty warn" role="alert">{state.error}</p>
      ) : state.loading && !state.data ? (
        <span className="skel big" />
      ) : (
        <>
          <section className="hero lglass sq">
            <div>
              <div className="kicker">Library</div>
              <div className="big">{num(corpora.length)} <span className="dimmed" style={{ fontSize: 18, fontWeight: 600 }}>{corpora.length === 1 ? "corpus" : "corpora"}</span></div>
              <div className="sub">Searched by Library and Search. Removing one unregisters it; the file stays on disk.</div>
            </div>
            <div className="kpis">
              <div className="kpi"><span><BookOpen size={12} strokeWidth={1.9} /> Ready</span><b className={ready === corpora.length ? "ok" : "warn"}>{num(ready)}</b></div>
              <div className="kpi"><span><Globe size={12} strokeWidth={1.9} /> Doc sites</span><b>{num(docs.length)}</b></div>
              <div className="kpi"><span>Pages cached</span><b>{num(pages)}</b></div>
            </div>
          </section>

          {corpora.length === 0 ? (
            <p className="empty">
              No Library corpus yet. Index a folder with <code>footnote index</code> or crawl docs with <code>footnote crawl</code>.
            </p>
          ) : (
            <div className="corpora">
              <div className="row-head" aria-hidden="true"><span>Corpus</span><span>Database</span><span>State</span><span /></div>
              <ul className="rows" aria-label="Corpora">
                {corpora.map((c) => {
                  const name = corpusName(c.path);
                  return (
                    <li key={c.path} className="line-row surface sq lit">
                      <Tip tip={name.length > 32 ? name : null}><span className="cell-name">{clip(name, 32)}</span></Tip>
                      <span><PathPill path={c.path} keep={2} missing={!c.exists} /></span>
                      <span className={`state-dot${c.exists ? "" : " warn"}`}>{c.exists ? "Ready" : "Missing"}</span>
                      <Trash what={name} busy={busyPath === c.path} onConfirm={() => remove(c.path)} />
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {docs.length > 0 && (
            <section className="group sub" aria-labelledby="docs-title" style={{ marginTop: 6 }}>
              <h2 id="docs-title" className="heading">Shared docs cache<span className="count">{docs.length}</span></h2>
              <p className="dimmed small">Sites indexed once per machine with <code>footnote docs add</code> and reused by every project.</p>
              <div className="docs">
                <div className="row-head" aria-hidden="true">
                  <span>Site</span><span>Version</span><span>State</span><span className="num-r">Pages</span><span className="num-r">Size</span><span className="num-r">Updated</span>
                </div>
                <ul className="rows" aria-label="Doc sites">
                  {docs.map((d) => (
                    <li key={`${d.site}@${d.version}`} className="line-row surface sq lit">
                      <span className="cell-name">{d.site}</span>
                      <span className="cell-dim mono">{d.version}</span>
                      <span className={`state-dot${d.state === "ready" ? "" : " idle"}`}>{d.state === "ready" ? "Ready" : d.state.startsWith("embedding") ? <span className="shimmer">{clip(d.state, 18)}</span> : clip(d.state, 18)}</span>
                      <span className="num-r mono small">{d.pages != null ? num(d.pages) : "–"}</span>
                      <span className="num-r mono small">{d.bytes != null ? mb(d.bytes) : "–"}</span>
                      <span className="num-r mono small dimmed">
                        {d.modified_unix ? shortDate(new Date(d.modified_unix * 1000).toISOString().slice(0, 10)) : "–"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
