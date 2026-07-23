/**
 * collect.tsx — Capture page entry point.
 *
 * @module collect
 */

import { render } from 'preact';
import { CaptureApp } from './components/capture/CaptureApp';

render(<CaptureApp />, document.getElementById('capture-root')!);
