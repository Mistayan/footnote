// Product heroes: each product page tells its own story on a canvas behind the hero, around its glass lens.
//   lib   the lens is a magnifier over a page of your docs; the line under it is cited with file:line and whether it changed since
//   mem   memories fly in from the conversation and join a small web in the lens; each session start recalls a few and sends them on
//   code  a call graph: callers in, callees out, pulses through the function in the lens; focus walks to the next function.
//         One caller stays dashed and unnamed: Code would rather show no caller than a wrong one.
//   lean  orange noise and green failure lines arrive mixed; the lens separates them cleanly — green goes into a structured
//         prompt headed by a real benchmark case, while orange passes straight through as filtered-out noise.
// Same rules as the home stream: draws only on screen, in a visible tab, without reduced motion (then one still frame).
const GLOW = "95,211,195", HI = "150,236,224", TEXT = "234,240,235", OK = "127,211,154", WARN = "242,184,75";
const MONO = '"JetBrains Mono", ui-monospace, monospace';
const ease = u => (u < 0 ? 0 : u > 1 ? 1 : u * u * (3 - 2 * u));
const env = (u, len, fade = 400) => ease(u / fade) * (1 - ease((u - len + fade) / fade));   // fade in, hold, fade out over len ms
const rgba = (c, a) => `rgba(${c},${a < 0 ? 0 : a > 1 ? 1 : a})`;
function seeded(s) { return () => { s |= 0; s = (s + 0x6d2b79f5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

export function initScene(c, motion) {
  const x = c.getContext("2d"), lens = document.querySelector(c.dataset.lens), S = SCENES[c.dataset.scene];
  if (!lens || !S) return;
  const v = {};                                     // view: W, H, cx, cy, R, narrow
  let k, st, raf = 0, onScreen = true;

  function layout() {
    k = Math.min(devicePixelRatio || 1, 2);
    v.W = c.clientWidth; v.H = c.clientHeight; c.width = v.W * k; c.height = v.H * k;
    const r = lens.getBoundingClientRect(), b = c.getBoundingClientRect();
    v.cx = r.left - b.left + r.width / 2; v.cy = r.top - b.top + r.height / 2; v.R = r.width / 2;
    v.narrow = innerWidth < 760;                  // labels go under the lens instead of beside it
    st = S.init(v, seeded(11));
    if (motion.matches) frame(0);
  }

  function frame(t) {
    raf = 0;
    x.setTransform(k, 0, 0, k, 0, 0); x.clearRect(0, 0, v.W, v.H);
    S.draw(x, v, st, motion.matches ? S.still : t);
    schedule();
  }
  function schedule() { if (!raf && onScreen && !document.hidden && !motion.matches) raf = requestAnimationFrame(frame); }

  new IntersectionObserver(([e]) => { onScreen = e.isIntersecting; if (onScreen) schedule(); else { cancelAnimationFrame(raf); raf = 0; } }).observe(c);
  document.addEventListener("visibilitychange", schedule);
  motion.addEventListener("change", () => (motion.matches ? frame(0) : schedule()));
  addEventListener("resize", layout);
  layout(); schedule();
  document.fonts.load(`500 12px ${MONO}`).then(() => motion.matches && frame(0), () => {});
}

// A small pill with mono text, like the tags on the page.
function pill(x, text, px, py, color, a, align = "left") {
  x.font = `500 11px ${MONO}`;
  const w = x.measureText(text).width + 16, h = 20, left = align === "center" ? px - w / 2 : align === "right" ? px - w : px;
  x.beginPath(); x.roundRect(left, py - h / 2, w, h, 8);
  x.fillStyle = rgba("9,18,11", .8 * a); x.fill();
  x.strokeStyle = rgba(color, .5 * a); x.lineWidth = 1; x.stroke();
  x.fillStyle = rgba(color, a); x.textBaseline = "middle"; x.textAlign = "left"; x.fillText(text, left + 8, py + .5);
  return w;
}
function label(x, text, px, py, color, a, align = "left", size = 12) {
  x.font = `500 ${size}px ${MONO}`; x.fillStyle = rgba(color, a); x.textBaseline = "middle"; x.textAlign = align; x.fillText(text, px, py);
  return x.measureText(text).width;
}

const SCENES = {
  // ---- Library: a magnifier over your docs
  lib: {
    still: 1700,
    init(v, rnd) {
      const lines = [], CW = Math.min(v.R * 3.6, v.W - 24);
      for (let i = 0; i < 64; i++) {
        if (rnd() < .13) { lines.push(null); continue; }  // paragraph break
        const words = [], fill = CW * (.55 + .45 * rnd());
        for (let xw = 0; xw < fill;) { const w = 8 + rnd() * 34; words.push([xw, Math.min(w, fill - xw)]); xw += w + 6; }
        lines.push(words);
      }
      const files = Array.from({ length: 12 }, () => ({ p: rnd(), y: rnd() * 2 - 1, s: .6 + rnd() * .6 }));
      return { lines, files, CW, LH: 15, M: 1.7, cites: [["docs/api.md:142", "current", OK], ["notes/db.md:88", "changed since", WARN], ["guide/wal.md:42", "current", OK]] };
    },
    draw(x, v, s, T) {
      const { cx, cy, R, W } = v, { lines, LH, M, CW } = s, total = lines.length * LH, left = cx - CW / 2, span = R * (v.narrow ? 1.5 : 2.3);   // on a phone the page stays clear of the text above
      const yOf = (i, t) => ((((i * LH - t * .018) % total) + total) % total) - total / 2 + cy;
      // files drift in from the left: what you allowed Library to index
      for (const f of s.files) {
        const p = (f.p + T * .00004 * f.s) % 1, fx = p * (cx - R * 1.1), fy = cy + f.y * (1 - p) * v.H * .4, a = .35 * Math.sin(p * Math.PI);
        x.strokeStyle = rgba(GLOW, a); x.lineWidth = 1; x.strokeRect(fx, fy - 6, 9, 12);
        x.fillStyle = rgba(GLOW, a); x.fillRect(fx + 2, fy - 3, 5, 1); x.fillRect(fx + 2, fy, 4, 1);
      }
      const page = (alpha, hi) => {
        for (let i = 0; i < lines.length; i++) {
          const w = lines[i]; if (!w) continue;
          const y = yOf(i, T), d = Math.abs(y - cy) / span; if (d > 1) continue;
          x.fillStyle = rgba(i === hi ? HI : GLOW, alpha * (1 - d * d) * (i === hi ? 2.2 : 1));
          for (const [wx, ww] of w) x.fillRect(left + wx, y, ww, 1.6);
        }
      };
      // the cited line: picked when the cycle starts, followed while it scrolls through the lens
      const C = 3200, n = Math.floor(T / C), u = T % C, e = env(u, C);
      let hi = -1, best = 1e9;
      for (let i = 0; i < lines.length; i++) if (lines[i]) { const dd = Math.abs(yOf(i, n * C + 600) - cy); if (dd < best) { best = dd; hi = i; } }
      // outside the lens: the page, dim
      x.save(); x.beginPath(); x.rect(0, 0, W, v.H); x.arc(cx, cy, R, 0, Math.PI * 2); x.clip("evenodd"); page(.13, -1); x.restore();
      // inside: magnified, in focus
      x.save(); x.beginPath(); x.arc(cx, cy, R - 1, 0, Math.PI * 2); x.clip();
      x.translate(cx, cy); x.scale(M, M); x.translate(-cx, -cy);
      const yh = yOf(hi, T);
      if (e > 0) { x.fillStyle = rgba(GLOW, .13 * e); x.fillRect(left - 6, yh - 4.5, CW + 12, 10.5); }
      page(.42, e > .3 ? hi : -1);
      x.restore();
      // the citation
      if (e > 0) {
        const ym = cy + (yh - cy) * M, [file, tag, col] = s.cites[n % s.cites.length];
        if (Math.abs(ym - cy) < R * .9) {
          if (v.narrow) {
            const ly = cy + R + 22; label(x, file, cx, ly, TEXT, .85 * e, "center"); pill(x, tag, cx, ly + 24, col, e, "center");
          } else {
            x.strokeStyle = rgba(GLOW, .5 * e); x.lineWidth = 1; x.beginPath(); x.moveTo(cx + Math.sqrt(Math.max(0, R * R - (ym - cy) ** 2)), ym); x.lineTo(cx + R + 14, ym); x.stroke();
            const w = label(x, file, cx + R + 20, ym, TEXT, .85 * e); pill(x, tag, cx + R + 28 + w, ym, col, e);
          }
        }
      }
    },
  },

  // ---- Memory: saved from the conversation, recalled at session start
  mem: {
    still: 8700,
    init(v, rnd) {
      const nodes = [], R = v.R;
      for (let tries = 0; nodes.length < 22 && tries < 4000; tries++) {
        const a = rnd() * Math.PI * 2, r = Math.sqrt(rnd()) * R * .74, bx = Math.cos(a) * r, by = Math.sin(a) * r;
        if (nodes.every(n => Math.hypot(n.bx - bx, n.by - by) > R * .22)) nodes.push({ bx, by, ph: rnd() * 6.3 });
      }
      const edges = new Set();
      nodes.forEach((n, i) => nodes.map((m, j) => [j, Math.hypot(n.bx - m.bx, n.by - m.by)]).filter(([j]) => j !== i).sort((p, q) => p[1] - q[1]).slice(0, 2).forEach(([j]) => edges.add(i < j ? i + "-" + j : j + "-" + i)));
      const turns = Array.from({ length: 16 }, (_, i) => ({ p: i / 16 + rnd() * .03, lane: i % 2, len: 14 + rnd() * 34 }));
      return { nodes, edges: [...edges].map(e => e.split("-").map(Number)), turns };
    },
    draw(x, v, s, T) {
      const { cx, cy, R } = v, { nodes, edges, turns } = s;
      const pos = n => [cx + n.bx + Math.sin(T * .0005 + n.ph) * 3, cy + n.by + Math.cos(T * .0004 + n.ph) * 3];
      // the conversation: turns of a chat drifting toward the lens
      const end = cx - R * 1.15;
      for (const t of turns) {
        const p = (t.p + T * .00003) % 1, tx = p * end, a = .3 * Math.sin(p * Math.PI);
        x.fillStyle = rgba(t.lane ? GLOW : TEXT, a * (t.lane ? 1 : .6));
        x.beginPath(); x.roundRect(tx, cy + (t.lane ? 8 : -14), t.len, 6, 3); x.fill();
      }
      // saving: every 2.4 s one memory leaves the conversation and joins the web
      const SV = 2400, sn = Math.floor(T / SV), su = T % SV, target = nodes[(sn * 7) % nodes.length], [tx, ty] = pos(target);
      const flash = su > 1400 ? 1 - ease((su - 1400) / 800) : 0;
      if (su < 1400) {
        const q = ease(su / 1400), sx = end, sy = cy + 11, mx = (sx + tx) / 2, my = Math.min(sy, ty) - R * .5;
        for (let j = 0; j < 4; j++) {
          const qq = Math.max(0, q - j * .035), px = (1 - qq) ** 2 * sx + 2 * (1 - qq) * qq * mx + qq * qq * tx, py = (1 - qq) ** 2 * sy + 2 * (1 - qq) * qq * my + qq * qq * ty;
          x.fillStyle = rgba(HI, .9 - j * .22); x.fillRect(px - 1.6, py - 1.6, 3.2, 3.2);
        }
      }
      // recall: every 7.2 s a session starts, a pulse goes out and three memories light up and are sent on
      const RC = 7200, rn = Math.floor(T / RC), ru = T % RC, re = env(ru, 3600, 500);
      const lit = new Set([(rn * 5 + 1) % nodes.length, (rn * 5 + 8) % nodes.length, (rn * 5 + 15) % nodes.length]);
      if (ru < 1600) { x.strokeStyle = rgba(GLOW, .45 * (1 - ru / 1600)); x.lineWidth = 1.5; x.beginPath(); x.arc(cx, cy, R * (.25 + 1.3 * ease(ru / 1600)), 0, Math.PI * 2); x.stroke(); }
      x.lineWidth = 1;
      for (const [i, j] of edges) {
        const [ax, ay] = pos(nodes[i]), [bx, by] = pos(nodes[j]), on = re > 0 && lit.has(i) && lit.has(j);
        x.strokeStyle = rgba(on ? HI : GLOW, on ? .5 * re : .2); x.beginPath(); x.moveTo(ax, ay); x.lineTo(bx, by); x.stroke();
      }
      const P = v.narrow ? [cx, cy + R + 30] : [cx + R + 34, cy];
      nodes.forEach((n, i) => {
        const [px, py] = pos(n), l = lit.has(i) ? re : 0, f = n === target ? flash : 0, sz = 3 + 2.4 * Math.max(l, f);
        x.fillStyle = rgba(l || f ? HI : GLOW, .55 + .45 * Math.max(l, f)); x.beginPath(); x.arc(px, py, sz / 2 + .6, 0, Math.PI * 2); x.fill();
        if (l > 0 && ru > 500) {                     // sent on to the agent
          const q = ease((ru - 500) / 900);
          x.strokeStyle = rgba(HI, .35 * l); x.beginPath(); x.moveTo(px, py); x.lineTo(px + (P[0] - px) * q, py + (P[1] - py) * q); x.stroke();
        }
      });
      if (re > 0 && ru > 900) {
        const a = env(ru - 900, 2700, 400);
        if (v.narrow) { pill(x, "session start", P[0], P[1] + 4, GLOW, a, "center"); label(x, "3 memories recalled", P[0], P[1] + 30, TEXT, .8 * a, "center"); }
        else { const w = pill(x, "session start", P[0] + 6, P[1], GLOW, a); label(x, "3 recalled", P[0] + 14 + w, P[1], TEXT, .8 * a); }
      }
    },
  },

  // ---- Lean: a long shell log goes through the lens; green failure lines enter the prompt box, orange noise goes straight through as filtered out
  lean: {
    still: 2600,
    init(v, rnd) {
      // Orange is noise, green is what matters. Greens are evenly spaced so they reach the prompt on a steady beat.
      const N = 150, K = 5;
      const items = Array.from({ length: N }, (_, i) => {
        const keep = i % K === 0;
        return { p: keep ? i / N : i / N + rnd() * .004, y: rnd() * 2 - 1, len: 10 + rnd() * 40, keep, k: i / K };
      });
      // Real cases from bench/experiments/LEAN-D-RESULTS-2026-11-20.md; the kept lines are the kind of marker each case keeps.
      const cases = [
        { cmd: "cargo test", saved: "84% smaller", kept: "5 of 5 kept", rows: ["FAILED merge_overlaps", "panicked at lib.rs:88", "left: 3, right: 4", "test result: 1 failed"] },
        { cmd: "git log -20", saved: "70% smaller", kept: "10 of 10 kept", rows: ["737812a fix(site)", "8ab1904 fix(site)", "c3851cb fix(skills)", "a7fedbb fix(skills)"] },
        { cmd: "ruff", saved: "68% smaller", kept: "5 of 5 kept", rows: ["E501 db.py:31", "F401 app.py:3", "E711 cli.py:58", "Found 5 errors"] },
        { cmd: "cargo build", saved: "81% smaller", kept: "6 of 6 kept", rows: ["error[E0308] run.rs:142", "mismatched types", "expected u64, found i64", "error: could not compile"] },
      ];
      return { items, gap: K / N, cases };
    },
    draw(x, v, s, T) {
      const { cx, cy, R, W, H } = v, inL = cx - R, outL = cx + R, band = R * .4, SP = .000032, C = 4200;
      // the structured prompt: beside the lens (upper track) when there is room, under it otherwise
      const rowH = 22, ROWS = 5, headH = 32, footH = 26, ch = headH + ROWS * rowH + footH;
      let cw = Math.min(264, W - outL - 40), side = cw >= 176 && innerWidth > 1000;   // stacked layouts keep it under the lens
      if (!side) cw = Math.min(264, W - 32);
      const cardX = side ? outL + 26 : cx - cw / 2, cardY = side ? Math.max(12, cy - ch + 22) : cy + R + 26;
      const slotY = cardY + headH + (ROWS - 1) * rowH + rowH / 2, slotX = cardX + 12;
      const E = side ? [outL, slotY] : [cx - R * .25, cy + R * .92];                  // where the greens leave the lens
      const noiseY = side ? Math.max(cardY + ch + 38, cy + R * .44) : cy - R * .12;   // dedicated straight-through lane for orange noise
      const noiseBand = Math.min(14, R * .12);
      const travel = side ? cardX - outL : R * .9;
      const span = W + 160, qOut = (outL + 80) / span, qSlot = (outL + travel + 80) / span;
      const spread = v.narrow ? R * 1.3 : H * .42;

      // the stream, drawn first so lines slide in under the card
      for (const it of s.items) {
        const q = (it.p + T * SP) % 1, px = q * span - 80;
        let X = px, Y, a, col = it.keep ? GLOW : WARN, w = it.len, h = 1.6;
        const ny = noiseY + it.y * noiseBand;
        if (px < inL) {                               // in: orange and green mixed, funnelling into the lens
          const f = Math.max(0, px) / inL, g = ease((px - (inL - R * 1.3)) / (R * 1.3));
          Y = cy + it.y * (spread * (1 - f) + band * f); a = .06 + .5 * g;   // faint behind the hero text
        } else if (px < outL) {                       // the lens separates them: green aligns to the prompt box, orange aligns to its straight-through lane
          const f = (px - inL) / (2 * R), y0 = cy + it.y * band;
          if (it.keep) { Y = y0 + (E[1] - y0) * ease(f / .65); X = side ? px : px + (E[0] - px) * ease((f - .4) / .6); a = .95; w = 20; h = 2.2; }
          else { Y = y0 + (ny - y0) * ease(f / .55); a = .62; w *= .85; }
        } else if (it.keep) {                         // out (green): into the bottom row of the prompt card
          if (q > qSlot) continue;
          const t = ease((q - qOut) / (qSlot - qOut));
          X = E[0] + (slotX - E[0]) * t; Y = E[1] + (slotY - E[1]) * t; a = .95; w = 20 * (1 - .6 * t); h = 2.2;
        } else {                                      // out (orange): passes straight through as filtered-out noise
          const dOut = (px - outL) / Math.max(160, W - outL);
          if (dOut >= 1) continue;
          X = px; Y = ny; a = .5 * (1 - ease(dOut)); w *= .75; h = 1.4;
        }
        if (a <= 0) continue;
        x.fillStyle = rgba(col, a); x.fillRect(X, Y, w, h);
      }

      // label the straight-through orange stream as filtered-out noise
      if (side) {
        const nw = pill(x, "noise", cardX, noiseY + 26, WARN, .9);
        label(x, "filtered out", cardX + nw + 8, noiseY + 26, TEXT, .65, "left", 11);
      } else if (W - outL >= 115) {
        pill(x, "noise", outL + 12, noiseY + 26, WARN, .9);
        label(x, "filtered out", outL + 12, noiseY + 46, TEXT, .65, "left", 11);
      } else {
        pill(x, "noise · filtered", W - 12, noiseY + 28, WARN, .9, "right");
      }

      // the card: the case on screen now in the header, the kept lines below
      const n = Math.floor(T / C), e = env(T % C, C), cs = s.cases[n % s.cases.length];
      x.beginPath(); x.roundRect(cardX, cardY, cw, ch, 14);
      x.fillStyle = "rgba(9,18,11,.92)"; x.fill(); x.strokeStyle = rgba(GLOW, .35); x.lineWidth = 1; x.stroke();
      label(x, cs.cmd, cardX + 12, cardY + headH / 2 + 1, TEXT, .9 * e, "left", 12);
      label(x, cs.saved, cardX + cw - 12, cardY + headH / 2 + 1, HI, e, "right", 11);
      x.fillStyle = rgba(GLOW, .2); x.fillRect(cardX + 1, cardY + headH, cw - 2, 1); x.fillRect(cardX + 1, cardY + ch - footH, cw - 2, 1);
      label(x, cs.kept, cardX + 12, cardY + ch - footH / 2 + 1, TEXT, .6 * e, "left", 11);
      label(x, "prompt", cardX + cw - 12, cardY + ch - footH / 2 + 1, GLOW, .55, "right", 11);
      // rows: every green that reached the slot, newest at the bottom, older ones scrolling up and out;
      // a row keeps the text of the case that was on screen when it arrived
      x.save(); x.beginPath(); x.rect(cardX, cardY + headH + 1, cw, ROWS * rowH); x.clip();
      for (const it of s.items) {
        if (!it.keep) continue;
        const d = ((((it.p + T * SP) % 1) - qSlot) % 1 + 1) % 1, pos = d / s.gap;
        if (pos > ROWS) continue;
        const arrived = Math.max(0, T - d / SP), rc = s.cases[Math.floor(arrived / C) % s.cases.length];
        const ry = slotY - pos * rowH, a = ease(pos / .35) * (1 - ease((pos - (ROWS - 1.3)) / .5)), fresh = 1 - ease(pos / 1.2);
        if (a <= 0) continue;
        if (fresh > 0) { x.fillStyle = rgba(GLOW, .12 * fresh); x.fillRect(cardX + 2, ry - rowH / 2 + 1, cw - 4, rowH - 2); }
        x.fillStyle = rgba(GLOW, .9 * a); x.beginPath(); x.arc(cardX + 15, ry, 2.4, 0, Math.PI * 2); x.fill();
        label(x, rc.rows[it.k % rc.rows.length], cardX + 25, ry + 1, HI, a, "left", 11);
      }
      x.restore();
    },
  },

  // ---- Code: who calls what, from the compiler's index
  code: {
    still: 2000,
    init() {
      return { sets: [
        { f: "index", ins: ["cli::run", "watch::sync", "update"], outs: ["crawl", "extract", "embed"], unknown: true, next: 1 },
        { f: "extract", ins: ["index", "reindex"], outs: ["parse_pdf", "chunk", "hash"], next: 1 },
        { f: "chunk", ins: ["extract", "split_md"], outs: ["tokens", "overlap"], unknown: true, next: 0 },
      ] };
    },
    draw(x, v, s, T) {
      const { cx, cy, R } = v, C = 5200, n = Math.floor(T / C), u = T % C, e = env(u, C, 500), set = s.sets[n % s.sets.length];
      const rr = R * (v.narrow ? 1.3 : 1.5);
      const angs = k => (k === 3 ? [-32, 0, 32] : [-20, 20]);
      x.font = `600 14px ${MONO}`;
      const pw = Math.min(x.measureText(set.f).width + 26, R * 1.6), ph = 30;
      const node = (deg, side) => { const a = deg * Math.PI / 180; return [cx + side * Math.cos(a) * rr, cy + Math.sin(a) * rr * .85]; };
      const edge = (ax, ay, bx, by, dashed, a) => {
        x.setLineDash(dashed ? [4, 5] : []); x.strokeStyle = rgba(dashed ? TEXT : GLOW, a); x.lineWidth = 1.2;
        const mx = (ax + bx) / 2; x.beginPath(); x.moveTo(ax, ay); x.bezierCurveTo(mx, ay, mx, by, bx, by); x.stroke(); x.setLineDash([]);
      };
      const at = (ax, ay, bx, by, q) => { const mx = (ax + bx) / 2, w = 1 - q; return [w ** 3 * ax + 3 * w * w * q * mx + 3 * w * q * q * mx + q ** 3 * bx, w ** 3 * ay + 3 * w * w * q * ay + 3 * w * q * q * by + q ** 3 * by]; };
      const L = [cx - pw / 2, cy], Rr = [cx + pw / 2, cy];
      const walk = u > C - 1400 ? ease((u - (C - 1400)) / 500) : 0;   // the next function lights up just before focus moves to it
      const draw = (names, side) => names.forEach((nm, i) => {
        const [nx, ny] = node(angs(names.length)[i], side), [ex, ey] = side < 0 ? L : Rr;
        edge(nx, ny, ex, ey, false, .4 * e);
        const q = ((T / 1500 + i * .37) % 1), [px, py] = side < 0 ? at(nx, ny, ex, ey, q) : at(ex, ey, nx, ny, q);
        x.fillStyle = rgba(HI, .9 * e * Math.sin(q * Math.PI)); x.fillRect(px - 1.8, py - 1.8, 3.6, 3.6);
        const nextOne = side > 0 && i === set.next && walk > 0;
        x.fillStyle = rgba(nextOne ? HI : GLOW, e); x.beginPath(); x.arc(nx, ny, nextOne ? 4.5 : 3.5, 0, Math.PI * 2); x.fill();
        label(x, nm, nx, ny - 15, nextOne ? HI : TEXT, (nextOne ? 1 : .72) * e, "center");
      });
      draw(set.ins, -1); draw(set.outs, 1);
      if (set.unknown) {                               // a call Code could not resolve: it stays unnamed rather than guessed
        const [nx, ny] = node(62, -1);
        edge(nx, ny, L[0], L[1], true, .28 * e);
        x.strokeStyle = rgba(TEXT, .4 * e); x.lineWidth = 1; x.beginPath(); x.arc(nx, ny, 3.5, 0, Math.PI * 2); x.stroke();
        label(x, "?", nx, ny + 16, TEXT, .5 * e, "center");
      }
      // the function in focus
      x.beginPath(); x.roundRect(cx - pw / 2, cy - ph / 2, pw, ph, 15);
      x.fillStyle = rgba(GLOW, .1 * e); x.fill(); x.strokeStyle = rgba(GLOW, .9 * e); x.lineWidth = 1.4; x.stroke();
      label(x, set.f, cx, cy + .5, HI, e, "center", 14);
    },
  },
};
