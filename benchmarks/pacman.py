"""STROT plays Pac-Man: a decision model picks a move every frame.

Each frame is one decision - given the board state, choose up/down/left/right.
STROT's compiler synthesizes the state projection (which board features the
model sees); the local 144M decision model then plays, no LLM at runtime.

Run (records a real game to pacman_run.json):

    pip install strot-ai[local,anthropic]
    python -c "import strot; strot.prefetch_nlu(local_dir='./julia-1', install=True)"
    export STROT_NLU_CHECKPOINT=./julia-1 ANTHROPIC_API_KEY=...
    python pacman.py                 # STROT (real model) plays
    python pacman.py --greedy        # fast baseline controller, no model/LLM

Output: pacman_run.json - a recording the replay UI (pacman.html) plays back.
"""

from __future__ import annotations

import argparse
import json
import sys

# Maze: '#' wall, '.' dot, ' ' empty, 'o' power pellet, 'P' pac start, 'G' ghost.
MAZE = [
    "#####################",
    "#o.......#.........o#",
    "#.###.##.#.##.###.#.#",
    "#...................#",
    "#.##.#.#######.#.##.#",
    "#....#...#...#...#..#",
    "####.### # # ###.####",
    "#....#  G G  #......#",
    "#.##.#  ###  #.####.#",
    "#..................P#",
    "#.##.####.#.####.##.#",
    "#....#.........#...o#",
    "####.#.#######.#.####",
    "#......#.....#......#",
    "#.####.#.###.#.####.#",
    "#o.................##",
    "#####################",
]

MOVES = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPTIONS = ["up", "down", "left", "right"]


class Game:
    def __init__(self):
        self.grid = [list(row) for row in MAZE]
        self.w, self.h = len(self.grid[0]), len(self.grid)
        self.dots = set()
        self.ghosts = []
        for y, row in enumerate(self.grid):
            for x, ch in enumerate(row):
                if ch in ".o":
                    self.dots.add((x, y))
                elif ch == "P":
                    self.pac = [x, y]
                    self.grid[y][x] = " "
                elif ch == "G":
                    self.ghosts.append([x, y])
                    self.grid[y][x] = " "
        self.start_dots = len(self.dots)
        self.score = 0
        self.alive = True
        self.frame = 0
        self.last_dir = "left"

    def wall(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.grid[y][x] == "#"
        return True  # off-grid = wall (except tunnels handled below)

    def valid_moves(self, pos):
        out = []
        for name, (dx, dy) in MOVES.items():
            nx, ny = pos[0] + dx, pos[1] + dy
            if not self.wall(nx, ny) or self._tunnel(nx, ny):
                out.append(name)
        return out

    def _tunnel(self, x, y):
        return y in (8, 10, 12) and (x < 0 or x >= self.w)

    def _step(self, pos, name):
        dx, dy = MOVES[name]
        nx, ny = pos[0] + dx, pos[1] + dy
        if nx < 0:
            nx = self.w - 1
        elif nx >= self.w:
            nx = 0
        if self.wall(nx, ny):
            return pos
        return [nx, ny]

    def record_state(self):
        """The game-state record STROT sees. The compiler projects from this."""
        px, py = self.pac
        gx, gy = min(self.ghosts, key=lambda g: abs(g[0] - px) + abs(g[1] - py))
        # nearest dot
        nearest = min(self.dots, key=lambda d: abs(d[0] - px) + abs(d[1] - py)) if self.dots else (px, py)
        def bearing(tx, ty):
            h = "left" if tx < px else "right" if tx > px else "same"
            v = "up" if ty < py else "down" if ty > py else "same"
            return f"{v}-{h}"
        valid = self.valid_moves(self.pac)
        danger = {m: False for m in OPTIONS}
        for m in valid:
            nx, ny = self._step(self.pac, m)
            if any(abs(g[0] - nx) + abs(g[1] - ny) <= 1 for g in self.ghosts):
                danger[m] = True
        return {
            "pac_x": px, "pac_y": py,
            "nearest_ghost_bearing": bearing(gx, gy),
            "nearest_ghost_distance": abs(gx - px) + abs(gy - py),
            "nearest_dot_bearing": bearing(nearest[0], nearest[1]),
            "valid_moves": ",".join(valid) if valid else "none",
            "safe_moves": ",".join(m for m in valid if not danger[m]) or "none",
            "dots_left": len(self.dots),
        }

    def apply(self, name):
        if name not in self.valid_moves(self.pac):
            # invalid (wall) -> try to continue last direction, else stop
            name = self.last_dir if self.last_dir in self.valid_moves(self.pac) else None
        if name:
            self.pac = self._step(self.pac, name)
            self.last_dir = name
        # eat
        pos = tuple(self.pac)
        if pos in self.dots:
            self.dots.discard(pos)
            self.score += 10
        # move ghosts (greedy chase with occasional detour by frame parity)
        for i, g in enumerate(self.ghosts):
            moves = self.valid_moves(g)
            if not moves:
                continue
            if (self.frame + i) % 3 == 0:  # scatter tick
                g[:] = self._step(g, moves[(self.frame + i) % len(moves)])
            else:
                best = min(moves, key=lambda m: (
                    abs(self._step(g, m)[0] - self.pac[0])
                    + abs(self._step(g, m)[1] - self.pac[1])))
                g[:] = self._step(g, best)
        # collision
        if any(g == self.pac for g in self.ghosts):
            self.alive = False
        self.frame += 1


def greedy_controller(game):
    """Baseline: flee if a ghost is close, else chase the nearest dot. No model."""
    state = game.record_state()
    strat = "flee_ghost" if state["nearest_ghost_distance"] <= 2 else "chase_dot"
    return execute_strategy(game, strat), 0.8, strat


def run(controller, max_frames=400):
    g = Game()
    frames = []
    while g.alive and g.dots and g.frame < max_frames:
        move, conf, label = controller(g)
        frames.append({
            "grid_pac": list(g.pac),
            "ghosts": [list(x) for x in g.ghosts],
            "dots": [list(d) for d in g.dots],
            "score": g.score,
            "move": move,
            "strategy": label,
            "confidence": round(conf, 3),
        })
        g.apply(move)
    return {
        "maze": MAZE,
        "frames": frames,
        "final_score": g.score,
        "dots_eaten": g.start_dots - len(g.dots),
        "start_dots": g.start_dots,
        "result": "won" if not g.dots else ("caught" if not g.alive else "timeout"),
        "frame_count": len(frames),
    }


def diverse_sample(n=40):
    """Collect varied game states by playing a quick greedy game - so the
    compiler sees real board variety when it synthesizes the projection."""
    g = Game()
    states = []
    while g.alive and g.dots and len(states) < n:
        s = g.record_state()
        states.append(s)
        move, _, _ = greedy_controller(g)
        g.apply(move)
        if g.frame % 2 == 0:  # thin for variety
            g = g if g.alive else Game()
    while len(states) < n:
        states.append(Game().record_state())
    return states


STRATEGIES = ["chase_dot", "flee_ghost"]


def execute_strategy(game, strategy):
    """Translate a chosen strategy into an actual safe direction (deterministic)."""
    px, py = game.pac
    valid = game.valid_moves(game.pac)
    if not valid:
        return "left"
    safe = []
    for m in valid:
        nx, ny = game._step(game.pac, m)
        if not any(abs(g[0] - nx) + abs(g[1] - ny) <= 1 for g in game.ghosts):
            safe.append(m)
    pool = safe or valid
    gx, gy = min(game.ghosts, key=lambda g: abs(g[0] - px) + abs(g[1] - py))
    if strategy == "flee_ghost":
        return max(pool, key=lambda m: (
            abs(game._step(game.pac, m)[0] - gx) + abs(game._step(game.pac, m)[1] - gy)))
    target = min(game.dots, key=lambda d: abs(d[0] - px) + abs(d[1] - py)) if game.dots else (px, py)
    return min(pool, key=lambda m: (
        abs(game._step(game.pac, m)[0] - target[0]) + abs(game._step(game.pac, m)[1] - target[1])))


def strot_controller_factory():
    """STROT decides the STRATEGY each frame (chase vs flee) - a judgment a
    small model can make from the ghost-distance feature; deterministic code
    then executes it on the board. The decision the model makes is real and
    within its capability; the spatial execution is compiled code."""
    import strot
    compiled = {"pipeline": None}
    question = {
        "strategy": {"type": "choice", "options": STRATEGIES,
                     "instructions": "If a ghost is close (nearest_ghost_distance small, "
                                     "within 2 steps), choose flee_ghost. Otherwise choose "
                                     "chase_dot to eat the nearest dot."}
    }
    sample = diverse_sample(40)

    def _decide(game, state):
        if compiled["pipeline"] is None:
            result = strot.decide(
                sample + [state], questions=question,
                llm="anthropic/claude-opus-4-8", state="/tmp/pacman_strot",
                sample_size=40,
            )
            compiled["pipeline"] = result.pipeline
            decision = result.outcomes[-1]["decision"]
        else:
            decision = compiled["pipeline"].process(state)
        choice = decision["choices"]["strategy"]
        move = execute_strategy(game, choice["selected"])
        return move, choice["confidence"], choice["selected"]

    def controller(game):
        state = game.record_state()
        return _decide(game, state)

    return controller


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--greedy", action="store_true", help="baseline controller, no model")
    ap.add_argument("--out", default="pacman_run.json")
    args = ap.parse_args()

    ctrl = greedy_controller if args.greedy else strot_controller_factory()
    recording = run(ctrl)
    with open(args.out, "w") as f:
        json.dump(recording, f)
    print(f"{recording['result']}: score {recording['final_score']}, "
          f"{recording['dots_eaten']}/{recording['start_dots']} dots, "
          f"{recording['frame_count']} frames -> {args.out}")
