# POC Implementation — Task Plan

Delegation plan for building the finish-line rider-number POC described in
`../requirements.md` and `../design.md`. Each `taskN.md` is scoped for **one sonnet
subagent** working from a cold start, so every task file is self-contained and names the
files it owns.

## Read-first (every agent)
- `../requirements.md` — what & why (esp. §5 functional reqs, §9 success criteria)
- `../design.md` — architecture, module breakdown (§4), config (§7), decisions (§12)

## Dependency graph

```
task1 (scaffold + contracts + env)
        │  ← BLOCKING: must finish before any other task
        ├──────────────┬──────────────┐
        ▼              ▼              ▼
     task2          task3          task4          ← can run in PARALLEL
   detect+zone    locate+ocr     validate+score     (all code against the
        └──────────────┴──────────────┘             frozen contracts from task1)
                       ▼
                    task5  (pipeline integration + outputs)   ← after 2,3,4
                       ▼
                    task6  (tune, evaluate, README)           ← after 5
```

## Suggested waves
- **Wave A:** task1 alone.
- **Wave B:** task2, task3, task4 in parallel (each owns different files — no overlap).
- **Wave C:** task5.
- **Wave D:** task6.

## Shared conventions (all agents must follow)
- **Do not change the contracts** defined in `task1.md` (`src/rider_id/types.py` and the
  function signatures). If a signature is genuinely wrong, stop and flag it rather than
  silently diverging — other agents depend on it.
- **File ownership is exclusive.** Only edit the files your task lists under "Files you
  own." Do not touch another task's files (prevents parallel collisions).
- Images are **OpenCV BGR `np.ndarray`** everywhere. Boxes are `(x1, y1, x2, y2)` in
  **absolute pixel coords** of the full input image, floats.
- Config is the parsed `config.yaml` as a nested `dict`; access with `cfg["section"]["key"]`.
- Everything runs **CPU-only on a laptop** (design §11) — no GUI, no network at
  runtime. Use `opencv-python-headless`.
- **Always work inside the project venv (Python 3.12):** `source comp-vision-results/.venv/bin/activate`
  before running anything. The system default `python3` is **3.14** and will break the
  ML wheels — never use it. Task1 creates the venv with `/usr/bin/python3.12`.
- Keep code small and readable; no speculative abstraction beyond the module boundaries.

## Test asset
Single input image: `../ridersFromThBack.jpg` (road peloton, backs to camera, numbers
101/102/103/108 visible). The nearest rider (`101`) is the primary POC target.
