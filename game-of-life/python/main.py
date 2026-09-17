# Runs on the Linux side (MPU): simulates the world and streams a window of it to the MCU.
import time

import numpy as np
from arduino.app_utils import App, Bridge

WORLD_H, WORLD_W = 32, 52  # simulated world (wraps around at the edges)
VIEW_H, VIEW_W = 8, 13     # LED matrix size
DENSITY = 0.35             # fraction of cells alive at (re)seed
STEP_S = 0.2               # seconds per generation
PAN_EVERY = 4              # move the view one cell diagonally every N generations (0 = fixed)
FADE = 2                   # brightness lost per generation by dead cells (trail effect)
MAX_LEVEL = 7              # matrix uses 3-bit grayscale (0..7)

rng = np.random.default_rng()


def seed() -> np.ndarray:
    return rng.random((WORLD_H, WORLD_W)) < DENSITY


def step(world: np.ndarray) -> np.ndarray:
    neighbors = sum(
        np.roll(np.roll(world, dy, axis=0), dx, axis=1)
        for dy in (-1, 0, 1)
        for dx in (-1, 0, 1)
        if (dy, dx) != (0, 0)
    )
    return (neighbors == 3) | (world & (neighbors == 2))


world = seed()
glow = world.astype(np.int8) * MAX_LEVEL
generation = 0
recent = []  # hashes of recent states, to detect still lifes and oscillators


def loop():
    global world, glow, generation, recent

    top = (generation // PAN_EVERY) % WORLD_H if PAN_EVERY else 0
    left = (generation // PAN_EVERY) % WORLD_W if PAN_EVERY else 0
    rows = np.arange(top, top + VIEW_H) % WORLD_H
    cols = np.arange(left, left + VIEW_W) % WORLD_W
    view = glow[np.ix_(rows, cols)].astype(np.uint8)
    Bridge.call("draw", bytes(view.flatten()), timeout=2)

    world = step(world)
    glow = np.where(world, MAX_LEVEL, np.maximum(glow - FADE, 0)).astype(np.int8)
    generation += 1

    state = hash(world.tobytes())
    if state in recent or world.sum() < 4:
        print(f"gen {generation}: world settled (pop {world.sum()}), reseeding", flush=True)
        world, recent = seed(), []
    else:
        recent = (recent + [state])[-16:]
    if generation % 50 == 0:
        print(f"gen {generation}: population {world.sum()}", flush=True)

    time.sleep(STEP_S)


App.run(user_loop=loop)
