/**
 * results.js — Poll loop, transform pipeline, sidebar wiring, run selector.
 * Entry module loaded as <script type="module" src="results/results.js">.
 *
 * Reads #label-input.value on every tick (back-end normalizes raw labels).
 * Populates #run-select from GET /runs.
 * Delegates card clicks to openSidebar(); sidebar close button to closeSidebar().
 *
 * @module results/results
 */

import {
  resultsFromCrossings,
  sortDescending,
  groupIntoPacks,
  computeLanes,
} from "./data.js";
import { renderTimeline } from "./render.js";
import {
  openSidebar,
  closeSidebar,
  reapplySelectionHighlight,
} from "./sidebar.js";

// ---------------------------------------------------------------------------
// Config — from the frozen config.js (design §7)
// ---------------------------------------------------------------------------

const { RESULTS_POLL_MS } = window.COLLECTION_CONFIG;

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------

const timelineEl = document.getElementById("timeline");
const labelEl    = document.getElementById("label-input");
const runSelect  = document.getElementById("run-select");
const sidebarClose = document.getElementById("sidebar-close");

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

/** Last JSON string rendered — skip DOM write when payload is unchanged. */
let _lastPayloadJson = null;

/** Label that produced the last render — clear timeline when it changes. */
let _lastLabel = null;

/** Ticks since last /runs poll — refresh every ~10 ticks (~15 s at default cadence). */
let _ticksSinceRunsPoll = 0;
const RUNS_POLL_EVERY = 10;

// ---------------------------------------------------------------------------
// Sidebar close button
// ---------------------------------------------------------------------------

if (sidebarClose) {
  sidebarClose.addEventListener("click", () => closeSidebar());
}

// ---------------------------------------------------------------------------
// Run selector → label field
// Picking a known run sets label-input.value and resets the selector to the
// placeholder so the field stays authoritative ("jump to run" affordance).
// We never overwrite a non-empty label except on explicit selection.
// ---------------------------------------------------------------------------

if (runSelect && labelEl) {
  runSelect.addEventListener("change", () => {
    const chosen = runSelect.value;
    if (chosen) {
      labelEl.value = chosen;
      // Reset back to placeholder so the select reads "-- active label --" again,
      // keeping label-input as the single source of truth (design §8).
      runSelect.value = "";
    }
  });
}

// ---------------------------------------------------------------------------
// Delegated click handler on #timeline
// A click on any element carrying [data-crossing-id] opens the sidebar.
// ---------------------------------------------------------------------------

if (timelineEl) {
  timelineEl.addEventListener("click", (e) => {
    /** @type {HTMLElement|null} */
    const card = e.target.closest("[data-crossing-id]");
    if (!card) return;

    // Reconstruct a minimal Result object from the card's data attributes.
    // The sidebar only needs crossingId, annotatedUrl, raceNumber, name,
    // category, matched, and time.  We store raceNumber/name/category/matched
    // as data attributes set during render so we don't need to re-fetch.
    openSidebar({
      crossingId:   card.dataset.crossingId,
      annotatedUrl: card.dataset.annotatedUrl,
      raceNumber:   Number(card.dataset.raceNumber)  || 0,
      name:         card.dataset.name                || null,
      category:     card.dataset.category            || "Unknown",
      matched:      card.dataset.matched             === "true",
      time:         new Date(card.dataset.time       || 0),
    });
  });
}

// ---------------------------------------------------------------------------
// Poll /results
// ---------------------------------------------------------------------------

async function pollResults() {
  if (!labelEl || !timelineEl) return;

  const label = labelEl.value.trim();

  // FR4 / blank-label rule: skip the fetch when the label field is empty.
  if (!label) {
    // If the label just became blank, clear the timeline.
    if (_lastLabel !== null) {
      _lastLabel = null;
      _lastPayloadJson = null;
      timelineEl.innerHTML =
        '<p class="timeline__empty">No crossings yet — waiting for riders…</p>';
    }
    return;
  }

  // Label changed — clear state so the new run starts fresh.
  if (label !== _lastLabel) {
    _lastLabel = label;
    _lastPayloadJson = null;
    timelineEl.innerHTML = "";
  }

  try {
    const resp = await fetch(
      `/results?run=${encodeURIComponent(label)}`,
      { cache: "no-store" }
    );
    if (!resp.ok) return;   // NFR6: keep last rendered state on HTTP error

    const payload = await resp.json();
    const payloadJson = JSON.stringify(payload);

    // Skip DOM write when payload is unchanged (idle polls are no-ops, FR4).
    if (payloadJson === _lastPayloadJson) return;
    _lastPayloadJson = payloadJson;

    // Transform pipeline (design §8).
    const results = resultsFromCrossings(payload);
    const sorted  = sortDescending(results);
    const packs   = groupIntoPacks(sorted, 3);
    const lanes   = computeLanes(sorted, { laneOrder: null });

    renderTimeline(timelineEl, packs, lanes, { collapseBreakpointPx: 640 });

    // Re-apply selection highlight after every re-render (design §8 / SC4).
    reapplySelectionHighlight();

  } catch (_err) {
    // NFR6: fetch/network error — keep last rendered state, no error banners.
  }
}

// ---------------------------------------------------------------------------
// Poll /runs — populate the run selector
// ---------------------------------------------------------------------------

async function pollRuns() {
  if (!runSelect) return;
  try {
    const resp = await fetch("/runs", { cache: "no-store" });
    if (!resp.ok) return;
    const data = await resp.json();
    const runs = Array.isArray(data.runs) ? data.runs : [];

    // Rebuild options: placeholder + one option per run id.
    // Preserve the placeholder as first child.
    runSelect.innerHTML = '<option value="">-- active label --</option>';
    for (const run of runs) {
      const opt = document.createElement("option");
      opt.value = run;
      opt.textContent = run;
      runSelect.appendChild(opt);
    }
  } catch (_err) {
    // Ignore — run selector just won't update.
  }
}

// ---------------------------------------------------------------------------
// Kick off the poll loop
// ---------------------------------------------------------------------------

async function tick() {
  // Poll /runs periodically.
  if (_ticksSinceRunsPoll === 0) {
    await pollRuns();
  }
  _ticksSinceRunsPoll = (_ticksSinceRunsPoll + 1) % RUNS_POLL_EVERY;

  await pollResults();
}

// Initial poll immediately, then on interval.
tick();
setInterval(tick, RESULTS_POLL_MS);
