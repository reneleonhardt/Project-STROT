# STROT plays Pac-Man

A self-contained demo: a 144M local decision model (SupersonicLabs/Julia-1)
decides Pac-Man's strategy every frame — **chase the nearest dot** or **flee the
nearest ghost** — and deterministic code executes the move on the board. One
real decision per frame, no LLM at runtime.

- `pacman.html` — drop-in retro replay UI (neon maze, confidence readout,
  play/pause/speed). Reads `pacman_run.json`, or set `window.PACMAN_RUN`.
- `pacman_run.json` — a real recorded game (the numbers below are from this run).
- `../benchmarks/pacman.py` — the engine + STROT controller that produced it.

## What the model actually does

Each frame STROT compiles a projection of the board (ghost distance/bearing,
nearest-dot bearing, safe moves) once via the LLM, then the local model makes a
**choice** decision with calibrated confidence. The recorded run:

| | |
|---|---|
| Result | survived all 400 frames |
| Score / dots | 300 · 30 of 167 |
| Strategy mix | 214 chase · 186 flee — the model **modulates** by ghost distance |
| Mean confidence | 0.86 |
| Runtime cost | ~60 ms/decision, CPU, $0 |

## Honest notes

- The model decides the **strategy** (a judgment a 144M model can make from a
  distance feature), not raw up/down/left/right — asked to pick abstract
  directions zero-shot, a model this small latches onto one and can't ground
  them spatially. Deciding chase-vs-flee is a real decision within its
  capability; the spatial execution is compiled code. That split *is* the STROT
  idea: the model decides, the compiler handles everything around it.
- It plays cautiously (flees often → fewer dots than a hand-tuned baseline's 79)
  but survives — a genuine, imperfect game, not a scripted win.

## Regenerate

```bash
pip install strot-ai[local,anthropic]
python -c "import strot; strot.prefetch_nlu(local_dir='./julia-1', install=True)"
export STROT_NLU_CHECKPOINT=./julia-1 ANTHROPIC_API_KEY=...
python ../benchmarks/pacman.py            # STROT (real model) plays
python ../benchmarks/pacman.py --greedy   # baseline, no model/LLM
```
