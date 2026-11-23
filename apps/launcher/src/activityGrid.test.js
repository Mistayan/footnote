// npm test
import { test } from "node:test";
import assert from "node:assert/strict";
import { buildActivityGrid } from "./activityGrid.js";

test("activity grid sizes dots by share, blends --save and --recall, and marks the week's busiest hour", () => {
  const mkDay = (date, saved, recalls, sessions, hotHour, hotSaved, hotRecalls) => ({
    date,
    saved,
    recalls,
    sessions,
    hours: Array.from({ length: 24 }, (_, h) =>
      h === hotHour ? { saved: hotSaved, recalls: hotRecalls } : { saved: 0, recalls: 0 },
    ),
  });
  const grid = buildActivityGrid({
    hours: [
      mkDay("2026-11-17", 4, 0, 1, 9, 4, 0),
      mkDay("2026-11-18", 0, 10, 2, 14, 0, 10),
      mkDay("2026-11-19", 6, 10, 3, 15, 6, 10),
    ],
  });

  assert.deepEqual(grid.totals, { saved: 10, recalls: 20, sessions: 6 });
  assert.deepEqual(grid.peak, { day: 2, hour: 15 });
  assert.equal(grid.rows[0].dots[0].fill, "var(--empty)");
  assert.equal(grid.rows[0].dots[0].r, 1.15);
  assert.equal(grid.rows[0].dots[9].fill, "color-mix(in oklab, var(--save) 100%, var(--recall))");
  assert.equal(grid.rows[1].dots[14].fill, "color-mix(in oklab, var(--save) 0%, var(--recall))");
  assert.equal(grid.rows[2].dots[15].busiest, true);
  assert.equal(grid.rows[2].dots[15].r, 6.4);
});

test("empty activity produces seven rows of 24 empty dots with no busiest ring", () => {
  const grid = buildActivityGrid({ days: [] }, new Date(2026, 10, 23));
  assert.equal(grid.rows.length, 7);
  assert.equal(grid.rows[6].today, true);
  assert.equal(grid.rows[6].dots.length, 24);
  assert.equal(grid.peak, null);
  assert.ok(grid.rows.every((r) => r.dots.every((d) => d.fill === "var(--empty)" && !d.busiest)));
});
