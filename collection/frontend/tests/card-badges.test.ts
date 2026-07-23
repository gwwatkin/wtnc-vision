/**
 * card-badges.test.ts — Component tests for provenance badges on Card (FR-parity).
 *
 * Asserts that the three provenance badges (manual / edited / moved) render when
 * the corresponding flags are set on a crossing result, and are absent for a plain
 * auto crossing. This guards the regression fixed in followup_1 where
 * `${cond && html`…`}` emitted `false` instead of nothing under htm.
 *
 * Run via: npm run unit  (or npm run check)
 *
 * @module tests/card-badges.test
 */

import { describe, it } from 'vitest';
import assert from 'node:assert/strict';
import { h, render } from 'preact';
import { Card } from '../components/results/Card';

// ---------------------------------------------------------------------------
// Fixture helpers
// ---------------------------------------------------------------------------

function makeCrossing(overrides: object = {}) {
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

// ---------------------------------------------------------------------------
// Render helper: mount Card into a fresh <div>, return the container.
// ---------------------------------------------------------------------------

function mountCard(crossing: object): Element {
  const container = document.createElement('div');
  document.body.appendChild(container);
  render(
    h(Card, {
      crossing,
      column: 1,
      selected: false,
      onClick: () => {},
    }),
    container,
  );
  return container;
}

function unmount(container: Element) {
  render(null, container);
  container.remove();
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Card provenance badges', () => {

  it('renders .badge--manual for a manual crossing (source === "manual")', () => {
    const crossing = makeCrossing({ source: 'manual' });
    const container = mountCard(crossing);

    const badge = container.querySelector('.badge--manual');
    assert.ok(badge, 'expected .badge--manual element to be present');
    assert.ok(
      badge.textContent!.includes('manual'),
      '.badge--manual should contain the text "manual"',
    );

    // The other badges must NOT appear.
    assert.equal(
      container.querySelectorAll('.badge--edited').length,
      0,
      '.badge--edited should be absent when edited is false',
    );
    assert.equal(
      container.querySelectorAll('.badge--moved').length,
      0,
      '.badge--moved should be absent when orderOverridden is false',
    );

    unmount(container);
  });

  it('renders .badge--edited for an edited crossing (edited === true)', () => {
    const crossing = makeCrossing({ edited: true });
    const container = mountCard(crossing);

    const badge = container.querySelector('.badge--edited');
    assert.ok(badge, 'expected .badge--edited element to be present');
    assert.ok(
      badge.textContent!.includes('edited'),
      '.badge--edited should contain the text "edited"',
    );

    // The other badges must NOT appear.
    assert.equal(
      container.querySelectorAll('.badge--manual').length,
      0,
      '.badge--manual should be absent when source is "auto"',
    );
    assert.equal(
      container.querySelectorAll('.badge--moved').length,
      0,
      '.badge--moved should be absent when orderOverridden is false',
    );

    unmount(container);
  });

  it('renders .badge--moved for a reordered crossing (orderOverridden === true)', () => {
    const crossing = makeCrossing({ orderOverridden: true });
    const container = mountCard(crossing);

    const badge = container.querySelector('.badge--moved');
    assert.ok(badge, 'expected .badge--moved element to be present');
    assert.ok(
      badge.textContent!.includes('moved'),
      '.badge--moved should contain the text "moved"',
    );

    // The other badges must NOT appear.
    assert.equal(
      container.querySelectorAll('.badge--manual').length,
      0,
      '.badge--manual should be absent when source is "auto"',
    );
    assert.equal(
      container.querySelectorAll('.badge--edited').length,
      0,
      '.badge--edited should be absent when edited is false',
    );

    unmount(container);
  });

  it('renders no badges for a plain auto crossing', () => {
    const crossing = makeCrossing(); // defaults: source="auto", edited=false, orderOverridden=false
    const container = mountCard(crossing);

    assert.equal(
      container.querySelectorAll('.badge').length,
      0,
      'no badge elements should be present for a plain auto crossing',
    );

    unmount(container);
  });

  it('renders all three badges simultaneously when all flags are set', () => {
    const crossing = makeCrossing({
      source: 'manual',
      edited: true,
      orderOverridden: true,
    });
    const container = mountCard(crossing);

    assert.ok(container.querySelector('.badge--manual'), '.badge--manual must be present');
    assert.ok(container.querySelector('.badge--edited'), '.badge--edited must be present');
    assert.ok(container.querySelector('.badge--moved'), '.badge--moved must be present');
    assert.equal(
      container.querySelectorAll('.badge').length,
      3,
      'exactly 3 badge elements should be rendered',
    );

    unmount(container);
  });

  it('badges appear before .card__number in DOM order', () => {
    const crossing = makeCrossing({ source: 'manual', edited: true });
    const container = mountCard(crossing);

    const card = container.querySelector('.card');
    assert.ok(card, 'expected a .card element');

    const children = Array.from(card.children);
    const manualIdx = children.findIndex((el) => el.classList.contains('badge--manual'));
    const editedIdx = children.findIndex((el) => el.classList.contains('badge--edited'));
    const numberIdx = children.findIndex((el) => el.classList.contains('card__number'));

    assert.ok(manualIdx !== -1, '.badge--manual not found in card children');
    assert.ok(editedIdx !== -1, '.badge--edited not found in card children');
    assert.ok(numberIdx !== -1, '.card__number not found in card children');
    assert.ok(manualIdx < numberIdx, '.badge--manual must come before .card__number');
    assert.ok(editedIdx < numberIdx, '.badge--edited must come before .card__number');
    assert.ok(manualIdx < editedIdx, '.badge--manual must come before .badge--edited');

    unmount(container);
  });
});
