"""Build consistent views from the exact cockroach image supplied by the user.

Authoring dependencies: Pillow and NumPy. Neither is needed at runtime.
The single source view is rotated in the image plane to preserve the same
individual in every heading; small body rocking offsets provide crawl motion.
"""

from __future__ import annotations

from pathlib import Path
import math

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artwork"
SOURCE = ART / "roach_reference_original.png"
CUTOUT = ART / "roach_reference_cutout.png"
ASSETS = ROOT / "assets"
FRAME_COUNT = 16
DIRECTION_COUNT = 32
OUTPUT_SIZE = 192
FIT_WIDTH = 158
FIT_HEIGHT = 158


def largest_component(binary: np.ndarray) -> np.ndarray:
    """Discard isolated high-frequency background texture from the matte."""
    height, width = binary.shape
    seen = np.zeros(binary.shape, dtype=bool)
    best: list[int] = []
    for y, x in zip(*np.where(binary)):
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
                    if binary[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append(ny * width + nx)
        if len(component) > len(best):
            best = component
    result = np.zeros(binary.shape, dtype=np.uint8)
    if best:
        result.flat[best] = 255
    return result


def make_cutout() -> Image.Image:
    """Use the photo's local detail to separate the textured insect from glow."""
    source = Image.open(SOURCE).convert("RGB")
    pixels = np.asarray(source, dtype=np.int16)
    local_average = np.asarray(source.filter(ImageFilter.GaussianBlur(3.0)), dtype=np.int16)
    detail = np.max(np.abs(pixels - local_average), axis=2)
    mask = Image.fromarray(np.where(detail >= 8, 255, 0).astype(np.uint8), "L")
    # Close tiny gaps in the shell and legs without drawing the soft backdrop in.
    mask = mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
    silhouette = largest_component(np.asarray(mask, dtype=np.uint8) > 0)
    mask = Image.fromarray(silhouette, "L").filter(ImageFilter.MinFilter(3))

    rgba = source.convert("RGBA")
    rgba.putalpha(mask)
    rgba_pixels = np.asarray(rgba, dtype=np.uint8).copy()
    rgba_pixels[rgba_pixels[..., 3] == 0, :3] = (1, 2, 3)
    cutout = Image.fromarray(rgba_pixels, "RGBA")
    cutout.save(CUTOUT, optimize=True)
    return cutout


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    cutout = make_cutout()
    alpha = np.asarray(cutout.getchannel("A"), dtype=np.uint8)
    ys, xs = np.where(alpha > 0)
    if not len(xs):
        raise ValueError("The reference cutout is empty; check the source image.")
    source = cutout.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    factor = min(FIT_WIDTH / source.width, FIT_HEIGHT / source.height)
    size = (max(1, round(source.width * factor)), max(1, round(source.height * factor)))
    source = source.resize(size, Image.Resampling.LANCZOS)

    for old in ASSETS.glob("roach_walk_*_dir_*.png"):
        old.unlink()

    for direction in range(DIRECTION_COUNT):
        angle = direction * 360.0 / DIRECTION_COUNT
        for pose in range(FRAME_COUNT):
            phase = 2 * math.pi * pose / FRAME_COUNT
            # Keep the supplied photograph intact; only rock the whole body a
            # little as it crawls. This avoids swapping in a different insect.
            rocking = 2.4 * math.sin(phase)
            sprite = source.rotate(-angle - rocking, resample=Image.Resampling.BICUBIC, expand=True)
            scale = 1.0 + 0.01 * math.cos(phase)
            if abs(scale - 1.0) > 0.001:
                sprite = sprite.resize((round(sprite.width * scale), round(sprite.height * scale)),
                                       Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (OUTPUT_SIZE, OUTPUT_SIZE), (1, 2, 3, 0))
            x = (OUTPUT_SIZE - sprite.width) // 2
            y = (OUTPUT_SIZE - sprite.height) // 2 + round(math.sin(phase) * 1.5)
            canvas.alpha_composite(sprite, (x, y))
            # The Windows color-key window needs crisp transparent pixels.
            a = canvas.getchannel("A").point(lambda value: 255 if value >= 160 else 0)
            canvas.putalpha(a)
            rgb = np.asarray(canvas, dtype=np.uint8).copy()
            rgb[rgb[..., 3] == 0, :3] = (1, 2, 3)
            Image.fromarray(rgb, "RGBA").save(
                ASSETS / f"roach_walk_{pose}_dir_{direction}.png", optimize=True
            )

    preview = Image.new("RGB", (OUTPUT_SIZE * 4, OUTPUT_SIZE * 4), (34, 40, 46))
    for row, pose in enumerate((0, 4, 8, 12)):
        for column, direction in enumerate((0, 8, 16, 24)):
            frame = Image.open(ASSETS / f"roach_walk_{pose}_dir_{direction}.png").convert("RGBA")
            preview.paste(frame, (column * OUTPUT_SIZE, row * OUTPUT_SIZE), frame)
    preview.save(ART / "roach_animation_preview.png", optimize=True)

    print(f"Wrote {FRAME_COUNT} motion poses x {DIRECTION_COUNT} headings from the supplied roach photo.")


if __name__ == "__main__":
    main()
