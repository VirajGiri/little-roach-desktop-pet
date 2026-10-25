"""Build direction sprites from the 8-view, 8-pose transparent roach atlas.

Authoring dependencies: Pillow and NumPy. Neither is needed at runtime.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artwork"
SOURCE = ART / "roach_rotation_gait_sheet.png"
ASSETS = ROOT / "assets"
FRAME_COUNT = 8
VIEW_COUNT = 8
DIRECTION_COUNT = 32
OUTPUT_SIZE = 192
FIT_WIDTH = 156
FIT_HEIGHT = 122
GROUND_Y = 166


def clean_edge(image: Image.Image) -> Image.Image:
    """Remove isolated alpha flecks while retaining the insect and antennae."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    core = np.asarray(alpha, dtype=np.uint8) >= 96
    seen = np.zeros(core.shape, dtype=bool)
    largest: list[int] = []
    height, width = core.shape
    for y, x in zip(*np.where(core)):
        if seen[y, x]:
            continue
        seen[y, x] = True
        stack = [int(y * width + x)]
        component: list[int] = []
        while stack:
            index = stack.pop()
            component.append(index)
            cy, cx = divmod(index, width)
            for ny in range(max(0, cy - 1), min(height, cy + 2)):
                for nx in range(max(0, cx - 1), min(width, cx + 2)):
                    if core[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append(ny * width + nx)
        if len(component) > len(largest):
            largest = component
    if not largest:
        raise ValueError("An atlas cell has no opaque cockroach pixels.")
    solid = np.zeros(core.shape, dtype=np.uint8)
    solid.flat[largest] = 255
    nearby = Image.fromarray(solid, "L").filter(ImageFilter.MaxFilter(13))
    keep = np.asarray(nearby, dtype=np.uint8) > 0
    pixels = np.asarray(rgba, dtype=np.uint8).copy()
    pixels[..., 3] = np.where(keep, pixels[..., 3], 0).astype(np.uint8)
    pixels[pixels[..., 3] == 0, :3] = (1, 2, 3)
    return Image.fromarray(pixels, "RGBA")


def load_cells() -> list[list[Image.Image]]:
    sheet = Image.open(SOURCE).convert("RGBA")
    if sheet.width % VIEW_COUNT or sheet.height % FRAME_COUNT:
        raise ValueError(f"Expected an 8x8 atlas, got {sheet.size}")
    cell_w, cell_h = sheet.width // VIEW_COUNT, sheet.height // FRAME_COUNT
    frames: list[list[Image.Image]] = []
    for pose in range(FRAME_COUNT):
        row: list[Image.Image] = []
        for view in range(VIEW_COUNT):
            cell = clean_edge(sheet.crop((view * cell_w, pose * cell_h,
                                          (view + 1) * cell_w, (pose + 1) * cell_h)))
            alpha = np.asarray(cell.getchannel("A"), dtype=np.uint8)
            ys, xs = np.where(alpha > 24)
            if not len(xs):
                raise ValueError(f"No insect found in gait row {pose}, direction {view}")
            crop = cell.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
            factor = min(FIT_WIDTH / crop.width, FIT_HEIGHT / crop.height)
            size = (max(1, round(crop.width * factor)), max(1, round(crop.height * factor)))
            crop = crop.resize(size, Image.Resampling.LANCZOS)
            frame = Image.new("RGBA", (OUTPUT_SIZE, OUTPUT_SIZE), (1, 2, 3, 0))
            frame.alpha_composite(crop, ((OUTPUT_SIZE - crop.width) // 2,
                                         GROUND_Y - crop.height))
            row.append(frame)
        frames.append(row)
    return frames


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    frames = load_cells()
    for old in ASSETS.glob("roach_walk_*_dir_*.png"):
        old.unlink()

    for direction in range(DIRECTION_COUNT):
        angle = direction * 360.0 / DIRECTION_COUNT
        view = int(round(angle / 45.0)) % VIEW_COUNT
        view_angle = view * 45.0
        offset = (angle - view_angle + 180.0) % 360.0 - 180.0
        for pose in range(FRAME_COUNT):
            sprite = frames[pose][view]
            if abs(offset) >= 0.01:
                sprite = sprite.rotate(-offset, resample=Image.Resampling.BICUBIC)
            alpha = sprite.getchannel("A").point(lambda value: 255 if value >= 160 else 0)
            sprite.putalpha(alpha)
            pixels = np.asarray(sprite, dtype=np.uint8).copy()
            pixels[pixels[..., 3] == 0, :3] = (1, 2, 3)
            Image.fromarray(pixels, "RGBA").save(
                ASSETS / f"roach_walk_{pose}_dir_{direction}.png", optimize=True
            )

    preview = Image.new("RGB", (OUTPUT_SIZE * VIEW_COUNT, OUTPUT_SIZE * FRAME_COUNT), (34, 40, 46))
    for pose in range(FRAME_COUNT):
        for direction in range(VIEW_COUNT):
            frame = Image.open(ASSETS / f"roach_walk_{pose}_dir_{direction * 4}.png").convert("RGBA")
            preview.paste(frame, (direction * OUTPUT_SIZE, pose * OUTPUT_SIZE), frame)
    preview.save(ART / "roach_animation_preview.png", optimize=True)
    print(f"Wrote {FRAME_COUNT} gait poses x {DIRECTION_COUNT} headings from {VIEW_COUNT} painted body views.")


if __name__ == "__main__":
    main()
