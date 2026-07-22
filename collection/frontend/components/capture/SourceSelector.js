/**
 * SourceSelector.js — Camera / video source toggle.
 *
 * @module components/capture/SourceSelector
 */

import { html } from '../../vendor/preact-setup.js';

/**
 * @param {import('../../types').SourceSelectorProps} props
 * @returns {any}
 */
export function SourceSelector({ value, onChange }) {
  return html`
    <div class="source-selector">
      <label>
        <input
          type="radio"
          name="source"
          value="camera"
          checked=${value === 'camera'}
          onChange=${(/** @type {Event} */ e) => onChange(/** @type {HTMLInputElement} */ (e.target).value)}
        />
        Camera
      </label>
      <label>
        <input
          type="radio"
          name="source"
          value="video"
          checked=${value === 'video'}
          onChange=${(/** @type {Event} */ e) => onChange(/** @type {HTMLInputElement} */ (e.target).value)}
        />
        Video file
      </label>
    </div>
  `;
}
