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
 * Crossing cards carry:
 *   - data-crossing-id      (for sidebar wiring and re-applying selection highlight)
 *   - data-annotated-url    (for the sidebar image)
 *   - data-source           "auto" | "manual"
 *   - data-edited           "true" | "false"
 *   - data-order-key        epoch-ms float as string
 *   - data-order-overridden "true" | "false"
 *   - class card--selectable (cursor + hover affordance)
 *   - provenance badges: ✚ manual, ✎ edited, ↕ moved
 *
 * Candidate pseudo-result cards carry:
 *   - data-candidate-id     (NOT data-crossing-id — tasks 6/7 distinguish by this)
 *   - data-run
 *   - data-time             ISO string
 *   - data-last-seen        ISO string
 *   - data-frame-count
 *   - data-hint-number      hint number string, or "" when null
 *   - data-hint-conf
 *   - data-image-url
 *   - data-rep-box          JSON-encoded [x1,y1,x2,y2]
 *   - data-number-text
 *   - class card card--candidate card--selectable
 *
 * Selection highlight (card--selected) is NOT applied here — results.js applies
 * it after each render so re-renders stay pure.
 *
 * @param {HTMLElement}                                        root
 * @param {import('./data.js').Pack[]}                        packs
 * @param {import('./data.js').Lane[]}                        lanes
 * @param {{ collapseBreakpointPx: number }}                  opts
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
      if (result.isCandidate) {
        root.appendChild(_buildCandidateCard(result, lanes));
      } else {
        root.appendChild(_buildCrossingCard(result, laneByCategory, lanes));
      }
    });
  });
}

// ---------------------------------------------------------------------------
// Card builders — private helpers
// ---------------------------------------------------------------------------

/**
 * Build a crossing result card.
 *
 * @param {import('./data.js').Result} result
 * @param {Map<string, import('./data.js').Lane>} laneByCategory
 * @param {import('./data.js').Lane[]} lanes
 * @returns {HTMLElement}
 */
function _buildCrossingCard(result, laneByCategory, lanes) {
  const lane = laneByCategory.get(result.category);
  const col = lane != null ? lane.index + 1 : lanes.length;

  const card = document.createElement("div");
  card.style.gridColumn = col;

  const isUnknown = !result.matched;
  card.className = isUnknown
    ? "card card--unknown card--selectable"
    : "card card--selectable";
  card.dataset.category = result.category;

  // ── Crossing identity & sidebar data ──────────────────────────────────────
  card.dataset.crossingId   = result.crossingId;
  card.dataset.run          = result.run;
  card.dataset.annotatedUrl = result.annotatedUrl;
  card.dataset.raceNumber   = result.raceNumber;
  card.dataset.name         = result.name ?? "";
  card.dataset.matched      = result.matched ? "true" : "false";
  card.dataset.time         = result.time.toISOString();

  // ── New fields (task5) ────────────────────────────────────────────────────
  card.dataset.source           = result.source;
  card.dataset.edited           = result.edited ? "true" : "false";
  card.dataset.orderKey         = String(result.orderKey);
  card.dataset.orderOverridden  = result.orderOverridden ? "true" : "false";
  card.dataset.numberText       = result.numberText;

  // ── Provenance badges (D3) ────────────────────────────────────────────────
  // Rendered before the number so they appear at the top-left of the card.
  if (result.source === "manual") {
    const badge = document.createElement("span");
    badge.className = "badge badge--manual";
    badge.textContent = "✚ manual";
    card.appendChild(badge);
  }
  if (result.edited) {
    const badge = document.createElement("span");
    badge.className = "badge badge--edited";
    badge.textContent = "✎ edited";
    card.appendChild(badge);
  }
  if (result.orderOverridden) {
    const badge = document.createElement("span");
    badge.className = "badge badge--moved";
    badge.textContent = "↕ moved";
    card.appendChild(badge);
  }

  // ── Race number — always shown ─────────────────────────────────────────────
  const numEl = document.createElement("span");
  numEl.className = "card__number";
  // Use numberText for display so "—" renders for unidentified crossings.
  numEl.textContent = result.numberText !== "—"
    ? `#${result.raceNumber}`
    : "# —";
  card.appendChild(numEl);

  // ── Name — "Unknown rider" when unmatched ─────────────────────────────────
  const nameEl = document.createElement("span");
  nameEl.className = "card__name";
  nameEl.textContent = isUnknown ? "Unknown rider" : result.name;
  card.appendChild(nameEl);

  // ── Meta line: category + time ─────────────────────────────────────────────
  const metaEl = document.createElement("span");
  metaEl.className = "card__meta";
  if (!isUnknown) {
    metaEl.textContent = `${result.category} · ${formatTimeOfDay(result.time)}`;
  } else {
    metaEl.textContent = formatTimeOfDay(result.time);
  }
  card.appendChild(metaEl);

  return card;
}

/**
 * Build a candidate pseudo-result card.
 * Uses class "card card--candidate card--selectable".
 * Sets data-candidate-id (NOT data-crossing-id) and all candidate-specific
 * data-* attributes consumed by tasks 6/7.
 *
 * Candidates have no lane assignment — they are placed in the rightmost
 * available column (lanes.length), which in a no-lane or unknown-only run
 * falls back to column 1.
 *
 * @param {import('./data.js').CandidateResult} result
 * @param {import('./data.js').Lane[]} lanes
 * @returns {HTMLElement}
 */
function _buildCandidateCard(result, lanes) {
  // Candidates carry category=UNKNOWN_CATEGORY. Attempt to find that lane;
  // fall back to the last column if there is no such lane.
  const col = lanes.length > 0 ? lanes.length : 1;

  const card = document.createElement("div");
  card.style.gridColumn = col;
  card.className = "card card--candidate card--selectable";

  // ── Candidate-specific data-* attributes (exact names per frozen addendum) ─
  card.dataset.candidateId  = result.candidateId;
  card.dataset.run          = result.run;
  card.dataset.time         = result.time.toISOString();
  card.dataset.lastSeen     = result.lastSeen.toISOString();
  card.dataset.frameCount   = String(result.frameCount);
  card.dataset.hintNumber   = result.hintNumber ?? "";
  card.dataset.hintConf     = String(result.hintConf);
  card.dataset.imageUrl     = result.imageUrl;
  card.dataset.repBox       = JSON.stringify(result.repBox);
  card.dataset.numberText   = result.numberText;

  // ── Label: "? unidentified" or "? <hint>?" when hintNumber ───────────────
  const numEl = document.createElement("span");
  numEl.className = "card__number";
  numEl.textContent = result.hintNumber ? `? ${result.hintNumber}?` : "? unidentified";
  card.appendChild(numEl);

  // ── Meta line: time ────────────────────────────────────────────────────────
  const metaEl = document.createElement("span");
  metaEl.className = "card__meta";
  metaEl.textContent = formatTimeOfDay(result.time);
  card.appendChild(metaEl);

  return card;
}
