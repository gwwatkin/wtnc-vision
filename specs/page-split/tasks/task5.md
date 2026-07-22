# task5 — `CaptureApp` integration: settings + status target (Wave B)

**Model:** sonnet · Depends on task1 (`backend-url.js`, `BackendSettings` stub).

Source of truth: `../design.md` (§5), `tasks/README.md` (FROZEN-1, FROZEN-6). Codes against
`BackendSettings`'s frozen `{}` props, not its implementation (task3). Run FE commands from
`collection/frontend/`.

## Owns (exclusive)
- `collection/frontend/components/capture/CaptureApp.js`

## Do (additive edits — preserve all existing capture behavior, FR16/parity)

1. Import `{ BackendSettings }` from `../common/BackendSettings.js` and
   `{ getBackendUrl, backendLabel, onBackendUrlChange }` from `../../backend-url.js`.
2. **Render** `<${BackendSettings} />` at the **top** of the returned tree (above
   `SourceSelector`), inside `.capture-app`.
3. **Status line shows the target (OQ2/OQ4).** Keep the existing sent/dropped/last status
   text; append the active back-end. Track it in state or a small `useState` seeded from
   `getBackendUrl()` and updated via an `onBackendUrlChange` subscription (unsubscribe on
   unmount). Final line, e.g.:
   ```
   Recording — sent: 12  dropped: 0  last: ok  ·  back-end: same-origin
   ```
   Use `backendLabel(currentUrl)`.
4. **React to a target change:** in the same subscription, if a recording is active, call
   `stopRecording()` (the upload target moved) and re-run the mount health check
   (`api.checkHealth()` → dispatch `HEALTH_RESULT`). Keep it minimal; do not otherwise alter
   the capture loop.

## Constraints
- No `styles.css` edits (BackendSettings brings its own FROZEN-4 classes). The capture
  reducer/loop stay as-is except the small subscription above.
- All back-end calls already go through `api.js` (task2) — do not add direct `fetch`.

## Done when
- `npm run typecheck` green. Collector renders the settings panel; the status line names the
  active back-end and updates live when it changes; capture from camera and video still works.
