/**
 * backend-url.ts — Cookie-backed runtime base-URL store.
 *
 * Single source of truth for the configurable back-end base URL.
 * Pure browser module — no framework import, no top-level side effects
 * beyond declaring the subscriber Set.
 *
 * FROZEN-1 surface (page-split spec, design §3):
 *   normalizeBackendUrl, getBackendUrl, setBackendUrl,
 *   onBackendUrlChange, backendLabel
 *
 * @module backend-url
 */

import type { CollectionConfig } from './types';

const COOKIE = 'wtnc_backend_url';

const DEFAULT = (): string =>
  (window as Window & { COLLECTION_CONFIG?: CollectionConfig })
    .COLLECTION_CONFIG?.BACKEND_URL ?? '';

const _subscribers = new Set<(url: string) => void>();

// ---------------------------------------------------------------------------
// Exports
// ---------------------------------------------------------------------------

/**
 * Normalize a raw URL string: trim whitespace, strip a single trailing '/'.
 * An empty result means same-origin.
 */
export function normalizeBackendUrl(raw: string | null | undefined): string {
  let s = String(raw ?? '').trim();
  if (s.endsWith('/')) s = s.slice(0, -1);
  return s;
}

/**
 * Return the current back-end base URL: the cookie value if present
 * (decoded + normalized), else the config default (normalised).
 */
export function getBackendUrl(): string {
  const cookie = _readCookie(COOKIE);
  if (cookie !== null) {
    return normalizeBackendUrl(decodeURIComponent(cookie));
  }
  return normalizeBackendUrl(DEFAULT());
}

/**
 * Persist the chosen URL to a cookie (path=/, ~1 year, SameSite=Lax) and
 * notify all subscribers. Passing '' clears the explicit override — the
 * empty cookie value resolves to same-origin on the next read.
 */
export function setBackendUrl(url: string): void {
  const v = normalizeBackendUrl(url);
  document.cookie =
    `${COOKIE}=${encodeURIComponent(v)}; path=/; max-age=31536000; SameSite=Lax`;
  for (const cb of _subscribers) cb(v);
}

/**
 * Subscribe to URL changes. Fires after every call to setBackendUrl.
 * Returns an unsubscribe function.
 */
export function onBackendUrlChange(cb: (url: string) => void): () => void {
  _subscribers.add(cb);
  return () => _subscribers.delete(cb);
}

/**
 * Human-readable label for the status line.
 *   '' → 'same-origin'
 *   else the URL's host[:port], or the raw string if unparseable.
 */
export function backendLabel(url: string): string {
  if (!url) return 'same-origin';
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Read a named cookie from document.cookie. Returns the raw (encoded) value
 * string if found, or null if the cookie is absent.
 */
function _readCookie(name: string): string | null {
  const prefix = name + '=';
  for (const part of document.cookie.split(';')) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return trimmed.slice(prefix.length);
    }
  }
  return null;
}
