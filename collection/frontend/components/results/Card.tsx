/**
 * Card.tsx — Crossing card and Candidate card components.
 * Presentational: driven entirely by props. No data-* wiring, no imperative selection.
 * DOM structure and CSS classes match render.js:155–281 exactly (FROZEN-3).
 *
 * @module components/results/Card
 */

import { formatTimeOfDay } from './format';
import type { CardProps, CandidateCardProps, Result, CandidateResult } from '../../types';

/**
 * Crossing result card.
 */
export function Card({ crossing, column, selected, onClick }: CardProps) {
  // CardProps.crossing is typed as `object` (frozen in types.ts); cast to Result
  // so the compiler can verify field access throughout this function.
  const r = crossing as Result;

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

  return (
    <div
      class={classes}
      style={{ gridColumn: column }}
      onClick={onClick}
    >
      {r.source === 'manual' ? <span class="badge badge--manual">✚ manual</span> : null}
      {r.edited            ? <span class="badge badge--edited">✎ edited</span> : null}
      {r.orderOverridden   ? <span class="badge badge--moved">↕ moved</span> : null}
      <span class="card__number">{numberText}</span>
      <span class="card__name">{nameText}</span>
      <span class="card__meta">{metaText}</span>
    </div>
  );
}

/**
 * Candidate pseudo-result card.
 */
export function CandidateCard({ candidate, column, selected, onClick }: CandidateCardProps) {
  // CandidateCardProps.candidate is typed as `object` (frozen in types.ts); cast
  // to CandidateResult so the compiler can verify field access.
  const c = candidate as CandidateResult;

  const classes = [
    'card',
    'card--candidate',
    'card--selectable',
    selected ? 'card--selected' : '',
  ].filter(Boolean).join(' ');

  // "? <hintNumber>?" when hint present, else "? unidentified"
  const numberText = c.hintNumber ? `? ${c.hintNumber}?` : '? unidentified';

  return (
    <div
      class={classes}
      style={{ gridColumn: column }}
      onClick={onClick}
    >
      <span class="card__number">{numberText}</span>
      <span class="card__meta">{formatTimeOfDay(c.time)}</span>
    </div>
  );
}
