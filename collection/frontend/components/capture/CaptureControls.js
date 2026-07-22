/**
 * CaptureControls.js — Start/stop capture controls with inflight/frame counter.
 * Reflects the `recording` class app.js uses on the toggle button.
 *
 * @module components/capture/CaptureControls
 */

import { html } from '../../vendor/preact-setup.js';

/**
 * @param {import('../../types').CaptureControlsProps} props
 * @returns {any}
 */
export function CaptureControls({ active, onStart, onStop, inflight, label, onLabel }) {
  const btnClass = active ? 'recording' : '';

  return html`
    <div class="capture-controls">
      <div class="capture-controls__label-row">
        <label for="label-input">Run label:</label>
        <input
          id="label-input"
          type="text"
          value=${label}
          onInput=${(/** @type {Event} */ e) => onLabel(/** @type {HTMLInputElement} */ (e.target).value)}
          placeholder="e.g. race-2024-01"
        />
      </div>
      <div class="capture-controls__buttons">
        <button
          id="toggle-btn"
          class=${btnClass}
          onClick=${active ? onStop : onStart}
        >
          ${active ? 'Stop' : 'Start'}
        </button>
      </div>
      <div id="status" class="capture-controls__status">
        ${active ? 'Recording' : 'Stopped'} — in-flight: ${inflight}
      </div>
    </div>
  `;
}
