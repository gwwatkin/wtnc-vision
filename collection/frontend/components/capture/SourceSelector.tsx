/**
 * SourceSelector.tsx — Camera / video source toggle.
 *
 * @module components/capture/SourceSelector
 */

import type { SourceSelectorProps } from '../../types';

export function SourceSelector({ value, onChange }: SourceSelectorProps) {
  return (
    <div class="source-selector">
      <label>
        <input
          type="radio"
          name="source"
          value="camera"
          checked={value === 'camera'}
          onChange={(e: Event) => onChange((e.target as HTMLInputElement).value)}
        />
        Camera
      </label>
      <label>
        <input
          type="radio"
          name="source"
          value="video"
          checked={value === 'video'}
          onChange={(e: Event) => onChange((e.target as HTMLInputElement).value)}
        />
        Video file
      </label>
    </div>
  );
}
