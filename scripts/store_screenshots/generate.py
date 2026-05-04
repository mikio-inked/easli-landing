"""
easli App Store Screenshot Generator

Generates 55 marketing screenshots (5 scenes × 11 UI languages) at
1290 × 2796 px (Apple's 6.9" iPhone requirement).

Each screenshot has:
  - Brand gradient background
  - Headline + subline at top
  - Device mockup (iPhone 15 Pro Max silhouette) showing a mock of the app UI
    in the matching language

Usage:
  python3 generate.py              # renders all 11 locales × 5 scenes
  python3 generate.py --only en    # renders one locale
  python3 generate.py --scenes 1,4 # renders selected scenes
"""
import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from strings import FLAGS, HEADLINES, LANGS, MOCK_UI, SUBLINES  # noqa: E402

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:
    arabic_reshaper = None
    get_display = None

# ─────────────────────────────────────────────────────────────────────────
#  Constants
# ─────────────────────────────────────────────────────────────────────────
W, H = 1290, 2796
OUT_DIR = Path(__file__).parent / "out"

# Brand colours
BRAND = "#1F6FEB"
BRAND_DARK = "#0F4FB8"
BG_TOP = "#EEF4FF"
BG_MID = "#F5F8FF"
BG_BOTTOM = "#FFFFFF"
TEXT_DARK = "#0F2540"
TEXT_MUTED = "#556783"
DEVICE_BEZEL = "#0C121E"
CARD_BG = "#FFFFFF"
CARD_BORDER = "#E3EAF5"
SURFACE_SOFT = "#F3F6FB"
ACCENT_GREEN = "#17B26A"
ACCENT_AMBER = "#F59E0B"
ACCENT_RED = "#EF4444"

# Font paths
F_LATIN_BOLD = "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"
F_LATIN_REG = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
F_ARABIC_BOLD = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf"
F_ARABIC_REG = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
F_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
F_CJK_BOLD = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def font(size: int, bold: bool = False, script: str = "latin") -> ImageFont.FreeTypeFont:
    if script == "arabic":
        path = F_ARABIC_BOLD if bold else F_ARABIC_REG
        return ImageFont.truetype(path, size)
    if script == "cjk":
        path = F_CJK_BOLD if bold else F_CJK
        return ImageFont.truetype(path, size)
    path = F_LATIN_BOLD if bold else F_LATIN_REG
    return ImageFont.truetype(path, size)


def shape_rtl(text: str) -> str:
    """Reshape + bidi-reorder Arabic text for correct PIL rendering."""
    if arabic_reshaper is None or get_display is None:
        return text
    return get_display(arabic_reshaper.reshape(text))


def text_for(s: str, script: str) -> str:
    """Apply RTL shaping for Arabic strings; pass others through."""
    if script == "arabic":
        return shape_rtl(s)
    return s


# ─────────────────────────────────────────────────────────────────────────
#  Primitive helpers
# ─────────────────────────────────────────────────────────────────────────
def gradient_background(img: Image.Image) -> None:
    """Vertical gradient BG_TOP → BG_BOTTOM, with a subtle brand accent band."""
    draw = ImageDraw.Draw(img)
    top = tuple(int(BG_TOP[i:i + 2], 16) for i in (1, 3, 5))
    mid = tuple(int(BG_MID[i:i + 2], 16) for i in (1, 3, 5))
    bot = tuple(int(BG_BOTTOM[i:i + 2], 16) for i in (1, 3, 5))
    for y in range(H):
        if y < H * 0.45:
            t = y / (H * 0.45)
            c = tuple(int(top[i] + (mid[i] - top[i]) * t) for i in range(3))
        else:
            t = (y - H * 0.45) / (H * 0.55)
            c = tuple(int(mid[i] + (bot[i] - mid[i]) * t) for i in range(3))
        draw.line([(0, y), (W, y)], fill=c)


def rounded_rect(draw: ImageDraw.ImageDraw, xy, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_shadow(img: Image.Image, xy, radius, blur=40, alpha=90):
    """Cast a soft shadow rectangle onto img."""
    x1, y1, x2, y2 = xy
    pad = blur + 10
    shadow = Image.new("RGBA", (x2 - x1 + pad * 2, y2 - y1 + pad * 2), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (pad, pad, x2 - x1 + pad, y2 - y1 + pad),
        radius=radius,
        fill=(0, 0, 0, alpha),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(shadow, (x1 - pad, y1 - pad + 20))


def measure(text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    """Return (w, h) of text in given font."""
    bbox = fnt.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def draw_text_centered(draw, xy, text, fnt, fill):
    x, y = xy
    w, h = measure(text, fnt)
    draw.text((x - w / 2, y), text, font=fnt, fill=fill)


def draw_multiline_centered(draw, cx, y, lines, fnt, fill, line_height_mult=1.1):
    """Draw multi-line text, each line horizontally centered around cx."""
    ascent, descent = fnt.getmetrics()
    lh = int((ascent + descent) * line_height_mult)
    for i, line in enumerate(lines):
        w, _ = measure(line, fnt)
        draw.text((cx - w / 2, y + i * lh), line, font=fnt, fill=fill)
    return y + len(lines) * lh


def draw_flag(draw, xy, lang_code, size=(80, 56)):
    """Tiny simplified flag rectangle."""
    x, y = xy
    fw, fh = size
    orient, colors = FLAGS.get(lang_code, ("h", ["#AAAAAA"] * 3))
    # soft shadow / border
    draw.rounded_rectangle((x - 2, y - 2, x + fw + 2, y + fh + 2), radius=8, fill="#E8ECF2")
    if orient == "h":
        band_h = fh / len(colors)
        for i, c in enumerate(colors):
            draw.rectangle((x, y + i * band_h, x + fw, y + (i + 1) * band_h), fill=c)
    else:
        band_w = fw / len(colors)
        for i, c in enumerate(colors):
            draw.rectangle((x + i * band_w, y, x + (i + 1) * band_w, y + fh), fill=c)
    # mask to rounded
    mask = Image.new("L", (fw, fh), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, fw, fh), radius=8, fill=255)


# ─────────────────────────────────────────────────────────────────────────
#  Headline + subline at top
# ─────────────────────────────────────────────────────────────────────────
def draw_top_marketing(img, locale, scene, script):
    draw = ImageDraw.Draw(img)
    headline = HEADLINES[scene][locale]
    subline = SUBLINES[scene][locale]

    # Arabic shaping
    h_lines = [text_for(ln, script) for ln in headline.split("\n")]
    sub = text_for(subline, script)

    # Headline size depends on text length
    longest = max((len(ln) for ln in h_lines), default=0)
    size = 110 if longest <= 18 else (94 if longest <= 24 else 80)

    f_head = font(size, bold=True, script=script)
    f_sub = font(44, bold=False, script=script)

    y = 130
    y = draw_multiline_centered(draw, W / 2, y, h_lines, f_head, TEXT_DARK, 1.04)
    y += 22
    # subline (single line, but may need wrapping if very long)
    sw, _ = measure(sub, f_sub)
    if sw > W - 160:
        # try 2 lines by splitting on last space around middle
        mid = len(sub) // 2
        sp = sub.rfind(" ", 0, mid + 10)
        if sp > 0:
            s1, s2 = sub[:sp].strip(), sub[sp:].strip()
            draw_multiline_centered(draw, W / 2, y, [s1, s2], f_sub, TEXT_MUTED, 1.12)
        else:
            draw_multiline_centered(draw, W / 2, y, [sub], f_sub, TEXT_MUTED, 1.12)
    else:
        draw_multiline_centered(draw, W / 2, y, [sub], f_sub, TEXT_MUTED, 1.12)


# ─────────────────────────────────────────────────────────────────────────
#  Device mockup (iPhone 15 Pro Max silhouette)
# ─────────────────────────────────────────────────────────────────────────
DEVICE_W, DEVICE_H = 960, 1950
DEVICE_X = (W - DEVICE_W) // 2
DEVICE_Y = 720  # top of device frame

# Inner screen (inside bezel) — bezel is 24px on sides, 28 top/bottom
BEZEL = 24
SCREEN_X = DEVICE_X + BEZEL
SCREEN_Y = DEVICE_Y + BEZEL
SCREEN_W = DEVICE_W - BEZEL * 2
SCREEN_H = DEVICE_H - BEZEL * 2
SCREEN_R = 86  # inner rounded corner radius
DEVICE_R = 110  # outer device corner radius


def draw_device_frame(img, screen_bg="#FFFFFF"):
    """Draw the iPhone silhouette with screen filled in screen_bg.
       Returns a sub-image / canvas where scene content can be drawn."""
    draw_shadow(img, (DEVICE_X, DEVICE_Y, DEVICE_X + DEVICE_W, DEVICE_Y + DEVICE_H), DEVICE_R, blur=50, alpha=110)
    draw = ImageDraw.Draw(img)
    # outer bezel
    rounded_rect(
        draw,
        (DEVICE_X, DEVICE_Y, DEVICE_X + DEVICE_W, DEVICE_Y + DEVICE_H),
        radius=DEVICE_R,
        fill=DEVICE_BEZEL,
    )
    # inner screen
    rounded_rect(
        draw,
        (SCREEN_X, SCREEN_Y, SCREEN_X + SCREEN_W, SCREEN_Y + SCREEN_H),
        radius=SCREEN_R,
        fill=screen_bg,
    )
    # Dynamic Island
    island_w, island_h = 280, 38
    ix = SCREEN_X + (SCREEN_W - island_w) // 2
    iy = SCREEN_Y + 26
    rounded_rect(
        draw,
        (ix, iy, ix + island_w, iy + island_h),
        radius=island_h // 2,
        fill="#0C121E",
    )
    # status bar: time left, icons right (subtle)
    f_time = font(26, bold=True, script="latin")
    draw.text((SCREEN_X + 48, iy + 2), "9:41", font=f_time, fill=TEXT_DARK)
    # battery
    batx = SCREEN_X + SCREEN_W - 90
    rounded_rect(draw, (batx, iy + 10, batx + 62, iy + 28), radius=4, outline=TEXT_DARK, width=2)
    draw.rectangle((batx + 3, iy + 13, batx + 55, iy + 25), fill=TEXT_DARK)


# Helper: content area (below status bar, above home indicator)
def content_box():
    top = SCREEN_Y + 100  # below status bar
    bottom = SCREEN_Y + SCREEN_H - 60
    return SCREEN_X + 36, top, SCREEN_X + SCREEN_W - 36, bottom


def draw_home_indicator(img):
    draw = ImageDraw.Draw(img)
    bar_w, bar_h = 280, 8
    bx = SCREEN_X + (SCREEN_W - bar_w) // 2
    by = SCREEN_Y + SCREEN_H - 28
    rounded_rect(draw, (bx, by, bx + bar_w, by + bar_h), radius=4, fill="#0C121E")


# ─────────────────────────────────────────────────────────────────────────
#  Scene renderers
# ─────────────────────────────────────────────────────────────────────────
def _draw_app_header(img, locale, script, title, subtitle=None):
    draw = ImageDraw.Draw(img)
    cx, top, cxr, _ = content_box()
    f_brand = font(32, bold=True, script="latin")
    # little "e" logo badge
    lx, ly = cx, top + 10
    rounded_rect(draw, (lx, ly, lx + 50, ly + 50), radius=14, fill=BRAND)
    draw.text((lx + 14, ly + 4), "e", font=font(38, bold=True, script="latin"), fill="#FFFFFF")
    draw.text((lx + 66, ly + 12), "easli", font=f_brand, fill=TEXT_DARK)
    y = ly + 80
    # title
    f_title = font(60, bold=True, script=script)
    t_text = text_for(title, script)
    anchor_x = cxr if script == "arabic" else cx
    tw, _ = measure(t_text, f_title)
    if script == "arabic":
        draw.text((anchor_x - tw, y), t_text, font=f_title, fill=TEXT_DARK)
    else:
        draw.text((anchor_x, y), t_text, font=f_title, fill=TEXT_DARK)
    y += 78
    if subtitle:
        f_sub = font(32, bold=False, script=script)
        s_text = text_for(subtitle, script)
        sw, _ = measure(s_text, f_sub)
        if script == "arabic":
            draw.text((anchor_x - sw, y), s_text, font=f_sub, fill=TEXT_MUTED)
        else:
            draw.text((anchor_x, y), s_text, font=f_sub, fill=TEXT_MUTED)
        y += 50
    return y + 20


def _draw_primary_cta(img, locale, script, label):
    draw = ImageDraw.Draw(img)
    cx, _, cxr, bottom = content_box()
    btn_h = 92
    btn_y = bottom - btn_h - 30
    rounded_rect(draw, (cx, btn_y, cxr, btn_y + btn_h), radius=btn_h // 2, fill=BRAND)
    f_btn = font(34, bold=True, script=script)
    t = text_for(label, script)
    w, _ = measure(t, f_btn)
    draw.text(((cx + cxr) / 2 - w / 2, btn_y + (btn_h - 40) / 2), t, font=f_btn, fill="#FFFFFF")


def render_scene_1_language(img, locale, script):
    """Onboarding — language picker with 11 languages."""
    ui = MOCK_UI[1][locale]
    y = _draw_app_header(img, locale, script, ui["title"], ui["sub"])
    draw = ImageDraw.Draw(img)
    cx, _, cxr, _ = content_box()
    # 7 language rows (enough to show the variety, list scrolls)
    selected_lang = locale
    visible = [c for c, *_ in LANGS][:7]
    row_h = 108
    gap = 14
    f_name = font(32, bold=True, script="latin")
    f_en = font(24, bold=False, script="latin")
    for i, code in enumerate(visible):
        native, script_of, *_ = next(((c[1], c[2]) for c in LANGS if c[0] == code), ("", "latin"))
        ry = y + i * (row_h + gap)
        if ry + row_h > content_box()[3] - 150:
            break
        is_sel = code == selected_lang
        rounded_rect(
            draw,
            (cx, ry, cxr, ry + row_h),
            radius=24,
            fill="#E8F0FE" if is_sel else CARD_BG,
            outline=BRAND if is_sel else CARD_BORDER,
            width=2 if is_sel else 1,
        )
        draw_flag(draw, (cx + 28, ry + (row_h - 56) // 2), code, (80, 56))
        # Use CJK font for Chinese native name, Arabic for Arabic
        name_script = "cjk" if code == "zh" else ("arabic" if code == "ar" else "latin")
        f_native = font(34, bold=True, script=name_script)
        native_text = text_for(native, name_script)
        draw.text((cx + 136, ry + 22), native_text, font=f_native, fill=TEXT_DARK)
        # english subname (except for English itself)
        eng = next((c[0] for c in LANGS if c[0] == code), "")
        eng_map = {
            "de": "German", "en": "English", "fr": "French", "it": "Italian",
            "es": "Spanish", "pl": "Polish", "ar": "Arabic", "tr": "Turkish",
            "ru": "Russian", "vi": "Vietnamese", "zh": "Chinese",
        }
        draw.text((cx + 136, ry + 60), eng_map.get(eng, ""), font=f_en, fill=TEXT_MUTED)
        # checkmark on selected
        if is_sel:
            bx = cxr - 78
            by = ry + (row_h - 48) // 2
            rounded_rect(draw, (bx, by, bx + 48, by + 48), radius=24, fill=BRAND)
            # checkmark
            draw.line([(bx + 14, by + 26), (bx + 22, by + 34), (bx + 36, by + 16)], fill="#FFFFFF", width=5)
    _draw_primary_cta(img, locale, script, ui["cta"])


def render_scene_2_home(img, locale, script):
    """Home — welcome + big scan CTA + recent list."""
    ui = MOCK_UI[2][locale]
    y = _draw_app_header(img, locale, script, ui["title"])
    draw = ImageDraw.Draw(img)
    cx, _, cxr, _ = content_box()
    # Hero CTA card (big scan button with camera icon)
    card_h = 340
    rounded_rect(draw, (cx, y, cxr, y + card_h), radius=28, fill=BRAND)
    # subtle gradient overlay via a translucent darker rect at top
    # Camera icon (drawn shape)
    icon_cx, icon_cy = (cx + cxr) / 2, y + 120
    # lens
    draw.ellipse((icon_cx - 60, icon_cy - 60, icon_cx + 60, icon_cy + 60), outline="#FFFFFF", width=8)
    draw.ellipse((icon_cx - 28, icon_cy - 28, icon_cx + 28, icon_cy + 28), fill="#FFFFFF")
    # viewfinder corners
    for dx, dy in [(-105, -75), (105, -75), (-105, 75), (105, 75)]:
        x0 = icon_cx + dx
        y0 = icon_cy + dy
        if dx < 0 and dy < 0:
            draw.line([(x0, y0 + 22), (x0, y0), (x0 + 22, y0)], fill="#FFFFFF", width=6)
        elif dx > 0 and dy < 0:
            draw.line([(x0 - 22, y0), (x0, y0), (x0, y0 + 22)], fill="#FFFFFF", width=6)
        elif dx < 0 and dy > 0:
            draw.line([(x0, y0 - 22), (x0, y0), (x0 + 22, y0)], fill="#FFFFFF", width=6)
        else:
            draw.line([(x0 - 22, y0), (x0, y0), (x0, y0 - 22)], fill="#FFFFFF", width=6)
    # CTA label
    f_cta = font(42, bold=True, script=script)
    t = text_for(ui["cta"], script)
    w, _ = measure(t, f_cta)
    draw.text(((cx + cxr) / 2 - w / 2, y + card_h - 100), t, font=f_cta, fill="#FFFFFF")
    y += card_h + 48

    # "Recent" heading
    f_h = font(34, bold=True, script=script)
    t_recent = text_for(ui["recent"], script)
    if script == "arabic":
        w, _ = measure(t_recent, f_h)
        draw.text((cxr - w, y), t_recent, font=f_h, fill=TEXT_DARK)
    else:
        draw.text((cx, y), t_recent, font=f_h, fill=TEXT_DARK)
    y += 56

    # Recent items (2)
    for idx, (item_key, ago_key, color) in enumerate([
        ("item1", "ago1", ACCENT_RED),
        ("item2", "ago2", ACCENT_AMBER),
    ]):
        item = ui[item_key]
        ago = ui[ago_key]
        rh = 130
        rounded_rect(draw, (cx, y, cxr, y + rh), radius=22, fill=CARD_BG, outline=CARD_BORDER, width=1)
        # icon square
        ix, iy = cx + 22, y + (rh - 78) // 2
        rounded_rect(draw, (ix, iy, ix + 78, iy + 78), radius=18, fill="#EEF2F9")
        # document icon lines
        draw.rectangle((ix + 22, iy + 22, ix + 56, iy + 26), fill=BRAND)
        draw.rectangle((ix + 22, iy + 36, ix + 50, iy + 40), fill="#9AB1D1")
        draw.rectangle((ix + 22, iy + 50, ix + 56, iy + 54), fill="#9AB1D1")
        # text
        f_item = font(28, bold=True, script="cjk" if locale == "zh" else ("arabic" if script == "arabic" else "latin"))
        f_ago = font(22, bold=False, script="cjk" if locale == "zh" else ("arabic" if script == "arabic" else "latin"))
        item_t = text_for(item, script)
        ago_t = text_for(ago, script)
        if script == "arabic":
            tw, _ = measure(item_t, f_item)
            draw.text((cxr - tw - 120, y + 22), item_t, font=f_item, fill=TEXT_DARK)
            aw, _ = measure(ago_t, f_ago)
            draw.text((cxr - aw - 120, y + 64), ago_t, font=f_ago, fill=TEXT_MUTED)
        else:
            draw.text((ix + 100, y + 22), item_t, font=f_item, fill=TEXT_DARK)
            draw.text((ix + 100, y + 64), ago_t, font=f_ago, fill=TEXT_MUTED)
        # urgency dot
        dot_x = cxr - 36 if script != "arabic" else cx + 24
        draw.ellipse((dot_x - 10, y + 24, dot_x + 10, y + 44), fill=color)
        y += rh + 16


def render_scene_3_scan(img, locale, script):
    """Scan / camera view — dark background, doc outline detected."""
    ui = MOCK_UI[3][locale]
    draw = ImageDraw.Draw(img)
    # Override screen bg dark
    rounded_rect(
        draw,
        (SCREEN_X, SCREEN_Y, SCREEN_X + SCREEN_W, SCREEN_Y + SCREEN_H),
        radius=SCREEN_R,
        fill="#0A0F18",
    )
    # redraw Dynamic Island on top
    island_w, island_h = 280, 38
    ix = SCREEN_X + (SCREEN_W - island_w) // 2
    iy = SCREEN_Y + 26
    rounded_rect(draw, (ix, iy, ix + island_w, iy + island_h), radius=island_h // 2, fill="#000000")
    # light status bar
    draw.text((SCREEN_X + 48, iy + 2), "9:41", font=font(26, bold=True), fill="#FFFFFF")

    cx, top, cxr, bottom = content_box()
    # Top hint bar
    hint = text_for(ui["hint"], script)
    f_hint = font(28, bold=False, script=script)
    hw, _ = measure(hint, f_hint)
    hint_y = top + 20
    rounded_rect(draw, ((W - hw - 80) // 2, hint_y, (W + hw + 80) // 2, hint_y + 60), radius=30, fill="#FFFFFF30")
    draw.text(((W - hw) // 2, hint_y + 10), hint, font=f_hint, fill="#FFFFFF")

    # Document viewfinder rectangle (detected doc with corners)
    vx1, vx2 = cx + 40, cxr - 40
    vy1, vy2 = top + 180, bottom - 340
    # doc "ghost" (slightly lighter fill + corners)
    rounded_rect(draw, (vx1, vy1, vx2, vy2), radius=28, fill="#FFFFFF14", outline="#17B26A", width=5)
    # corner brackets
    cl = 60
    for cxy in [(vx1, vy1), (vx2, vy1), (vx1, vy2), (vx2, vy2)]:
        xc, yc = cxy
        if xc == vx1 and yc == vy1:
            draw.line([(xc, yc + cl), (xc, yc), (xc + cl, yc)], fill="#FFFFFF", width=8)
        elif xc == vx2 and yc == vy1:
            draw.line([(xc - cl, yc), (xc, yc), (xc, yc + cl)], fill="#FFFFFF", width=8)
        elif xc == vx1 and yc == vy2:
            draw.line([(xc, yc - cl), (xc, yc), (xc + cl, yc)], fill="#FFFFFF", width=8)
        else:
            draw.line([(xc - cl, yc), (xc, yc), (xc, yc - cl)], fill="#FFFFFF", width=8)

    # mock doc text lines inside frame
    for i in range(8):
        ty = vy1 + 80 + i * 62
        draw.rectangle((vx1 + 60, ty, vx2 - 60 - (i * 40 % 180), ty + 8), fill="#FFFFFFAA")

    # Status pill
    status_y = vy2 + 30
    rounded_rect(
        draw,
        ((W - 400) // 2, status_y, (W + 400) // 2, status_y + 72),
        radius=36,
        fill=ACCENT_GREEN,
    )
    f_st = font(30, bold=True, script=script)
    st_t = text_for(ui["status"], script)
    stw, _ = measure(st_t, f_st)
    draw.text(((W - stw) // 2, status_y + 18), st_t, font=f_st, fill="#FFFFFF")

    # Page indicator
    pg_y = status_y + 100
    f_pg = font(26, bold=False, script=script)
    pg_t = text_for(ui["page"], script)
    pgw, _ = measure(pg_t, f_pg)
    draw.text(((W - pgw) // 2, pg_y), pg_t, font=f_pg, fill="#C6D0DE")

    # Capture button (big circle)
    btn_y = bottom - 140
    btn_cx = (cx + cxr) / 2
    # outer ring
    draw.ellipse((btn_cx - 62, btn_y - 62, btn_cx + 62, btn_y + 62), outline="#FFFFFF", width=6)
    # inner solid
    draw.ellipse((btn_cx - 48, btn_y - 48, btn_cx + 48, btn_y + 48), fill="#FFFFFF")


def render_scene_4_result(img, locale, script):
    """Result — doc title + AI summary bullets + deadline callout."""
    ui = MOCK_UI[4][locale]
    y = _draw_app_header(img, locale, script, ui["summary"])
    draw = ImageDraw.Draw(img)
    cx, _, cxr, _ = content_box()

    # Document header card (doc title + from)
    card_h = 180
    rounded_rect(draw, (cx, y, cxr, y + card_h), radius=22, fill=SURFACE_SOFT)
    f_doc = font(36, bold=True, script=script)
    f_from = font(26, bold=False, script=script)
    doc_t = text_for(ui["doc"], script)
    from_t = text_for(ui["from"], script)
    # Document icon
    ix, iy = cx + 24, y + 34
    rounded_rect(draw, (ix, iy, ix + 110, iy + 110), radius=18, fill=BRAND)
    draw.rectangle((ix + 24, iy + 28, ix + 86, iy + 36), fill="#FFFFFF")
    draw.rectangle((ix + 24, iy + 52, ix + 72, iy + 58), fill="#FFFFFFA0")
    draw.rectangle((ix + 24, iy + 72, ix + 86, iy + 78), fill="#FFFFFFA0")
    if script == "arabic":
        tw, _ = measure(doc_t, f_doc)
        draw.text((cxr - tw - 24, y + 40), doc_t, font=f_doc, fill=TEXT_DARK)
        fw, _ = measure(from_t, f_from)
        draw.text((cxr - fw - 24, y + 92), from_t, font=f_from, fill=TEXT_MUTED)
    else:
        draw.text((ix + 134, y + 40), doc_t, font=f_doc, fill=TEXT_DARK)
        draw.text((ix + 134, y + 92), from_t, font=f_from, fill=TEXT_MUTED)
    y += card_h + 28

    # Bullet points (3)
    bullets = [ui["b1"], ui["b2"], ui["b3"]]
    bullet_colors = [BRAND, ACCENT_GREEN, ACCENT_AMBER]
    f_bullet = font(28, bold=False, script=script)
    for i, b in enumerate(bullets):
        b_text = text_for(b, script)
        # wrap manually
        words = b_text.split(" ")
        max_w = cxr - cx - 100
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if measure(test, f_bullet)[0] <= max_w:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        rh = 40 + len(lines) * 44
        rounded_rect(draw, (cx, y, cxr, y + rh), radius=18, fill=CARD_BG, outline=CARD_BORDER, width=1)
        # bullet dot
        draw.ellipse((cx + 24, y + 26, cx + 46, y + 48), fill=bullet_colors[i])
        # lines
        for j, ln in enumerate(lines):
            if script == "arabic":
                lw, _ = measure(ln, f_bullet)
                draw.text((cxr - lw - 32, y + 20 + j * 44), ln, font=f_bullet, fill=TEXT_DARK)
            else:
                draw.text((cx + 66, y + 20 + j * 44), ln, font=f_bullet, fill=TEXT_DARK)
        y += rh + 16

    # Deadline pill at bottom
    _, _, _, bottom = content_box()
    pill_h = 120
    pill_y = bottom - pill_h - 20
    rounded_rect(draw, (cx, pill_y, cxr, pill_y + pill_h), radius=24, fill="#FFF4E5", outline=ACCENT_AMBER, width=2)
    # calendar icon
    icx, icy = cx + 26, pill_y + 28
    rounded_rect(draw, (icx, icy, icx + 66, icy + 66), radius=12, fill=ACCENT_AMBER)
    draw.rectangle((icx + 12, icy + 22, icx + 54, icy + 30), fill="#FFFFFF")
    draw.rectangle((icx + 12, icy + 38, icx + 54, icy + 50), fill="#FFFFFFAA")
    f_dl = font(26, bold=False, script=script)
    f_dv = font(34, bold=True, script=script)
    dl_t = text_for(ui["deadline_label"], script)
    dv_t = text_for(ui["deadline"], script)
    if script == "arabic":
        dlw, _ = measure(dl_t, f_dl)
        draw.text((cxr - dlw - 28, pill_y + 24), dl_t, font=f_dl, fill="#8B5A1C")
        dvw, _ = measure(dv_t, f_dv)
        draw.text((cxr - dvw - 28, pill_y + 56), dv_t, font=f_dv, fill=TEXT_DARK)
    else:
        draw.text((icx + 92, pill_y + 24), dl_t, font=f_dl, fill="#8B5A1C")
        draw.text((icx + 92, pill_y + 56), dv_t, font=f_dv, fill=TEXT_DARK)


def render_scene_5_reply(img, locale, script):
    """Reply / draft — intent chips + email compose UI."""
    ui = MOCK_UI[5][locale]
    y = _draw_app_header(img, locale, script, ui["title"])
    draw = ImageDraw.Draw(img)
    cx, _, cxr, _ = content_box()

    # Intent chips row
    chips = [ui["chip1"], ui["chip2"], ui["chip3"]]
    chip_y = y
    f_chip = font(26, bold=True, script=script)
    chip_h = 64
    gap = 12
    # Layout chips (LTR default; RTL will position in reverse)
    chip_widths = []
    for c in chips:
        t = text_for(c, script)
        w, _ = measure(t, f_chip)
        chip_widths.append(w + 56)
    total_w = sum(chip_widths) + gap * (len(chips) - 1)
    x = cx if total_w <= cxr - cx else cx
    scale = 1.0
    if total_w > cxr - cx:
        scale = (cxr - cx) / total_w
    for i, c in enumerate(chips):
        w = int(chip_widths[i] * scale)
        is_active = (i == 0)
        rounded_rect(draw, (x, chip_y, x + w, chip_y + chip_h), radius=chip_h // 2,
                     fill=BRAND if is_active else CARD_BG,
                     outline=BRAND if is_active else CARD_BORDER, width=2)
        t = text_for(c, script)
        tw, _ = measure(t, f_chip)
        tcolor = "#FFFFFF" if is_active else TEXT_DARK
        draw.text((x + (w - tw) / 2, chip_y + (chip_h - 34) / 2), t, font=f_chip, fill=tcolor)
        x += w + gap
    y = chip_y + chip_h + 32

    # "To" field
    f_lbl = font(22, bold=False, script=script)
    f_val = font(28, bold=True, script=script)

    def field(label, value, yy):
        rh = 104
        rounded_rect(draw, (cx, yy, cxr, yy + rh), radius=18, fill=CARD_BG, outline=CARD_BORDER, width=1)
        lbl_t = text_for(label, script)
        val_t = text_for(value, script)
        if script == "arabic":
            lw, _ = measure(lbl_t, f_lbl)
            draw.text((cxr - lw - 24, yy + 16), lbl_t, font=f_lbl, fill=TEXT_MUTED)
            vw, _ = measure(val_t, f_val)
            draw.text((cxr - vw - 24, yy + 50), val_t, font=f_val, fill=TEXT_DARK)
        else:
            draw.text((cx + 24, yy + 16), lbl_t, font=f_lbl, fill=TEXT_MUTED)
            draw.text((cx + 24, yy + 50), val_t, font=f_val, fill=TEXT_DARK)
        return yy + rh + 16

    y = field(ui["to"], ui["to_val"], y)
    y = field(ui["subject"], ui["subject_val"], y)

    # Body (multi-line)
    body_lines_raw = [ui["body1"], ui["body2"]]
    # body_lines_raw[1] is long — wrap it
    max_w = cxr - cx - 48
    f_body = font(26, bold=False, script=script)
    wrapped = []
    for raw in body_lines_raw:
        txt = text_for(raw, script)
        words = txt.split(" ")
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if measure(test, f_body)[0] <= max_w:
                cur = test
            else:
                if cur:
                    wrapped.append(cur)
                cur = w
        if cur:
            wrapped.append(cur)
        wrapped.append("")  # paragraph break

    # Body card
    body_h = 60 + len(wrapped) * 40
    rounded_rect(draw, (cx, y, cxr, y + body_h), radius=18, fill=SURFACE_SOFT)
    for i, line in enumerate(wrapped):
        if script == "arabic":
            lw, _ = measure(line, f_body)
            draw.text((cxr - lw - 24, y + 24 + i * 40), line, font=f_body, fill=TEXT_DARK)
        else:
            draw.text((cx + 24, y + 24 + i * 40), line, font=f_body, fill=TEXT_DARK)

    # CTA "Open in Mail"
    _draw_primary_cta(img, locale, script, ui["cta"])


SCENE_RENDERERS = {
    1: render_scene_1_language,
    2: render_scene_2_home,
    3: render_scene_3_scan,
    4: render_scene_4_result,
    5: render_scene_5_reply,
}

SCENE_NAMES = {
    1: "01-language-picker",
    2: "02-home",
    3: "03-scan",
    4: "04-result",
    5: "05-reply",
}


def render(locale: str, script: str, scene: int) -> Image.Image:
    img = Image.new("RGBA", (W, H), (255, 255, 255, 255))
    gradient_background(img)
    draw_top_marketing(img, locale, scene, script)
    draw_device_frame(img, screen_bg="#FFFFFF")
    SCENE_RENDERERS[scene](img, locale, script)
    draw_home_indicator(img)
    # easli watermark at very bottom
    draw = ImageDraw.Draw(img)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="Comma-separated locales (e.g. de,en)", default="")
    ap.add_argument("--scenes", help="Comma-separated scene numbers (1..5)", default="1,2,3,4,5")
    ap.add_argument("--out", help="Output directory", default=str(OUT_DIR))
    args = ap.parse_args()

    only = [x.strip() for x in args.only.split(",") if x.strip()]
    scenes = [int(x) for x in args.scenes.split(",") if x.strip()]

    out_base = Path(args.out)
    out_base.mkdir(parents=True, exist_ok=True)

    for code, native, script, rtl in LANGS:
        if only and code not in only:
            continue
        lang_dir = out_base / f"ios-6.9-{code}"
        lang_dir.mkdir(parents=True, exist_ok=True)
        for scene in scenes:
            print(f"Rendering {code} scene {scene}...", flush=True)
            img = render(code, script, scene)
            out_path = lang_dir / f"{SCENE_NAMES[scene]}-{code}.png"
            # Flatten alpha before saving PNG (Apple wants no alpha channel)
            rgb = Image.new("RGB", img.size, (255, 255, 255))
            rgb.paste(img, mask=img.split()[3])
            rgb.save(out_path, "PNG", optimize=True)
    print(f"\n✅ Done. Output: {out_base}")


if __name__ == "__main__":
    main()
