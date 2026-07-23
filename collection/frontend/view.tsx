/**
 * view.tsx — Results page entry point.
 *
 * @module view
 */

import { render } from 'preact';
import { ResultsApp } from './components/results/ResultsApp';

render(<ResultsApp />, document.getElementById('results-root')!);
