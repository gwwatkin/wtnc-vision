/**
 * render.js — DOM building and time formatting for the live results timeline.
 * Adapted from web/render.js.  Cards additionally set data-crossing-id /
 * data-annotated-url and carry the card--selectable class.
 * DOM manipulation only — no fetch, no pure data transforms.
 *
 * @module results/render
 */

import { UNKNOWN_CATEGORY } from "./data.js";

// ---------------------------------------------------------------------------
// Formatters (unchanged from web/render.js)
// ---------------------------------------------------------------------------

/**
 * Format a Date as wall-clock time-of-day "hh:mm:ss".
 * @param {Date} d
 * @returns {string}
 */
export function formatTimeOfDay(d) {
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

/**
 * Format a Date as "hh:mm" for use in gap separator labels.
 * @param {Date} d
 * @returns {string}
 */
export function formatGapLabel(d) {
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}

// ---------------------------------------------------------------------------
// Timeline renderer
// ---------------------------------------------------------------------------

/**
 * Build the timeline DOM under root (clears it first).  Renders lane headers,
 * then per pack: a full-width gap separator (formatGapLabel(pack.startTime))
 * followed by each result as a card placed in its lane's column.
 *
 * Each card carries:
 *   - data-crossing-id   (for sidebar wiring and re-applying selection highlight)
 *   - data-annotated-url (for the sidebar image)
 *   - class card--selectable (cursor + hover affordance)
 *
 * Selection highlight (card--selected) is NOT applied here — results.js applies
 * it after each render so re-renders stay pure.
 *
 * @param {HTMLElement}                          root
 * @param {import('./data.js').Pack[]}           packs
 * @param {import('./data.js').Lane[]}           lanes
 * @param {{ collapseBreakpointPx: number }}     opts
 * @returns {void}
 */
export function renderTimeline(root, packs, lanes, opts) {
  // Clear root.
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

  // Semantic class drives the grid layout in styles.css.
  root.classList.add("timeline");

  // Build lookup: category → lane.
  /** @type {Map<string, import('./data.js').Lane>} */
  const laneByCategory = new Map(lanes.map((l) => [l.category, l]));

  // Empty state.
  const hasResults = packs.some((p) => p.results.length > 0);
  if (!packs.length || !hasResults) {
    const empty = document.createElement("p");
    empty.className = "timeline__empty";
    empty.textContent = "No crossings yet — waiting for riders…";
    root.appendChild(empty);
    return;
  }

  // ── Lane header row ──────────────────────────────────────────────────────
  lanes.forEach((lane) => {
    const header = document.createElement("div");
    header.className = "lane-header";
    header.dataset.category = lane.category;
    header.style.gridColumn = lane.index + 1;
    header.textContent = lane.category;
    root.appendChild(header);
  });

  // ── Packs ─────────────────────────────────────────────────────────────────
  packs.forEach((pack) => {
    if (!pack.results.length) return;

    // Gap separator — spans all columns.
    const separator = document.createElement("div");
    separator.className = "gap-separator";
    separator.style.gridColumn = "1 / -1";
    separator.textContent = formatGapLabel(pack.startTime);
    root.appendChild(separator);

    // Each result as a card in its lane column.
    pack.results.forEach((result) => {
      const lane = laneByCategory.get(result.category);
      const col = lane != null ? lane.index + 1 : lanes.length;

      const card = document.createElement("div");
      card.style.gridColumn = col;

      const isUnknown = !result.matched;
      card.className = isUnknown
        ? "card card--unknown card--selectable"
        : "card card--selectable";
      card.dataset.category = result.category;

      // ── Task5 additions: crossing id + annotated URL for sidebar ──────────
      card.dataset.crossingId   = result.crossingId;
      card.dataset.annotatedUrl = result.annotatedUrl;
      // Extra attributes so results.js can reconstruct the Result on click
      // without re-fetching (avoids a second round-trip or shared state).
      card.dataset.raceNumber = result.raceNumber;
      card.dataset.name       = result.name ?? "";
      card.dataset.matched    = result.matched ? "true" : "false";
      card.dataset.time       = result.time.toISOString();
      // ─────────────────────────────────────────────────────────────────────

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

      // Meta line: category + time.  Category omitted for unknown riders.
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
