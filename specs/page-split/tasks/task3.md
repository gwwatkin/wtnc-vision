# task3 — `BackendSettings` component (Wave B)

**Model:** sonnet · Depends on task1 (`backend-url.js`, stub file).

Source of truth: `../design.md` (§5), `tasks/README.md` (FROZEN-1, FROZEN-4, FROZEN-6).
Run FE commands from `collection/frontend/`.

## Owns (exclusive)
- `collection/frontend/components/common/BackendSettings.js` (fill task1's stub)

## Do

Implement the shared collapsible settings + reachability indicator (props `{}` — FROZEN-6).
Import Preact hooks from `../../vendor/preact-setup.js`, `backend-url.js` functions, and
`api.checkHealth`.

**State (local):** `expanded` (bool, default `false` — collapsed per OQ1); `url` (string,
init `getBackendUrl()`); `draft` (string, the input value, init `url`); `health`
(`'checking' | 'ok' | 'bad'`).

**Effects:**
- Subscribe to `onBackendUrlChange` on mount; on fire, update `url` (and reset `draft` to it);
  unsubscribe on unmount.
- A `useEffect` keyed on `url`: set `health='checking'`, run `api.checkHealth()` →
  `'ok'`/`'bad'` (`.catch` → `'bad'`). This re-probes whenever the target changes.

**Render (FROZEN-4 classes):**
```
<div class="backend-settings">
  <div class="backend-settings__summary">
    <span class="backend-settings__dot backend-settings__dot--{ok|bad|checking}"></span>
    <span class="backend-settings__label">Back-end: ${backendLabel(url)}</span>
    <button class="backend-settings__toggle" onClick=toggle>{expanded ? '▾' : '▸'}</button>
  </div>
  ${expanded && html`
    <div class="backend-settings__panel">
      <input class="backend-settings__input" value=${draft}
             placeholder="same-origin (default)" onInput=…/>
      <button class="backend-settings__save" onClick=${() => setBackendUrl(draft)}>Save</button>
      <button class="backend-settings__default" onClick=${() => setBackendUrl('')}>Use default</button>
    </div>`}
</div>
```
- **Save / Use default** call `setBackendUrl(...)` — that writes the cookie and notifies
  subscribers; the mount subscription then refreshes `url` and the health effect re-runs. Do
  **not** reload the page (live re-apply, OQ2). Leaving the input blank and Saving is
  equivalent to same-origin.
- The dot's title/aria can describe the state (`reachable`/`unreachable`/`checking…`).

## Constraints
- No `styles.css` edits — use FROZEN-4 classes; if you need one not listed, **flag to task8**.
- Pure to the store/api seam: no direct `fetch`, no cookie parsing (use `backend-url.js`).

## Done when
- `npm run typecheck` green; component renders collapsed with a label + health dot and expands
  to the editor; Save/Use default persist via `backend-url.js` without a reload.
