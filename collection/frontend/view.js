/**
 * view.js — Entry point for the viewer page (view.html).
 *
 * Mounts ResultsApp into #results-root only.
 *
 * Load order: config.js (classic, synchronous) must set window.COLLECTION_CONFIG
 * before this module executes — guaranteed by the <script> ordering in view.html.
 *
 * @module view
 */

import { h, render } from './vendor/preact-setup.js';
import ResultsApp from './components/results/ResultsApp.js';

render(h(ResultsApp, null), document.getElementById('results-root'));
