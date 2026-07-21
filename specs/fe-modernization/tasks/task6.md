# task6 — Capture page: CaptureApp + children (Wave B)

**Model:** sonnet. **Depends on:** task1. Parity source: `app.js` (602 lines). Behaviors
to preserve are FROZEN-9 / requirements A4.

## Exclusive files (fill task1 stubs)
```
components/capture/CaptureApp.js       (replaces app.js)
components/capture/SourceSelector.js
components/capture/CameraPreview.js
components/capture/CaptureControls.js
components/capture/RosterUpload.js
```

## Do
1. **`CaptureApp`** — no props (reads `COLLECTION_CONFIG`). Owns a **local** `useReducer`
   (shape NOT frozen) for: source (`camera`|`video`, default `DEFAULT_SOURCE`), recording
   on/off, in-flight count (cap `MAX_IN_FLIGHT`), frame counter, roster status. Composes
   the four children. Drives the capture loop: grab frames at `CAPTURE_FPS`, encode via
   canvas `toBlob` at `JPEG_QUALITY` (downscale to `TARGET_WIDTH`), POST through
   `api.postFrame`, respecting backpressure (`MAX_IN_FLIGHT`). Health check via
   `api.checkHealth`. Preserve today's start/stop + counter behavior exactly (parity).
2. **`SourceSelector`** — `{ value, onChange }` — camera|video toggle.
3. **`CameraPreview`** — `{ active }`. **OQ-D3 (FROZEN-9): this component owns
   `getUserMedia`** in a `useEffect` keyed on `active` — acquire on `active=true`, stop all
   tracks + release on `active=false`/unmount. Renders the `<video>` preview (parity with
   today's `#preview`). Manages its own stream ref internally.
4. **`CaptureControls`** — `{ active, onStart, onStop, inflight, label, onLabel }` — the
   record toggle button (reflect `recording` class today uses), the run-label input, and
   the in-flight/frame counter readout.
5. **`RosterUpload`** — `{ onUpload, status }` — file input + button; calls
   `onUpload(file)` (which `CaptureApp` implements via `api.uploadRoster`) and shows
   `status`.

All server I/O goes through `api.js` (`checkHealth`, `postFrame`, `uploadRoster`) — no
direct `fetch`.

## Acceptance
- `npm run typecheck` passes. Capture flows (camera preview, video ingest, start/stop,
  counters, roster upload + status) reach parity with `app.js` — verified manually against
  a real camera/run in task9 (NFR6/SC3).
- No direct `fetch`; camera stream is released on stop/unmount (no leaked tracks).

## Do not
Touch `styles.css` (flag new classes to task9), `config.js`, `api.js`, or other tasks'
files.
