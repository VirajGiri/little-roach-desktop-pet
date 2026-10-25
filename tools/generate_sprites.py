"""Build crisp size variants from the exact high-resolution reference cutout.

The source stays pixel-identical; only its background mask is used. The source
shows one side view, so the app mirrors it for left/right travel instead of
fabricating front/rear views that change the insect's identity.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artwork"
SOURCE = ART / "roach_reference_cutout_precise.png"
ASSETS = ROOT / "assets"
SIZES = tuple(range(7, 21))  # 0.7x through 2.0x in 0.1 increments
KEY = (1, 2, 3)


def source_cutout() -> Image.Image:
    image = Image.open(SOURCE).convert("RGBA")
    alpha = np.asarray(image.getchannel("A"), dtype=np.uint8)
    ys, xs = np.where(alpha >= 128)
    if not len(xs):
        raise ValueError(f"No cockroach found in {SOURCE}")
    crop = image.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
    # A small inset keeps the long antennae and feet away from the window edge.
    return crop


def render(cutout: Image.Image, canvas_size: int, mirror: bool) -> Image.Image:
    if mirror:
        cutout = cutout.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    margin = max(2, round(canvas_size * 0.035))
    factor = min((canvas_size - margin * 2) / cutout.width,
                 (canvas_size - margin * 2) / cutout.height)
    width = max(1, round(cutout.width * factor))
    height = max(1, round(cutout.height * factor))
    cutout = cutout.resize((width, height), Image.Resampling.LANCZOS)
    frame = Image.new("RGBA", (canvas_size, canvas_size), (*KEY, 0))
    frame.alpha_composite(cutout, ((canvas_size - width) // 2,
                                   (canvas_size - height) // 2))
    pixels = np.asarray(frame, dtype=np.uint8).copy()
    # Tk's Windows color-key window needs a hard edge. Keeping original RGB
    # values inside the silhouette avoids the dark fringe from matte blending.
    pixels[..., 3] = np.where(pixels[..., 3] >= 128, 255, 0).astype(np.uint8)
    pixels[pixels[..., 3] == 0, :3] = KEY
    return Image.fromarray(pixels, "RGBA")


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    for old in ASSETS.glob("roach_walk_*_dir_*.png"):
        old.unlink()
    for old in ASSETS.glob("roach_photo_*_scale_*.png"):
        old.unlink()
    cutout = source_cutout()
    for size in SIZES:
        canvas_size = round(192 * size / 10)
        for side, mirror in (("right", False), ("left", True)):
            render(cutout, canvas_size, mirror).save(
                ASSETS / f"roach_photo_{side}_scale_{size}.png", optimize=True
            )

    preview_size = 384
    preview = Image.new("RGB", (preview_size * 2, preview_size), (34, 40, 46))
    for column, mirror in enumerate((False, True)):
        frame = render(cutout, preview_size, mirror).convert("RGBA")
        preview.paste(frame, (column * preview_size, 0), frame)
    preview.save(ART / "roach_animation_preview.png", optimize=True)
    print(f"Wrote {len(SIZES)} sharp size variants for each of two reference-matched side views.")


if __name__ == "__main__":
    main()
