/**
 * render.js — DOM building and time formatting.
 * Owned exclusively by task4 for implementation; stubs created in task1.
 * DOM manipulation only — no fetch, no pure data transforms.
 */

import { UNKNOWN_CATEGORY } from "./data.js";

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

/** Format a Date as wall-clock time-of-day "hh:mm:ss".
 *  @param {Date} d
 *  @returns {string}
 */
export function formatTimeOfDay(d) {
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

/** Format a Date as "hh:mm" for use in gap separator labels.
 *  @param {Date} d
 *  @returns {string}
 */
export function formatGapLabel(d) {
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

// ---------------------------------------------------------------------------
// Timeline renderer
// ---------------------------------------------------------------------------

/** Build the timeline DOM under root (clears it first). Renders lane headers, then
 *  per pack: a full-width gap separator (formatGapLabel(pack.startTime)) followed by
 *  each result as a card placed in its lane's column (grid-column) and its own row.
 *  @param {HTMLElement} root
 *  @param {import('./data.js').Pack[]} packs
 *  @param {import('./data.js').Lane[]} lanes
 *  @param {{collapseBreakpointPx: number}} opts
 *  @returns {void}
 */
export function renderTimeline(root, packs, lanes, opts) {
  // Clear root first.
  root.innerHTML = "";

  // Expose lane count and collapse breakpoint as custom properties on root.
  root.style.setProperty("--lane-count", lanes.length);
  if (opts && opts.collapseBreakpointPx != null) {
    root.style.setProperty(
      "--collapse-breakpoint-px",
      opts.collapseBreakpointPx
    );
    root.dataset.collapseBreakpointPx = opts.collapseBreakpointPx;
  }

  // Add the semantic class.
  root.classList.add("timeline");

  // Build a lookup: category → lane (for placing cards).
  /** @type {Map<string, import('./data.js').Lane>} */
  const laneByCategory = new Map(lanes.map((l) => [l.category, l]));

  // Empty state — no packs or all packs are empty.
  const hasResults = packs.some((p) => p.results.length > 0);
  if (!packs.length || !hasResults) {
    const empty = document.createElement("p");
    empty.className = "timeline__empty";
    empty.textContent = "No crossings yet — waiting for riders…";
    root.appendChild(empty);
    return;
  }

  // ── Lane header row ─────────────────────────────────────────────────────
  // One header cell per lane, placed in its column.
  lanes.forEach((lane) => {
    const header = document.createElement("div");
    header.className = "lane-header";
    header.dataset.category = lane.category;
    header.style.gridColumn = lane.index + 1;
    header.textContent = lane.category;
    root.appendChild(header);
  });

  // ── Packs ────────────────────────────────────────────────────────────────
  packs.forEach((pack) => {
    // Skip completely empty packs silently.
    if (!pack.results.length) return;

    // Gap separator — spans all columns.
    const separator = document.createElement("div");
    separator.className = "gap-separator";
    separator.style.gridColumn = "1 / -1";
    separator.textContent = formatGapLabel(pack.startTime);
    root.appendChild(separator);

    // Each result as its own card in its lane's column, in its own auto row.
    pack.results.forEach((result) => {
      const lane = laneByCategory.get(result.category);
      // Defensive: unknown category falls back to last column.
      const col = lane != null ? lane.index + 1 : lanes.length;

      const card = document.createElement("div");
      card.style.gridColumn = col;

      const isUnknown = !result.matched;
      card.className = isUnknown ? "card card--unknown" : "card";
      card.dataset.category = result.category;

      // Race number — always shown.
      const numEl = document.createElement("span");
      numEl.className = "card__number";
      numEl.textContent = `#${result.raceNumber}`;
      card.appendChild(numEl);

      // Name — "Unknown rider" when unmatched.
      const nameEl = document.createElement("span");
      nameEl.className = "card__name";
      nameEl.textContent = isUnknown ? "Unknown rider" : result.name;
      card.appendChild(nameEl);

      // Meta line: category + time. Category omitted for unknown riders.
      const metaEl = document.createElement("span");
      metaEl.className = "card__meta";
      if (!isUnknown) {
        metaEl.textContent = `${result.category} · ${formatTimeOfDay(result.time)}`;
      } else {
        metaEl.textContent = formatTimeOfDay(result.time);
      }
      card.appendChild(metaEl);

      root.appendChild(card);
    });
  });
}
