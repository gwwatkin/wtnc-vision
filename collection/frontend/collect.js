/**
 * collect.js — Entry point for the collector page (collect.html).
 *
 * Mounts CaptureApp into #capture-root only.
 *
 * Load order: config.js (classic, synchronous) must set window.COLLECTION_CONFIG
 * before this module executes — guaranteed by the <script> ordering in collect.html.
 *
 * @module collect
 */

import { h, render } from './vendor/preact-setup.js';
import CaptureApp from './components/capture/CaptureApp.js';

render(h(CaptureApp, null), document.getElementById('capture-root'));
