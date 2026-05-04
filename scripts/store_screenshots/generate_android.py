"""
Google Play Store assets generator for easli.

Produces:
  - Phone screenshots 1080×2160 (9:18 — within Play 2:1 ratio limit)
    Derived from the iOS 1290×2796 renders: downscale + center-crop.
  - Feature Graphic 1024×500 (per language) — brand hero banner.

Run AFTER `generate.py` has produced iOS screenshots in `out/ios-6.9-*/`.

Usage:
  python3 generate_android.py                 # all languages
  python3 generate_android.py --only de,en
"""
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from strings import HEADLINES, LANGS, SUBLINES  # noqa: E402

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = None
    get_display = None

HERE = Path(__file__).parent
IOS_OUT = HERE / "out"  # iOS screenshots source
AND_OUT = HERE / "out_android"  # Android screenshots destination

# Play Store phone screenshot target
PHONE_W, PHONE_H = 1080, 2160

# Play Store Feature Graphic
FG_W, FG_H = 1024, 500

# Fonts
F_LATIN_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
F_LATIN_REG = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
F_ARABIC_BOLD = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
F_ARABIC_REG = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
F_CJK_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
F_CJK_REG = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

BRAND = "#1F6FEB"
BRAND_DARK = "#0F4FB8"
BRAND_VERY_DARK = "#072357"
TEXT_DARK = "#0F2540"


def fnt(size: int, bold: bool = False, script: str = "latin") -> ImageFont.FreeTypeFont:
    if script == "arabic":
        return ImageFont.truetype(F_ARABIC_BOLD if bold else F_ARABIC_REG, size)
    if script == "cjk":
        return ImageFont.truetype(F_CJK_BOLD if bold else F_CJK_REG, size)
    return ImageFont.truetype(F_LATIN_BOLD if bold else F_LATIN_REG, size)


def shape(text: str, script: str) -> str:
    if script == "arabic" and arabic_reshaper and get_display:
        return get_display(arabic_reshaper.reshape(text))
    return text


def measure(text, f):
    b = f.getbbox(text)
    return b[2] - b[0], b[3] - b[1]


# ──────────────────────────────────────────────────────────────────
#  Phone screenshots — downscale + crop the iOS renders
# ──────────────────────────────────────────────────────────────────
def phone_from_ios(ios_path: Path, out_path: Path) -> None:
    img = Image.open(ios_path).convert("RGB")
    # iOS: 1290×2796 (ratio 2.167). Target: 1080×2160 (ratio 2.000).
    # Downscale uniformly by width-fit: 1080/1290 = 0.8372 → new H = 2796*0.8372 = 2341
    # Then center-crop to 2160 (losing ~90px each side of top/bottom padding).
    scale = PHONE_W / img.width  # 0.8372
    new_h = int(img.height * scale)
    resized = img.resize((PHONE_W, new_h), Image.LANCZOS)
    # center-crop
    crop_top = (new_h - PHONE_H) // 2
    cropped = resized.crop((0, crop_top, PHONE_W, crop_top + PHONE_H))
    cropped.save(out_path, "PNG", optimize=True)


# ──────────────────────────────────────────────────────────────────
#  Feature Graphic 1024×500
# ──────────────────────────────────────────────────────────────────
def tagline(locale: str) -> tuple[str, str]:
    """Returns (headline, subline) optimised for 1024×500 banner."""
    # Reuse scene-4 messaging (plain language / your language) — best brand fit
    head = HEADLINES[4][locale].replace("\n", " ").strip()
    # shorter subline tuned for banner width
    subs = {
        "de": "Brief scannen · KI erklärt · In 11 Sprachen",
        "en": "Scan letter · AI explains · 11 languages",
        "fr": "Scannez · L'IA explique · 11 langues",
        "it": "Scansiona · IA spiega · 11 lingue",
        "es": "Escanea · IA explica · 11 idiomas",
        "pl": "Skanuj · AI wyjaśnia · 11 języków",
        "ar": "امسح · الذكاء يشرح · 11 لغة",
        "tr": "Tara · AI açıklar · 11 dil",
        "ru": "Сканируй · ИИ объясняет · 11 языков",
        "vi": "Quét · AI giải thích · 11 ngôn ngữ",
        "zh": "扫描 · AI 解释 · 11 种语言",
    }
    return head, subs.get(locale, subs["en"])


def draw_feature_graphic(locale: str, script: str, out_path: Path) -> None:
    img = Image.new("RGB", (FG_W, FG_H), BRAND)
    draw = ImageDraw.Draw(img)

    # Diagonal gradient: deep brand blue top-left → lighter brand bottom-right
    top = tuple(int(BRAND_VERY_DARK[i:i + 2], 16) for i in (1, 3, 5))
    bot = tuple(int(BRAND[i:i + 2], 16) for i in (1, 3, 5))
    for y in range(FG_H):
        t = y / FG_H
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
        draw.line([(0, y), (FG_W, y)], fill=c)

    # Soft light orb top-right
    orb = Image.new("RGBA", (FG_W, FG_H), (0, 0, 0, 0))
    od = ImageDraw.Draw(orb)
    od.ellipse((FG_W - 600, -300, FG_W + 200, 500), fill=(255, 255, 255, 36))
    img = Image.alpha_composite(img.convert("RGBA"), orb).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Embed mini phone mockup of scene 4 (result) for this locale, if available
    scene4_path = IOS_OUT / f"ios-6.9-{locale}" / f"04-result-{locale}.png"
    if scene4_path.exists():
        mini = Image.open(scene4_path).convert("RGB")
        # crop to the device area (rough center crop of the upper/middle portion)
        # ios canvas is 1290×2796. Device is ~960×1950 starting at y=720.
        # Crop a tight area around the device + a little surrounding.
        crop_box = (150, 700, 1140, 2700)  # x1,y1,x2,y2
        mini_cropped = mini.crop(crop_box)  # 990×2000 ≈ 9:18 ratio
        # Target height within banner: 430 px (leaves 35 px margin top+bottom)
        target_h = 430
        scale = target_h / mini_cropped.height
        target_w = int(mini_cropped.width * scale)
        mini_scaled = mini_cropped.resize((target_w, target_h), Image.LANCZOS)
        # Tilt + shadow
        tilted = mini_scaled.rotate(-6, resample=Image.BICUBIC, expand=True)
        # Drop shadow behind mini
        shadow_size = tilted.size
        shadow = Image.new("RGBA", (shadow_size[0] + 80, shadow_size[1] + 80), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow)
        sd.rectangle((40, 40, shadow_size[0] + 40, shadow_size[1] + 40), fill=(0, 0, 0, 120))
        from PIL import ImageFilter
        shadow = shadow.filter(ImageFilter.GaussianBlur(22))
        # Place both
        px = FG_W - tilted.width - 40
        py = (FG_H - tilted.height) // 2
        img_rgba = img.convert("RGBA")
        img_rgba.alpha_composite(shadow, (px - 20, py - 10))
        img_rgba.paste(tilted, (px, py), tilted.convert("RGBA"))
        img = img_rgba.convert("RGB")
        draw = ImageDraw.Draw(img)

    # easli logo lockup (left)
    logo_x, logo_y = 54, 56
    # badge
    draw.rounded_rectangle((logo_x, logo_y, logo_x + 80, logo_y + 80), radius=20, fill="#FFFFFF")
    draw.text((logo_x + 24, logo_y + 4), "e", font=fnt(62, bold=True), fill=BRAND)
    draw.text((logo_x + 100, logo_y + 16), "easli", font=fnt(56, bold=True), fill="#FFFFFF")

    # Tagline
    head, sub = tagline(locale)
    head_s = shape(head, script)
    sub_s = shape(sub, script)

    # Head size depends on length
    sz_head = 64 if len(head_s) <= 24 else 54 if len(head_s) <= 32 else 46
    f_head = fnt(sz_head, bold=True, script=script)
    f_sub = fnt(22, bold=False, script=script)

    # position tagline below logo
    tx = logo_x
    ty = 190
    # allow the headline to wrap if too wide
    max_w = FG_W - 380  # leave room for envelope graphic
    hw, _ = measure(head_s, f_head)
    if hw > max_w:
        # try to break head at a space before the mid
        parts = head_s.split(" ")
        mid = len(parts) // 2
        line1 = " ".join(parts[:max(mid, 1)])
        line2 = " ".join(parts[max(mid, 1):])
        draw.text((tx, ty), line1, font=f_head, fill="#FFFFFF")
        draw.text((tx, ty + sz_head + 6), line2, font=f_head, fill="#FFFFFF")
        ty += (sz_head + 6) * 2 + 14
    else:
        draw.text((tx, ty), head_s, font=f_head, fill="#FFFFFF")
        ty += sz_head + 14

    draw.text((tx, ty), sub_s, font=f_sub, fill="#D8E5FB")

    img.save(out_path, "PNG", optimize=True)


# ──────────────────────────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────────────────────────
SCENE_FILES = [
    "01-language-picker",
    "02-home",
    "03-scan",
    "04-result",
    "05-reply",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="Comma-separated locales")
    args = ap.parse_args()
    only = [x.strip() for x in args.only.split(",") if x.strip()]

    AND_OUT.mkdir(exist_ok=True)

    missing_ios = []
    for code, _, script, _ in LANGS:
        if only and code not in only:
            continue

        ios_dir = IOS_OUT / f"ios-6.9-{code}"
        if not ios_dir.exists():
            missing_ios.append(code)
            continue

        and_dir = AND_OUT / f"android-phone-{code}"
        and_dir.mkdir(exist_ok=True)

        # Phone screenshots
        for scene_file in SCENE_FILES:
            src = ios_dir / f"{scene_file}-{code}.png"
            if not src.exists():
                continue
            dst = and_dir / f"{scene_file}-{code}.png"
            phone_from_ios(src, dst)
            print(f"  ✓ {dst.relative_to(HERE)}")

        # Feature graphic
        fg_path = and_dir / f"feature-graphic-{code}.png"
        draw_feature_graphic(code, script, fg_path)
        print(f"  ✓ {fg_path.relative_to(HERE)}")

    if missing_ios:
        print(
            f"\n⚠️  iOS screenshots missing for: {', '.join(missing_ios)}\n"
            f"   Run: python3 generate.py first."
        )
    print(f"\n✅ Android assets in: {AND_OUT}")


if __name__ == "__main__":
    main()
