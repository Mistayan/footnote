// 7-day × 24-hour activity bubble grid (#635): turns `footnote activity`'s hourly counts (or day totals when earlier days
// have no hourly saves) into dot radii, blended save/recall fills and the week's busiest hour. Pure functions, tested in node.

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export const GRID_W = 256;
export const SLOT = GRID_W / 24;
export const ROW_H = 20;

export const hh = (h) => String(h).padStart(2, "0");

const shortDate = (iso) => {
  const [, m, d] = String(iso ?? "").split("-").map(Number);
  return `${d} ${MONTHS[(m || 1) - 1] ?? ""}`;
};

export function weekday(iso) {
  const [y, m, d] = String(iso ?? "").split("-").map(Number);
  return WEEKDAYS[new Date(y, (m || 1) - 1, d || 1).getDay()] ?? "";
}

function defaultWeek(now = new Date()) {
  return [6, 5, 4, 3, 2, 1, 0].map((back) => {
    const d = new Date(now);
    d.setDate(now.getDate() - back);
    const iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    return { date: iso, saved: 0, recalls: 0, sessions: 0, hours: Array.from({ length: 24 }, () => ({ saved: 0, recalls: 0 })) };
  });
}

export function buildActivityGrid(activity, now = new Date()) {
  const raw = activity?.hours?.length
    ? activity.hours.slice(-7)
    : activity?.days?.length
      ? activity.days.slice(-7)
      : defaultWeek(now);
  const days = raw.map((d) => {
    const cells = Array.from({ length: 24 }, (_, h) => ({
      saved: Number(d.hours?.[h]?.saved ?? 0),
      recalls: Number(d.hours?.[h]?.recalls ?? 0),
    }));
    const saved = Number(d.saved ?? 0);
    const recalls = Number(d.recalls ?? d.prompts_given_memories ?? 0);
    const sessions = Number(d.sessions ?? 0);
    const hourlySaved = cells.reduce((sum, c) => sum + c.saved, 0);
    return {
      date: d.date,
      wd: weekday(d.date),
      short: shortDate(d.date),
      saved,
      recalls,
      sessions,
      hourlySaved,
      hours: cells,
    };
  });

  const totalSaved = days.reduce((sum, d) => sum + d.saved, 0);
  const totalRecalls = days.reduce((sum, d) => sum + d.recalls, 0);
  const totalSessions = days.reduce((sum, d) => sum + d.sessions, 0);
  const sumHourlySaved = days.reduce((sum, d) => sum + d.hourlySaved, 0) || totalSaved;
  const sumHourlyRecalls =
    days.reduce((sum, d) => sum + d.hours.reduce((s, c) => s + c.recalls, 0), 0) || totalRecalls;

  const share = (c) =>
    (sumHourlySaved > 0 ? c.saved / sumHourlySaved : 0) +
    (sumHourlyRecalls > 0 ? c.recalls / sumHourlyRecalls : 0);

  let maxT = 0;
  let peak = [0, -1, -1];
  days.forEach((d, di) => {
    d.hours.forEach((c, h) => {
      const t = share(c);
      if (t > maxT) maxT = t;
      if (t > peak[0]) peak = [t, di, h];
    });
  });

  const rows = days.map((d, di) => ({
    ...d,
    today: di === days.length - 1,
    dots: d.hours.map((c, h) => {
      const a = sumHourlySaved > 0 ? c.saved / sumHourlySaved : 0;
      const b = sumHourlyRecalls > 0 ? c.recalls / sumHourlyRecalls : 0;
      const t = a + b;
      const rad = t > 0 && maxT > 0 ? 1.8 + Math.sqrt(t / maxT) * 4.6 : 1.15;
      const pct = t > 0 ? Math.round((a / t) * 100) : 0;
      const fill =
        t > 0
          ? `color-mix(in oklab, var(--save) ${pct}%, var(--recall))`
          : "var(--empty)";
      const cx = h * SLOT + SLOT / 2;
      const busiest = peak[0] > 0 && di === peak[1] && h === peak[2];
      return {
        h,
        saved: c.saved,
        recalls: c.recalls,
        cx,
        cy: ROW_H / 2,
        r: Number(rad.toFixed(2)),
        ringR: Number((rad + 2.6).toFixed(2)),
        fill,
        busiest,
      };
    }),
  }));

  return {
    rows,
    totals: { saved: totalSaved, recalls: totalRecalls, sessions: totalSessions },
    peak: peak[0] > 0 ? { day: peak[1], hour: peak[2] } : null,
  };
}
