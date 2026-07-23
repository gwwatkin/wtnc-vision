/**
 * format.ts — Pure formatting helpers (port from render.js).
 * Implemented here because Card.tsx (the Wave A reference component) depends on
 * formatTimeOfDay; task3 will fill/verify the implementation during Wave B.
 *
 * @module components/results/format
 */

/**
 * Format a Date as wall-clock time-of-day "hh:mm:ss".
 */
export function formatTimeOfDay(date: Date): string {
  const hh = String(date.getHours()).padStart(2, '0');
  const mm = String(date.getMinutes()).padStart(2, '0');
  const ss = String(date.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}

/**
 * Format a Date as "hh:mm" for use in gap separator labels.
 */
export function formatGapLabel(date: Date): string {
  const hh = String(date.getHours()).padStart(2, '0');
  const mm = String(date.getMinutes()).padStart(2, '0');
  return `${hh}:${mm}`;
}
