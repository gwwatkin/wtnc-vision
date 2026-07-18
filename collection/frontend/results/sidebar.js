/**
 * sidebar.js — Crossing detail sidebar management.
 *
 * openSidebar(result):  unhide #sidebar, replace its content with the relevant
 *   mode — crossing mode (edit, move, delete, view frames) or candidate mode
 *   (rep frame with box overlay, promote/dismiss/view frames).  Calling again
 *   replaces content (no stacking, FR14).
 *
 * closeSidebar():  hide #sidebar and clear the selection highlight.
 *
 * selectedCrossingId():  the crossing currently shown, or null.
 *
 * reapplySelectionHighlight(): re-apply card--selected after a re-render.
 *
 * @module results/sidebar
 */

import { UNKNOWN_CATEGORY } from "./data.js";
import { formatTimeOfDay } from "./render.js";
import {
  patchCrossing,
  setPosition,
  resolveCandidate,
  loadRosterNumbers,
} from "./edits.js";
import { openBrowser } from "./browser.js";

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
 * Branches on result.isCandidate (design §6.4).
 *
 * @param {import('./data.js').Result} result
 */
export function openSidebar(result) {
  const sidebar = document.getElementById("sidebar");
  const content = document.getElementById("sidebar-content");
  if (!sidebar || !content) return;

  // Track selection.  Candidates don't have a crossingId so we use candidateId
  // as the sentinel when in candidate mode.
  _selectedCrossingId = result.isCandidate
    ? (result.candidateId ?? null)
    : (result.crossingId ?? null);

  // Build new content — replace entirely (FR14, no stacking).
  content.innerHTML = "";

  if (result.isCandidate) {
    _buildCandidateMode(content, result);
  } else {
    _buildCrossingMode(content, result);
  }

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

/**
 * Re-apply the selection highlight after a timeline re-render.
 * Called by results.js after each renderTimeline() call.
 */
export function reapplySelectionHighlight() {
  if (_selectedCrossingId) {
    _applySelectionHighlight();
  }
}

// ---------------------------------------------------------------------------
// Crossing mode
// ---------------------------------------------------------------------------

/**
 * Build the crossing-mode sidebar content.
 * Layout: annotated image, details block, action row.
 *
 * @param {HTMLElement} content
 * @param {import('./data.js').Result} result
 */
function _buildCrossingMode(content, result) {
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
  numEl.textContent = result.numberText
    ? `#${result.numberText}`
    : `#${result.raceNumber}`;
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

  // Action row.
  const actions = document.createElement("div");
  actions.className = "sidebar__actions";

  // ── Edit number row ──────────────────────────────────────────────────────
  const editRow = document.createElement("div");
  editRow.className = "sidebar__action-row";

  const numberInput = document.createElement("input");
  numberInput.type = "text";
  numberInput.className = "sidebar__number-input";
  numberInput.setAttribute("list", "roster-numbers");
  numberInput.placeholder = "Race number";
  // Prefill with current number (numberText carries "" for unidentified).
  const currentNumber = result.numberText != null
    ? result.numberText
    : (result.raceNumber != null ? String(result.raceNumber) : "");
  numberInput.value = currentNumber === "—" ? "" : currentNumber;

  const confirmBtn = document.createElement("button");
  confirmBtn.type = "button";
  confirmBtn.className = "sidebar__btn sidebar__btn--primary";
  confirmBtn.textContent = "Save number";
  confirmBtn.addEventListener("click", async () => {
    const newNumber = numberInput.value.trim();
    try {
      confirmBtn.disabled = true;
      const updated = await patchCrossing(result.crossingId, { number: newNumber });
      // Refresh sidebar from the response.
      _refreshCrossingFromResponse(content, result, updated);
    } catch (err) {
      _showError(actions, err.message);
    } finally {
      confirmBtn.disabled = false;
    }
  });

  editRow.appendChild(numberInput);
  editRow.appendChild(confirmBtn);
  actions.appendChild(editRow);

  // Load roster datalist (non-blocking; errors are swallowed inside loadRosterNumbers).
  loadRosterNumbers(result.run);

  // ── Move earlier / Move later row ────────────────────────────────────────
  const moveRow = document.createElement("div");
  moveRow.className = "sidebar__action-row";

  const { earlierBtn, laterBtn } = _buildMoveButtons(result.crossingId);
  moveRow.appendChild(earlierBtn);
  moveRow.appendChild(laterBtn);
  actions.appendChild(moveRow);

  // ── Delete / View frames row ──────────────────────────────────────────────
  const bottomRow = document.createElement("div");
  bottomRow.className = "sidebar__action-row";

  const deleteBtn = document.createElement("button");
  deleteBtn.type = "button";
  deleteBtn.className = "sidebar__btn sidebar__btn--danger";
  deleteBtn.textContent = "Delete";
  deleteBtn.addEventListener("click", async () => {
    if (!confirm("Delete this crossing? This action can be undone by the next edit.")) {
      return;
    }
    try {
      deleteBtn.disabled = true;
      await patchCrossing(result.crossingId, { deleted: true });
      closeSidebar();
    } catch (err) {
      _showError(actions, err.message);
      deleteBtn.disabled = false;
    }
  });

  const framesBtn = document.createElement("button");
  framesBtn.type = "button";
  framesBtn.className = "sidebar__btn";
  framesBtn.textContent = "View frames";
  framesBtn.addEventListener("click", () => {
    const centerTs = result.time instanceof Date
      ? result.time.toISOString()
      : String(result.time);
    openBrowser({ run: result.run, centerTs });
  });

  bottomRow.appendChild(deleteBtn);
  bottomRow.appendChild(framesBtn);
  actions.appendChild(bottomRow);

  content.appendChild(actions);
}

/**
 * Refresh the sidebar's number/name/category display after an edit, using the
 * response body.  The action rows stay in place; only the details block is
 * updated to avoid full re-open (which would reset the number input).
 *
 * @param {HTMLElement} content
 * @param {import('./data.js').Result} result  original result (for fields not in the response)
 * @param {object} updated  crossing dict from the server
 */
function _refreshCrossingFromResponse(content, result, updated) {
  // Update the number display in the details block.
  const numEl = content.querySelector(".sidebar__number");
  if (numEl) {
    const n = updated.number != null ? String(updated.number) : "";
    numEl.textContent = n ? `#${n}` : "#—";
  }

  const nameEl = content.querySelector(".sidebar__name");
  if (nameEl) {
    const matched = Boolean(updated.matched);
    const name = updated.name ? String(updated.name) : null;
    nameEl.textContent = matched && name ? name : "Unknown rider";
  }

  // Also update the input to reflect the saved value.
  const input = content.querySelector(".sidebar__number-input");
  if (input) {
    input.value = updated.number != null ? String(updated.number) : "";
  }
}

/**
 * Build the Move earlier / Move later buttons.
 * Neighbor rule (README refinement 8 — followed exactly):
 *   Timeline displays newest-first (DESC by order_key).
 *   Order-of-record is ASC.
 *
 *   Walk all [data-crossing-id] cards in #timeline in document order,
 *   SKIPPING [data-candidate-id] cards.
 *
 *   Move earlier (down in DESC display → earlier in order-of-record):
 *     let Y = card below the selected one
 *     let Z = card below Y
 *     call setPosition(id, { earlierId: Z?.crossingId ?? null, laterId: Y.crossingId })
 *     Disabled when Y is absent (already at the bottom of the display = earliest in record).
 *
 *   Move later (up in DESC display → later in order-of-record):
 *     let Y = card above the selected one
 *     let Z = card above Y
 *     call setPosition(id, { earlierId: Y.crossingId, laterId: Z?.crossingId ?? null })
 *     Disabled when Y is absent (already at the top = latest in record).
 *
 * @param {string} crossingId
 * @returns {{ earlierBtn: HTMLButtonElement, laterBtn: HTMLButtonElement }}
 */
function _buildMoveButtons(crossingId) {
  const earlierBtn = document.createElement("button");
  earlierBtn.type = "button";
  earlierBtn.className = "sidebar__btn";
  earlierBtn.textContent = "Move earlier";

  const laterBtn = document.createElement("button");
  laterBtn.type = "button";
  laterBtn.className = "sidebar__btn";
  laterBtn.textContent = "Move later";

  // Compute neighbor state at click time (DOM reflects latest render).
  function computeNeighbors() {
    const timeline = document.getElementById("timeline");
    if (!timeline) return { cards: [], idx: -1 };
    // All crossing cards, skipping candidate cards.
    const cards = Array.from(
      timeline.querySelectorAll("[data-crossing-id]")
    ).filter((c) => !c.hasAttribute("data-candidate-id"));
    const idx = cards.findIndex((c) => c.dataset.crossingId === crossingId);
    return { cards, idx };
  }

  // Determine initial disabled state (DOM may not be ready yet; re-check on click).
  function updateDisabled() {
    const { cards, idx } = computeNeighbors();
    if (idx < 0) {
      // Card not found — disable both (crossing may have been deleted).
      earlierBtn.disabled = true;
      laterBtn.disabled = true;
      return;
    }
    // Move earlier → card below (idx+1) must exist.
    earlierBtn.disabled = idx >= cards.length - 1;
    // Move later → card above (idx-1) must exist.
    laterBtn.disabled = idx <= 0;
  }

  updateDisabled();

  earlierBtn.addEventListener("click", async () => {
    const { cards, idx } = computeNeighbors();
    if (idx < 0 || idx >= cards.length - 1) return; // already at end / not found
    const Y = cards[idx + 1];
    const Z = cards[idx + 2] ?? null;
    try {
      earlierBtn.disabled = true;
      laterBtn.disabled = true;
      await setPosition(crossingId, {
        earlierId: Z ? Z.dataset.crossingId : null,
        laterId: Y.dataset.crossingId,
      });
      updateDisabled();
    } catch (err) {
      _showError(earlierBtn.closest(".sidebar__actions"), err.message);
      updateDisabled();
    }
  });

  laterBtn.addEventListener("click", async () => {
    const { cards, idx } = computeNeighbors();
    if (idx <= 0) return; // already at top / not found
    const Y = cards[idx - 1];
    const Z = cards[idx - 2] ?? null;
    try {
      earlierBtn.disabled = true;
      laterBtn.disabled = true;
      await setPosition(crossingId, {
        earlierId: Y.dataset.crossingId,
        laterId: Z ? Z.dataset.crossingId : null,
      });
      updateDisabled();
    } catch (err) {
      _showError(laterBtn.closest(".sidebar__actions"), err.message);
      updateDisabled();
    }
  });

  return { earlierBtn, laterBtn };
}

// ---------------------------------------------------------------------------
// Candidate mode
// ---------------------------------------------------------------------------

/**
 * Build the candidate-mode sidebar content.
 * Layout: rep frame with repBox canvas overlay, details, number input,
 * Promote / Dismiss / View frames actions.
 *
 * @param {HTMLElement} content
 * @param {object} result  pseudo-result with isCandidate: true (design §6.2)
 */
function _buildCandidateMode(content, result) {
  // ── Representative frame with canvas overlay ─────────────────────────────
  const wrapper = document.createElement("div");
  wrapper.className = "frame-canvas-wrapper";

  const img = document.createElement("img");
  img.alt = `Representative frame for candidate ${result.candidateId}`;
  img.className = "sidebar__image";

  const canvas = document.createElement("canvas");
  canvas.className = "frame-canvas-overlay";

  // Draw the repBox overlay scaled to the displayed image size.
  function drawOverlay() {
    if (!result.repBox || result.repBox.length !== 4) return;
    const [x1, y1, x2, y2] = result.repBox;
    const scaleX = img.clientWidth  / (img.naturalWidth  || img.clientWidth);
    const scaleY = img.clientHeight / (img.naturalHeight || img.clientHeight);
    canvas.width  = img.clientWidth;
    canvas.height = img.clientHeight;
    canvas.style.width  = `${img.clientWidth}px`;
    canvas.style.height = `${img.clientHeight}px`;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = "#f59e0b"; // amber — candidate hint color
    ctx.lineWidth   = 2;
    ctx.strokeRect(
      x1 * scaleX,
      y1 * scaleY,
      (x2 - x1) * scaleX,
      (y2 - y1) * scaleY
    );
  }

  img.addEventListener("load", drawOverlay);
  // Redraw if the element is resized (e.g. sidebar width change).
  if (typeof ResizeObserver !== "undefined") {
    new ResizeObserver(drawOverlay).observe(img);
  }

  img.src = result.imageUrl ?? "";

  wrapper.appendChild(img);
  wrapper.appendChild(canvas);
  content.appendChild(wrapper);

  // ── Details ───────────────────────────────────────────────────────────────
  const details = document.createElement("div");
  details.className = "sidebar__details";

  const typeEl = document.createElement("p");
  typeEl.className = "sidebar__number";
  typeEl.textContent = "? Candidate crossing";
  details.appendChild(typeEl);

  const timeEl = document.createElement("p");
  timeEl.className = "sidebar__time";
  if (result.time instanceof Date) {
    timeEl.textContent = `First seen: ${formatTimeOfDay(result.time)}`;
  } else if (result.time) {
    const d = new Date(result.time);
    timeEl.textContent = `First seen: ${isNaN(d.getTime()) ? String(result.time) : formatTimeOfDay(d)}`;
  }
  details.appendChild(timeEl);

  if (result.frameCount != null) {
    const framesEl = document.createElement("p");
    framesEl.className = "sidebar__meta";
    framesEl.textContent = `${result.frameCount} frame${result.frameCount !== 1 ? "s" : ""}`;
    details.appendChild(framesEl);
  }

  if (result.hintNumber) {
    const hintEl = document.createElement("p");
    hintEl.className = "sidebar__meta";
    const confPct = result.hintConf != null
      ? ` (${Math.round(result.hintConf * 100)}% conf.)`
      : "";
    hintEl.textContent = `Pipeline saw: #${result.hintNumber}${confPct}`;
    details.appendChild(hintEl);
  }

  content.appendChild(details);

  // ── Action row ────────────────────────────────────────────────────────────
  const actions = document.createElement("div");
  actions.className = "sidebar__actions";

  // Number input row.
  const editRow = document.createElement("div");
  editRow.className = "sidebar__action-row";

  const numberInput = document.createElement("input");
  numberInput.type = "text";
  numberInput.className = "sidebar__number-input";
  numberInput.setAttribute("list", "roster-numbers");
  numberInput.placeholder = "Race number (blank = unidentified)";
  // Prefill with pipeline hint if present.
  numberInput.value = result.hintNumber ? String(result.hintNumber) : "";

  editRow.appendChild(numberInput);
  actions.appendChild(editRow);

  // Load roster datalist.
  loadRosterNumbers(result.run);

  // Promote / Dismiss / View frames row.
  const btnRow = document.createElement("div");
  btnRow.className = "sidebar__action-row";

  const promoteBtn = document.createElement("button");
  promoteBtn.type = "button";
  promoteBtn.className = "sidebar__btn sidebar__btn--primary";
  promoteBtn.textContent = "Promote";
  promoteBtn.addEventListener("click", async () => {
    try {
      promoteBtn.disabled = true;
      dismissBtn.disabled = true;
      await resolveCandidate(result.candidateId, {
        action: "promote",
        number: numberInput.value.trim(),
      });
      closeSidebar();
    } catch (err) {
      _showError(actions, err.message);
      promoteBtn.disabled = false;
      dismissBtn.disabled = false;
    }
  });

  const dismissBtn = document.createElement("button");
  dismissBtn.type = "button";
  dismissBtn.className = "sidebar__btn sidebar__btn--danger";
  dismissBtn.textContent = "Dismiss";
  dismissBtn.addEventListener("click", async () => {
    try {
      promoteBtn.disabled = true;
      dismissBtn.disabled = true;
      await resolveCandidate(result.candidateId, { action: "dismiss" });
      closeSidebar();
    } catch (err) {
      _showError(actions, err.message);
      promoteBtn.disabled = false;
      dismissBtn.disabled = false;
    }
  });

  const framesBtn = document.createElement("button");
  framesBtn.type = "button";
  framesBtn.className = "sidebar__btn";
  framesBtn.textContent = "View frames";
  framesBtn.addEventListener("click", () => {
    let centerTs = null;
    if (result.time instanceof Date) {
      centerTs = result.time.toISOString();
    } else if (result.time) {
      centerTs = String(result.time);
    }
    openBrowser({ run: result.run, centerTs });
  });

  btnRow.appendChild(promoteBtn);
  btnRow.appendChild(dismissBtn);
  btnRow.appendChild(framesBtn);
  actions.appendChild(btnRow);

  content.appendChild(actions);
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Add card--selected to the card matching _selectedCrossingId, clear all others.
 * Matches on data-crossing-id OR data-candidate-id to support both modes.
 */
function _applySelectionHighlight() {
  const timeline = document.getElementById("timeline");
  if (!timeline || !_selectedCrossingId) return;

  // Crossing cards.
  timeline.querySelectorAll("[data-crossing-id]").forEach((card) => {
    if (card.dataset.crossingId === _selectedCrossingId) {
      card.classList.add("card--selected");
    } else {
      card.classList.remove("card--selected");
    }
  });

  // Candidate cards.
  timeline.querySelectorAll("[data-candidate-id]").forEach((card) => {
    if (card.dataset.candidateId === _selectedCrossingId) {
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
 * Display an inline error message in the actions container.
 * Replaces any previous error.
 *
 * @param {HTMLElement|null} container
 * @param {string} message
 */
function _showError(container, message) {
  if (!container) return;
  let el = container.querySelector(".sidebar__error");
  if (!el) {
    el = document.createElement("p");
    el.className = "sidebar__error";
    el.style.cssText = "color:#dc2626;font-size:0.8rem;margin:0.25rem 0 0;";
    container.appendChild(el);
  }
  el.textContent = message;
}
