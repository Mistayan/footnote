import { useEffect, useState } from "react";
import { RefreshCw, ExternalLink } from "lucide-react";
import { footnote, mb, num, openSupport, shortDate } from "./data.js";
import { Tabs, Tip } from "./ui.jsx";

const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const tokens = (n) =>
  n >= 1e9 ? `${(n / 1e9).toFixed(2)}B` : n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k` : num(n);

const AGENT_META = {
  "claude-code": { label: "Claude Code", color: "var(--c1)" },
  antigravity: { label: "Antigravity", color: "var(--c2)" },
  codex: { label: "Codex", color: "var(--c3)" },
  "deepseek-harness": { label: "DeepSeek Harness", color: "var(--c4)" },
};
const resetsIn = (m) => (m >= 1440 ? `${Math.round(m / 1440)} d` : m >= 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`);
const agentInfo = (id) => AGENT_META[id] ?? { label: id, color: "var(--mute)" };
const totalTokens = (t) => (t.input ?? 0) + (t.output ?? 0) + (t.cache_read ?? 0) + (t.cache_write_5m ?? 0) + (t.cache_write_1h ?? 0);

function smoothPath(pts) {
  if (pts.length === 0) return "";
  if (pts.length === 1) return `M${pts[0][0]},${pts[0][1]}`;
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    // Clamp control points between the two ends so the curve never overshoots (no dips below zero).
    const lo = Math.min(p1[1], p2[1]), hi = Math.max(p1[1], p2[1]);
    const clamp = (v) => Math.min(hi, Math.max(lo, v));
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
    const cp1y = clamp(p1[1] + (p2[1] - p0[1]) / 6);
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
    const cp2y = clamp(p2[1] - (p3[1] - p1[1]) / 6);
    d += ` C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`;
  }
  return d;
}

function DailyChart({ byDay, byDayAgent, agents, metric }) {
  const [hover, setHover] = useState(null);
  const dates = byDay.map((d) => d.date);
  if (dates.length === 0) return <p className="dimmed small">No daily activity in this period.</p>;

  const W = 640, H = 196, padL = 48, padR = 14, padT = 14, padB = 26;
  const cw = W - padL - padR;
  const ch = H - padT - padB;
  const val = (row) => (metric === "cost" ? row.api_price_usd ?? 0 : totalTokens(row));

  // Build one series per agent (falling back to overall total if by_day_agent isn't present).
  const series =
    byDayAgent?.length > 0 && agents.length > 0
      ? agents.map((a) => ({
          id: a.agent,
          color: agentInfo(a.agent).color,
          values: dates.map((dt) => {
            const hit = byDayAgent.find((r) => r.date === dt && r.agent === a.agent);
            return hit ? val(hit) : 0;
          }),
        }))
      : [{ id: "all", color: "var(--c1)", values: byDay.map(val) }];

  const maxV = Math.max(1e-6, ...series.flatMap((s) => s.values));
  const y = (v) => padT + ch - (v / maxV) * ch;
  const x = (i) => (dates.length === 1 ? padL + cw / 2 : padL + (i / (dates.length - 1)) * cw);
  const ticks = [0, 0.5, 1];
  const fmtTick = (v) => (metric === "cost" ? usd.format(v) : tokens(Math.round(v)));
  const labelIdx = dates.length <= 4 ? dates.map((_, i) => i) : [0, Math.floor((dates.length - 1) / 2), dates.length - 1];
  const hi = hover != null && hover < dates.length ? hover : null;
  const pick = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const vx = ((e.clientX - r.left) / r.width) * W;
    setHover(dates.length === 1 ? 0 : Math.max(0, Math.min(dates.length - 1, Math.round(((vx - padL) / cw) * (dates.length - 1)))));
  };
  const onKey = (e) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      const step = e.key === "ArrowLeft" ? -1 : 1;
      setHover((h) => Math.max(0, Math.min(dates.length - 1, (h ?? (step > 0 ? -1 : dates.length)) + step)));
    } else if (e.key === "Escape") setHover(null);
  };
  const title = metric === "cost" ? "Daily API list cost" : "Daily processed tokens";

  return (
    <div className="usage-chart">
      <div className="usage-chart-title">{title}</div>
      <div className="usage-chart-plot">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`${title}. Hover or use arrow keys to read each day.`} tabIndex={0}
        onMouseMove={pick} onMouseLeave={() => setHover(null)} onKeyDown={onKey} onBlur={() => setHover(null)}>
        <defs>
          {series.map((s) => (
            <linearGradient key={s.id} id={`ug-${s.id}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" style={{ stopColor: s.color, stopOpacity: 0.22 }} />
              <stop offset="100%" style={{ stopColor: s.color, stopOpacity: 0.01 }} />
            </linearGradient>
          ))}
        </defs>
        {ticks.map((f) => {
          const yy = padT + ch * (1 - f);
          return (
            <g key={f}>
              <line x1={padL} y1={yy} x2={W - padR} y2={yy} className="chart-grid" />
              <text x={padL - 8} y={yy + 3} textAnchor="end" className="chart-axis">{fmtTick(maxV * f)}</text>
            </g>
          );
        })}
        {series.map((s) => {
          const pts = s.values.map((v, i) => [x(i), y(v)]);
          const line = smoothPath(pts);
          const area = `${line} L${pts[pts.length - 1][0].toFixed(1)},${(padT + ch).toFixed(1)} L${pts[0][0].toFixed(1)},${(padT + ch).toFixed(1)} Z`;
          return (
            <g key={s.id}>
              {pts.length > 1 && <path d={area} fill={`url(#ug-${s.id})`} />}
              <path d={line} fill="none" style={{ stroke: s.color }} strokeWidth="1.8" />
              {pts.map(([px, py], i) => (
                <circle key={dates[i]} cx={px} cy={py} r={i === hi ? 4 : 2.5} style={{ fill: s.color }} opacity={i === hi ? 1 : pts.length <= 14 ? 0.85 : 0} />
              ))}
            </g>
          );
        })}
        {hi != null && <line x1={x(hi)} x2={x(hi)} y1={padT} y2={padT + ch} className="chart-cursor" />}
        {labelIdx.map((i) => (
          <text key={dates[i]} x={x(i)} y={H - 6} textAnchor={i === 0 ? "start" : i === dates.length - 1 ? "end" : "middle"} className="chart-axis">
            {shortDate(dates[i]).toUpperCase()}
          </text>
        ))}
      </svg>
      {hi != null && (
        <div className={`chart-tip${x(hi) > W * 0.6 ? " left" : ""}`} style={{ left: `${(100 * x(hi)) / W}%` }} aria-live="polite">
          <b>{shortDate(dates[hi])}</b>
          {series
            .map((s) => ({ s, v: s.values[hi] }))
            .sort((a, b) => b.v - a.v)
            .map(({ s, v }) => (
              <span key={s.id}>
                <i style={{ background: s.color }} />
                <span className="dimmed">{s.id === "all" ? "All agents" : agentInfo(s.id).label}</span>
                <b className="mono">{fmtTick(v)}</b>
              </span>
            ))}
          {series.length > 1 && (
            <span className="chart-tip-total">
              <span className="dimmed">Total</span>
              <b className="mono">{fmtTick(series.reduce((a, s) => a + s.values[hi], 0))}</b>
            </span>
          )}
        </div>
      )}
      </div>
    </div>
  );
}

export default function Usage() {
  const [days, setDays] = useState(7);
  const [metric, setMetric] = useState("tokens"); // "tokens" | "cost"
  const [breakdown, setBreakdown] = useState("model"); // "model" | "day"
  const [state, setState] = useState({ loading: true });
  const [syncing, setSyncing] = useState(false);

  const loadUsage = (sync = false) => {
    let live = true;
    if (sync) setSyncing(true);
    else setState((s) => ({ ...s, loading: true, error: null }));
    const args = sync ? ["usage", "--days", String(days), "--sync-prices"] : ["usage", "--days", String(days)];
    footnote(...args).then(
      (data) => {
        if (!live) return;
        setSyncing(false);
        setState({ loading: false, data });
      },
      (error) => {
        if (!live) return;
        setSyncing(false);
        setState((s) => ({ ...s, loading: false, error: String(error) }));
      },
    );
    return () => { live = false; };
  };

  useEffect(() => loadUsage(false), [days]);

  const data = state.data;
  const t = data?.totals;
  const allTok = t ? totalTokens(t) : 0;
  const agents = (data?.by_agent ?? []).slice().sort((a, b) => (metric === "cost" ? b.api_price_usd - a.api_price_usd : totalTokens(b) - totalTokens(a)));
  const models = (data?.by_model ?? []).slice().sort((a, b) => (metric === "cost" ? b.api_price_usd - a.api_price_usd : totalTokens(b) - totalTokens(a)));
  const daysDesc = (data?.by_day ?? []).slice().reverse();

  const lean = data?.measured_savings;
  const leanTok = lean?.total_saved_tokens_estimate ?? ((lean?.shell?.saved_tokens_estimate ?? 0) + (lean?.footnote?.saved_tokens_estimate ?? 0));
  const leanBytes = lean?.total_saved_bytes ?? 0;

  const cacheWrite = t ? t.cache_write_5m + t.cache_write_1h : 0;
  const segs = t && allTok > 0
    ? [
        { k: "Cache read", n: t.cache_read, cost: t.cost_cache_read, color: "var(--c1)" },
        { k: "Uncached input", n: t.input, cost: t.cost_input, color: "var(--c3)" },
        { k: "Cache write", n: cacheWrite, cost: t.cost_cache_write, color: "var(--c2)" },
        { k: "Output", n: t.output, cost: t.cost_output, color: "var(--c4)" },
      ]
    : [];
  // Measured savings never reached the model, so they sit beside the processed tokens, not inside them.
  const saved = [
    { k: "Saved by Lean (shell)", n: lean?.shell?.saved_tokens_estimate ?? 0 },
    { k: "Saved by Footnote tools", n: lean?.footnote?.saved_tokens_estimate ?? 0 },
  ].filter((s) => s.n > 0);
  const barTotal = allTok + saved.reduce((a, s) => a + s.n, 0);

  const priceSource = data?.price_source;

  return (
    <div className="body usage-page">
      <div className="bar wrap">
        <Tabs value={days} options={[[1, "Past 24h"], [7, "7 days"], [30, "30 days"], [90, "90 days"]]} onChange={setDays} label="Period" />
        <Tabs value={metric} options={[["cost", "Cost"], ["tokens", "Tokens"]]} onChange={setMetric} label="Metric" />
        <span style={{ marginLeft: "auto" }}>
          <Tip tip={syncing ? "Syncing prices…" : "Sync the latest model prices from LiteLLM"} side="left">
            <button type="button" className="ic-btn" disabled={syncing} onClick={() => loadUsage(true)} aria-label="Sync prices">
              <RefreshCw size={15} strokeWidth={1.75} className={syncing ? "spin" : ""} />
            </button>
          </Tip>
        </span>
      </div>

      {state.error ? (
        <p className="empty warn" role="alert">{state.error}</p>
      ) : !data ? (
        <span className="skel" />
      ) : (
        <>
          <section className="usage-hero sq">
            <div className="usage-hero-left">
              <div className="usage-big">{metric === "cost" ? usd.format(t.api_price_usd) : tokens(allTok)}</div>
              <div className="dimmed small">
                {num(t.requests)} requests · {metric === "cost" ? `${tokens(allTok)} tokens` : `${usd.format(t.api_price_usd)} at API list prices`}
                {t.unpriced_requests > 0 && <span className="warn"> · {num(t.unpriced_requests)} unpriced</span>}
              </div>
              <ul className="usage-agents">
                {agents.map((a) => {
                  const info = agentInfo(a.agent);
                  const share = allTok > 0 ? (100 * totalTokens(a)) / allTok : 0;
                  return (
                    <li key={a.agent}>
                      <div className="ua-top">
                        <span className="ua-dot" style={{ background: info.color }} />
                        <b>{info.label}</b>
                        <span className="dimmed small">{num(a.requests)} req</span>
                        <span className="mono ua-val">{metric === "cost" ? usd.format(a.api_price_usd) : tokens(totalTokens(a))}</span>
                      </div>
                      <div className="dimmed small ua-sub">
                        {share.toFixed(1)}% of tokens · {usd.format(a.api_price_usd)}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
            <DailyChart byDay={data.by_day ?? []} byDayAgent={data.by_day_agent} agents={agents} metric={metric} />
          </section>

          <section className="usage-totals">
            <h2 className="section">Totals</h2>
            <div className="totals-strip sq">
              <div><span className="dimmed small">Processed tokens</span><b className="mono">{tokens(allTok)}</b></div>
              <div><span className="dimmed small">Cached input</span><b className="mono">{tokens(t.cache_read)}</b></div>
              <div><span className="dimmed small">Uncached input</span><b className="mono">{tokens(t.input)}</b></div>
              <div><span className="dimmed small">Output</span><b className="mono">{tokens(t.output)}</b></div>
              <div>
                <span className="dimmed small">Trimmed by Footnote Lean</span>
                <b className="mono ok">{tokens(leanTok)}</b>
                {leanBytes > 0 && <span className="dimmed small">{mb(leanBytes)} filtered · not priced</span>}
              </div>
            </div>
          </section>

          <section className="usage-limits">
            <h2 className="section">Rate limits</h2>
            {(data.limits?.current ?? []).length === 0 ? (
              <p className="dimmed small">
                No limit window open. Codex logs the share used on every turn; Claude Code logs a limit only when it is hit.
              </p>
            ) : (
              <ul className="limit-list">
                {data.limits.current.map((l) => {
                  const pct = Math.min(100, Math.max(0, l.used_percent));
                  return (
                    <li key={`${l.agent}|${l.window}`}>
                      <span className="small"><b>{agentInfo(l.agent).label}</b> <span className="dimmed">{l.window}</span></span>
                      <span className="meter" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(pct)} aria-label={`${agentInfo(l.agent).label} ${l.window} limit used`}>
                        <span className={pct >= 90 ? "warn-fill" : ""} style={{ width: `${pct}%` }} />
                      </span>
                      <span className="mono small">{Math.round(pct)}%</span>
                      <span className="dimmed small">resets in {resetsIn(l.resets_in_minutes)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {segs.length > 0 && (
            <section className="usage-types">
              <h2 className="section">Tokens by type</h2>
              <div className="stack-bar" role="img" aria-label="Token share by type">
                {segs.map((s) => (
                  <span key={s.k} style={{ width: `${Math.max(0.4, (100 * s.n) / barTotal)}%`, background: s.color }} title={`${s.k}: ${tokens(s.n)}`} />
                ))}
                {saved.map((s) => (
                  <span key={s.k} className="seg-saved" style={{ width: `${Math.max(0.4, (100 * s.n) / barTotal)}%` }} title={`${s.k}: ${tokens(s.n)} (measured, never sent)`} />
                ))}
              </div>
              <div className="stack-legend">
                {segs.map((s) => (
                  <span key={s.k} className="small">
                    <i style={{ background: s.color }} />
                    <span className="dimmed">{s.k}</span> <b className="mono">{tokens(s.n)}</b>
                    {s.cost != null && <span className="mono dimmed"> · {usd.format(s.cost)}</span>}
                  </span>
                ))}
                {saved.map((s) => (
                  <span key={s.k} className="small">
                    <i className="seg-saved" />
                    <span className="dimmed">{s.k}</span> <b className="mono ok">−{tokens(s.n)}</b>
                  </span>
                ))}
              </div>
            </section>
          )}

          <section className="usage-breakdown">
            <div className="bar">
              <h2 className="section">Breakdown</h2>
              <Tabs value={breakdown} options={[["model", "Model"], ["day", "Day"]]} onChange={setBreakdown} label="Breakdown view"
                className="push" />
            </div>
            {breakdown === "model" ? (
              <table className="tbl usage-tbl">
                <thead>
                  <tr>
                    <th scope="col" style={{ width: 32 }}>#</th>
                    <th scope="col">Model</th>
                    <th scope="col" className="num">Cost</th>
                    <th scope="col" className="num">Share</th>
                    <th scope="col" className="num">Tokens</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m, idx) => {
                    const mt = totalTokens(m);
                    const pct = allTok > 0 ? (100 * mt) / allTok : 0;
                    const maxRow = models[0] ? (metric === "cost" ? Math.max(0.01, models[0].api_price_usd) : Math.max(1, totalTokens(models[0]))) : 1;
                    const barPct = (100 * (metric === "cost" ? m.api_price_usd : mt)) / maxRow;
                    return (
                      <tr key={m.model}>
                        <td className="dimmed mono">{idx + 1}</td>
                        <td>
                          <div className="mono">{m.model}{m.unpriced_requests > 0 && <span className="warn small"> · unpriced</span>}</div>
                          <div className="inline-bar"><span style={{ width: `${Math.max(1, barPct)}%` }} /></div>
                        </td>
                        <td className="num mono">{usd.format(m.api_price_usd)}</td>
                        <td className="num mono dimmed">{pct.toFixed(1)}%</td>
                        <td className="num mono">{tokens(mt)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            ) : (
              <table className="tbl usage-tbl">
                <thead>
                  <tr>
                    <th scope="col">Day</th>
                    <th scope="col" className="num">Requests</th>
                    <th scope="col" className="num">Cache read</th>
                    <th scope="col" className="num">Output</th>
                    <th scope="col" className="num">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {daysDesc.map((d) => (
                    <tr key={d.date}>
                      <td className="mono">{shortDate(d.date)}</td>
                      <td className="num mono">{num(d.requests)}</td>
                      <td className="num mono">{tokens(d.cache_read)}</td>
                      <td className="num mono">{tokens(d.output)}</td>
                      <td className="num mono">{usd.format(d.api_price_usd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <footer className="usage-foot">
            <span className="dimmed small">Local session counts only (no prompt text kept). Dates in UTC.</span>
            <span className="dimmed small usage-credit">
              Prices provided by{" "}
              <button type="button" className="help-link" onClick={() => openSupport("litellm")}>
                {priceSource?.name ?? "LiteLLM"}
                <ExternalLink size={11} strokeWidth={1.75} style={{ marginLeft: 3, verticalAlign: "-1px" }} />
              </button>
              {" + Footnote overrides"}
              {priceSource?.synced_at ? ` · synced ${priceSource.synced_at}` : ` · ${data.prices}`}
            </span>
          </footer>
        </>
      )}
    </div>
  );
}
