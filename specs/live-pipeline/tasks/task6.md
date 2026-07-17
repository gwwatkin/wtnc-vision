# Task 6 — Front-end capture: source selector, video ingest, roster upload

**Agent:** sonnet  **Depends on:** task1  **Blocks:** task7
**Runs in parallel with:** tasks 2, 3, 4, 5 (disjoint files)

## Objective
Extend the capture page's behavior: a pixel-source abstraction so frames come from the
live camera **or** a supplied video file through the same canvas→JPEG→`POST /frames`
path, and a roster-upload control posting to `POST /roster`. The capture loop's
transport, backpressure, and status behavior stay as they are.

## Read first
`../requirements.md` FR4a, FR16–FR20 (upload UX side), D7; `../design.md` §8 (source
selector + roster upload — your blueprint), §4 (`POST /roster` request shape, and the
201 `run` field on `/frames`); `README.md` here (DOM contract — you own the behavior of
`#source-select`, `#video-file`, `#roster-file`, `#roster-upload-btn`, `#roster-status`;
`BACKEND_URL` is now `""` = same-origin). Current `collection/frontend/app.js`.

## Files you own
```
collection/frontend/app.js   # all behavior below
```
Do **not** touch `index.html`/`config.js`/`styles.css` (task1's frozen shell — the
elements you need already exist with the contract ids), `results/*.js` (task5), or the
back-end. If a needed element is missing from the shell, **stop and flag it**.

## Implement — source abstraction (D7 / FR4a)

- `#source-select` (`camera` | `video`, initial value from
  `COLLECTION_CONFIG.DEFAULT_SOURCE`):
  - **camera** — today's path, unchanged: `getUserMedia` → `preview.srcObject`;
    `#camera-select` enabled; `#video-file` hidden/disabled.
  - **video** — `#video-file` visible; on file choose, `preview.srcObject = null` and
    `preview.src = URL.createObjectURL(file)` (revoke the previous URL); `preview`
    muted, no autoplay. `#camera-select` disabled. Switching source never requires a
    back-end restart (it's all client-side) and stops any active recording first.
- **Start/stop** — Start with source=video requires a chosen file (else status message);
  it records `videoStartWallclock = Date.now()`, calls `preview.play()`, and runs the
  **same** capture timer; Stop pauses the video. The video's `ended` event auto-stops
  recording (status line says so). `captureTick` is source-agnostic: it draws `preview`
  to the canvas exactly as today (guard `preview.readyState`/`videoWidth` so early
  ticks skip cleanly).
- **`client_ts`** — camera: wall-clock now (unchanged). Video:
  `new Date(videoStartWallclock + preview.currentTime * 1000).toISOString()` so frames
  spread across the timeline (design §8, A1).
- All fetches are relative (`${BACKEND_URL}/frames` with `BACKEND_URL === ""`), so no
  code besides the config value should assume a host. Label/seq/session/backpressure
  (`MAX_IN_FLIGHT`) logic unchanged.

## Implement — roster upload (FR16–FR19 UX)

- `#roster-upload-btn`: requires a non-blank `#label-input` (the run — README DOM
  contract) and a chosen `#roster-file`; posts `FormData` fields `run` = raw label,
  `roster` = the file, to `/roster`.
- On 200 → `#roster-status`: `Roster set for <run>: N riders` (use the echoed safe
  `run`). On 400/503 → show the response `detail`. Network error → generic failure
  message. Never blocks or interferes with an active recording (it's one fetch).

## Acceptance criteria
Verify in a real browser against the task1 back-end (engine may still be stubbed —
that's fine, you only need `/frames` 201s and `/roster` responses; for `/roster`, a 400
on garbage and the disabled-mode 503 are also fine to demonstrate):
- Camera path: behaves exactly as before (record, status counts, stop).
- Video path: choose a short clip (record one with any device), Start → frames POST at
  `CAPTURE_FPS` with monotonically increasing `client_ts` derived from video time
  (verify in the network tab), recording auto-stops at `ended`.
- Switching source mid-recording stops cleanly; switching back to camera restores the
  live preview.
- Roster upload: happy path shows the count + safe run id; a garbage file shows the
  server's rejection message; blank label is caught client-side.
- No console errors; no changes visible in the timeline area (task5's territory).

## Out of scope
Timeline/sidebar (task5), back-end roster parsing (task4), storage (task3), engine
(task2).

## Final report to include
Confirm acceptance criteria (name the clip you tested with); describe the source-switching
state machine briefly (states + what Start/Stop do in each); flag any DOM-contract gap
you hit rather than editing the shell.
