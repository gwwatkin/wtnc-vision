/**
 * RosterUpload.tsx — CSV roster upload with status display.
 *
 * @module components/capture/RosterUpload
 */

import { useRef } from 'preact/hooks';
import type { RosterUploadProps } from '../../types';

export function RosterUpload({ onUpload, status }: RosterUploadProps) {
  const fileRef = useRef<HTMLInputElement | null>(null);

  function handleUpload() {
    const file = fileRef.current && fileRef.current.files && fileRef.current.files[0];
    if (!file) return;
    onUpload(file);
  }

  return (
    <div class="roster-upload">
      <input
        id="roster-file"
        type="file"
        accept=".csv"
        ref={fileRef}
      />
      <button
        id="roster-upload-btn"
        onClick={handleUpload}
      >
        Upload roster
      </button>
      <span id="roster-status">{status || ''}</span>
    </div>
  );
}
