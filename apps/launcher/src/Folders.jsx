import { useEffect, useRef, useState } from "react";
import { ChevronRight, Folder, FolderGit2, FolderPlus, HardDrive, House, X } from "lucide-react";
import { browseFolders, footnote } from "./data.js";
import { Scroll, Tip, clip, toast } from "./ui.jsx";

// Add project (22 Nov 2026): the app's own folder browser instead of the Windows dialog. One level at a time: the drives,
// then folders by name (a git repository is marked); the folder you are in is the one added.

export default function AddProject({ refresh }) {
  const dialog = useRef(null);
  const [at, setAt] = useState(null); // the listing shown: { path, parent, drives, folders, git }
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const go = (path) => {
    setError(null);
    browseFolders(path).then(setAt, (e) => setError(String(e)));
  };
  const open = () => {
    dialog.current?.showModal();
    browseFolders(null).then((root) => (root.home ? go(root.home) : setAt(root)), (e) => setError(String(e)));
  };
  const close = () => dialog.current?.close();
  const add = async () => {
    if (!at?.path) return;
    setBusy(true);
    try {
      const r = await footnote("projects", "add", at.path);
      close();
      toast(`Added ${r?.name ?? at.path}.`);
      refresh?.();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    const d = dialog.current;
    const onClose = () => setAt(null);
    d?.addEventListener("close", onClose);
    return () => d?.removeEventListener("close", onClose);
  }, []);

  // `D:/Projets/Footnote` -> ["D:/", "D:/Projets", "D:/Projets/Footnote"], each a step of the path bar.
  const steps = at?.path
    ? at.path.replace(/\/+$/, "").split("/").reduce((acc, part, i) => {
        const prev = acc[i - 1]?.path;
        acc.push({ name: part, path: i === 0 ? `${part}/` : `${prev.replace(/\/$/, "")}/${part}` });
        return acc;
      }, [])
    : [];

  return (
    <>
      <button type="button" className="btn add-project" onClick={open}>
        <FolderPlus size={15} strokeWidth={2} /> Add project
      </button>
      <dialog ref={dialog} className="picker lglass sq" aria-labelledby="picker-title">
        <header className="picker-head">
          <h2 id="picker-title">Add a project folder</h2>
          <button type="button" className="mw-btn" onClick={close} aria-label="Close"><X size={14} strokeWidth={2} /></button>
        </header>
        <div className="picker-drives">
          {at?.drives?.map((d) => (
            <Tip key={d} tip={`Drive ${d}`}>
              <button type="button" className={`drive-btn${at.path?.startsWith(d) ? " on" : ""}`} onClick={() => go(d)} aria-label={`Drive ${d}`}>
                <HardDrive size={13} strokeWidth={1.9} /> {d.replace(/[:/]+$/, "")}
              </button>
            </Tip>
          ))}
          {at?.home && (
            <Tip tip="Your user folder">
              <button type="button" className="drive-btn" onClick={() => go(at.home)} aria-label="Your user folder"><House size={13} strokeWidth={1.9} /></button>
            </Tip>
          )}
        </div>
        <nav className="picker-path" aria-label="Path">
          {steps.map((s, i) => (
            <span key={s.path}>
              {i > 0 && <ChevronRight size={12} strokeWidth={2} aria-hidden="true" />}
              <button type="button" onClick={() => go(s.path)} aria-current={i === steps.length - 1 ? "location" : undefined}>
                {clip(s.name, 28)}
              </button>
            </span>
          ))}
        </nav>
        {error && <p className="warn small" role="alert">{error}</p>}
        <Scroll compact className="picker-list">
          {!at ? <span className="skel" /> : at.folders.length === 0 ? (
            <p className="dimmed small picker-empty">{at.path ? "No folders inside." : "Pick a drive."}</p>
          ) : (
            <ul role="list">
              {at.folders.map((f) => (
                <li key={f.path}>
                  <button type="button" className="picker-row" onClick={() => go(f.path)}>
                    {f.git ? <FolderGit2 size={15} strokeWidth={1.9} className="git" /> : <Folder size={15} strokeWidth={1.9} />}
                    <span className="picker-name">{f.name}</span>
                    <ChevronRight size={14} strokeWidth={2} className="picker-chev" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Scroll>
        <footer className="picker-foot">
          <span className="picker-current mono small">
            {at?.git && <FolderGit2 size={13} strokeWidth={1.9} className="git" />}
            {at?.path ? clip(at.path, 52) : "–"}
          </span>
          <button type="button" className="btn" onClick={close}>Cancel</button>
          <button type="button" className="btn primary" onClick={add} disabled={!at?.path || busy}>
            {busy ? "Adding…" : "Add this folder"}
          </button>
        </footer>
      </dialog>
    </>
  );
}
