"""
Generates marketing assets for easli.app landing page:
- og.png: 1200x630 Open Graph image for link previews (WhatsApp / iMessage / X / FB)
- apple-touch-icon.png: 180x180 iOS home-screen icon

Uses PIL with Liberation Sans Bold (Inter-like fallback).
Run from /app/landing/: python3 _make_assets.py
"""
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# easli brand
BRAND = (31, 111, 235)        # #1F6FEB
BRAND_DARK = (15, 76, 175)    # darker shade for gradient
WHITE = (255, 255, 255)
TEXT = (12, 22, 51)
SUBTLE = (76, 93, 130)
ACCENT = (31, 111, 235)
SOFT_BG = (240, 246, 255)

FONT_BOLD = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"


def rounded_rect(draw, xy, radius, fill):
    """Draw a rounded rect — PIL has it natively but kept for clarity."""
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def make_logo_tile(size, radius_ratio=0.22):
    """Returns a PIL Image: blue rounded square with white 'e' centered."""
    radius = int(size * radius_ratio)
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rounded_rect(draw, (0, 0, size, size), radius, BRAND)

    # white 'e' centered — use ~62% of size as font size so it sits visually centered
    font_size = int(size * 0.62)
    try:
        font = ImageFont.truetype(FONT_BOLD, font_size)
    except Exception:
        font = ImageFont.load_default()

    # measure
    bbox = draw.textbbox((0, 0), "e", font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    # text bbox top is offset; correct position so optical center matches geometric center
    x = (size - tw) / 2 - bbox[0]
    y = (size - th) / 2 - bbox[1] - int(size * 0.02)  # nudge up slightly
    draw.text((x, y), "e", fill=WHITE, font=font)
    return img


def make_apple_touch_icon():
    img = make_logo_tile(180)
    # iOS adds rounded corners automatically, but providing a rounded one looks good in older iOS
    # Save as opaque (iOS prefers no alpha for touch icons)
    bg = Image.new("RGB", (180, 180), WHITE)
    bg.paste(img, (0, 0), img)
    bg.save("/app/landing/apple-touch-icon.png", "PNG", optimize=True)
    print("✅ apple-touch-icon.png (180x180) generated")


def make_og_image():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), SOFT_BG)
    draw = ImageDraw.Draw(img)

    # ---- Background: subtle gradient from soft-blue to white (top-left to bottom-right) ----
    grad = Image.new("RGB", (W, H), SOFT_BG)
    g = grad.load()
    for y in range(H):
        for x in range(W):
            # diagonal blend
            t = (x / W * 0.4 + y / H * 0.6)
            r = int(SOFT_BG[0] * (1 - t * 0.5) + 255 * t * 0.5)
            gg = int(SOFT_BG[1] * (1 - t * 0.5) + 255 * t * 0.5)
            b = int(SOFT_BG[2] * (1 - t * 0.5) + 255 * t * 0.5)
            g[x, y] = (r, gg, b)
    img.paste(grad)
    draw = ImageDraw.Draw(img)

    # ---- Soft blue blob top-right (decorative) ----
    blob = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    blob_draw = ImageDraw.Draw(blob)
    blob_draw.ellipse((W - 480, -180, W + 80, 380), fill=(31, 111, 235, 38))
    blob_draw.ellipse((W - 320, 280, W + 40, 720), fill=(31, 111, 235, 25))
    blob = blob.filter(ImageFilter.GaussianBlur(radius=40))
    img.paste(blob, (0, 0), blob)
    draw = ImageDraw.Draw(img)

    # ---- Logo + brand top-left ----
    logo = make_logo_tile(72)
    img.paste(logo, (72, 60), logo)

    brand_font = ImageFont.truetype(FONT_BOLD, 38)
    draw.text((160, 75), "easli", fill=TEXT, font=brand_font)

    # ---- Eyebrow ----
    eyebrow_font = ImageFont.truetype(FONT_BOLD, 24)
    draw.rounded_rectangle((72, 200, 410, 244), radius=22, fill=(255, 255, 255), outline=BRAND, width=2)
    draw.text((92, 207), "PAPERWORK. MADE SIMPLE.", fill=BRAND, font=eyebrow_font)

    # ---- Hero Headline ----
    headline_font = ImageFont.truetype(FONT_BOLD, 76)
    line1 = "Behördenpost"
    line2 = "klar erklärt."
    draw.text((72, 270), line1, fill=TEXT, font=headline_font)
    draw.text((72, 358), line2, fill=BRAND, font=headline_font)

    # ---- Subline ----
    sub_font = ImageFont.truetype(FONT_REG, 28)
    draw.text((72, 462), "In deiner Sprache. In unter zwei Minuten.", fill=SUBTLE, font=sub_font)

    # ---- Bottom badges (text-only, no emojis to avoid font fallback issues) ----
    badges = ["EU-gehostet", "DSGVO-konform", "25 Sprachen"]
    badge_font = ImageFont.truetype(FONT_BOLD, 22)
    bx = 72
    by = 530
    for b in badges:
        bbox = draw.textbbox((0, 0), b, font=badge_font)
        bw = bbox[2] - bbox[0] + 56  # extra room for dot indicator
        bh = 48
        draw.rounded_rectangle((bx, by, bx + bw, by + bh), radius=24, fill=WHITE, outline=(210, 222, 240), width=1)
        # blue dot indicator
        dot_r = 6
        dot_cx = bx + 20
        dot_cy = by + bh // 2
        draw.ellipse((dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r), fill=BRAND)
        draw.text((bx + 36, by + 11), b, fill=TEXT, font=badge_font)
        bx += bw + 12

    # ---- Big logo on the right side ----
    big_logo = make_logo_tile(380, radius_ratio=0.22)
    # subtle drop shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((W - 380 - 80 + 8, 130 + 16, W - 80 + 8, 130 + 380 + 16), radius=int(380 * 0.22), fill=(31, 111, 235, 60))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=24))
    img.paste(shadow, (0, 0), shadow)
    img.paste(big_logo, (W - 380 - 80, 130), big_logo)

    img.save("/app/landing/og.png", "PNG", optimize=True)
    print("✅ og.png (1200x630) generated")


if __name__ == "__main__":
    make_apple_touch_icon()
    make_og_image()
    print("\n🎉 Done. Files written to /app/landing/")
