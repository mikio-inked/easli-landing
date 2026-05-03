"""
Generates marketing assets for easli.app landing page using the REAL easli brand icon:
- og.png: 1200x630 Open Graph image for link previews (WhatsApp / iMessage / X / FB)
- apple-touch-icon.png: 180x180 iOS home-screen icon

Uses /app/frontend/assets/images/easli-icon-source.png (2048x2048 RGBA) as the canonical logo.
Text uses Liberation Sans Bold (Inter-like fallback).

Run: python3 _make_assets.py
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# easli brand palette (matches the icon gradient: blue -> teal/mint)
BRAND_BLUE = (31, 111, 235)          # #1F6FEB — primary
BRAND_BLUE_LIGHT = (70, 160, 245)    # lighter blend
BRAND_TEAL = (83, 215, 188)          # teal/mint accent from logo top-right
TEXT = (12, 22, 51)                  # #0C1633 — headline
SUBTLE = (76, 93, 130)               # #4C5D82 — sub-lede
WHITE = (255, 255, 255)
SOFT_BG = (240, 246, 255)

FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"

# Canonical source icon (2048x2048 RGBA)
SOURCE_ICON = "/app/frontend/assets/images/easli-icon-source.png"


def load_source_icon():
    return Image.open(SOURCE_ICON).convert("RGBA")


def resize_high_quality(img, size):
    return img.resize((size, size), Image.LANCZOS)


def make_apple_touch_icon():
    """180x180 iOS home-screen bookmark icon — just a crisp resize of the real logo."""
    src = load_source_icon()
    out = resize_high_quality(src, 180)
    # iOS prefers opaque PNG without alpha for touch-icons (safer across iOS versions)
    bg = Image.new("RGB", (180, 180), WHITE)
    bg.paste(out, (0, 0), out)
    bg.save("/app/landing/apple-touch-icon.png", "PNG", optimize=True)
    print("apple-touch-icon.png (180x180) — real easli logo")


def make_og_image():
    """1200x630 OG image: real logo on the right, marketing text on the left."""
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), SOFT_BG)
    draw = ImageDraw.Draw(img)

    # ---- Background: subtle top-left (white) to bottom-right (soft blue) gradient ----
    grad = Image.new("RGB", (W, H), SOFT_BG)
    g = grad.load()
    for y in range(H):
        for x in range(W):
            t_x = x / W
            t_y = y / H
            # mix: top-left mostly white, bottom-right mostly SOFT_BG
            mix = (1 - t_x * 0.5) * (1 - t_y * 0.3)
            r = int(SOFT_BG[0] * (1 - mix) + 255 * mix)
            gg = int(SOFT_BG[1] * (1 - mix) + 255 * mix)
            b = int(SOFT_BG[2] * (1 - mix) + 255 * mix)
            g[x, y] = (r, gg, b)
    img.paste(grad)

    # ---- Soft brand blobs (decorative, behind the logo on the right) ----
    blob = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blob)
    # teal/mint blob top-right
    bd.ellipse((W - 340, -140, W + 80, 300), fill=(*BRAND_TEAL, 60))
    # blue blob bottom-right
    bd.ellipse((W - 420, 260, W + 60, 780), fill=(*BRAND_BLUE, 45))
    blob = blob.filter(ImageFilter.GaussianBlur(radius=48))
    img.paste(blob, (0, 0), blob)
    draw = ImageDraw.Draw(img)

    # ---- Real logo (large) on the right side ----
    src = load_source_icon()
    LOGO_SIZE = 420
    logo = resize_high_quality(src, LOGO_SIZE)

    # Drop shadow behind the logo
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    logo_x = W - LOGO_SIZE - 70
    logo_y = (H - LOGO_SIZE) // 2
    sd.rounded_rectangle(
        (logo_x + 12, logo_y + 22, logo_x + LOGO_SIZE + 12, logo_y + LOGO_SIZE + 22),
        radius=int(LOGO_SIZE * 0.22),
        fill=(31, 111, 235, 70),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=32))
    img.paste(shadow, (0, 0), shadow)
    img.paste(logo, (logo_x, logo_y), logo)

    # ---- Brand lockup top-left (small logo + wordmark) ----
    small_logo = resize_high_quality(src, 64)
    img.paste(small_logo, (72, 64), small_logo)
    brand_font = ImageFont.truetype(FONT_BOLD, 38)
    draw.text((150, 76), "easli", fill=TEXT, font=brand_font)

    # ---- Eyebrow ----
    eyebrow_font = ImageFont.truetype(FONT_BOLD, 22)
    eb_text = "PAPERWORK. MADE SIMPLE."
    eb_bbox = draw.textbbox((0, 0), eb_text, font=eyebrow_font)
    eb_w = eb_bbox[2] - eb_bbox[0] + 36
    draw.rounded_rectangle((72, 195, 72 + eb_w, 195 + 42), radius=21, fill=WHITE, outline=BRAND_BLUE, width=2)
    draw.text((90, 203), eb_text, fill=BRAND_BLUE, font=eyebrow_font)

    # ---- Hero headline ----
    headline_font = ImageFont.truetype(FONT_BOLD, 72)
    draw.text((72, 260), "Behördenpost", fill=TEXT, font=headline_font)
    draw.text((72, 344), "klar erklärt.", fill=BRAND_BLUE, font=headline_font)

    # ---- Subline ----
    sub_font = ImageFont.truetype(FONT_REG, 26)
    draw.text((72, 446), "In deiner Sprache. In unter zwei Minuten.", fill=SUBTLE, font=sub_font)

    # ---- Bottom badges (text + dot) ----
    badges = ["EU-gehostet", "DSGVO-konform", "25 Sprachen"]
    badge_font = ImageFont.truetype(FONT_BOLD, 22)
    bx = 72
    by = 528
    for b in badges:
        bbox = draw.textbbox((0, 0), b, font=badge_font)
        bw = bbox[2] - bbox[0] + 56
        bh = 46
        draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=23, fill=WHITE, outline=(215, 225, 242), width=1)
        dot_r = 6
        dot_cx = bx + 20
        dot_cy = by + bh // 2
        draw.ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill=BRAND_BLUE)
        draw.text((bx + 36, by + 10), b, fill=TEXT, font=badge_font)
        bx += bw + 12

    img.save("/app/landing/og.png", "PNG", optimize=True)
    print("og.png (1200x630) — real easli logo")


if __name__ == "__main__":
    make_apple_touch_icon()
    make_og_image()
    print("Done. Files written to /app/landing/")
