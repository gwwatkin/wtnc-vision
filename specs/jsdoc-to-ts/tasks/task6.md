# task6 — Capture page components (Wave B)

**Model:** sonnet · **Depends on:** task1 (uses stubbed `api.ts`, `backend-url.ts`,
`types.ts`, and `BackendSettings` — rendered against its frozen empty props).
**Parallel with:** task2–task5, task7, task8.

Source of truth: `../design.md` §9, §10 + `tasks/README.md` FROZEN-1, FROZEN-2. All paths
under `collection/frontend/`.

## What you own (fill all five)

- `components/capture/CaptureApp.tsx`
- `components/capture/CameraPreview.tsx`
- `components/capture/CaptureControls.tsx`
- `components/capture/RosterUpload.tsx`
- `components/capture/SourceSelector.tsx`

## Steps

1. **Convert each to JSX (FROZEN-1).** For every file: delete the `preact-setup.js` import;
   hooks from `preact/hooks`; `import type { CaptureAppProps, CameraPreviewProps,
   CaptureControlsProps, RosterUploadProps, SourceSelectorProps } from '../../types'`;
   annotate params; `as` casts; `class=` and verbatim DOM attrs/handlers. Byte-for-byte DOM
   parity with the htm originals.

2. **Preserve capture behavior exactly.** `CameraPreview` owns `getUserMedia` in a
   `useEffect` keyed on its `active` prop and tears the stream down on `active=false`/unmount;
   `CaptureApp` owns recording/in-flight/source state and renders `<BackendSettings />`,
   `<SourceSelector />`, `<CameraPreview />`, `<CaptureControls />`, `<RosterUpload />`.
   Capture fetches go through `api.ts` (`checkHealth`, `postFrame`, `uploadRoster`) exactly
   as today. `CaptureApp`'s internal reducer/state shape is **not** frozen — keep it as the
   old file has it.

3. **JSX call-sites are now checked.** Because `<CameraPreview active={…} />` etc. are typed,
   a wrong prop fails `tsc`. Keep prop names byte-exact against `types.ts`.

## Definition of done

- `npm run typecheck` passes.
- Camera preview start/stop, video ingest, capture start/stop with in-flight/frame counters,
  and roster upload all preserve their behavior; DOM/classes are parity. (Live verification
  is task9's checklist — here, ensure the port is faithful and type-clean.)

## Do NOT

- Edit `api.ts`, `backend-url.ts`, `BackendSettings.tsx`, `types.ts`, `styles.css`, or any
  other task's files. Flag any missing CSS class to task9.
</content>
