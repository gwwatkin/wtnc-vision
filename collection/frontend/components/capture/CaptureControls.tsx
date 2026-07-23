/**
 * CaptureControls.tsx — Start/stop capture controls with inflight/frame counter.
 * Reflects the `recording` class app.js uses on the toggle button.
 *
 * @module components/capture/CaptureControls
 */

import type { CaptureControlsProps } from '../../types';

export function CaptureControls({ active, onStart, onStop, inflight, label, onLabel }: CaptureControlsProps) {
  const btnClass = active ? 'recording' : '';

  return (
    <div class="capture-controls">
      <div class="capture-controls__label-row">
        <label for="label-input">Run label:</label>
        <input
          id="label-input"
          type="text"
          value={label}
          onInput={(e: Event) => onLabel((e.target as HTMLInputElement).value)}
          placeholder="e.g. race-2024-01"
        />
      </div>
      <div class="capture-controls__buttons">
        <button
          id="toggle-btn"
          class={btnClass}
          onClick={active ? onStop : onStart}
        >
          {active ? 'Stop' : 'Start'}
        </button>
      </div>
      <div id="status" class="capture-controls__status">
        {active ? 'Recording' : 'Stopped'} — in-flight: {inflight}
      </div>
    </div>
  );
}
