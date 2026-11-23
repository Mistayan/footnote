import { useEffect, useId, useRef, useState } from "react";
import { Box, ChevronRight, Folder, FolderGit2, FolderPlus, HardDrive, House, X } from "lucide-react";
import { browseFolders, footnote, mb } from "./data.js";
import { Scroll, Tip, clip, toast } from "./ui.jsx";

// The app's own folder browser instead of the Windows dialog (22 Nov 2026). One level at a time: the drives, then folders by
// name (a git repository is marked). Add project picks the folder you are in; Load a GGUF model (#556) picks a `.gguf` file.

export default function AddProject({ refresh }) {
  return (
    <Browser title="Add a project folder" opener={<><FolderPlus size={15} strokeWidth={2} /> Add project</>} openerClass="add-project"
      action="Add this folder" acting="Adding…"
      pick={async (path) => {
        const r = await footnote("projects", "add", path);
        toast(`Added ${r?.name ?? path}.`);
        refresh?.();
      }} />
  );
}

/** Load a GGUF model (#556): the browser shows folders and `.gguf` files; the engine checks and copies the chosen one. A
 * measured model's card opens it too, with its own `opener` and accessible `label`. */
export function ImportGguf({ done, disabled, opener = "Load a GGUF model…", label }) {
  return (
    <Browser title="Load a GGUF model" opener={opener} label={label} disabled={disabled} gguf
      note="Footnote checks that the file is an embedding model and copies it into its models folder. The original stays where it is."
      action="Load this model" acting="Checking and copying…"
      pick={async (path) => {
        const r = await footnote("models", "import", path);
        toast(`Loaded ${r?.name ?? path}.`);
        done?.(r);
      }} />
  );
}

/** The browser dialog. Without `gguf`, the folder you are in is the pick; with it, the `.gguf` file you select is. */
function Browser({ title, opener, label, openerClass = "", disabled, gguf, note, action, acting, pick }) {
  const dialog = useRef(null);
  const id = `picker-title${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;
  const [at, setAt] = useState(null); // the listing shown: { path, parent, drives, folders, files, git }
  const [chosen, setChosen] = useState(null); // with `gguf`: the selected file's path
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const go = (path) => {
    setError(null);
    setChosen(null);
    browseFolders(path, gguf).then(setAt, (e) => setError(String(e)));
  };
  const open = () => {
    dialog.current?.showModal();
    browseFolders(null, gguf).then((root) => (root.home ? go(root.home) : setAt(root)), (e) => setError(String(e)));
  };
  const close = () => dialog.current?.close();
  const target = gguf ? chosen : at?.path;
  const run = async () => {
    if (!target) return;
    setBusy(true);
    try {
      await pick(target);
      close();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  useEffect(() => {
    const d = dialog.current;
    const onClose = () => { setAt(null); setChosen(null); setError(null); };
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
  const files = at?.files ?? [];

  return (
    <>
      <button type="button" className={`btn ${openerClass}`.trim()} onClick={open} disabled={disabled} aria-label={label}>{opener}</button>
      <dialog ref={dialog} className="picker lglass sq" aria-labelledby={id}>
        <header className="picker-head">
          <h2 id={id}>{title}</h2>
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
        {note && <p className="dimmed small picker-note">{note}</p>}
        {error && <p className="warn small" role="alert">{error}</p>}
        <Scroll compact className="picker-list">
          {!at ? <span className="skel" /> : at.folders.length + files.length === 0 ? (
            <p className="dimmed small picker-empty">{!at.path ? "Pick a drive." : gguf ? "No folders or .gguf files inside." : "No folders inside."}</p>
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
              {files.map((f) => (
                <li key={f.path}>
                  <button type="button" className={`picker-row${chosen === f.path ? " on" : ""}`} aria-pressed={chosen === f.path}
                    onClick={() => setChosen(f.path)}>
                    <Box size={15} strokeWidth={1.9} className="git" />
                    <span className="picker-name">{f.name}</span>
                    <span className="dimmed small mono">{mb(f.bytes)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Scroll>
        <footer className="picker-foot">
          <span className="picker-current mono small">
            {!gguf && at?.git && <FolderGit2 size={13} strokeWidth={1.9} className="git" />}
            {target ? clip(target, 52) : gguf ? "Select a .gguf file" : "–"}
          </span>
          <button type="button" className="btn" onClick={close}>Cancel</button>
          <button type="button" className="btn primary" onClick={run} disabled={!target || busy}>
            {busy ? acting : action}
          </button>
        </footer>
      </dialog>
    </>
  );
}
