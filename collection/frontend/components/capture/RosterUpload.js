/**
 * RosterUpload.js — CSV roster upload with status display.
 *
 * @module components/capture/RosterUpload
 */

import { html, useRef } from '../../vendor/preact-setup.js';

/**
 * @param {import('../../types').RosterUploadProps} props
 * @returns {any}
 */
export function RosterUpload({ onUpload, status }) {
  const fileRef = useRef(/** @type {HTMLInputElement | null} */ (null));

  function handleUpload() {
    const file = fileRef.current && fileRef.current.files && fileRef.current.files[0];
    if (!file) return;
    onUpload(file);
  }

  return html`
    <div class="roster-upload">
      <input
        id="roster-file"
        type="file"
        accept=".csv"
        ref=${fileRef}
      />
      <button
        id="roster-upload-btn"
        onClick=${handleUpload}
      >
        Upload roster
      </button>
      <span id="roster-status">${status || ''}</span>
    </div>
  `;
}
