# followup_1 — Restore the provenance badges (manual / edited / moved)

**Model:** sonnet. **Depends on:** fe-modernization shipped (task9). **Runs parallel with**
followup_2 and followup_3 — see *Exclusive files* (no overlap).

## Problem
On the results timeline the provenance badges — **✚ manual**, **✎ edited**, **↕ moved** —
no longer appear on cards, a parity regression against the legacy UI (FROZEN-3 in
`tasks/README.md`; legacy reference was `results/render.js`).

The obvious pieces are all present, so this is a runtime bug, not a missing feature:
- `components/results/Card.js:49–51` renders each badge as `${cond && html\`<span …>\`}`.
- `results/data.js:116–119` maps the source fields (`source`, `edited`,
  `order_overridden → orderOverridden`).
- `styles.css:448–487` defines `.badge`, `.badge--manual/edited/moved`.

## Investigate
Reproduce with data that actually sets the flags — a manually-added crossing
(`source === "manual"`), an edited number (`edited === true`), and a reordered crossing
(`orderOverridden === true`, i.e. after followup work / the reorder action). Then find why
the spans don't render/show. Likely suspects, in order:
1. **htm boolean-expression rendering.** Confirm `${cond && html\`…\`}` inside the outer
   `` html`…` `` actually emits the vnode when `cond` is truthy (vs. rendering `false`/text).
   If htm mishandles the inline `&&`, switch to a ternary (`cond ? html\`…\` : null`) or hoist
   the badges into an array built before the `return`.
2. **Field survival.** Verify `crossing.source/edited/orderOverridden` are still truthy on
   the object Card receives (log the prop) — i.e. `resultsFromCrossings` output survives
   `sortByOrder`/`groupIntoPacks` unchanged. `data.js` is FROZEN — do **not** edit it; if the
   data is genuinely wrong, **stop and flag** it.
3. **Visibility.** Rule out a CSS/layout cause (badge rendered but clipped/hidden by the
   `.card` grid). If a real style fix is needed it belongs to followup_2 (owner of
   `styles.css`) — flag it there rather than editing `styles.css` here.

## Do
1. Fix the render so all three badges appear, in order (manual, edited, moved), matching
   FROZEN-3 exactly (classes, glyphs, text). Keep Card presentational — no data-* wiring.
2. While in this file, tighten its `@type {any}` casts (see followup_3 for the standard):
   `Card.js` currently launders `crossing`/`candidate` through `any` — annotate against the
   real `Result` / `CandidateResult` typedefs instead where the compiler allows.
3. Add a component test `tests/card-badges.test.js` (happy-dom, same harness as
   `tests/timeline.test.js`) asserting: a `manual` crossing renders `.badge--manual`; an
   `edited` one renders `.badge--edited`; an `orderOverridden` one renders `.badge--moved`;
   a plain auto crossing renders none.

## Exclusive / owned files
```
components/results/Card.js        ← MODIFIED
tests/card-badges.test.js         ← NEW
```
Do **not** touch `results/data.js` (FROZEN), `styles.css` (followup_2), or any other
component.

## Acceptance
- `npm run check` green (typecheck + all tests, including the new one).
- Manually verified: manual/edited/moved crossings show their badges on the timeline.
