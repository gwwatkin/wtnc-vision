/**
 * backend-url.ts — Cookie-backed runtime base-URL store.
 * STUB: task7 fills the real implementation.
 *
 * FROZEN-1 surface (page-split spec, design §3):
 *   normalizeBackendUrl, getBackendUrl, setBackendUrl,
 *   onBackendUrlChange, backendLabel
 *
 * @module backend-url
 */

export function normalizeBackendUrl(raw: string | null | undefined): string {
  throw new Error('stub: normalizeBackendUrl');
}

export function getBackendUrl(): string {
  throw new Error('stub: getBackendUrl');
}

export function setBackendUrl(url: string): void {
  throw new Error('stub: setBackendUrl');
}

export function onBackendUrlChange(cb: (url: string) => void): () => void {
  throw new Error('stub: onBackendUrlChange');
}

export function backendLabel(url: string): string {
  throw new Error('stub: backendLabel');
}
