/**
 * backend-url.test.js — Unit tests for backend-url.js (FROZEN-1, page-split spec).
 *
 * Run with:
 *   node --test --import ./tests/setup-dom.js tests/backend-url.test.js
 * Or via:
 *   npm run unit
 *
 * Happy-dom requires a URL context for document.cookie to persist. We replace
 * the global window/document with a URL-aware Window before any test runs;
 * backend-url.js functions reference `document` dynamically (at call time)
 * so they pick up this replacement correctly.
 */

// @ts-nocheck
import { describe, it, before, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { Window } from 'happy-dom';

// Give every test a FRESH happy-dom Window (and thus a fresh, empty cookie jar).
// happy-dom requires a URL context for document.cookie to persist, and its
// string-based `max-age=0` expiry is unreliable at second granularity — so
// rather than expiring cookies between cases (flaky), we rebuild the jar.
// backend-url.js references `document` dynamically at call time, so it picks
// up each fresh replacement. This runs before any test callback because
// module top-level is synchronous, then again before each individual test.
function freshWindow() {
  const win = new Window({ url: 'http://localhost/' });
  globalThis.window = win;
  globalThis.document = win.document;
}
freshWindow();
beforeEach(freshWindow);

import {
  normalizeBackendUrl,
  getBackendUrl,
  setBackendUrl,
  onBackendUrlChange,
  backendLabel,
} from '../backend-url.js';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Clear ALL cookies between cases by expiring each one. */
function clearCookies() {
  for (const part of document.cookie.split(';')) {
    const name = part.split('=')[0].trim();
    if (name) {
      document.cookie = `${name}=; path=/; max-age=0`;
    }
  }
}

// ---------------------------------------------------------------------------
// normalizeBackendUrl
// ---------------------------------------------------------------------------

describe('normalizeBackendUrl', () => {
  it('returns empty string for null/undefined/empty', () => {
    assert.equal(normalizeBackendUrl(null), '');
    assert.equal(normalizeBackendUrl(undefined), '');
    assert.equal(normalizeBackendUrl(''), '');
  });

  it('trims leading and trailing whitespace', () => {
    assert.equal(normalizeBackendUrl('  http://localhost:8000  '), 'http://localhost:8000');
  });

  it('strips a single trailing slash', () => {
    assert.equal(normalizeBackendUrl('http://localhost:8000/'), 'http://localhost:8000');
  });

  it('does not strip more than one trailing slash', () => {
    // Only one trailing slash is removed per the spec
    assert.equal(normalizeBackendUrl('http://localhost:8000//'), 'http://localhost:8000/');
  });

  it('trims whitespace then strips trailing slash', () => {
    assert.equal(normalizeBackendUrl('  http://localhost:8000/  '), 'http://localhost:8000');
  });

  it('returns empty string for whitespace-only input', () => {
    assert.equal(normalizeBackendUrl('   '), '');
  });

  it('does not alter a URL with no trailing slash', () => {
    assert.equal(normalizeBackendUrl('http://example.com:9000'), 'http://example.com:9000');
  });
});

// ---------------------------------------------------------------------------
// cookie round-trip: setBackendUrl then getBackendUrl
// ---------------------------------------------------------------------------

describe('cookie round-trip', () => {
  beforeEach(() => {
    clearCookies();
    // Ensure COLLECTION_CONFIG fallback does not interfere
    window.COLLECTION_CONFIG = { BACKEND_URL: '' };
  });

  afterEach(() => {
    clearCookies();
  });

  it('setBackendUrl persists value; getBackendUrl reads it back', () => {
    setBackendUrl('http://192.168.1.10:8001');
    assert.equal(getBackendUrl(), 'http://192.168.1.10:8001');
  });

  it('setBackendUrl normalizes before writing (strips trailing slash)', () => {
    setBackendUrl('http://192.168.1.10:8001/');
    assert.equal(getBackendUrl(), 'http://192.168.1.10:8001');
  });

  it('setBackendUrl with empty string stores empty, getBackendUrl returns empty (same-origin)', () => {
    setBackendUrl('http://example.com');
    setBackendUrl('');
    assert.equal(getBackendUrl(), '');
  });

  it('URL-encodes special characters in the cookie value', () => {
    // The value should survive encode/decode round-trip
    const url = 'http://example.com:8000';
    setBackendUrl(url);
    assert.equal(getBackendUrl(), url);
  });
});

// ---------------------------------------------------------------------------
// default fallback when no cookie is set
// ---------------------------------------------------------------------------

describe('getBackendUrl fallback', () => {
  beforeEach(() => {
    clearCookies();
  });

  afterEach(() => {
    clearCookies();
    delete window.COLLECTION_CONFIG;
  });

  it('returns empty string when no cookie and no COLLECTION_CONFIG', () => {
    delete window.COLLECTION_CONFIG;
    assert.equal(getBackendUrl(), '');
  });

  it('returns COLLECTION_CONFIG.BACKEND_URL (normalized) when no cookie is set', () => {
    window.COLLECTION_CONFIG = { BACKEND_URL: 'http://fallback.local:8000/' };
    assert.equal(getBackendUrl(), 'http://fallback.local:8000');
  });

  it('returns empty string when COLLECTION_CONFIG.BACKEND_URL is empty', () => {
    window.COLLECTION_CONFIG = { BACKEND_URL: '' };
    assert.equal(getBackendUrl(), '');
  });

  it('cookie takes precedence over COLLECTION_CONFIG fallback', () => {
    window.COLLECTION_CONFIG = { BACKEND_URL: 'http://config-default.local' };
    setBackendUrl('http://cookie-value.local');
    assert.equal(getBackendUrl(), 'http://cookie-value.local');
  });
});

// ---------------------------------------------------------------------------
// backendLabel
// ---------------------------------------------------------------------------

describe('backendLabel', () => {
  it('returns "same-origin" for empty string', () => {
    assert.equal(backendLabel(''), 'same-origin');
  });

  it('returns the host portion of a full URL', () => {
    assert.equal(backendLabel('http://example.com'), 'example.com');
  });

  it('returns host:port when a non-standard port is present', () => {
    assert.equal(backendLabel('http://192.168.1.10:8001'), '192.168.1.10:8001');
  });

  it('falls back to the raw string for an unparseable URL', () => {
    const bad = 'not-a-valid-url';
    assert.equal(backendLabel(bad), bad);
  });
});

// ---------------------------------------------------------------------------
// onBackendUrlChange — fires on setBackendUrl, stops after unsubscribe
// ---------------------------------------------------------------------------

describe('onBackendUrlChange', () => {
  beforeEach(() => {
    clearCookies();
    window.COLLECTION_CONFIG = { BACKEND_URL: '' };
  });

  afterEach(() => {
    clearCookies();
  });

  it('fires the callback with the normalized URL when setBackendUrl is called', () => {
    const calls = [];
    const unsub = onBackendUrlChange((url) => calls.push(url));
    try {
      setBackendUrl('http://listener.local/');
      assert.equal(calls.length, 1);
      assert.equal(calls[0], 'http://listener.local');
    } finally {
      unsub();
    }
  });

  it('does not fire after unsubscribe', () => {
    const calls = [];
    const unsub = onBackendUrlChange((url) => calls.push(url));
    setBackendUrl('http://before.local');
    unsub();
    setBackendUrl('http://after.local');
    // Only the pre-unsub call should have fired
    assert.equal(calls.length, 1);
    assert.equal(calls[0], 'http://before.local');
  });

  it('multiple subscribers each receive the URL', () => {
    const a = [];
    const b = [];
    const unsubA = onBackendUrlChange((url) => a.push(url));
    const unsubB = onBackendUrlChange((url) => b.push(url));
    try {
      setBackendUrl('http://multi.local');
      assert.equal(a.length, 1);
      assert.equal(b.length, 1);
      assert.equal(a[0], 'http://multi.local');
      assert.equal(b[0], 'http://multi.local');
    } finally {
      unsubA();
      unsubB();
    }
  });

  it('unsubscribing one does not affect the other', () => {
    const a = [];
    const b = [];
    const unsubA = onBackendUrlChange((url) => a.push(url));
    const unsubB = onBackendUrlChange((url) => b.push(url));
    setBackendUrl('http://first.local');
    unsubA();
    setBackendUrl('http://second.local');
    unsubB();
    assert.equal(a.length, 1, 'a stopped receiving after unsubscribe');
    assert.equal(b.length, 2, 'b kept receiving until its unsubscribe');
  });
});
