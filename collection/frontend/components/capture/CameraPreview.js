/**
 * CameraPreview.js — Live camera preview.
 * OQ-D3 (FROZEN-9): owns getUserMedia in a useEffect keyed on `active`.
 * Acquires the stream on active=true, stops all tracks on active=false or unmount.
 *
 * @module components/capture/CameraPreview
 */

import { html, useEffect, useRef } from '../../vendor/preact-setup.js';

/**
 * @param {import('../../types').CameraPreviewProps} props
 * @returns {any}
 */
export function CameraPreview({ active }) {
  const videoRef = useRef(/** @type {HTMLVideoElement | null} */ (null));

  const streamRef = useRef(/** @type {MediaStream | null} */ (null));

  useEffect(() => {
    if (!active) {
      // Release stream on active=false.
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((/** @type {MediaStreamTrack} */ t) => t.stop());
        streamRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
      return;
    }

    // active=true — acquire camera stream.
    let cancelled = false;

    async function acquire() {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        return;
      }

      let stream;
      try {
        // Initial permission call (unlocks device labels); then re-acquire on
        // first device found. Mirrors app.js initCamera pattern.
        const tempStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
        tempStream.getTracks().forEach((/** @type {MediaStreamTrack} */ t) => t.stop());

        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoInputs = devices.filter(d => d.kind === 'videoinput');
        const deviceId = videoInputs.length > 0 ? videoInputs[0].deviceId : undefined;

        const constraints = {
          video: deviceId ? { deviceId: { exact: deviceId } } : true,
          audio: false,
        };
        stream = await navigator.mediaDevices.getUserMedia(constraints);
      } catch (_err) {
        return;
      }

      if (cancelled) {
        stream.getTracks().forEach((/** @type {MediaStreamTrack} */ t) => t.stop());
        return;
      }

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.autoplay = true;
        videoRef.current.muted = true;
      }
    }

    acquire();

    return () => {
      cancelled = true;
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((/** @type {MediaStreamTrack} */ t) => t.stop());
        streamRef.current = null;
      }
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    };
  }, [active]);

  return html`
    <video
      id="preview"
      ref=${videoRef}
      autoplay
      muted
      playsinline
    ></video>
  `;
}
