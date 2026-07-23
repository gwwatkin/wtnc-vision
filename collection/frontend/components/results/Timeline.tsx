/**
 * Timeline.tsx — CSS-grid timeline of packs and cards.
 * Also exports Pack, GapSeparator components (all in this file per task3 ownership).
 *
 * @module components/results/Timeline
 */

import { Card, CandidateCard } from './Card';
import { formatGapLabel } from './format';
import type { TimelineProps, PackProps, GapSeparatorProps, Lane, Result, CandidateResult } from '../../types';

/**
 * Full timeline: lane headers + one Pack per pack group.
 */
export function Timeline({ packs, lanes, candidatesVisible, selectedId, onSelect }: TimelineProps) {
  // Empty state: no packs at all, or all packs are empty.
  const hasResults = packs.some((p) => p.results.length > 0);
  if (!packs.length || !hasResults) {
    return (
      <div class="timeline" style={{ '--lane-count': lanes.length } as any}>
        <p class="timeline__empty">No crossings yet — waiting for riders…</p>
      </div>
    );
  }

  return (
    <div class="timeline" style={{ '--lane-count': lanes.length } as any}>
      {lanes.map((lane: Lane) => (
        <div
          class="lane-header"
          data-category={lane.category}
          style={{ gridColumn: lane.index + 1 }}
        >{lane.category}</div>
      ))}
      {packs.map((pack) => pack.results.length === 0 ? null : (
        <Pack
          pack={pack}
          lanes={lanes}
          selectedId={selectedId}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

/**
 * One pack group: a leading GapSeparator then a Card/CandidateCard per result.
 */
export function Pack({ pack, lanes, selectedId, onSelect }: PackProps) {
  // Build category→lane lookup once per pack render.
  const laneByCategory = new Map<string, Lane>(lanes.map((l) => [l.category, l]));

  return (
    <>
      <GapSeparator label={formatGapLabel(pack.startTime)} />
      {pack.results.map((item) => {
        if (item.isCandidate) {
          const c = item as CandidateResult;
          // Candidate column: lanes.length, or 1 if no lanes yet.
          const col = lanes.length || 1;
          return (
            <CandidateCard
              candidate={c}
              column={col}
              selected={c.candidateId === selectedId}
              onClick={() => onSelect(c)}
            />
          );
        } else {
          const r = item as Result;
          // Crossing column: lane.index+1, or lanes.length as fallback.
          const lane = laneByCategory.get(r.category);
          const col = lane != null ? lane.index + 1 : lanes.length;
          return (
            <Card
              crossing={r}
              column={col}
              selected={r.crossingId === selectedId}
              onClick={() => onSelect(r)}
            />
          );
        }
      })}
    </>
  );
}

/**
 * Full-width separator between time groups.
 */
export function GapSeparator({ label }: GapSeparatorProps) {
  return (
    <div class="gap-separator" style={{ gridColumn: '1 / -1' }}>{label}</div>
  );
}
