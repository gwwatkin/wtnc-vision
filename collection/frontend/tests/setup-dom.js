// @ts-nocheck
// tests/setup-dom.js — preloaded via --import, runs before any test module.
// happy-dom globals must exist before Preact's module graph evaluates because
// import statements are hoisted and run before any top-level assignment.
import { Window } from 'happy-dom';

const win = new Window();
globalThis.window = win;
globalThis.document = win.document;
globalThis.customElements = win.customElements;
