/**
 * roster.ts — Populates the shared #roster-numbers datalist.
 *
 * The shared <datalist id="roster-numbers"> lives in index.html and is consumed
 * by both Sidebar and FrameBrowser via list="roster-numbers". Only the open
 * overlay calls setRosterOptions — errors are swallowed so the datalist degrades
 * gracefully when the roster is absent or the network fails.
 *
 * @module components/results/roster
 */

import * as api from '../../api';

/**
 * Fetch the roster for `run` and write <option value=number label=name> entries
 * into the shared <datalist id="roster-numbers"> in index.html.
 * Tolerates empty/absent roster — swallows all errors.
 */
export async function setRosterOptions(run: string): Promise<void> {
  const datalist = document.getElementById('roster-numbers');
  if (!datalist) return;

  let riders: Array<{ number: string; name: string }> = [];
  try {
    riders = await api.fetchRoster(run);
  } catch (_) {
    // Network error or absent roster — leave datalist empty; non-fatal.
    return;
  }

  if (!Array.isArray(riders)) return;

  datalist.innerHTML = '';
  for (const rider of riders) {
    const opt = document.createElement('option');
    opt.value = String(rider.number);
    opt.label = rider.name ? String(rider.name) : String(rider.number);
    datalist.appendChild(opt);
  }
}
