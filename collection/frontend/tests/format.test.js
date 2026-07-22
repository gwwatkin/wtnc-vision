/**
 * format.test.js — Unit tests for format.js (FR8).
 * Runner: node --test (no DOM required — format.js is pure).
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

// format.js is pure — no Preact dependency, importable directly under node.
import {
  formatTimeOfDay,
  formatGapLabel,
} from '../components/results/format.js';

// ---------------------------------------------------------------------------
// formatTimeOfDay — "hh:mm:ss"
// ---------------------------------------------------------------------------

describe('formatTimeOfDay', () => {
  it('formats a mid-morning time', () => {
    const d = new Date(2024, 5, 1, 9, 5, 3); // 09:05:03
    assert.equal(formatTimeOfDay(d), '09:05:03');
  });

  it('pads single-digit hours, minutes, seconds to two digits', () => {
    const d = new Date(2024, 0, 1, 1, 2, 3); // 01:02:03
    assert.equal(formatTimeOfDay(d), '01:02:03');
  });

  it('handles midnight (00:00:00)', () => {
    const d = new Date(2024, 0, 1, 0, 0, 0);
    assert.equal(formatTimeOfDay(d), '00:00:00');
  });

  it('handles noon (12:00:00)', () => {
    const d = new Date(2024, 0, 1, 12, 0, 0);
    assert.equal(formatTimeOfDay(d), '12:00:00');
  });

  it('handles end-of-day (23:59:59)', () => {
    const d = new Date(2024, 0, 1, 23, 59, 59);
    assert.equal(formatTimeOfDay(d), '23:59:59');
  });

  it('pads all-zeros seconds correctly', () => {
    const d = new Date(2024, 0, 1, 10, 30, 0); // 10:30:00
    assert.equal(formatTimeOfDay(d), '10:30:00');
  });
});

// ---------------------------------------------------------------------------
// formatGapLabel — "hh:mm"
// ---------------------------------------------------------------------------

describe('formatGapLabel', () => {
  it('formats a mid-morning time', () => {
    const d = new Date(2024, 5, 1, 9, 5, 42); // 09:05
    assert.equal(formatGapLabel(d), '09:05');
  });

  it('pads single-digit hours and minutes to two digits', () => {
    const d = new Date(2024, 0, 1, 1, 2, 59); // 01:02
    assert.equal(formatGapLabel(d), '01:02');
  });

  it('handles midnight (00:00)', () => {
    const d = new Date(2024, 0, 1, 0, 0, 0);
    assert.equal(formatGapLabel(d), '00:00');
  });

  it('handles noon (12:00)', () => {
    const d = new Date(2024, 0, 1, 12, 0, 0);
    assert.equal(formatGapLabel(d), '12:00');
  });

  it('handles end-of-day (23:59)', () => {
    const d = new Date(2024, 0, 1, 23, 59, 59);
    assert.equal(formatGapLabel(d), '23:59');
  });

  it('omits seconds (only hh:mm)', () => {
    const d = new Date(2024, 0, 1, 14, 7, 33); // 14:07, seconds ignored
    assert.equal(formatGapLabel(d), '14:07');
  });
});
