# CLAUDE.md

Guidance for Claude Code when working in this repo.

## What this is
A CV pipeline that detects cyclists crossing a finish line and reads their printed
back-number. See `README.md` to run it; `specs/completed/poc/` holds the POC spec.

## How we build features here

We use a **spec-first, parallel-agent** workflow. Each feature moves through three stages:

1. **Requirements** (`requirements.md`) — *what & why*: goals, scope, assumptions,
   functional/non-functional requirements, success criteria. No tech choices.
2. **Design** (`design.md`) — *how*: tech stack, architecture, module contracts human readable
   (dataclasses + exact function signatures), config, and how the POC extends later. 
   Use SVG diagram to explain complext concepts. Every design doc must have at least one high level diagram to explain the design. The svg diagram must be in a different file and imported with `![](file.svg)`.
3. **Parallel tasks** (`tasks/taskN.md`) — the design sliced into small, self-contained
   task files, each owning **exclusive files** and coding against the contracts (which should be frozen for the scope of an implementation run),
   then delegated to **sonnet/haiku subagents**.

Pause in between stages and ask for human review.

### Delegation rules
- **`tasks/README.md` is the map** — it defines the dependency graph, execution *waves*,
  and shared conventions. Read it before spawning agents.
- **Scaffold first, blocking.** One foundation task creates the project skeleton, the
  frozen `types.py`/signatures, and the environment. Nothing else starts until it lands.
- **Then fan out in parallel.** Independent tasks (exclusive file ownership, fixed
  contracts) run as concurrent subagents; integration + tuning tasks run after.
- **Contracts are frozen.** An agent that finds a signature genuinely wrong must **stop
  and flag it**, never silently diverge — siblings depend on it.
- Use **sonnet** for implementation tasks; **haiku** for cheap mechanical ones.
  Give each agent its `taskN.md` plus the requirements/design docs as source of truth.

When a feature ships, move its spec + tasks under `specs/completed/<name>/` (see the POC).

## Environment
- **Python 3.12 only** (`/usr/bin/python3.12`) — the system default (3.14) lacks
  paddle/torch wheels. Always work inside `.venv`: `source .venv/bin/activate`.
- CPU-only; `opencv-python-headless`; no network at runtime beyond first-run model pulls.
