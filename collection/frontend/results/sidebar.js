/**
 * sidebar.js — Crossing detail sidebar management.
 *
 * openSidebar(result):  unhide #sidebar, replace its content with the annotated
 *   frame image + number / name / category / time-of-day.  Calling again replaces
 *   content (no stacking, FR14).
 *
 * closeSidebar():  hide #sidebar and clear the selection highlight.
 *
 * selectedCrossingId():  the crossing currently shown, or null.
 *
 * @module results/sidebar
 */

import { UNKNOWN_CATEGORY } from "./data.js";
import { formatTimeOfDay } from "./render.js";

// ---------------------------------------------------------------------------
// Module-level state
// ---------------------------------------------------------------------------

/** @type {string|null} */
let _selectedCrossingId = null;

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

/**
 * Open (or replace) the sidebar with the given result's details.
 * @param {import('./data.js').Result} result
 */
export function openSidebar(result) {
  const sidebar = document.getElementById("sidebar");
  const content = document.getElementById("sidebar-content");
  if (!sidebar || !content) return;

  _selectedCrossingId = result.crossingId;

  // Build new content — replace entirely (FR14, no stacking).
  content.innerHTML = "";

  // Annotated frame image.
  const img = document.createElement("img");
  img.src = result.annotatedUrl;
  img.alt = `Annotated frame for crossing ${result.crossingId}`;
  img.className = "sidebar__image";
  content.appendChild(img);

  // Details block.
  const details = document.createElement("div");
  details.className = "sidebar__details";

  // Race number.
  const numEl = document.createElement("p");
  numEl.className = "sidebar__number";
  numEl.textContent = `#${result.raceNumber}`;
  details.appendChild(numEl);

  // Name — "Unknown rider" when unmatched.
  const nameEl = document.createElement("p");
  nameEl.className = "sidebar__name";
  nameEl.textContent =
    result.matched && result.name ? result.name : "Unknown rider";
  details.appendChild(nameEl);

  // Category — omit for unknown riders.
  if (result.matched && result.category && result.category !== UNKNOWN_CATEGORY) {
    const catEl = document.createElement("p");
    catEl.className = "sidebar__category";
    catEl.textContent = result.category;
    details.appendChild(catEl);
  }

  // Time of day.
  const timeEl = document.createElement("p");
  timeEl.className = "sidebar__time";
  timeEl.textContent = formatTimeOfDay(result.time);
  details.appendChild(timeEl);

  content.appendChild(details);

  // Unhide the panel.
  sidebar.removeAttribute("hidden");

  // Apply selection highlight to this card.
  _applySelectionHighlight();
}

/**
 * Close the sidebar and clear the selection highlight.
 */
export function closeSidebar() {
  const sidebar = document.getElementById("sidebar");
  if (sidebar) {
    sidebar.setAttribute("hidden", "");
  }
  _selectedCrossingId = null;
  _clearSelectionHighlight();
}

/**
 * The crossing id currently displayed in the sidebar, or null if closed.
 * Used by results.js to re-apply the highlight after each re-render.
 * @returns {string|null}
 */
export function selectedCrossingId() {
  return _selectedCrossingId;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Add card--selected to the card matching _selectedCrossingId, clear all others.
 * Called internally; results.js also calls _applySelectionHighlight via
 * reapplySelectionHighlight() below.
 */
function _applySelectionHighlight() {
  const timeline = document.getElementById("timeline");
  if (!timeline || !_selectedCrossingId) return;

  timeline.querySelectorAll("[data-crossing-id]").forEach((card) => {
    if (card.dataset.crossingId === _selectedCrossingId) {
      card.classList.add("card--selected");
    } else {
      card.classList.remove("card--selected");
    }
  });
}

function _clearSelectionHighlight() {
  const timeline = document.getElementById("timeline");
  if (!timeline) return;
  timeline.querySelectorAll(".card--selected").forEach((card) => {
    card.classList.remove("card--selected");
  });
}

/**
 * Re-apply the selection highlight after a timeline re-render.
 * Called by results.js after each renderTimeline() call.
 */
export function reapplySelectionHighlight() {
  if (_selectedCrossingId) {
    _applySelectionHighlight();
  }
}
