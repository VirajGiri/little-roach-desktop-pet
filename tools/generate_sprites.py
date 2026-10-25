"""Prepare 16 gait poses and 32 headings from the source roach sprite sheet.

Requires Pillow and NumPy. This is an asset-authoring tool; neither package is
needed to run the desktop pet.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artwork" / "roach_gait_sheet_keyed.png"
ASSETS = ROOT / "assets"
FRAME_COUNT = 16
DIRECTION_COUNT = 32
CELL_WIDTH = 384
CELL_HEIGHT = 256
OUTPUT_SIZE = 192


def remove_green_key(image: Image.Image) -> Image.Image:
    """Convert the flat green key to alpha and remove green spill on edges."""
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32)
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    excess = np.maximum(0.0, green - np.maximum(red, blue) - 12.0)
    alpha = np.clip(255.0 - excess * (255.0 / 55.0), 0.0, 255.0)

    # Chroma key against pure green: recover the foreground RGB beneath the
    # partially blended edge pixels instead of leaving a bright green fringe.
    a = np.maximum(alpha / 255.0, 1.0 / 255.0)
    foreground = np.stack((red / a, (green - (1.0 - a) * 255.0) / a, blue / a), axis=-1)
    foreground = np.clip(foreground, 0.0, 255.0).astype(np.uint8)
    foreground[alpha <= 0] = 0
    rgba = np.dstack((foreground, alpha.astype(np.uint8)))
    return Image.fromarray(rgba, "RGBA")


def gait_frames() -> list[Image.Image]:
    sheet = Image.open(SOURCE).convert("RGB")
    if sheet.size != (CELL_WIDTH * 4, CELL_HEIGHT * 4):
        raise ValueError(f"Expected a 1536x1024 sheet, got {sheet.size}")

    frames: list[Image.Image] = []
    for index in range(FRAME_COUNT):
        col, row = index % 4, index // 4
        cell = sheet.crop((col * CELL_WIDTH, row * CELL_HEIGHT,
                           (col + 1) * CELL_WIDTH, (row + 1) * CELL_HEIGHT))
        keyed = remove_green_key(cell)
        alpha = np.asarray(keyed.getchannel("A"))
        ys, xs = np.where(alpha > 48)
        if not len(xs):
            raise ValueError(f"Frame {index} contains no visible insect")
        bounds = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
        insect = keyed.crop(bounds)

        # Keep a stable scale and foot baseline even if the generated sheet
        # shifted a frame by a few pixels.
        fit = min(154.0 / insect.width, 132.0 / insect.height)
        scaled_size = (max(1, round(insect.width * fit)), max(1, round(insect.height * fit)))
        insect = insect.resize(scaled_size, Image.Resampling.LANCZOS)
        frame = Image.new("RGBA", (OUTPUT_SIZE, OUTPUT_SIZE), (0, 0, 0, 0))
        frame.alpha_composite(insect, ((OUTPUT_SIZE - insect.width) // 2,
                                       OUTPUT_SIZE - 38 - insect.height))
        frames.append(frame)
    return frames


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for path in ASSETS.glob("roach_walk_*_dir_*.png"):
        path.unlink()

    frames = gait_frames()
    for direction in range(DIRECTION_COUNT):
        angle = direction * (360.0 / DIRECTION_COUNT)
        for frame_index, frame in enumerate(frames):
            rotated = frame.rotate(-angle, resample=Image.Resampling.BICUBIC)
            rotated.save(ASSETS / f"roach_walk_{frame_index}_dir_{direction}.png", optimize=True)

    print(f"Wrote {FRAME_COUNT * DIRECTION_COUNT} sprites to {ASSETS}")


if __name__ == "__main__":
    main()
