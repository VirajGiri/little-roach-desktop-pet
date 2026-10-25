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
