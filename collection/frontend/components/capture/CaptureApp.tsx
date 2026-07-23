/**
 * CaptureApp.tsx — Root Preact component for the capture page.
 * Self-contained via COLLECTION_CONFIG; no props.
 *
 * Owns a local useReducer for:
 *   - source: 'camera' | 'video'
 *   - recording: boolean
 *   - inFlight: number (capped at MAX_IN_FLIGHT)
 *   - frameCount: number (sent frames in current session)
 *   - droppedCount: number
 *   - lastResult: string
 *   - rosterStatus: string | null
 *   - videoFile: File | null  (chosen video file)
 *   - statusMsg: string | null  (override message, e.g. video ended)
 *   - label: string
 *
 * Drives the capture loop: grab frames at CAPTURE_FPS, encode via canvas
 * toBlob at JPEG_QUALITY (downscaled to TARGET_WIDTH), POST through api.postFrame,
 * respecting backpressure (MAX_IN_FLIGHT). Health check via api.checkHealth.
 *
 * @module components/capture/CaptureApp
 */

import { useReducer, useEffect, useRef, useCallback, useState } from 'preact/hooks';
import { SourceSelector } from './SourceSelector';
import { CameraPreview } from './CameraPreview';
import { CaptureControls } from './CaptureControls';
import { RosterUpload } from './RosterUpload';
import * as api from '../../api';
import { BackendSettings } from '../common/BackendSettings';
import { getBackendUrl, backendLabel, onBackendUrlChange } from '../../backend-url';
import type { CaptureAppProps, CollectionConfig, PostFrameResult } from '../../types';

// ---------------------------------------------------------------------------
// Config — read once from the frozen window object
// ---------------------------------------------------------------------------
const cfg = ((window as unknown) as { COLLECTION_CONFIG?: CollectionConfig }).COLLECTION_CONFIG ?? {};
const CAPTURE_FPS    = cfg.CAPTURE_FPS    ?? 5;
const JPEG_QUALITY   = cfg.JPEG_QUALITY   ?? 0.7;
const TARGET_WIDTH   = cfg.TARGET_WIDTH   ?? 0;
const MAX_IN_FLIGHT  = cfg.MAX_IN_FLIGHT  ?? 4;
const DEFAULT_SOURCE = cfg.DEFAULT_SOURCE ?? 'camera';

const FRAME_INTERVAL_MS = 1000 / CAPTURE_FPS;

// ---------------------------------------------------------------------------
// Reducer types
// ---------------------------------------------------------------------------

interface CaptureState {
  source: string;
  recording: boolean;
  inFlight: number;
  frameCount: number;
  droppedCount: number;
  lastResult: string;
  rosterStatus: string | null;
  videoFile: File | null;
  statusMsg: string | null;
  label: string;
}

type CaptureAction =
  | { type: 'SET_SOURCE'; source: string }
  | { type: 'SET_LABEL'; label: string }
  | { type: 'START_RECORDING' }
  | { type: 'STOP_RECORDING' }
  | { type: 'INFLIGHT_INC' }
  | { type: 'INFLIGHT_DEC' }
  | { type: 'FRAME_DROPPED' }
  | { type: 'FRAME_SENT'; result: string }
  | { type: 'FRAME_ERROR'; result: string }
  | { type: 'SET_ROSTER_STATUS'; status: string | null }
  | { type: 'SET_VIDEO_FILE'; file: File | null }
  | { type: 'SET_STATUS_MSG'; msg: string | null }
  | { type: 'HEALTH_RESULT'; result: string };

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

const initialState: CaptureState = {
  source:       DEFAULT_SOURCE || 'camera',
  recording:    false,
  inFlight:     0,
  frameCount:   0,
  droppedCount: 0,
  lastResult:   'none',
  rosterStatus: null,
  videoFile:    null,
  statusMsg:    null,
  label:        '',
};

function reducer(state: CaptureState, action: CaptureAction): CaptureState {
  switch (action.type) {
    case 'SET_SOURCE':
      return { ...state, source: action.source, recording: false, statusMsg: null };
    case 'SET_LABEL':
      return { ...state, label: action.label };
    case 'START_RECORDING':
      return { ...state, recording: true, frameCount: 0, droppedCount: 0, lastResult: 'none', statusMsg: null };
    case 'STOP_RECORDING':
      return { ...state, recording: false };
    case 'INFLIGHT_INC':
      return { ...state, inFlight: state.inFlight + 1 };
    case 'INFLIGHT_DEC':
      return { ...state, inFlight: Math.max(0, state.inFlight - 1) };
    case 'FRAME_DROPPED':
      return { ...state, droppedCount: state.droppedCount + 1 };
    case 'FRAME_SENT':
      return { ...state, frameCount: state.frameCount + 1, lastResult: action.result };
    case 'FRAME_ERROR':
      return { ...state, lastResult: action.result };
    case 'SET_ROSTER_STATUS':
      return { ...state, rosterStatus: action.status };
    case 'SET_VIDEO_FILE':
      return { ...state, videoFile: action.file, statusMsg: action.file ? `Video file selected: ${action.file.name}` : null };
    case 'SET_STATUS_MSG':
      return { ...state, statusMsg: action.msg };
    case 'HEALTH_RESULT':
      return { ...state, lastResult: action.result };
    default:
      return state;
  }
}

// ---------------------------------------------------------------------------
// CaptureApp
// ---------------------------------------------------------------------------

export function CaptureApp(_props: CaptureAppProps) {
  const [state, dispatch] = useReducer(reducer, initialState);

  // Track the active back-end URL so the status line stays live (OQ2/OQ4).
  const [currentUrl, setCurrentUrl] = useState(() => getBackendUrl());

  // Offscreen canvas — reused every tick to avoid GC pressure.
  const canvasRef  = useRef<HTMLCanvasElement | null>(null);
  const ctxRef     = useRef<CanvasRenderingContext2D | null>(null);

  // video element ref (shared between preview and capture loop)
  const videoRef   = useRef<HTMLVideoElement | null>(null);

  // Interval handle
  const timerRef   = useRef<number | null>(null);

  // Session state (mutable refs, not state, to avoid stale closures in tick)
  const sessionIdRef      = useRef<string | null>(null);
  const seqRef            = useRef(0);
  const inFlightRef       = useRef(0);
  const recordingRef      = useRef(false);
  const sourceRef         = useRef(state.source);
  const labelRef          = useRef(state.label);

  // Video source state (mutable refs)
  const videoObjectUrlRef      = useRef<string | null>(null);
  const videoStartWallclockRef = useRef<number | null>(null);

  // Keep refs in sync with state so tick closure always sees fresh values
  useEffect(() => { sourceRef.current = state.source; }, [state.source]);
  useEffect(() => { labelRef.current  = state.label;  }, [state.label]);
  useEffect(() => { recordingRef.current = state.recording; }, [state.recording]);

  // Initialise canvas once
  useEffect(() => {
    const c = document.createElement('canvas');
    canvasRef.current = c;
    ctxRef.current    = c.getContext('2d');
  }, []);

  // Health check on mount
  useEffect(() => {
    api.checkHealth().then(ok => {
      dispatch({ type: 'HEALTH_RESULT', result: ok ? 'backend ok' : 'backend unhealthy' });
    }).catch(() => {
      dispatch({ type: 'HEALTH_RESULT', result: 'backend unreachable' });
    });
  }, []);

  // Subscribe to back-end URL changes: update status label, stop any active
  // recording (upload target moved), and re-run the health check (OQ2/OQ4).
  useEffect(() => {
    const unsub = onBackendUrlChange((newUrl) => {
      setCurrentUrl(newUrl);
      if (timerRef.current !== null) {
        stopRecording();
      }
      api.checkHealth().then(ok => {
        dispatch({ type: 'HEALTH_RESULT', result: ok ? 'backend ok' : 'backend unhealthy' });
      }).catch(() => {
        dispatch({ type: 'HEALTH_RESULT', result: 'backend unreachable' });
      });
    });
    return unsub;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ------------------------------------------------------------------
  // Source-aware client_ts
  // ------------------------------------------------------------------
  function currentClientTs() {
    if (sourceRef.current === 'video' && videoStartWallclockRef.current !== null) {
      const videoEl = videoRef.current;
      if (videoEl) {
        return new Date(videoStartWallclockRef.current + videoEl.currentTime * 1000).toISOString();
      }
    }
    return new Date().toISOString();
  }

  // ------------------------------------------------------------------
  // sendFrame — isolated error handling; failure never stops the loop (FR7)
  // ------------------------------------------------------------------
  const sendFrame = useCallback(
    async (blob: Blob, label: string, clientTs: string, frameSeq: number, sid: string | null) => {
      inFlightRef.current++;
      dispatch({ type: 'INFLIGHT_INC' });

      try {
        const result = await api.postFrame({
          image:      blob,
          label,
          client_ts:  clientTs,
          seq:        frameSeq,
          session_id: sid ?? undefined,
        });
        const json = result as PostFrameResult;
        let detail = 'ok';
        if (json && json.stored) detail += ' ' + json.stored;
        if (json && json.run)    detail += ' [' + json.run + ']';
        dispatch({ type: 'FRAME_SENT', result: detail });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        dispatch({ type: 'FRAME_ERROR', result: 'send failed: ' + msg });
      } finally {
        inFlightRef.current--;
        dispatch({ type: 'INFLIGHT_DEC' });
      }
    },
    []
  );

  // ------------------------------------------------------------------
  // Capture tick
  // ------------------------------------------------------------------
  const captureTick = useCallback(() => {
    if (!recordingRef.current) return;

    // Backpressure: drop this frame if too many are in flight.
    if (inFlightRef.current >= MAX_IN_FLIGHT) {
      dispatch({ type: 'FRAME_DROPPED' });
      return;
    }

    const videoEl = videoRef.current;
    if (!videoEl) return;

    const source = sourceRef.current;
    const hasData =
      source === 'camera'
        ? (videoEl.srcObject !== null && videoEl.readyState >= videoEl.HAVE_CURRENT_DATA)
        : (videoEl.src !== '' && videoEl.readyState >= videoEl.HAVE_CURRENT_DATA);

    if (!hasData) return;

    const vw = videoEl.videoWidth;
    const vh = videoEl.videoHeight;
    if (!vw || !vh) return;

    const canvas = canvasRef.current;
    const ctx    = ctxRef.current;
    if (!canvas || !ctx) return;

    let drawW = vw;
    let drawH = vh;
    if (TARGET_WIDTH > 0 && vw > TARGET_WIDTH) {
      drawW = TARGET_WIDTH;
      drawH = Math.round(vh * (TARGET_WIDTH / vw));
    }

    canvas.width  = drawW;
    canvas.height = drawH;
    ctx.drawImage(videoEl, 0, 0, drawW, drawH);

    const captureLabel   = labelRef.current;
    const clientTs       = currentClientTs();
    const captureSeq     = seqRef.current++;
    const captureSession = sessionIdRef.current;

    canvas.toBlob((blob: Blob | null) => {
      if (!blob) return;
      sendFrame(blob, captureLabel, clientTs, captureSeq, captureSession);
    }, 'image/jpeg', JPEG_QUALITY);
  }, [sendFrame]);

  // ------------------------------------------------------------------
  // Video ended handler (auto-stop)
  // ------------------------------------------------------------------
  const onVideoEnded = useCallback(() => {
    if (recordingRef.current) {
      stopRecording();
      dispatch({ type: 'SET_STATUS_MSG', msg: 'Video ended — recording stopped automatically.' });
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ------------------------------------------------------------------
  // Start / Stop
  // ------------------------------------------------------------------
  function startRecording() {
    if (timerRef.current !== null) return;

    if (state.source === 'video') {
      if (!videoObjectUrlRef.current) {
        dispatch({ type: 'SET_STATUS_MSG', msg: 'Choose a video file before starting.' });
        return;
      }
      videoStartWallclockRef.current = Date.now();
      const videoEl = videoRef.current;
      if (videoEl) {
        videoEl.removeEventListener('ended', onVideoEnded);
        videoEl.addEventListener('ended', onVideoEnded, { once: true });
        videoEl.play().catch((err: unknown) => {
          dispatch({ type: 'SET_STATUS_MSG', msg: 'Could not play video: ' + (err instanceof Error ? err.message : String(err)) });
        });
      }
    }

    sessionIdRef.current = crypto.randomUUID();
    seqRef.current       = 0;
    inFlightRef.current  = 0;

    dispatch({ type: 'START_RECORDING' });
    recordingRef.current = true;

    // @types/node overrides setInterval to Timeout; cast through unknown to get browser number.
    timerRef.current = (setInterval(captureTick, FRAME_INTERVAL_MS) as unknown) as number;
  }

  function stopRecording() {
    if (timerRef.current === null) return;

    clearInterval(timerRef.current);
    timerRef.current = null;

    if (state.source === 'video') {
      const videoEl = videoRef.current;
      if (videoEl) {
        videoEl.pause();
        videoEl.removeEventListener('ended', onVideoEnded);
      }
      videoStartWallclockRef.current = null;
    }

    dispatch({ type: 'STOP_RECORDING' });
    recordingRef.current = false;
  }

  // ------------------------------------------------------------------
  // Source switch
  // ------------------------------------------------------------------
  function handleSourceChange(newSource: string) {
    if (newSource === state.source) return;

    // Stop recording before switching.
    if (timerRef.current !== null) {
      stopRecording();
    }

    if (newSource === 'video') {
      // Release video object URL when going back to camera later;
      // keep it if we already have one for the video source.
    }

    dispatch({ type: 'SET_SOURCE', source: newSource });
  }

  // ------------------------------------------------------------------
  // Video file selection (fed from a file input rendered by CaptureApp
  // since CameraPreview only shows for camera source)
  // ------------------------------------------------------------------
  function handleVideoFileChange(e: Event) {
    const input = e.target as HTMLInputElement;
    const file  = input.files && input.files[0];
    if (!file) return;

    // Revoke previous URL.
    if (videoObjectUrlRef.current) {
      URL.revokeObjectURL(videoObjectUrlRef.current);
      videoObjectUrlRef.current = null;
    }

    // Stop any active recording before replacing the source.
    if (timerRef.current !== null) {
      stopRecording();
    }

    const url = URL.createObjectURL(file);
    videoObjectUrlRef.current = url;

    const videoEl = videoRef.current;
    if (videoEl) {
      videoEl.removeEventListener('ended', onVideoEnded);
      videoEl.srcObject = null;
      videoEl.src       = url;
      videoEl.muted     = true;
      videoEl.autoplay  = false;
    }

    dispatch({ type: 'SET_VIDEO_FILE', file });
  }

  // ------------------------------------------------------------------
  // Roster upload
  // ------------------------------------------------------------------
  const handleRosterUpload = useCallback(
    async (file: File) => {
      const run = labelRef.current.trim();
      if (!run) {
        dispatch({ type: 'SET_ROSTER_STATUS', status: 'Enter a label/run name before uploading a roster.' });
        return;
      }
      dispatch({ type: 'SET_ROSTER_STATUS', status: 'Uploading…' });
      try {
        await api.uploadRoster(run, file);
        dispatch({ type: 'SET_ROSTER_STATUS', status: `Roster uploaded for run: ${run}` });
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        dispatch({ type: 'SET_ROSTER_STATUS', status: `Roster upload failed: ${msg}` });
      }
    },
    []
  );

  // ------------------------------------------------------------------
  // Status text (mirrors app.js renderStatus / setStatusMsg behaviour)
  // ------------------------------------------------------------------
  const statusText = (() => {
    if (state.statusMsg) return state.statusMsg;
    const recordingWord = state.recording ? 'Recording' : 'Stopped';
    return `${recordingWord} — sent: ${state.frameCount}  dropped: ${state.droppedCount}  last: ${state.lastResult}  ·  back-end: ${backendLabel(currentUrl)}`;
  })();

  const isCameraSource = state.source === 'camera';

  return (
    <div class="capture-app">
      <BackendSettings />

      <SourceSelector
        value={state.source}
        onChange={handleSourceChange}
      />

      {isCameraSource
        ? <CameraPreview active={!state.recording ? true : true} />
        : (
            <div class="video-source-controls">
              <input
                id="video-file"
                type="file"
                accept="video/*"
                onChange={handleVideoFileChange}
              />
              <video
                id="preview"
                ref={videoRef}
                muted
                playsinline
              ></video>
            </div>
          )
      }

      <CaptureControls
        active={state.recording}
        onStart={startRecording}
        onStop={stopRecording}
        inflight={state.inFlight}
        label={state.label}
        onLabel={(v: string) => dispatch({ type: 'SET_LABEL', label: v })}
      />

      <RosterUpload
        onUpload={handleRosterUpload}
        status={state.rosterStatus}
      />

      <p id="status">{statusText}</p>
    </div>
  );
}
