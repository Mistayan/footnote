import { cloneElement, isValidElement, useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { Check, ChevronDown, CircleAlert, X } from "lucide-react";

// The launcher's shared controls (DESIGN.md section 11, glass rework 22 Nov 2026). Each one follows a recipe from the
// design bank (`protos/css.html`): popover with entry and exit, sliding-indicator tabs, spring switch, anchored tooltip,
// height: auto reveal. Chromium (WebView2) supports all of them; under reduced motion nothing moves.

/** A CSS dashed ident from React's `useId` (":r3:" is not one). */
const useAnchor = (prefix) => `--${prefix}-${useId().replace(/[^a-zA-Z0-9_-]/g, "")}`;

/** Anchored tooltip: wraps one element and shows `tip` beside it on hover or keyboard focus. The tip lives in the top
 * layer (a manual popover), so no card or scroller clips it; the anchor places it without measuring. */
export function Tip({ tip, children, side = "top", className = "" }) {
  const anchor = useAnchor("tip");
  const id = useId();
  const ref = useRef(null);
  if (!tip) return children;
  const show = () => {
    try { ref.current?.showPopover(); } catch { /* already open, or detached */ }
  };
  const hide = () => {
    try { ref.current?.hidePopover(); } catch { /* already closed */ }
  };
  const child = isValidElement(children) ? cloneElement(children, { "aria-describedby": id }) : children;
  return (
    <span className={`tip-host ${className}`} style={{ "--anchor": anchor }} onPointerEnter={show} onPointerLeave={hide}
      onFocus={show} onBlur={hide} onKeyDown={(e) => e.key === "Escape" && hide()}>
      {child}
      <span ref={ref} id={id} role="tooltip" popover="manual" className={`tip tip-${side}`} style={{ "--anchor": anchor }}>{tip}</span>
    </span>
  );
}

/** Popover menu in place of a native `<select>`. `options`: [{ value, label, hint }]. */
export function Select({ value, options, onChange, label, icon: Icon, className = "" }) {
  const anchor = useAnchor("sel");
  const menu = useRef(null);
  const button = useRef(null);
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value) ?? options[0];
  const items = () => [...(menu.current?.querySelectorAll("[role='option']") ?? [])];
  const close = (refocus = true) => {
    menu.current?.hidePopover?.();
    if (refocus) button.current?.focus();
  };
  const pick = (v) => {
    onChange(v);
    close();
  };
  const onToggle = (e) => {
    const isOpen = e.newState === "open";
    setOpen(isOpen);
    if (isOpen) requestAnimationFrame(() => (items().find((el) => el.getAttribute("aria-selected") === "true") ?? items()[0])?.focus());
  };
  const onKey = (e) => {
    const list = items();
    const at = list.indexOf(document.activeElement);
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      list[(at + (e.key === "ArrowDown" ? 1 : list.length - 1)) % list.length]?.focus();
    } else if (e.key === "Home" || e.key === "End") {
      e.preventDefault();
      list[e.key === "Home" ? 0 : list.length - 1]?.focus();
    } else if (e.key === "Escape") {
      e.preventDefault();
      close();
    } else if (e.key === "Tab") close(false);
  };
  return (
    <>
      <button ref={button} type="button" className={`select ${className}`} popoverTarget={`${anchor}-m`} aria-haspopup="listbox"
        aria-expanded={open} aria-label={label ? `${label}: ${current?.label}` : undefined} style={{ "--anchor": anchor }}>
        {Icon && <Icon size={14} strokeWidth={1.75} aria-hidden="true" className="select-ic" />}
        <span className="select-val">{current?.label}</span>
        <ChevronDown size={14} strokeWidth={1.75} aria-hidden="true" className="select-chev" />
      </button>
      <div ref={menu} id={`${anchor}-m`} popover="auto" className="menu lglass" role="listbox" aria-label={label}
        style={{ "--anchor": anchor }} onToggle={onToggle} onKeyDown={onKey}>
        <Scroll compact className="menu-scroll">
          {options.map((o) => (
            <button key={String(o.value)} type="button" role="option" aria-selected={o.value === value} className="menu-item"
              onClick={() => pick(o.value)}>
              <Check size={14} strokeWidth={2} aria-hidden="true" className="menu-check" />
              <span className="menu-lbl">{o.label}</span>
              {o.hint != null && <span className="menu-hint">{o.hint}</span>}
            </button>
          ))}
        </Scroll>
      </div>
    </>
  );
}

/** Segmented tabs whose pill slides to the selected one. `options`: [[value, label]]. */
export function Tabs({ value, options, onChange, label, className = "" }) {
  const anchor = useAnchor("tabs");
  const onKey = (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const at = options.findIndex(([v]) => v === value);
    const next = options[(at + (e.key === "ArrowRight" ? 1 : options.length - 1)) % options.length][0];
    onChange(next);
    requestAnimationFrame(() => e.currentTarget?.querySelector("[aria-selected='true']")?.focus());
  };
  return (
    <div className={`tabs ${className}`} role="tablist" aria-label={label} style={{ "--anchor": anchor }} onKeyDown={onKey}>
      {options.map(([v, text]) => (
        <button key={v} type="button" role="tab" aria-selected={value === v} tabIndex={value === v ? 0 : -1} className="tab"
          onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
      <span className="tab-ind" aria-hidden="true" />
    </div>
  );
}

/** The spring switch (a `role="switch"` button; the knob overshoots on a `linear()` spring). */
export function Switch({ checked, onChange, label, labelledBy, disabled, innerRef }) {
  return (
    <button ref={innerRef} type="button" role="switch" aria-checked={checked} aria-label={label} aria-labelledby={labelledBy}
      className="switch" disabled={disabled} onClick={() => onChange(!checked)}>
      <span aria-hidden="true" />
    </button>
  );
}

/** A small trash button: the first click arms it (lid lifts, it takes the danger colour), the second does it. It disarms
 * itself after a few seconds or when focus leaves. */
export function Trash({ onConfirm, busy, what = "this", size = 28 }) {
  const [armed, setArmed] = useState(false);
  useEffect(() => {
    if (!armed) return;
    const t = setTimeout(() => setArmed(false), 4000);
    return () => clearTimeout(t);
  }, [armed]);
  const label = busy ? `Removing ${what}` : armed ? `Click again to remove ${what}` : `Remove ${what}`;
  return (
    <Tip tip={busy ? "Removing…" : armed ? "Click again to confirm" : `Remove ${what}`}>
      <button type="button" className={`trash${armed ? " armed" : ""}${busy ? " busy" : ""}`} aria-label={label} disabled={busy}
        style={{ "--sz": `${size}px` }} onBlur={() => setArmed(false)}
        onClick={(e) => {
          e.stopPropagation();
          if (armed) {
            setArmed(false);
            onConfirm();
          } else setArmed(true);
        }}>
        <svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8"
          strokeLinecap="round" strokeLinejoin="round">
          <g className="lid"><path d="M4 6.5h16" /><path d="M9.5 6.5V4.8c0-.7.5-1.3 1.2-1.3h2.6c.7 0 1.2.6 1.2 1.3v1.7" /></g>
          <g className="can"><path d="M6 6.5l.9 12.2c.1 1 .9 1.8 1.9 1.8h6.4c1 0 1.8-.8 1.9-1.8L18 6.5" /><path d="M10 10.5v6M14 10.5v6" /></g>
        </svg>
      </button>
    </Tip>
  );
}

/** Approve or reject: a green check and a red cross. Hovering draws the mark again; the one clicked pulses until the
 * engine answers. */
export function Verdict({ onApprove, onReject, busy, what = "this", approveTip = "Approve", rejectTip = "Reject" }) {
  const [chosen, setChosen] = useState(null);
  useEffect(() => {
    if (!busy) setChosen(null);
  }, [busy]);
  const pick = (which, run) => (e) => {
    e.stopPropagation();
    setChosen(which);
    run();
  };
  return (
    <span className="verdict">
      <Tip tip={busy && chosen === "yes" ? "Approving…" : approveTip}>
        <button type="button" className={`vd yes${chosen === "yes" ? " chosen" : ""}`} disabled={busy}
          aria-label={`Approve ${what}`} onClick={pick("yes", onApprove)}>
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.4"
            strokeLinecap="round" strokeLinejoin="round">
            <path pathLength="1" d="M5 12.5l4.5 4.5L19 7.5" />
          </svg>
        </button>
      </Tip>
      <Tip tip={busy && chosen === "no" ? "Rejecting…" : rejectTip}>
        <button type="button" className={`vd no${chosen === "no" ? " chosen" : ""}`} disabled={busy}
          aria-label={`Reject ${what}`} onClick={pick("no", onReject)}>
          <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2.4"
            strokeLinecap="round">
            <path pathLength="1" d="M7 7l10 10" />
            <path pathLength="1" d="M17 7L7 17" />
          </svg>
        </button>
      </Tip>
    </span>
  );
}

/** A path as a drive squircle and its last `keep` segments: `D:/Projets/Footnote` -> { drive: "D", tail: "~\\Footnote" }. */
export function splitPath(path, keep = 1) {
  const norm = String(path ?? "").replace(/\//g, "\\");
  const m = norm.match(/^([a-zA-Z]):\\?(.*)$/);
  const drive = m ? m[1].toUpperCase() : null;
  const parts = (m ? m[2] : norm).split("\\").filter(Boolean);
  const kept = parts.slice(-keep);
  const tail = parts.length > keep ? `~\\${kept.join("\\")}` : `\\${kept.join("\\")}`;
  return { drive, tail };
}

/** The drive squircle and the shortened path, the full path in a tooltip. Clickable when `onOpen` is given. */
export function PathPill({ path, keep = 1, onOpen, missing }) {
  const { drive, tail } = splitPath(path, keep);
  const body = (
    <>
      {drive && <span className="drive" aria-hidden="true">{drive}</span>}
      <span className="path-tail">{tail}</span>
    </>
  );
  return (
    <Tip tip={<span className="mono">{path}{missing ? " (missing)" : onOpen ? " · open in file manager" : ""}</span>}>
      {onOpen ? (
        <button type="button" className={`path-pill${missing ? " missing" : ""}`} onClick={onOpen} aria-label={`Open ${path}`}>{body}</button>
      ) : (
        <span className={`path-pill${missing ? " missing" : ""}`}>{body}</span>
      )}
    </Tip>
  );
}

/** Cut text to `max` characters on a word, with an ellipsis. */
export const clip = (text, max) => {
  const s = String(text ?? "");
  if (s.length <= max) return s;
  const cut = s.slice(0, max);
  const space = cut.lastIndexOf(" ");
  return `${(space > max * 0.6 ? cut.slice(0, space) : cut).replace(/[\s,.;:–-]+$/, "")}…`;
};

/** The scroll container with a tick rail in place of the scrollbar (T3 Code's rail): the more content is off screen, the
 * more ticks; the ticks in view are lit. Clicking or dragging the rail scrolls. Wheel, keys and touch scroll natively. */
export function Scroll({ children, className = "", label, compact = false }) {
  const box = useRef(null);
  const [m, setM] = useState({ ticks: 0, from: 0, to: 0, here: 0 });
  const [near, setNear] = useState(null); // the tick under the pointer, for the magnifier
  const measure = useCallback(() => {
    const el = box.current;
    if (!el) return;
    const { scrollHeight: sh, clientHeight: ch, scrollTop: st } = el;
    if (sh <= ch + 2) return setM((p) => (p.ticks === 0 ? p : { ticks: 0, from: 0, to: 0, here: 0 }));
    // About four ticks per screen of content (three in a menu), so the rail stays sparse like T3 Code's.
    const ticks = compact
      ? Math.min(20, Math.max(6, Math.round((sh / ch) * 3)))
      : Math.min(36, Math.max(8, Math.round((sh / ch) * 4)));
    const from = Math.floor((st / sh) * ticks);
    const to = Math.min(ticks - 1, Math.ceil(((st + ch) / sh) * ticks) - 1);
    const here = Math.min(ticks - 1, Math.floor(((st + ch / 2) / sh) * ticks));
    setM((p) => (p.ticks === ticks && p.from === from && p.to === to && p.here === here ? p : { ticks, from, to, here }));
  }, [compact]);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    const mo = new MutationObserver(measure);
    mo.observe(el, { childList: true, subtree: true });
    [...el.children].forEach((c) => ro.observe(c));
    el.addEventListener("scroll", measure, { passive: true });
    return () => {
      ro.disconnect();
      mo.disconnect();
      el.removeEventListener("scroll", measure);
    };
  }, [measure]);
  // The end of the scroll answers a push past it: a small bump and a faint accent glow at that edge. Pushing again within
  // half a second strengthens both, up to a light cap. Reduced motion keeps the glow only.
  const glow = useRef(null);
  const push = useRef({ n: 0, t: 0, anim: null });
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const onWheel = (e) => {
      if (!e.deltaY || el.scrollHeight <= el.clientHeight + 2) return;
      const down = e.deltaY > 0;
      const atEdge = down ? el.scrollTop + el.clientHeight >= el.scrollHeight - 1 : el.scrollTop <= 0;
      const p = push.current, now = performance.now();
      if (!atEdge) { p.n = 0; return; }
      if (p.anim?.playState === "running" && now - p.t < 120) return;
      p.n = now - p.t < 500 ? Math.min(p.n + 1, 4) : 1;
      p.t = now;
      const g = glow.current;
      g.dataset.edge = down ? "end" : "start";
      g.animate([{ opacity: 0 }, { opacity: 0.25 + p.n * 0.15 }, { opacity: 0 }], { duration: 560, easing: "ease-out" });
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
      const px = (2 + p.n * 1.5) * (down ? -1 : 1);
      p.anim = el.animate([{ translate: "0 0" }, { translate: `0 ${px}px` }, { translate: "0 0" }],
        { duration: 320, easing: "cubic-bezier(0.2, 0.8, 0.2, 1)" });
    };
    el.addEventListener("wheel", onWheel, { passive: true });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);
  const seek = (e, smooth) => {
    const el = box.current;
    const rail = e.currentTarget.getBoundingClientRect();
    const f = Math.min(1, Math.max(0, (e.clientY - rail.top) / rail.height));
    el.scrollTo({ top: f * el.scrollHeight - el.clientHeight / 2, behavior: smooth ? "smooth" : "instant" });
  };
  const point = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    setNear(Math.min(m.ticks - 1, Math.max(0, Math.floor(((e.clientY - r.top) / r.height) * m.ticks))));
  };
  return (
    <div className={`scroll-wrap ${className}${m.ticks > 0 ? " has-rail" : ""}${compact ? " compact" : ""}`}>
      <div ref={box} className="scroll" role={compact ? undefined : "region"} aria-label={compact ? undefined : label}>{children}</div>
      <i ref={glow} className="edge-glow" aria-hidden="true" />
      {m.ticks > 0 && (
        <div className="rail" aria-hidden="true"
          onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); seek(e, true); }}
          onPointerMove={(e) => { point(e); if (e.buttons === 1) seek(e, false); }}
          onPointerLeave={() => setNear(null)}>
          {Array.from({ length: m.ticks }, (_, i) => {
            const d = near === null ? 9 : Math.abs(i - near);
            const cls = [i >= m.from && i <= m.to && "on", i === m.here && "here", d < 3 && `h${d}`].filter(Boolean).join(" ");
            return <i key={i} className={cls} />;
          })}
        </div>
      )}
    </div>
  );
}

/** The lit border (design bank `protos/hover.html`): every `.lit` element near the pointer reads its position, so the
 * halo crosses neighbouring cards. One listener for the window; off for touch and under reduced motion. */
export function useSpotlight() {
  useEffect(() => {
    if (!matchMedia("(pointer: fine)").matches) return;
    const still = matchMedia("(prefers-reduced-motion: reduce)");
    let frame = 0;
    let x = -9999;
    let y = -9999;
    const paint = () => {
      frame = 0;
      if (still.matches) return;
      for (const el of document.querySelectorAll(".lit")) {
        const r = el.getBoundingClientRect();
        const near = x > r.left - 240 && x < r.right + 240 && y > r.top - 240 && y < r.bottom + 240;
        if (near) {
          el.style.setProperty("--x", `${x - r.left}px`);
          el.style.setProperty("--y", `${y - r.top}px`);
        } else if (el.style.getPropertyValue("--x") !== "-9999px") {
          el.style.setProperty("--x", "-9999px");
        }
      }
    };
    const move = (e) => {
      x = e.clientX;
      y = e.clientY;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const leave = () => {
      x = y = -9999;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    addEventListener("pointermove", move, { passive: true });
    document.documentElement.addEventListener("pointerleave", leave);
    return () => {
      removeEventListener("pointermove", move);
      document.documentElement.removeEventListener("pointerleave", leave);
      cancelAnimationFrame(frame);
    };
  }, []);
}

/** A short note at the bottom of the window, from anywhere: `toast("Copied")`. `<Toasts />` shows the latest. */
export function toast(text, tone = "ok", { sticky = false, action = null } = {}) {
  dispatchEvent(new CustomEvent("footnote-toast", { detail: { text, tone, sticky, action, at: Date.now() } }));
}

export function Toasts() {
  const [note, setNote] = useState(null);
  useEffect(() => {
    let timer;
    const on = (e) => {
      setNote(e.detail);
      clearTimeout(timer);
      if (!e.detail.sticky) timer = setTimeout(() => setNote(null), 4200);
    };
    addEventListener("footnote-toast", on);
    return () => {
      removeEventListener("footnote-toast", on);
      clearTimeout(timer);
    };
  }, []);
  return (
    <div className="toasts" role="status" aria-live="polite">
      {note && (
        <div key={note.at} className={`toast lglass sq${note.tone === "warn" ? " warn" : ""}`}>
          {note.tone === "warn" ? <CircleAlert size={15} strokeWidth={1.9} /> : <Check size={15} strokeWidth={2} />}
          <span>{note.text}</span>
          {note.action && (
            <button type="button" className="btn" onClick={() => { setNote(null); note.action.run(); }}>{note.action.label}</button>
          )}
          {note.sticky && (
            <button type="button" className="mw-btn" onClick={() => setNote(null)} aria-label="Dismiss"><X size={13} strokeWidth={2} /></button>
          )}
        </div>
      )}
    </div>
  );
}

/** The five palettes. Afterglow is the family's own; the others are for taste and light rooms. */
export const PALETTES = [
  { id: "afterglow", name: "Afterglow", sw: ["#09120b", "#5fd3c3"] },
  { id: "graphite", name: "Graphite", sw: ["#0b0b0e", "#4ea1ff"] },
  { id: "midnight", name: "Midnight", sw: ["#0f0d1a", "#a78bfa"] },
  { id: "ember", name: "Ember", sw: ["#140d0a", "#ff9f5a"] },
  { id: "daylight", name: "Daylight", sw: ["#eef1f4", "#0a6cdf"] },
];

const KEY = "footnote.palette";
const read = () => {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
};

/** Apply the saved palette before the first paint. */
export function applySavedPalette() {
  const p = read();
  document.documentElement.dataset.palette = PALETTES.some((x) => x.id === p) ? p : "afterglow";
}

export function usePalette() {
  const [palette, set] = useState(() => document.documentElement.dataset.palette || "afterglow");
  const choose = (id) => {
    document.documentElement.dataset.palette = id;
    try {
      localStorage.setItem(KEY, id);
    } catch {
      /* private mode: the choice lasts this session */
    }
    set(id);
  };
  return [palette, choose];
}
