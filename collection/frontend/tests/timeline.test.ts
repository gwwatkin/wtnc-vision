/**
 * timeline.test.ts — Component test for Timeline (FR9/SC6).
 *
 * Globals (window, document) are provided by happy-dom via Vitest's
 * environment: 'happy-dom' config. No setup-dom.js import needed.
 *
 * @module tests/timeline.test
 */

import { describe, it } from 'vitest';
import assert from 'node:assert/strict';
import { h, render } from 'preact';
import { Timeline } from '../components/results/Timeline';

// ---------------------------------------------------------------------------
// Fixture helpers — build minimal FROZEN-1 Pack and Lane objects directly
// rather than going through the data transform layer, to keep the test
// self-contained and fast.
// ---------------------------------------------------------------------------

import type { Result, CandidateResult, Lane, Pack } from '../types';

function makeResult(overrides: Partial<Result> = {}): Result {
  return {
    isCandidate: false,
    crossingId: 'c1',
    raceNumber: 42,
    name: 'Alice',
    category: 'Cat 3',
    matched: true,
    annotatedUrl: '/annotated/c1.jpg',
    source: 'auto',
    edited: false,
    orderKey: 1718445600000,
    orderOverridden: false,
    numberText: '42',
    time: new Date('2024-06-15T10:00:00Z'),
    ...overrides,
  };
}

function makeCandidate(overrides: Partial<CandidateResult> = {}): CandidateResult {
  return {
    isCandidate: true,
    candidateId: 'cand-1',
    run: 'run1',
    time: new Date('2024-06-15T10:05:00Z'),
    lastSeen: new Date('2024-06-15T10:05:01Z'),
    frameCount: 3,
    hintNumber: '7',
    hintConf: 0.9,
    imageUrl: '/frames/f1.jpg',
    repBox: [10, 20, 50, 80],
    orderKey: 1718445900000,
    numberText: '7?',
    category: 'Unknown',
    ...overrides,
  };
}

function makeLane(category: string, index: number): Lane {
  return { category, index };
}

function makePack(startTime: Date, results: Array<Result | CandidateResult>): Pack {
  return { startTime, results };
}

// ---------------------------------------------------------------------------
// Render helper: mount Timeline into a fresh <div>, return the container.
// ---------------------------------------------------------------------------

function mountTimeline(props: {
  packs: Pack[];
  lanes: Lane[];
  candidatesVisible: boolean;
  selectedId: string | null;
  onSelect: (item: object) => void;
}): Element {
  const container = document.createElement('div');
  document.body.appendChild(container);
  render(h(Timeline, props), container);
  return container;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Timeline component', () => {

  // SC6-a: correct card count for a given packs array
  it('renders the correct number of crossing cards for one pack', () => {
    const r1 = makeResult({ crossingId: 'c1', category: 'Cat 3' });
    const r2 = makeResult({ crossingId: 'c2', raceNumber: 7, name: 'Bob', category: 'Cat 3' });
    const lanes = [makeLane('Cat 3', 0)];
    const packs = [makePack(new Date('2024-06-15T10:00:00Z'), [r1, r2])];

    const container = mountTimeline({
      packs,
      lanes,
      candidatesVisible: false,
      selectedId: null,
      onSelect: () => {},
    });

    // Two cards should be rendered — one per result.
    const cards = container.querySelectorAll('.card');
    assert.equal(cards.length, 2, 'expected 2 crossing cards');

    render(null, container);
    container.remove();
  });

  // SC6-a continued: empty packs ⇒ empty state element
  it('renders empty state when packs is empty', () => {
    const container = mountTimeline({
      packs: [],
      lanes: [],
      candidatesVisible: false,
      selectedId: null,
      onSelect: () => {},
    });

    const empty = container.querySelector('.timeline__empty');
    assert.ok(empty, 'expected .timeline__empty element');

    render(null, container);
    container.remove();
  });

  // SC6-b: clicking a card calls onSelect with the right item
  it('calls onSelect with the correct item when a card is clicked', () => {
    const result = makeResult({ crossingId: 'click-test' });
    const lanes = [makeLane('Cat 3', 0)];
    const packs = [makePack(new Date('2024-06-15T10:00:00Z'), [result])];

    const received: object[] = [];
    const onSelect = (item: object) => received.push(item);

    const container = mountTimeline({
      packs,
      lanes,
      candidatesVisible: true,
      selectedId: null,
      onSelect,
    });

    const card = container.querySelector('.card');
    assert.ok(card, 'expected a card to exist');

    // Simulate a click event.
    card.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));

    assert.equal(received.length, 1, 'onSelect should have been called once');
    assert.equal(
      (received[0] as Result).crossingId,
      'click-test',
      'onSelect should receive the correct result item',
    );

    render(null, container);
    container.remove();
  });

  // SC6-b: clicking a candidate card also calls onSelect with the candidate item
  it('calls onSelect with the correct candidate item when a candidate card is clicked', () => {
    const candidate = makeCandidate({ candidateId: 'cand-click' });
    const lanes = [makeLane('Cat 3', 0)];
    const packs = [makePack(new Date('2024-06-15T10:05:00Z'), [candidate])];

    const received: object[] = [];

    const container = mountTimeline({
      packs,
      lanes,
      candidatesVisible: true,
      selectedId: null,
      onSelect: (item: object) => received.push(item),
    });

    const card = container.querySelector('.card--candidate');
    assert.ok(card, 'expected a candidate card to exist');

    card.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));

    assert.equal(received.length, 1, 'onSelect should have been called once');
    assert.equal(
      (received[0] as CandidateResult).candidateId,
      'cand-click',
      'onSelect should receive the correct candidate item',
    );

    render(null, container);
    container.remove();
  });

  // SC6-c: candidate cards appear / hide per candidatesVisible
  // Note: Timeline renders whatever packs it is given. candidatesVisible is
  // reflected by the packs array constructed by the caller (via deriveView).
  // Here we pass packs with / without candidates to simulate the toggle.
  it('candidate cards are present when packs include candidates', () => {
    const candidate = makeCandidate({ candidateId: 'cand-visible' });
    const lanes = [makeLane('Cat 3', 0)];
    const packs = [makePack(new Date('2024-06-15T10:05:00Z'), [candidate])];

    const container = mountTimeline({
      packs,
      lanes,
      candidatesVisible: true,
      selectedId: null,
      onSelect: () => {},
    });

    const candidateCards = container.querySelectorAll('.card--candidate');
    assert.equal(candidateCards.length, 1, 'expected one candidate card');

    render(null, container);
    container.remove();
  });

  it('candidate cards are absent when packs contain no candidates', () => {
    const result = makeResult({ crossingId: 'no-cand' });
    const lanes = [makeLane('Cat 3', 0)];
    const packs = [makePack(new Date('2024-06-15T10:00:00Z'), [result])];

    const container = mountTimeline({
      packs,
      lanes,
      candidatesVisible: false,
      selectedId: null,
      onSelect: () => {},
    });

    const candidateCards = container.querySelectorAll('.card--candidate');
    assert.equal(candidateCards.length, 0, 'expected no candidate cards');

    render(null, container);
    container.remove();
  });

  // SC6-d: selectedId applies card--selected
  it('applies card--selected to the card whose crossingId matches selectedId', () => {
    const r1 = makeResult({ crossingId: 'sel-1', category: 'Cat 3' });
    const r2 = makeResult({ crossingId: 'sel-2', raceNumber: 99, category: 'Cat 3' });
    const lanes = [makeLane('Cat 3', 0)];
    const packs = [makePack(new Date('2024-06-15T10:00:00Z'), [r1, r2])];

    const container = mountTimeline({
      packs,
      lanes,
      candidatesVisible: false,
      selectedId: 'sel-1',
      onSelect: () => {},
    });

    const selectedCards = container.querySelectorAll('.card--selected');
    assert.equal(selectedCards.length, 1, 'exactly one card should be selected');

    // Verify the selected card is the first one (sel-1), not sel-2.
    const allCards = container.querySelectorAll('.card');
    // Cards are rendered in pack.results order (r1 first, r2 second).
    assert.ok(
      allCards[0].classList.contains('card--selected'),
      'the first card (sel-1) should have card--selected',
    );
    assert.ok(
      !allCards[1].classList.contains('card--selected'),
      'the second card (sel-2) should not have card--selected',
    );

    render(null, container);
    container.remove();
  });

  // SC6-d continued: selectedId matching a candidate applies card--selected
  it('applies card--selected to a candidate card matching selectedId', () => {
    const candidate = makeCandidate({ candidateId: 'sel-cand-1' });
    const lanes = [makeLane('Cat 3', 0)];
    const packs = [makePack(new Date('2024-06-15T10:05:00Z'), [candidate])];

    const container = mountTimeline({
      packs,
      lanes,
      candidatesVisible: true,
      selectedId: 'sel-cand-1',
      onSelect: () => {},
    });

    const selectedCards = container.querySelectorAll('.card--selected');
    assert.equal(selectedCards.length, 1, 'exactly one candidate card should be selected');
    assert.ok(
      selectedCards[0].classList.contains('card--candidate'),
      'the selected card should also have card--candidate',
    );

    render(null, container);
    container.remove();
  });

  // Multiple packs → correct total card count
  it('renders cards from multiple packs', () => {
    const r1 = makeResult({ crossingId: 'mp-1', category: 'Cat 3' });
    const r2 = makeResult({ crossingId: 'mp-2', category: 'Cat 4' });
    const r3 = makeResult({ crossingId: 'mp-3', category: 'Cat 3' });
    const lanes = [makeLane('Cat 3', 0), makeLane('Cat 4', 1)];
    const packs = [
      makePack(new Date('2024-06-15T10:01:00Z'), [r1, r2]),
      makePack(new Date('2024-06-15T10:10:00Z'), [r3]),
    ];

    const container = mountTimeline({
      packs,
      lanes,
      candidatesVisible: false,
      selectedId: null,
      onSelect: () => {},
    });

    const cards = container.querySelectorAll('.card');
    assert.equal(cards.length, 3, 'expected 3 cards across 2 packs');

    render(null, container);
    container.remove();
  });
});
