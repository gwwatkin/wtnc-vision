/**
 * download.js — Crossings download helper.
 *
 * Fetches the export Blob via api.fetchExportBlob then triggers a named
 * file download via a temporary anchor. DOM anchor lives here, not in api.js,
 * so api.js stays DOM-free (design §6.2).
 *
 * @module components/results/download
 */

// @ts-check

import * as api from '../../api.js';

/**
 * Download a run's crossings via the export endpoint; blob→anchor so it works
 * cross-origin and lets us control the filename regardless of Content-Disposition.
 *
 * @param {string} run
 * @param {'csv'|'json'} format
 * @returns {Promise<void>}
 */
export async function downloadResults(run, format) {
  const blob = await api.fetchExportBlob(run, format);
  const url  = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: `crossings_${run}.${format}` });
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
