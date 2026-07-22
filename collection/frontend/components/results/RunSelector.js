/**
 * RunSelector.js — Run selector dropdown.
 *
 * Presentational port of the #run-select control in results/results.js.
 * No fetch — runs come from state (polled by ResultsApp via GET /runs).
 *
 * The new design has no separate label-input (§6 shell / §9 component list), so
 * RunSelector is the authoritative run picker: its value reflects the `selected`
 * prop and picking a run fires `onChange(runLabel)`. ResultsApp holds the
 * selection in reducer state (design §8/§9).
 *
 * @module components/results/RunSelector
 */

import { html } from '../../vendor/preact-setup.js';

/**
 * @param {import('../../types').RunSelectorProps} props
 * @returns {any}
 */
export function RunSelector({ runs, selected, onChange }) {
  /**
   * Handle native change event — extract value and lift it to ResultsApp.
   *
   * @param {Event} e
   */
  function handleChange(e) {
    const target = /** @type {HTMLSelectElement} */ (e.target);
    if (target.value) onChange(target.value);
  }

  return html`
    <select id="run-select" value=${selected ?? ''} onChange=${handleChange}>
      <option value="">-- select run --</option>
      ${runs.map(run => html`
        <option key=${run} value=${run}>${run}</option>
      `)}
    </select>
  `;
}
