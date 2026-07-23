/**
 * vitest.setup.ts — Global test setup.
 *
 * OQ-D2 spike result: Vitest's `environment: 'happy-dom'` (configured in
 * vite.config.ts) already provides document/window/customElements globally
 * before any test module loads — the manual Window install from setup-dom.js
 * is unnecessary. This file is therefore empty (but kept in setupFiles so
 * future residue can be added here if needed).
 */
