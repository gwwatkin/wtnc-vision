/**
 * app.js — Config resolution, fetch orchestration, polling loop.
 * Owned exclusively by task6 for implementation; stubs created in task1.
 * Imports all other modules and wires them together.
 */

import { parseCsv } from "./csv.js";
import {
  UNKNOWN_CATEGORY,
  parseCrossings,
  parseRoster,
  mergeResults,
  sortDescending,
  groupIntoPacks,
  computeLanes,
} from "./data.js";
import { renderTimeline } from "./render.js";

// ---------------------------------------------------------------------------
// Default configuration (design §6)
// ---------------------------------------------------------------------------

const DEFAULT_CONFIG = {
  crossingsUrl:         "data/crossings.csv",
  rosterUrl:            "data/roster.csv",
  gapSeconds:           3,        // FR4/FR6
  refreshMs:            5000,     // OQ1; 0 = render once
  laneOrder:            null,     // OQ6; e.g. ["Cat 3","Cat 4"]
  collapseBreakpointPx: 640,      // OQ5
};

// ---------------------------------------------------------------------------
// Config resolution
// ---------------------------------------------------------------------------

/** Merge window.RESULTS_CONFIG over DEFAULT_CONFIG, then apply query-string
 *  overrides. Priority: query string > window.RESULTS_CONFIG > DEFAULT_CONFIG.
 *  Query keys: gap→gapSeconds (int), refresh→refreshMs (int),
 *              crossings→crossingsUrl, roster→rosterUrl.
 *  Invalid/absent query params are silently ignored.
 *  @returns {typeof DEFAULT_CONFIG}
 */
function resolveConfig() {
  // Layer 1 + 2: start from DEFAULT_CONFIG, merge page global over it.
  const pageGlobal =
    (typeof window !== "undefined" && window.RESULTS_CONFIG) || {};
  const merged = Object.assign({}, DEFAULT_CONFIG, pageGlobal);

  // Layer 3: query-string overrides (only in a browser context).
  if (typeof window !== "undefined" && window.location && window.location.search) {
    const params = new URLSearchParams(window.location.search);

    const gap = params.get("gap");
    if (gap !== null) {
      const v = parseInt(gap, 10);
      if (!isNaN(v)) merged.gapSeconds = v;
    }

    const refresh = params.get("refresh");
    if (refresh !== null) {
      const v = parseInt(refresh, 10);
      if (!isNaN(v)) merged.refreshMs = v;
    }

    const crossings = params.get("crossings");
    if (crossings !== null && crossings !== "") merged.crossingsUrl = crossings;

    const roster = params.get("roster");
    if (roster !== null && roster !== "") merged.rosterUrl = roster;
  }

  return merged;
}

// ---------------------------------------------------------------------------
// Data loading
// ---------------------------------------------------------------------------

/** Fetch both CSVs (cache:'no-store'); returns raw text pair. Throws on HTTP error.
 *  @param {typeof DEFAULT_CONFIG} config
 *  @returns {Promise<{crossingsText: string, rosterText: string}>}
 */
async function loadData(config) {
  const [crossingsRes, rosterRes] = await Promise.all([
    fetch(config.crossingsUrl, { cache: "no-store" }),
    fetch(config.rosterUrl,    { cache: "no-store" }),
  ]);

  if (!crossingsRes.ok) {
    throw new Error(
      `Failed to load crossings: ${crossingsRes.status} ${crossingsRes.statusText} (${config.crossingsUrl})`
    );
  }
  if (!rosterRes.ok) {
    throw new Error(
      `Failed to load roster: ${rosterRes.status} ${rosterRes.statusText} (${config.rosterUrl})`
    );
  }

  const [crossingsText, rosterText] = await Promise.all([
    crossingsRes.text(),
    rosterRes.text(),
  ]);

  return { crossingsText, rosterText };
}

// ---------------------------------------------------------------------------
// Error banner
// ---------------------------------------------------------------------------

/** Show a non-blocking dismissible error banner above the timeline. Any
 *  previous banner is replaced so we don't accumulate banners on poll errors.
 *  @param {string} message
 */
function showErrorBanner(message) {
  const existing = document.getElementById("app-error-banner");
  if (existing) existing.remove();

  const banner = document.createElement("div");
  banner.id = "app-error-banner";
  banner.setAttribute("role", "alert");
  banner.style.cssText =
    "background:#fef3c7;border:1px solid #d97706;color:#92400e;" +
    "padding:0.75rem 1rem;margin-bottom:1rem;border-radius:4px;" +
    "font-family:monospace;font-size:0.875rem;display:flex;" +
    "justify-content:space-between;align-items:flex-start;gap:1rem;";

  const text = document.createElement("span");
  text.textContent = `Error: ${message}`;
  banner.appendChild(text);

  const dismiss = document.createElement("button");
  dismiss.textContent = "×";
  dismiss.setAttribute("aria-label", "Dismiss");
  dismiss.style.cssText =
    "background:none;border:none;cursor:pointer;font-size:1.25rem;" +
    "line-height:1;padding:0;color:inherit;flex-shrink:0;";
  dismiss.onclick = () => banner.remove();
  banner.appendChild(dismiss);

  // Insert before the timeline element, or at the top of body as a fallback.
  const timeline = document.getElementById("timeline");
  if (timeline && timeline.parentNode) {
    timeline.parentNode.insertBefore(banner, timeline);
  } else {
    document.body.prepend(banner);
  }
}

// ---------------------------------------------------------------------------
// Refresh
// ---------------------------------------------------------------------------

/** One full pipeline pass: load → parse → merge → sort → group → render.
 *  On any error, shows a non-blocking error banner and keeps the previous view.
 *  @param {typeof DEFAULT_CONFIG} config
 *  @returns {Promise<void>}
 */
async function refresh(config) {
  try {
    const { crossingsText, rosterText } = await loadData(config);

    const crossingRows = parseCsv(crossingsText);
    const rosterRows   = parseCsv(rosterText);

    const crossings = parseCrossings(crossingRows);
    const roster    = parseRoster(rosterRows);

    const results  = mergeResults(crossings, roster);
    const sorted   = sortDescending(results);
    const packs    = groupIntoPacks(sorted, config.gapSeconds);
    const lanes    = computeLanes(sorted, { laneOrder: config.laneOrder });

    const root = document.getElementById("timeline");
    renderTimeline(root, packs, lanes, {
      collapseBreakpointPx: config.collapseBreakpointPx,
    });

    // Clear any previous error banner on success.
    const existing = document.getElementById("app-error-banner");
    if (existing) existing.remove();
  } catch (err) {
    console.error("[app.js] refresh error:", err);
    showErrorBanner(err.message);
    // Previous rendered view is kept (renderTimeline was not called).
  }
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

/** Kick off: refresh() now, then every config.refreshMs (unless 0).
 *  Guards against overlapping refreshes via an in-flight flag.
 *  @returns {void}
 */
function start() {
  const config = resolveConfig();
  let refreshing = false;

  async function safeRefresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      await refresh(config);
    } finally {
      refreshing = false;
    }
  }

  safeRefresh();

  if (config.refreshMs > 0) {
    setInterval(safeRefresh, config.refreshMs);
  }
}

start();
