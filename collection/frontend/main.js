/**
 * main.js — Entry point: mounts both Preact roots.
 *
 * Uses h(Component, null) directly (not htm) so tsc can check the mount
 * call-site prop types (design §9 htm blind-spot note).
 *
 * Load order: config.js (classic, synchronous) must set window.COLLECTION_CONFIG
 * before this module executes — guaranteed by the <script> ordering in index.html.
 *
 * @module main
 */

import { h, render } from './vendor/preact-setup.js';
import CaptureApp from './components/capture/CaptureApp.js';
import ResultsApp from './components/results/ResultsApp.js';

render(h(CaptureApp, null), document.getElementById('capture-root'));
render(h(ResultsApp, null), document.getElementById('results-root'));
