/**
 * results.js — Poll loop, transform pipeline, sidebar wiring, run selector.
 * Entry module loaded as <script type="module" src="results/results.js">.
 *
 * Reads #label-input.value on every tick (back-end normalizes raw labels).
 * Populates #run-select from GET /runs.
 * Delegates card clicks to openSidebar(); sidebar close button to closeSidebar().
 *
 * Per-concern skip (design §6.5 — frozen):
 *   - Timeline skips re-render when the COMBINED /results + /candidates JSON is
 *     unchanged.  The /status payload is handled independently by status.js and
 *     NEVER forces a timeline re-render.
 *
 * @module results/results
 */

import {
  resultsFromCrossings,
  sortDescending,      // kept for any legacy callers; pipeline now uses sortByOrder
  groupIntoPacks,
  computeLanes,
  // Task5 exports (coded against frozen contracts; stubs or real bodies land in
  // wave B in parallel — import must be correct so task9's integration works).
  candidatesToResults,
  sortByOrder,
  mergeCandidates,
} from "./data.js";
import { renderTimeline } from "./render.js";
import {
  openSidebar,
  closeSidebar,
  reapplySelectionHighlight,
} from "./sidebar.js";
import { pollStatus } from "./status.js";
import { openBrowser } from "./browser.js";

// ---------------------------------------------------------------------------
// Config — from the frozen config.js (design §7 / §6.5)
// ---------------------------------------------------------------------------

const { RESULTS_POLL_MS } = window.COLLECTION_CONFIG;

// ---------------------------------------------------------------------------
// DOM references
// ---------------------------------------------------------------------------

const timelineEl      = document.getElementById("timeline");
const labelEl         = document.getElementById("label-input");
const runSelect       = document.getElementById("run-select");
const sidebarClose    = document.getElementById("sidebar-close");
const browseFramesBtn = document.getElementById("browse-frames-btn");
const candidatesToggle      = document.getElementById("candidates-toggle");
const candidatesToggleCount = document.getElementById("candidates-toggle-count");
const queueStatusEl   = document.getElementById("queue-status");

// ---------------------------------------------------------------------------
// Module state
// ---------------------------------------------------------------------------

/**
 * Last COMBINED JSON string rendered (results + candidates together) — skip DOM
 * write when payload is unchanged (design §6.5).  /status is compared
 * independently inside status.js and never touches this variable.
 */
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
      // Hide the queue-status element for the new run until the next successful poll.
      if (queueStatusEl) queueStatusEl.setAttribute("hidden", "");
      // Clear _lastPayloadJson so the new run renders from scratch.
      _lastPayloadJson = null;
    }
  });
}

// ---------------------------------------------------------------------------
// Label-input change — hide queue-status until next successful poll (task6 spec)
// ---------------------------------------------------------------------------

if (labelEl) {
  labelEl.addEventListener("input", () => {
    if (queueStatusEl) queueStatusEl.setAttribute("hidden", "");
    // Also clear the skip-cache so status re-renders on the first successful poll.
    // (pollStatus clears its own _lastStatusJson when label is empty or on change.)
  });
}

// ---------------------------------------------------------------------------
// Candidates toggle — immediate re-render when checked/unchecked (task6 spec)
// ---------------------------------------------------------------------------

if (candidatesToggle) {
  candidatesToggle.addEventListener("change", () => {
    // Clear the skip-cache so the next tick re-renders with the updated toggle state.
    _lastPayloadJson = null;
    // Re-render immediately rather than waiting for the next tick.
    pollResults();
  });
}

// ---------------------------------------------------------------------------
// wtnc:edited event — any edit clears the skip-cache so the next tick
// re-renders with the merged truth (NFR6; design §6.5).
// ---------------------------------------------------------------------------

document.addEventListener("wtnc:edited", () => {
  _lastPayloadJson = null;
});

// ---------------------------------------------------------------------------
// Browse frames button → openBrowser (§6.5 last paragraph)
// ---------------------------------------------------------------------------

if (browseFramesBtn && labelEl) {
  browseFramesBtn.addEventListener("click", () => {
    openBrowser({
      run: labelEl.value.trim(),
      centerTs: null,   // anchor at meta.last_ts (task8 resolves this)
    });
  });
}

// ---------------------------------------------------------------------------
// Delegated click handler on #timeline
//
// [data-crossing-id]  → existing behavior: rebuild Result from data-* and open sidebar.
// [data-candidate-id] → build pseudo-result from candidate data-* attributes
//                       (task5's frozen attribute names per README addendum) and
//                       call openSidebar with isCandidate: true (design §6.2).
// ---------------------------------------------------------------------------

if (timelineEl) {
  timelineEl.addEventListener("click", (e) => {
    // Try candidate card first (more specific check avoids ambiguity).
    const candidateCard = e.target.closest("[data-candidate-id]");
    if (candidateCard) {
      _openCandidateSidebar(candidateCard);
      return;
    }

    const crossingCard = e.target.closest("[data-crossing-id]");
    if (!crossingCard) return;

    // Reconstruct a minimal Result object from the card's data attributes.
    openSidebar({
      crossingId:        crossingCard.dataset.crossingId,
      run:               crossingCard.dataset.run                      || "",
      annotatedUrl:      crossingCard.dataset.annotatedUrl,
      raceNumber:        Number(crossingCard.dataset.raceNumber)       || 0,
      name:              crossingCard.dataset.name                     || null,
      category:          crossingCard.dataset.category                 || "Unknown",
      matched:           crossingCard.dataset.matched                  === "true",
      time:              new Date(crossingCard.dataset.time            || 0),
      // New fields from this spec:
      source:            crossingCard.dataset.source                   || "auto",
      edited:            crossingCard.dataset.edited                   === "true",
      orderKey:          Number(crossingCard.dataset.orderKey)         || 0,
      orderOverridden:   crossingCard.dataset.orderOverridden          === "true",
      numberText:        crossingCard.dataset.numberText               || "—",
      isCandidate:       false,
    });
  });
}

/**
 * Build a pseudo-Result from a candidate card's data-* attributes and open the
 * sidebar in candidate mode (design §6.2).
 *
 * Attribute names are frozen in the README addendum:
 *   data-candidate-id, data-run, data-time (ISO), data-last-seen (ISO),
 *   data-frame-count, data-hint-number (empty string when null),
 *   data-hint-conf, data-image-url, data-rep-box (JSON [x1,y1,x2,y2]),
 *   data-number-text.
 *
 * @param {HTMLElement} card
 */
function _openCandidateSidebar(card) {
  const d = card.dataset;

  let repBox = null;
  try {
    if (d.repBox) repBox = JSON.parse(d.repBox);
  } catch (_e) {
    // Malformed JSON — leave repBox null; sidebar handles it gracefully.
  }

  const time = new Date(d.time || 0);
  const lastSeen = new Date(d.lastSeen || 0);

  const pseudoResult = {
    isCandidate:   true,
    candidateId:   d.candidateId     || "",
    run:           d.run             || "",
    time:          isNaN(time.getTime())     ? new Date(0) : time,
    lastSeen:      isNaN(lastSeen.getTime()) ? new Date(0) : lastSeen,
    frameCount:    Number(d.frameCount) || 0,
    hintNumber:    d.hintNumber      || null,   // empty string → null
    hintConf:      Number(d.hintConf) || 0,
    imageUrl:      d.imageUrl        || "",
    repBox,
    numberText:    d.numberText      || "—",
    // orderKey mirrors candidatesToResults: epoch-ms of time
    orderKey:      isNaN(time.getTime()) ? 0 : time.getTime(),
  };

  // Normalise hintNumber: empty string maps to null (consistent with Candidate model).
  if (pseudoResult.hintNumber === "") pseudoResult.hintNumber = null;

  openSidebar(pseudoResult);
}

// ---------------------------------------------------------------------------
// Poll /results + /candidates together (design §6.5)
// ---------------------------------------------------------------------------

/**
 * Fetch /results?run= and /candidates?run= together (Promise.all), then
 * fire pollStatus as a fire-and-forget side effect.
 *
 * Timeline skip: compares the COMBINED results+candidates JSON string.
 * The /status payload is compared independently inside status.js and
 * never forces a timeline re-render (design §6.5 — frozen).
 */
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
    // Fire status even on blank label so it hides itself (pollStatus handles "").
    pollStatus(label);  // fire-and-forget
    return;
  }

  // Label changed — clear state so the new run starts fresh.
  if (label !== _lastLabel) {
    _lastLabel = label;
    _lastPayloadJson = null;
    timelineEl.innerHTML = "";
  }

  // Fetch /results and /candidates concurrently.
  let resultsPayload, candidatesPayload;
  try {
    const [resultsResp, candidatesResp] = await Promise.all([
      fetch(`/results?run=${encodeURIComponent(label)}`, { cache: "no-store" }),
      fetch(`/candidates?run=${encodeURIComponent(label)}`, { cache: "no-store" }),
    ]);

    if (!resultsResp.ok || !candidatesResp.ok) {
      // Keep last rendered state on any HTTP error (NFR6).
      pollStatus(label);  // fire-and-forget — don't let status fetch failure stop us
      return;
    }

    [resultsPayload, candidatesPayload] = await Promise.all([
      resultsResp.json(),
      candidatesResp.json(),
    ]);
  } catch (_err) {
    // NFR6: fetch/network error — keep last rendered state, no error banners.
    pollStatus(label);  // fire-and-forget
    return;
  }

  // Fire pollStatus independently — its own skip logic handles it.
  // Fire-and-forget: do NOT await; status must not block or delay the timeline.
  pollStatus(label);

  // ---------------------------------------------------------------------------
  // Always update the candidates-toggle open count (even when toggle is unchecked).
  // ---------------------------------------------------------------------------
  const allCandidates = (candidatesPayload && Array.isArray(candidatesPayload.candidates))
    ? candidatesPayload.candidates
    : [];
  const openCount = allCandidates.filter(c => c.state === "open").length;
  if (candidatesToggleCount) {
    candidatesToggleCount.textContent = String(openCount);
  }

  // ---------------------------------------------------------------------------
  // Per-concern timeline skip — compare COMBINED results + candidates JSON.
  // /status is NOT included here (design §6.5 — frozen).
  // ---------------------------------------------------------------------------
  const combinedJson = JSON.stringify({ r: resultsPayload, c: candidatesPayload });
  if (combinedJson === _lastPayloadJson) return;
  _lastPayloadJson = combinedJson;

  // ---------------------------------------------------------------------------
  // Transform pipeline (design §6.5):
  //   resultsFromCrossings → mergeCandidates (if toggle checked) → sortByOrder
  //   → groupIntoPacks → computeLanes → renderTimeline
  // ---------------------------------------------------------------------------

  // 1. Crossings → Results (extended with source/edited/orderKey/orderOverridden).
  const crossingResults = resultsFromCrossings(resultsPayload);

  // 2. Optionally include open candidates as pseudo-Results.
  let allResults;
  const showCandidates = candidatesToggle ? candidatesToggle.checked : false;
  if (showCandidates) {
    // candidatesToResults filters to open candidates only (task5 contract).
    const candidateResults = candidatesToResults(candidatesPayload);
    allResults = mergeCandidates(crossingResults, candidateResults);
  } else {
    allResults = crossingResults;
  }

  // 3. Sort by order-of-record DESC (replaces the old sortDescending call).
  const sorted = sortByOrder(allResults);

  // 4. Group into packs and compute lanes.
  const packs = groupIntoPacks(sorted, 3);
  const lanes = computeLanes(sorted, { laneOrder: null });

  // 5. Render.
  renderTimeline(timelineEl, packs, lanes, { collapseBreakpointPx: 640 });

  // Re-apply selection highlight after every re-render (design §8 / SC4).
  reapplySelectionHighlight();
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
  // Note: pollStatus is called inside pollResults (fire-and-forget).
  // It is NOT called again here to avoid a double-fetch per tick.
}

// Initial poll immediately, then on interval.
tick();
setInterval(tick, RESULTS_POLL_MS);
