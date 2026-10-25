"""Pure helpers shared by the pet and its tests."""

from __future__ import annotations

import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PetSettings:
    speed: float = 1.5
    scale: float = 1.0
    start_with_windows: bool = False

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> "PetSettings":
        speed = min(3.0, max(0.4, float(values.get("speed", 1.5))))
        scale = min(2.0, max(0.7, float(values.get("scale", 1.0))))
        return cls(speed, scale, bool(values.get("start_with_windows", False)))


def settings_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "LittleRoach" / "settings.json"


def choose_target(x: int, y: int, screen: tuple[int, int, int, int],
                  pet_width: int, pet_height: int, speed: float,
                  rng: Any = random) -> tuple[int, int]:
    """Pick a reachable screen position, with larger hops at higher speeds."""
    left, top, width, height = screen
    min_x, max_x = left, left + max(0, width - pet_width)
    min_y, max_y = top, top + max(0, height - pet_height)
    # Favor local wandering; occasionally allow a longer trip across the desktop.
    max_hop = max(160, int(360 * speed))
    if rng.random() < 0.2:
        tx = rng.randint(min_x, max_x)
        ty = rng.randint(min_y, max_y)
    else:
        tx = int(min(max_x, max(min_x, x + rng.randint(-max_hop, max_hop))))
        ty = int(min(max_y, max(min_y, y + rng.randint(-max_hop // 2, max_hop // 2))))
    return tx, ty


def approach_angle(current: float, target: float, max_step: float) -> float:
    """Turn toward target by at most max_step degrees along the short arc."""
    difference = (target - current + 180.0) % 360.0 - 180.0
    step = min(max_step, max(-max_step, difference))
    return (current + step) % 360.0


def gait_pose(distance: float, frame_count: int = 16,
              stride_distance: float = 80.0) -> int:
    """Select a leg-cycle frame from traveled distance, independent of FPS."""
    if frame_count < 1 or stride_distance <= 0:
        raise ValueError("frame_count and stride_distance must be positive")
    phase = (distance % stride_distance) / stride_distance
    return int(phase * frame_count) % frame_count


def movement_step(speed_per_40ms: float, elapsed_seconds: float) -> float:
    """Convert the legacy pace setting to distance for a variable-length frame."""
    return max(0.0, speed_per_40ms) * max(0.0, elapsed_seconds) / 0.04
