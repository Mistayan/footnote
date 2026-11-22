import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { footnote, mb, num, shortDate } from "./data.js";

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

  return (
    <div className="body">
      <p className="dimmed">
        Document corpora searched by Footnote Library and Search. Removing a corpus unregisters it without deleting the database file on disk.
      </p>
      {state.error ? (
        <p className="empty warn" role="alert">{state.error}</p>
      ) : state.loading && !state.data ? (
        <span className="skel" />
      ) : corpora.length === 0 ? (
        <p className="empty">
          No Library corpus yet. Index a folder with <code>footnote index</code> or crawl docs with <code>footnote crawl</code>.
        </p>
      ) : (
        <table className="tbl">
          <thead>
            <tr>
              <th scope="col">Corpus</th>
              <th scope="col">Database path</th>
              <th scope="col">State</th>
              <th scope="col" className="num">Action</th>
            </tr>
          </thead>
          <tbody>
            {corpora.map((c) => (
              <tr key={c.path}>
                <td>{corpusName(c.path)}</td>
                <td className="mono dimmed" title={c.path} style={{ maxWidth: 480, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {c.path}
                </td>
                <td className={c.exists ? "ok" : "warn"}>{c.exists ? "ready" : "file missing"}</td>
                <td className="num">
                  <button
                    type="button"
                    className="btn icon-btn"
                    disabled={busyPath === c.path}
                    onClick={() => remove(c.path)}
                    title="Unregister from Library (keeps file on disk)"
                  >
                    <Trash2 size={13} strokeWidth={1.75} />
                    {busyPath === c.path ? "Removing…" : "Remove"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {state.docs?.length > 0 && (
        <section className="group sub" aria-labelledby="docs-title">
          <h2 id="docs-title" className="heading">Shared docs cache<span className="count">{state.docs.length}</span></h2>
          <p className="dimmed small">Sites indexed once per machine with <code>footnote docs add</code> and reused by every project.</p>
          <table className="tbl">
            <thead>
              <tr>
                <th scope="col">Site</th>
                <th scope="col">Version</th>
                <th scope="col">State</th>
                <th scope="col" className="num">Pages</th>
                <th scope="col" className="num">Size</th>
                <th scope="col" className="num">Updated</th>
              </tr>
            </thead>
            <tbody>
              {state.docs.map((d) => (
                <tr key={`${d.site}@${d.version}`}>
                  <td>{d.site}</td>
                  <td className="mono dimmed">{d.version}</td>
                  <td className={d.state === "ready" ? "ok" : "dimmed"}>{d.state}</td>
                  <td className="num mono">{d.pages != null ? num(d.pages) : "—"}</td>
                  <td className="num mono">{d.bytes != null ? mb(d.bytes) : "—"}</td>
                  <td className="num mono dimmed">{d.modified_unix ? shortDate(new Date(d.modified_unix * 1000).toISOString().slice(0, 10)) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
