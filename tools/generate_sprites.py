"""Prepare 16 gait poses and 32 headings from two eight-view roach sheets.

Requires Pillow and NumPy. These are asset-authoring dependencies only.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artwork"
SOURCES = (ART / "roach_views_gait_01.png", ART / "roach_views_gait_02.png")
ASSETS = ROOT / "assets"
FRAME_COUNT = 16
VIEW_COUNT = 8
DIRECTION_COUNT = 32
OUTPUT_SIZE = 192
FIT_WIDTH = 150
FIT_HEIGHT = 132


def clean_edge(image: Image.Image) -> Image.Image:
    """Keep the insect silhouette and nearby antialiasing, pruning cell spill."""
    rgba = image.convert("RGBA")
    alpha = rgba.getchannel("A")
    core = np.asarray(alpha, dtype=np.uint8) >= 96
    # Some source cells contain antenna fragments from the neighboring cell.
    # Keep the largest connected solid insect silhouette, then retain soft
    # edges and thin appendages within a six-pixel margin of that silhouette.
    seen = np.zeros(core.shape, dtype=bool)
    largest: list[int] = []
    height, width = core.shape
    for y, x in zip(*np.where(core)):
        if seen[y, x]:
            continue
        stack = [int(y * width + x)]
        seen[y, x] = True
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
        return rgba
    body = np.zeros(core.shape, dtype=np.uint8)
    body.flat[largest] = 255
    nearby = Image.fromarray(body, "L").filter(ImageFilter.MaxFilter(13))
    keep = np.asarray(nearby, dtype=np.uint8) > 0
    pixels = np.asarray(rgba, dtype=np.uint8).copy()
    pixels[..., 3] = np.where(keep, pixels[..., 3], 0).astype(np.uint8)
    pixels[pixels[..., 3] == 0, :3] = 0
    return Image.fromarray(pixels, "RGBA")


def load_cells() -> list[list[Image.Image]]:
    cells: list[list[Image.Image]] = []
    for sheet_index, source in enumerate(SOURCES):
        sheet = Image.open(source).convert("RGBA")
        if sheet.width != sheet.height or sheet.width < 8:
            raise ValueError(f"Expected a square 8x8 sheet, got {source.name}: {sheet.size}")
        for row in range(8):
            pose = sheet_index * 8 + row
            for view in range(VIEW_COUNT):
                bounds = tuple(round(n * sheet.width / 8) for n in (view, row, view + 1, row + 1))
                cell = clean_edge(sheet.crop(bounds))
                alpha = np.asarray(cell.getchannel("A"))
                ys, xs = np.where(alpha > 24)
                if not len(xs):
                    raise ValueError(f"No insect found in pose {pose}, view {view}")
                crop = cell.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
                factor = min(FIT_WIDTH / crop.width, FIT_HEIGHT / crop.height)
                size = (max(1, round(crop.width * factor)), max(1, round(crop.height * factor)))
                crop = crop.resize(size, Image.Resampling.LANCZOS)
                frame = Image.new("RGBA", (OUTPUT_SIZE, OUTPUT_SIZE), (0, 0, 0, 0))
                frame.alpha_composite(crop, ((OUTPUT_SIZE - crop.width) // 2,
                                             OUTPUT_SIZE - 28 - crop.height))
                while len(cells) <= pose:
                    cells.append([])
                cells[pose].append(frame)
    return cells


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    frames = load_cells()
    for path in ASSETS.glob("roach_walk_*_dir_*.png"):
        path.unlink()

    for direction in range(DIRECTION_COUNT):
        angle = direction * 360.0 / DIRECTION_COUNT
        view = int(round(angle / 45.0)) % VIEW_COUNT
        view_angle = view * 45.0
        offset = (angle - view_angle + 180.0) % 360.0 - 180.0
        for pose in range(FRAME_COUNT):
            # Each 45-degree interval uses its own painted body perspective;
            # the small rotation only fills the gaps between those views.
            sprite = frames[pose][view]
            if abs(offset) >= 0.01:
                sprite = sprite.rotate(-offset, resample=Image.Resampling.BICUBIC)
            # Windows' Tk color-key transparency cannot composite soft PNG
            # edges against arbitrary desktop colors. A binary silhouette
            # prevents the dark matte fringe seen around the earlier sprite.
            alpha = sprite.getchannel("A").point(lambda value: 255 if value >= 160 else 0)
            sprite.putalpha(alpha)
            sprite.save(ASSETS / f"roach_walk_{pose}_dir_{direction}.png", optimize=True)

    print(f"Wrote {FRAME_COUNT} poses x {DIRECTION_COUNT} headings from {VIEW_COUNT} body views to {ASSETS}")


if __name__ == "__main__":
    main()
