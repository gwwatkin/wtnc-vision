/**
 * format.js — Pure formatting helpers (FROZEN-3 port from render.js).
 * Verbatim from render.js:21–37. No Preact, no DOM.
 *
 * @module components/results/format
 */

/**
 * Format a Date as wall-clock time-of-day "hh:mm:ss".
 * @param {Date} date
 * @returns {string}
 */
export function formatTimeOfDay(date) {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  const ss = String(date.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

/**
 * Format a Date as "hh:mm" for use in gap separator labels.
 * @param {Date} date
 * @returns {string}
 */
export function formatGapLabel(date) {
  const hh = String(date.getHours()).padStart(2, "0");
  const mm = String(date.getMinutes()).padStart(2, "0");
  return `${hh}:${mm}`;
}
