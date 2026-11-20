// Design lab panel. Lab.panel({title, subtitle, spec, state, onChange, key, open}) builds a liquid-glass control panel for an effect prototype.
// spec rows: [group, key, label, min, max, step, default]; state is mutated in place; onChange(key, value) fires on every edit.
// Header drags the panel; H or the chevron folds it; double-click a label resets that control; the number box is editable; Paste applies copied JSON.
window.Lab = { panel(o) {
  const { spec, state, onChange = () => {} } = o, store = "lab:" + (o.key || o.title), rows = {};
  try { Object.assign(state, JSON.parse(localStorage.getItem(store) || "{}")); } catch (_) {}
  const el = document.createElement("aside"); el.className = "lab"; el.setAttribute("aria-label", o.title + " controls");
  el.innerHTML = '<div class="lab-head"><div class="lab-title">' + o.title + '<small>' + (o.subtitle || "Double-click a label to reset it") + '</small></div>' +
    '<button class="lab-act" data-a="reset" type="button">Reset</button><button class="pri" data-a="copy" type="button">Copy</button>' +
    '<button data-a="fold" type="button" aria-expanded="true" aria-label="Fold controls">⌄</button></div>' +
    '<div class="lab-body"></div><div class="lab-foot"><button data-a="paste" type="button">Paste</button><span class="sp"></span><span class="hk">H hides</span></div><div class="lab-toast" role="status"></div>';
  const body = el.querySelector(".lab-body"), toast = el.querySelector(".lab-toast");
  const say = t => { toast.textContent = t; toast.classList.add("on"); clearTimeout(say.t); say.t = setTimeout(() => toast.classList.remove("on"), 1400); };
  const save = () => { try { localStorage.setItem(store, JSON.stringify(state)); } catch (_) {} };
  const fmt = (s, v) => (+v).toFixed(s[5] < .01 ? 3 : s[5] < 1 ? 2 : 0);
  const groups = [...new Set(spec.map(s => s[0]))];
  const refresh = () => groups.forEach(g => { const n = spec.filter(s => s[0] === g && state[s[1]] !== s[6]).length, d = body.querySelector('[data-g="' + g + '"]'); d.classList.toggle("dirty", n > 0); d.querySelector(".n").textContent = n + " changed"; });
  const paint = s => { const r = rows[s[1]], v = state[s[1]]; r.range.value = v; r.num.value = fmt(s, v); r.range.style.setProperty("--p", ((v - s[3]) / (s[4] - s[3]) * 100) + "%"); r.row.classList.toggle("dirty", v !== s[6]); };
  const set = (s, v, quiet) => { v = Math.min(s[4], Math.max(s[3], +v)); if (isNaN(v)) return; state[s[1]] = v; paint(s); refresh(); save(); if (!quiet) onChange(s[1], v); };
  groups.forEach((g, gi) => {
    const d = document.createElement("details"); d.className = "lab-group"; d.dataset.g = g; d.open = o.open ? o.open.includes(g) : gi === 0;
    d.innerHTML = '<summary>' + g + '<span class="n"></span></summary><div class="lab-rows"></div>';
    spec.filter(s => s[0] === g).forEach(s => {
      const id = "lab_" + s[1], row = document.createElement("div"); row.className = "lab-row";
      row.innerHTML = '<label for="' + id + '" title="Double-click to reset">' + s[2] + '</label><input type="number" min="' + s[3] + '" max="' + s[4] + '" step="' + s[5] + '" aria-label="' + s[2] + ' value">' +
        '<input id="' + id + '" type="range" min="' + s[3] + '" max="' + s[4] + '" step="' + s[5] + '">';
      const range = row.querySelector("[type=range]"), num = row.querySelector("[type=number]"); rows[s[1]] = { row, range, num };
      range.addEventListener("input", () => set(s, range.value)); num.addEventListener("change", () => set(s, num.value));
      row.querySelector("label").addEventListener("dblclick", () => set(s, s[6]));
      d.querySelector(".lab-rows").appendChild(row);
    });
    body.appendChild(d);
  });
  spec.forEach(s => set(s, s[1] in state ? state[s[1]] : s[6], true));
  const fold = el.querySelector("[data-a=fold]"), toggle = () => { const m = el.classList.toggle("min"); fold.textContent = m ? "⌃" : "⌄"; fold.setAttribute("aria-expanded", !m); };
  el.addEventListener("click", e => {
    const a = e.target.dataset && e.target.dataset.a; if (!a) return;
    if (a === "fold") toggle();
    if (a === "reset") { spec.forEach(s => set(s, s[6])); say("Reset to defaults"); }
    if (a === "copy") { const j = JSON.stringify(state); (navigator.clipboard ? navigator.clipboard.writeText(j) : Promise.reject()).then(() => say("Settings copied"), () => prompt("Settings", j)); }
    if (a === "paste") {
      const go = t => { try { const j = JSON.parse(t); spec.forEach(s => { if (s[1] in j) set(s, j[s[1]]); }); say("Settings applied"); } catch (_) { say("Not valid settings JSON"); } };
      navigator.clipboard && navigator.clipboard.readText ? navigator.clipboard.readText().then(go, () => go(prompt("Paste settings JSON") || "")) : go(prompt("Paste settings JSON") || "");
    }
  });
  addEventListener("keydown", e => { if (e.key === "h" && !/INPUT|TEXTAREA/.test(document.activeElement.tagName)) toggle(); });
  const head = el.querySelector(".lab-head"); let drag = null;       // drag by the header; the panel stays inside the window
  head.addEventListener("pointerdown", e => { if (e.target.closest("button")) return; const r = el.getBoundingClientRect(); drag = { x: e.clientX - r.left, y: e.clientY - r.top }; head.setPointerCapture(e.pointerId); });
  head.addEventListener("pointermove", e => { if (!drag) return; const w = el.offsetWidth, h = el.offsetHeight; el.style.right = el.style.bottom = "auto";
    el.style.left = Math.min(innerWidth - w - 8, Math.max(8, e.clientX - drag.x)) + "px"; el.style.top = Math.min(innerHeight - h - 8, Math.max(8, e.clientY - drag.y)) + "px"; });
  head.addEventListener("pointerup", () => { drag = null; });
  if (innerWidth < 700) toggle();
  document.body.appendChild(el);
  return { el, refresh: () => spec.forEach(paint) };
} };
