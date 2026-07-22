# Tasks — FE Modernization (Toolchain, Tests, Preact)

The map for the parallel-agent run. **Read this before spawning any agent.** Source of
truth is `../requirements.md` + `../design.md`; This file defines 3 parallel follwups for sonnet agents to perform now that the implementation tasks are complete


## Post-ship follow-ups (parallel-safe, disjoint file ownership)

Surfaced during final review, after task1–task9 landed. Each is self-contained and can be
delegated to a sonnet agent. File ownership is **disjoint** so all three can run at once;
the only shared file is `types.d.ts` (coordination note in followup_2/followup_3).

| Task | Fixes | Owns |
|------|-------|------|
| `followup_1.md` | Provenance badges (✚ manual / ✎ edited / ↕ moved) not rendering | `Card.js`, `tests/card-badges.test.js` |
| `followup_2.md` | No way to open the frame browser when a run has no crossings — add a toolbar "Browse frames" button | `ResultsApp.js`, `Timeline.js`*, `styles.css`, `types.d.ts`* |
| `followup_3.md` | Tighten avoidable `@type {any}` casts across the remaining FE files | `Sidebar.js`, `FrameBrowser.js`, `StatusBar.js`, `CaptureApp.js`, `api.js`, `tests/state.test.js`, `types.d.ts`* |

\* conditional/additive — see each task's *Coordination note*. Recommended order if merge
conflicts matter: followup_2 → followup_3; followup_1 is fully independent. followup_1 and
followup_2 each also tighten the `any` casts in the files they already own, so followup_3
covers only the rest.