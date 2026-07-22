/**
 * Card.js — Crossing card and Candidate card components.
 * Presentational: driven entirely by props. No data-* wiring, no imperative selection.
 * DOM structure and CSS classes match render.js:155–281 exactly (FROZEN-3).
 *
 * @module components/results/Card
 */

import { html } from '../../vendor/preact-setup.js';
import { formatTimeOfDay } from './format.js';

/**
 * Crossing result card.
 *
 * @param {import('../../types').CardProps} props
 * @returns {any}
 */
export function Card({ crossing, column, selected, onClick }) {
  // Cast to the shape we know from FROZEN-1 / render.js.
  /** @type {import('../../types').Result} */
  const r = /** @type {any} */ (crossing);

  const isUnknown = !r.matched;

  const classes = [
    'card',
    'card--selectable',
    isUnknown ? 'card--unknown' : '',
    selected   ? 'card--selected' : '',
  ].filter(Boolean).join(' ');

  // Number display: "#<raceNumber>" or "# —" per render.js:209–211
  const numberText = r.numberText !== '—' ? `#${r.raceNumber}` : '# —';

  // Name display: "Unknown rider" when unmatched
  const nameText = isUnknown ? 'Unknown rider' : r.name;

  // Meta: "<category> · hh:mm:ss" (matched) or just "hh:mm:ss" (unknown)
  const metaText = isUnknown
    ? formatTimeOfDay(r.time)
    : `${r.category} · ${formatTimeOfDay(r.time)}`;

  return html`
    <div
      class=${classes}
      style=${{ gridColumn: column }}
      onClick=${onClick}
    >
      ${r.source === 'manual' && html`<span class="badge badge--manual">✚ manual</span>`}
      ${r.edited            && html`<span class="badge badge--edited">✎ edited</span>`}
      ${r.orderOverridden   && html`<span class="badge badge--moved">↕ moved</span>`}
      <span class="card__number">${numberText}</span>
      <span class="card__name">${nameText}</span>
      <span class="card__meta">${metaText}</span>
    </div>
  `;
}

/**
 * Candidate pseudo-result card.
 *
 * @param {import('../../types').CandidateCardProps} props
 * @returns {any}
 */
export function CandidateCard({ candidate, column, selected, onClick }) {
  /** @type {import('../../types').CandidateResult} */
  const c = /** @type {any} */ (candidate);

  const classes = [
    'card',
    'card--candidate',
    'card--selectable',
    selected ? 'card--selected' : '',
  ].filter(Boolean).join(' ');

  // "? <hintNumber>?" when hint present, else "? unidentified"
  const numberText = c.hintNumber ? `? ${c.hintNumber}?` : '? unidentified';

  return html`
    <div
      class=${classes}
      style=${{ gridColumn: column }}
      onClick=${onClick}
    >
      <span class="card__number">${numberText}</span>
      <span class="card__meta">${formatTimeOfDay(c.time)}</span>
    </div>
  `;
}
