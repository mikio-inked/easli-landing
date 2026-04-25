"""Generate all KlarPost app icon variants from a single source PNG.

Source: /app/scripts/source_icon.png (the user-supplied square master icon)
Outputs (in /app/frontend/assets/images/):
  - icon.png                1024x1024  RGB (no alpha)  — iOS App Store
  - adaptive-icon.png       1024x1024  RGBA            — Android adaptive foreground
  - splash-icon.png         1024x1024  RGBA            — Splash screen
  - favicon.png               64x64    RGB             — Web favicon
  - play-store-icon.png      512x512   RGB             — Google Play store listing
  - marketing-icon-256.png   256x256   RGB             — Marketing/press kit

iOS forbids alpha channels on the App Store icon. Android adaptive icons must
sit safely within the inner 66% of the canvas, so we slightly downscale the
source onto a transparent canvas for that variant.
"""

from PIL import Image

SOURCE_PATH = "/app/scripts/source_icon.png"
OUT_DIR = "/app/frontend/assets/images"

# Background colour used to flatten any alpha for iOS / Play Store outputs.
# Matches the subtle light-blue gradient background of the supplied icon.
FLATTEN_BG = (235, 244, 255)  # soft very-light blue


def load_source() -> Image.Image:
    img = Image.open(SOURCE_PATH).convert("RGBA")
    # Make it square (it already is, but be safe)
    w, h = img.size
    if w != h:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
    return img


def save_opaque(img: Image.Image, path: str, size: int):
    """Resize and save as opaque RGB PNG (no alpha)."""
    resized = img.resize((size, size), Image.LANCZOS)
    if resized.mode != "RGBA":
        resized = resized.convert("RGBA")
    base = Image.new("RGB", (size, size), FLATTEN_BG)
    base.paste(resized, mask=resized.split()[3])
    base.save(path, "PNG", optimize=True)


def save_rgba(img: Image.Image, path: str, size: int, inner_scale: float = 1.0):
    """Resize and save as RGBA PNG. inner_scale<1 keeps the icon centered with
    transparent margin (used for adaptive-icon to respect Android safe zone)."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    inner = max(1, int(size * inner_scale))
    resized = img.resize((inner, inner), Image.LANCZOS)
    if resized.mode != "RGBA":
        resized = resized.convert("RGBA")
    offset = (size - inner) // 2
    canvas.paste(resized, (offset, offset), resized)
    canvas.save(path, "PNG", optimize=True)


def main():
    src = load_source()
    print(f"Loaded source: {src.size} {src.mode}")

    # 1) iOS App Store icon — 1024x1024 RGB, no alpha.
    save_opaque(src, f"{OUT_DIR}/icon.png", 1024)

    # 2) Android adaptive foreground — keep ~85% inner so the rounded badge
    #    sits comfortably inside Android's circular/squircle mask.
    save_rgba(src, f"{OUT_DIR}/adaptive-icon.png", 1024, inner_scale=0.86)

    # 3) Splash icon — full size RGBA so transparency lets the splash bg show.
    save_rgba(src, f"{OUT_DIR}/splash-icon.png", 1024, inner_scale=1.0)

    # 4) Favicon — small opaque PNG.
    save_opaque(src, f"{OUT_DIR}/favicon.png", 64)

    # 5) Google Play Store listing icon — 512x512 RGB, no alpha.
    save_opaque(src, f"{OUT_DIR}/play-store-icon.png", 512)

    # 6) Marketing/press preview.
    save_opaque(src, f"{OUT_DIR}/marketing-icon-256.png", 256)

    print("Generated icons:")
    for name in (
        "icon.png",
        "adaptive-icon.png",
        "splash-icon.png",
        "favicon.png",
        "play-store-icon.png",
        "marketing-icon-256.png",
    ):
        path = f"{OUT_DIR}/{name}"
        with Image.open(path) as im:
            print(f"  {name}: {im.size} {im.mode}")


if __name__ == "__main__":
    main()
