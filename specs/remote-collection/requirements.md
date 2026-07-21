# Requirements — Remote Collection (Multi-Device Roles)

## 1. Background & Purpose

Today the whole system runs on **one laptop**: the browser front-end is served by the
back-end at `http://localhost:8000` (same-origin), captures frames with `getUserMedia`,
and POSTs them to `/frames` where the CV pipeline processes them and the results UI shows
crossings (`specs/completed/collection/`, `specs/completed/live-pipeline/`).

We want to **split the roles across devices**: capture on one device (e.g. a phone at the
finish line), process/view on another (a laptop). The pipeline itself does not need to
change — the back-end already *receives + processes + serves results*. What is missing is
the ability to (a) **run the back-end reachable from another device**, and (b) let the
**front-end target an arbitrary back-end and play a chosen role** (collect, process, view,
or combinations) — configured from the UI, not by editing files.

This is deliberately the **LAN iteration**: everything lives on one trusted local network.
Serving the UI from the public internet (S3/CloudFront) and reaching a laptop back-end
through a tunnel is a **later spec** (§3.2) — it forces public HTTPS, tunnels, and stronger
auth that this iteration should not block on.

## 2. Goals

- **G1** — Let one device **capture and send frames to a back-end running on another
  device** on the same LAN, with no application-code edits per deployment.
- **G2** — Let the operator **configure the back-end target and the device's role from the
  UI**, persisted on the device, defaulting to today's all-in-one behaviour when unset.
- **G3** — Support three operator-meaningful **roles** from one front-end bundle:
  *collect + send*, *collect + process here* (all-in-one, unchanged), and *receive +
  process + view*.
- **G4** — Make the front-end **deployable as static files** independent of the back-end
  (served by the back-end as today, or from any static host on the LAN), so the UI is not
  hard-wired to same-origin.
- **G5** — Make the back-end **reachable and camera-capable across the LAN**: bind beyond
  loopback, accept cross-origin requests from the configured UI origin, and support a
  **secure context** (HTTPS) so remote devices can use the camera.
- **G6** — Keep the **all-in-one localhost path working with zero configuration** and no
  new certificates — remote is opt-in, not a tax on the simple case.
- **G7** — Add a **minimal ingest guard** so an exposed `/frames` endpoint is not
  world-writable by anyone who can reach the port.

## 3. Scope

### 3.1 This document / current phase — LAN multi-device roles
- **Front-end runtime configuration**: a UI screen to set the **back-end URL** and pick a
  **role**, persisted on the device (survives reload). Empty/default ⇒ same-origin
  all-in-one, exactly as today.
- **Roles** expressed as two independent switches over a back-end target:
  - *capture* on/off (show camera panel + run the capture loop), and
  - *view* on/off (show runs / timeline / results),
  so the three named roles are presets over `{ backendUrl, capture, view }`.
- **Back-end reachability**: bind to a LAN-visible host, **configurable CORS** that admits
  the front-end's origin, and **optional TLS** (self-signed) so remote capture devices get
  a secure context for `getUserMedia`.
- **Ingest guard**: an optional **shared token** the front-end sends and the back-end
  checks on write endpoints (`/frames`, roster upload), rejecting unauthenticated writes.
- **All-in-one localhost** remains a first-class, zero-config, no-TLS mode.

### 3.2 Later phases (out of scope now, captured for context)
- **Internet-hosted UI (S3/CloudFront) → laptop back-end via tunnel.** Public-HTTPS UI
  cannot reach a plain-HTTP or self-signed LAN back-end (mixed content + cert trust), so
  that path needs a tunnel (Tailscale / cloudflared / ngrok) and is its own spec.
- **Real (CA-signed) certificates / managed DNS** for the back-end.
- **Multi-user auth / accounts / roles-as-permissions.** This iteration's token is a single
  shared secret, not per-user identity.
- **Multiple simultaneous capture devices feeding one run** with server-side clock
  reconciliation and conflict handling (see A6 / OQ4).
- **Saved back-end presets / quick-switch between several servers** beyond one remembered
  target.
- **Discovery** (mDNS/Bonjour auto-find of the back-end) — the operator types/pastes the URL.

## 4. Key Facts & Assumptions

- **A1 — Trusted LAN.** All devices are on the same local network the operator controls.
  Security posture is "keep a stranger on the same Wi-Fi from trivially posting frames",
  not defence against a determined attacker.
- **A2 — Camera needs a secure context.** Browsers only grant `getUserMedia` on
  `https://` or `http://localhost`. A device loading the UI from `http://<lan-ip>:8000`
  therefore **cannot use the camera** — remote capture requires the page be served over
  **HTTPS** (self-signed is acceptable if the device trusts it) *or* be `localhost`.
- **A3 — Mixed content is blocked.** An HTTPS page cannot call an HTTP back-end. If the UI
  is served over HTTPS, the back-end URL it targets must also be HTTPS.
- **A4 — Same-origin needs no CORS; cross-origin does.** When the UI is served by the
  back-end it targets, requests are same-origin and CORS/auth-preflight are moot. Pointing
  the UI at a *different* origin makes every call cross-origin and subject to the back-end's
  CORS policy.
- **A5 — The back-end is already role-agnostic.** It always receives, processes, and serves
  results; "roles" are a **front-end** concern (which panels show, which loops run). No CV
  or storage contract changes.
- **A6 — One capturing device per run (this phase).** Frame ordering uses the *capturing
  device's* clock (`client_ts`); a single collector avoids cross-device clock-skew
  affecting crossing order. Multiple concurrent collectors are deferred (§3.2, OQ4).
- **A7 — The front-end is already static-friendly.** It is plain HTML/JS/CSS with config on
  a `window` object (`collection/frontend/config.js`) — no build step — so serving it from
  a static host is a matter of not assuming same-origin, not a rewrite.
- **A8 — Config keys are frozen, extended not replaced.** `config.js`'s existing keys stay;
  the runtime override layers on top (an empty override preserves today's behaviour).

## 5. Functional Requirements

### 5.1 Front-end — connection & role configuration
- **FR1** — Provide a **connection/role screen** where the operator sets a **back-end URL**
  and selects a **role**, without editing files.
- **FR2** — Persist the connection profile **on the device** (survives reload/restart); the
  device resumes its last role and target on next open.
- **FR3** — When **no profile is set**, behave exactly as today: **same-origin all-in-one**
  (capture + view against the serving back-end). The override must never break the
  zero-config localhost path (G6).
- **FR4** — Offer the three roles as presets over `{ backendUrl, capture, view }`:
  *collect + send* (capture on, view optional, remote URL), *collect + process here*
  (capture on, view on, local), *receive + process + view* (capture off, view on, local).
- **FR5** — **Show/hide UI panels by role**: the camera/capture controls appear only when
  *capture* is on; the runs/timeline/results appear only when *view* is on.
- **FR6** — **Validate/probe the configured back-end** (e.g. `GET /health`) and clearly
  report reachability, version, and — if applicable — TLS/mixed-content or CORS failure, so
  a misconfigured target is diagnosable from the UI, not the console.
- **FR7** — All existing back-end calls (`/frames`, `/health`, `/runs`, `/results`,
  `/roster`, `/frames/image`, `/crossings*`, `/candidates*`, …) must honour the configured
  back-end URL (today they use the frozen `BACKEND_URL`).

### 5.2 Front-end — capture over the network
- **FR8** — When *capture* is on and a **remote** back-end is targeted, stream frames to it
  exactly as the local case, preserving existing **backpressure** and **isolated per-frame
  error handling** (a network drop must not stop the loop).
- **FR9** — If an **ingest token** is configured, attach it to write requests (`/frames`,
  roster upload) so the back-end accepts them.
- **FR10** — Surface **remote-specific failures** (unreachable, TLS-untrusted, CORS
  blocked, 401 unauthorised) distinctly in the status line, not as a generic "send failed".

### 5.3 Back-end — reachability, CORS, TLS, auth
- **FR11** — Be startable **bound to a LAN-visible interface** (beyond `127.0.0.1`), via
  config, so other devices can reach it — without changing the localhost default for the
  simple case.
- **FR12** — Support **configurable CORS origins** admitting the front-end's origin, in a
  way that is consistent with credentialed requests (resolve the current
  `allow_origins:["*"]` + `allow_credentials=True` conflict).
- **FR13** — Support **optional TLS** (self-signed certificate/key via config) so it can
  serve/answer over HTTPS and give remote capture devices a secure context; TLS **off by
  default** for the localhost case.
- **FR14** — Enforce an **optional shared ingest token** on write endpoints: when a token
  is configured, reject writes lacking it with a clear `401`; when unset, behave as today
  (open, for trusted localhost).
- **FR15** — Provide a documented way to **generate the self-signed certificate** and to
  **trust it on a capture device** (accept-once or install), as part of run docs/scripts.

### 5.4 Deployment / operability
- **FR16** — The front-end must be **servable as static files independent of the back-end**
  (from the back-end as today, or any LAN static host), reading its back-end target from the
  runtime profile rather than assuming co-location.
- **FR17** — Provide **run modes / scripts** (or documented invocations) for: all-in-one
  localhost (today), and LAN back-end with TLS + bound host + optional token.
- **FR18** — All new networking behaviour (host, CORS origins, TLS cert/key paths, ingest
  token) is **configurable without code changes** (extends `config.yaml`).

## 6. Non-Functional Requirements

- **NFR1 (Zero-config simple path)** — All-in-one `http://localhost:8000` keeps working with
  **no profile, no CORS, no TLS, no token** — remote features are strictly additive (G6).
- **NFR2 (Robustness over the network)** — Higher-latency / lossy Wi-Fi must not corrupt
  data or freeze the tab; existing bounded in-flight + drop-or-skip backpressure holds for
  the remote case (NFR3 of the collection spec).
- **NFR3 (Diagnosability)** — A misconfigured remote setup (wrong URL, HTTP vs HTTPS,
  untrusted cert, CORS, bad token) yields an **actionable UI message**, not a silent no-op
  or a console-only error.
- **NFR4 (No pipeline/contract regression)** — The CV pipeline, storage layout, and results
  API are **unchanged**; a frame posted from a phone is byte-identical in handling to one
  posted from localhost (A5, NFR1 of collection).
- **NFR5 (Least surprise on security)** — With a token set, an exposed `/frames` is not
  writable by an arbitrary device on the LAN (A1, G7); the default localhost mode stays
  frictionless.
- **NFR6 (Static-hostability)** — The front-end remains a **no-build static bundle**;
  making it host-independent must not introduce a build step (A7).
- **NFR7 (Config-driven)** — Back-end host, CORS origins, TLS paths, and token, plus the
  front-end profile, are all adjustable via config/UI (FR11–FR18).

## 7. Out of Scope

- Internet-hosted UI (S3/CloudFront) and tunnels (Tailscale/cloudflared/ngrok) — **next
  spec** (§3.2).
- CA-signed certificates, managed DNS, or auto-renewing TLS.
- Per-user authentication, accounts, or role-based permissions (the token is one shared
  secret).
- Multiple concurrent capture devices feeding one run + server-side clock reconciliation.
- Back-end auto-discovery (mDNS) and multi-server preset management.
- Any change to detection/OCR/scoring, storage layout, or the results/review API.

## 8. Success Criteria

- **SC1** — With **no configuration**, `http://localhost:8000` still serves the app, camera
  works, frames process, and results show — identical to today (NFR1, FR3).
- **SC2** — With the back-end bound to the LAN and TLS enabled, a **phone** opens the UI
  over HTTPS, is set to *collect + send*, and its captured frames **land on the laptop** and
  appear as crossings in the laptop's results view (G1, G3, FR4, FR8, FR11, FR13).
- **SC3** — Setting a device to *receive + process + view* shows the **results UI with no
  camera panel**; setting *collect + send* shows the **camera panel and hides results**
  (FR4–FR5).
- **SC4** — Pointing the UI at a **wrong / unreachable / HTTP-while-page-is-HTTPS / untrusted-cert /
  CORS-blocked** back-end produces a **clear, specific UI message** (FR6, FR10, NFR3).
- **SC5** — With an **ingest token** configured, a frame POST **without** the token is
  rejected `401` while the configured front-end's POSTs succeed; with **no** token
  configured, localhost posts succeed as today (FR9, FR14, NFR5).
- **SC6** — The front-end bundle can be **served from a location other than the back-end**
  on the LAN and, via its runtime profile (URL + trusted TLS + token), drive capture against
  the back-end — no code edits (FR16, G4).
- **SC7** — Documented commands/scripts bring up **both** the zero-config localhost mode and
  the LAN-TLS mode, including cert generation and trusting it on the capture device
  (FR15, FR17).

## 9. Open Questions

### Resolved (this spec)
- **OQ1 — Where does the back-end URL live?** ✅ **Front-end runtime profile**, persisted on
  the device, overriding the frozen `config.js` key; empty ⇒ same-origin (FR1–FR3, A8).
- **OQ2 — Server "modes"?** ✅ **No.** The back-end stays role-agnostic; roles are a
  front-end preset over `{ backendUrl, capture, view }` (A5, FR4).
- **OQ3 — How do remote capture devices get camera access?** ✅ **Self-signed HTTPS** on the
  back-end (or serve the UI over HTTPS); `localhost` stays exempt and TLS-free (A2, FR13).
- **OQ4 — Internet-hosted UI (CloudFront)?** ✅ **Deferred** to a later spec — needs a tunnel
  and public HTTPS (§3.2).
- **OQ5 — Ingest security?** ✅ **Optional shared token** on write endpoints; off by default
  for localhost (FR14, NFR5).

### Still open (resolve in design)
- **OQ6 — Token transport.** Header vs query param vs both; how the front-end profile stores
  it; whether roster upload and other writes are all gated or only `/frames`.
- **OQ7 — CORS shape.** Fixed configured allowlist vs reflect-origin, and how to reconcile
  with `allow_credentials` (drop credentials for cross-origin, since auth is a token not a
  cookie?).
- **OQ8 — Cert workflow ergonomics.** Provide a generation script + IP-SAN guidance; decide
  accept-once vs install-cert instructions per platform (iOS/Android/desktop).
- **OQ9 — Profile UX surface.** A dedicated settings screen vs an inline panel; how a device
  with a broken profile recovers (reset-to-localhost affordance).
- **OQ10 — Does *collect + send* keep an optional results view** (poll the remote for
  confirmation) or stay capture-only for simplicity?
