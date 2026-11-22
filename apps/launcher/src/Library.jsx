import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { footnote } from "./data.js";

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
    footnote("corpora").then(
      (data) => live && setState({ loading: false, data }),
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
    </div>
  );
}
