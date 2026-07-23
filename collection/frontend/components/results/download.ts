/**
 * download.ts — Crossings download helper.
 *
 * Fetches the export Blob via api.fetchExportBlob then triggers a named
 * file download via a temporary anchor. DOM anchor lives here, not in api.ts,
 * so api.ts stays DOM-free (design §6.2).
 *
 * @module components/results/download
 */

import type { ExportFormat } from '../../types';
import * as api from '../../api';

/**
 * Download a run's crossings via the export endpoint; blob→anchor so it works
 * cross-origin and lets us control the filename regardless of Content-Disposition.
 */
export async function downloadResults(run: string, format: ExportFormat): Promise<void> {
  const blob = await api.fetchExportBlob(run, format);
  const url  = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: `crossings_${run}.${format}` });
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
