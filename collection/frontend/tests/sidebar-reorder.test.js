/**
 * sidebar-reorder.test.js — Regression test for the sidebar's neighbour-based
 * reorder (the "Move earlier" / "Move later" buttons).
 *
 * These buttons were originally mis-ported to a no-op frame-stepper; this test
 * pins the parity behaviour: they must call onReorder with the correct
 * neighbour ids given the timeline's DESC (newest-first) display order, and be
 * disabled at the ends of the list.
 *
 * Globals are installed by setup-dom.js via --import (see npm run unit).
 *
 * @module tests/sidebar-reorder.test
 */

// @ts-nocheck
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { h, render } from '../vendor/preact-setup.js';
import { Sidebar } from '../components/results/Sidebar.js';

/**
 * Minimal Result-shaped object for a confirmed crossing.
 * @param {string} crossingId
 * @returns {any}
 */
function makeResult(crossingId) {
  return {
    isCandidate: false,
    crossingId,
    raceNumber: 42,
    name: 'Alice',
    category: 'Cat 3',
    matched: true,
    annotatedUrl: `/annotated/${crossingId}.jpg`,
    source: 'auto',
    edited: false,
    orderKey: 1718445600000,
    orderOverridden: false,
    numberText: '42',
    time: new Date('2024-06-15T10:00:00Z'),
  };
}

/**
 * Mount Sidebar in crossing mode and return { container, calls }.
 * runLabel is '' so the roster-datalist effect (a network call) is skipped.
 * @param {object} overrides
 */
function mountSidebar(overrides = {}) {
  const container = document.createElement('div');
  document.body.appendChild(container);
  /** @type {any[]} */
  const calls = [];
  const props = {
    item: makeResult('b'),
    runLabel: '',
    orderedCrossingIds: ['a', 'b', 'c'], // display order: newest → oldest
    onClose: () => {},
    onEdit: async () => {},
    onDelete: async () => {},
    onReorder: async (crossingId, neighbours) => { calls.push({ crossingId, neighbours }); },
    onPromote: async () => {},
    onDismiss: async () => {},
    onOpenBrowser: () => {},
    ...overrides,
  };
  render(h(Sidebar, props), container);
  return { container, calls };
}

/** Find a .sidebar__btn by its trimmed text content. */
function btnByText(container, text) {
  return Array.from(container.querySelectorAll('.sidebar__btn'))
    .find((b) => b.textContent.trim() === text);
}

describe('Sidebar reorder (Move earlier / Move later)', () => {

  it('Move earlier calls onReorder with { earlierId: below-below, laterId: below }', () => {
    const { container, calls } = mountSidebar(); // selected 'b' (idx 1 of a,b,c)
    const btn = btnByText(container, 'Move earlier');
    assert.ok(btn && !btn.disabled, 'Move earlier should be enabled for a middle item');

    btn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));

    assert.equal(calls.length, 1, 'onReorder should fire once');
    assert.equal(calls[0].crossingId, 'b');
    // idx 1: laterId = ids[2] = 'c'; earlierId = ids[3] = undefined → null
    assert.deepEqual(calls[0].neighbours, { earlierId: null, laterId: 'c' });

    render(null, container);
    container.remove();
  });

  it('Move later calls onReorder with { earlierId: above, laterId: above-above }', () => {
    const { container, calls } = mountSidebar(); // selected 'b'
    const btn = btnByText(container, 'Move later');
    assert.ok(btn && !btn.disabled, 'Move later should be enabled for a middle item');

    btn.dispatchEvent(new window.MouseEvent('click', { bubbles: true }));

    assert.equal(calls.length, 1, 'onReorder should fire once');
    // idx 1: earlierId = ids[0] = 'a'; laterId = ids[-1] = undefined → null
    assert.deepEqual(calls[0].neighbours, { earlierId: 'a', laterId: null });

    render(null, container);
    container.remove();
  });

  it('Move later is disabled for the newest item (top of the list)', () => {
    const { container } = mountSidebar({ item: makeResult('a') }); // idx 0
    assert.equal(btnByText(container, 'Move later').disabled, true);
    assert.equal(btnByText(container, 'Move earlier').disabled, false);
    render(null, container);
    container.remove();
  });

  it('Move earlier is disabled for the oldest item (bottom of the list)', () => {
    const { container } = mountSidebar({ item: makeResult('c') }); // idx 2 (last)
    assert.equal(btnByText(container, 'Move earlier').disabled, true);
    assert.equal(btnByText(container, 'Move later').disabled, false);
    render(null, container);
    container.remove();
  });
});
