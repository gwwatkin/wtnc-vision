/**
 * Timeline.js — CSS-grid timeline of packs and cards.
 * Also exports Pack, GapSeparator components (all in this file per task3 ownership).
 *
 * @module components/results/Timeline
 */

import { html } from '../../vendor/preact-setup.js';
import { Card, CandidateCard } from './Card.js';
import { formatGapLabel } from './format.js';

/**
 * Full timeline: lane headers + one Pack per pack group.
 *
 * @param {import('../../types').TimelineProps} props
 * @returns {any}
 */
export function Timeline({ packs, lanes, candidatesVisible, selectedId, onSelect }) {
  // Empty state: no packs at all, or all packs are empty.
  const hasResults = packs.some((p) => p.results.length > 0);
  if (!packs.length || !hasResults) {
    return html`
      <div class="timeline" style=${{ '--lane-count': lanes.length }}>
        <p class="timeline__empty">No crossings yet — waiting for riders…</p>
      </div>
    `;
  }

  return html`
    <div class="timeline" style=${{ '--lane-count': lanes.length }}>
      ${lanes.map((lane) => html`
        <div
          class="lane-header"
          data-category=${lane.category}
          style=${{ gridColumn: lane.index + 1 }}
        >${lane.category}</div>
      `)}
      ${packs.map((pack) => pack.results.length === 0 ? null : html`
        <${Pack}
          pack=${pack}
          lanes=${lanes}
          selectedId=${selectedId}
          onSelect=${onSelect}
        />
      `)}
    </div>
  `;
}

/**
 * One pack group: a leading GapSeparator then a Card/CandidateCard per result.
 *
 * @param {import('../../types').PackProps} props
 * @returns {any}
 */
export function Pack({ pack, lanes, selectedId, onSelect }) {
  // Build category→lane lookup once per pack render.
  /** @type {Map<string, import('../../types').Lane>} */
  const laneByCategory = new Map(lanes.map((l) => [l.category, l]));

  return html`
    <${GapSeparator} label=${formatGapLabel(pack.startTime)} />
    ${pack.results.map((item) => {
      if (item.isCandidate) {
        // Candidate column: lanes.length, or 1 if no lanes yet.
        const col = lanes.length || 1;
        return html`
          <${CandidateCard}
            candidate=${item}
            column=${col}
            selected=${item.candidateId === selectedId}
            onClick=${() => onSelect(item)}
          />
        `;
      } else {
        // Crossing column: lane.index+1, or lanes.length as fallback.
        const lane = laneByCategory.get(item.category);
        const col = lane != null ? lane.index + 1 : lanes.length;
        return html`
          <${Card}
            crossing=${item}
            column=${col}
            selected=${item.crossingId === selectedId}
            onClick=${() => onSelect(item)}
          />
        `;
      }
    })}
  `;
}

/**
 * Full-width separator between time groups.
 *
 * @param {import('../../types').GapSeparatorProps} props
 * @returns {any}
 */
export function GapSeparator({ label }) {
  return html`
    <div class="gap-separator" style=${{ gridColumn: '1 / -1' }}>${label}</div>
  `;
}
