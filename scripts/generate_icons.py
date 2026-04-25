"""Generate KlarPost app icons at all required sizes.

Design: white envelope on solid trust-blue background with a clean blue
checkmark inside the envelope. Renders at 4x supersample then downsamples
with LANCZOS for crisp edges.
"""

from PIL import Image, ImageDraw

BRAND_BLUE = (29, 78, 216)  # #1D4ED8
WHITE = (255, 255, 255)


def render_icon(size: int, mode: str = "full_bleed") -> Image.Image:
    """Render an icon.

    mode:
      - "full_bleed": solid blue background + envelope (no transparency)
      - "badge": self-contained blue rounded-square badge on transparent bg
                 (good for splash + adaptive foreground that may sit on any bg)
      - "foreground": bare white envelope on transparent bg (Android adaptive
                      foreground when backgroundColor handles the blue)
    """
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background layer
    if mode == "full_bleed":
        d.rectangle([0, 0, s, s], fill=BRAND_BLUE)
        symbol_scale = 1.0
    elif mode == "badge":
        # Blue rounded-square badge centered, leaves transparent margin so the
        # logo reads as a self-contained blue chip on any backdrop.
        margin = int(s * 0.12)
        radius = int(s * 0.22)  # similar curvature to iOS app icon mask
        d.rounded_rectangle(
            [margin, margin, s - margin, s - margin],
            radius=radius,
            fill=BRAND_BLUE,
        )
        symbol_scale = 0.74
    else:  # foreground
        # No background — just the envelope sized for Android safe zone (66%).
        symbol_scale = 0.6

    # Envelope dimensions
    env_w = int(s * 0.58 * symbol_scale)
    env_h = int(s * 0.42 * symbol_scale)
    cx, cy = s // 2, s // 2
    x1 = cx - env_w // 2
    y1 = cy - env_h // 2
    x2 = cx + env_w // 2
    y2 = cy + env_h // 2
    env_radius = int(env_h * 0.14)

    # Envelope body
    body_color = WHITE if mode != "foreground" else WHITE
    d.rounded_rectangle([x1, y1, x2, y2], radius=env_radius, fill=body_color)

    # Subtle envelope flap line — two soft strokes from top corners meeting
    # at the centre. Drawn in brand blue so it reads as the fold of the flap
    # when the envelope is white on blue.
    flap_thickness = max(2, int(env_h * 0.07))
    flap_bottom_y = y1 + int(env_h * 0.42)
    flap_color = BRAND_BLUE if mode != "foreground" else (210, 220, 240)
    inset = env_radius + flap_thickness // 2
    d.line(
        [(x1 + inset, y1 + inset), (cx, flap_bottom_y)],
        fill=flap_color,
        width=flap_thickness,
    )
    d.line(
        [(x2 - inset, y1 + inset), (cx, flap_bottom_y)],
        fill=flap_color,
        width=flap_thickness,
    )

    # Check-mark inside the envelope, positioned in the lower half so it sits
    # below the flap and reads as "letter + verified".
    check_color = BRAND_BLUE if mode != "foreground" else BRAND_BLUE
    check_thickness = max(3, int(env_h * 0.13))
    cx_ck = cx
    cy_ck = cy + int(env_h * 0.16)
    cw = int(env_w * 0.46)
    ch = int(cw * 0.48)
    p1 = (cx_ck - cw // 2, cy_ck)
    p2 = (cx_ck - int(cw * 0.10), cy_ck + ch // 2)
    p3 = (cx_ck + cw // 2, cy_ck - ch // 2)
    d.line([p1, p2, p3], fill=check_color, width=check_thickness, joint="curve")
    # Round the stroke endpoints with small filled circles for a clean cap.
    half = check_thickness // 2
    for pt in (p1, p2, p3):
        d.ellipse(
            [pt[0] - half, pt[1] - half, pt[0] + half, pt[1] + half],
            fill=check_color,
        )

    # Downsample to target size
    return img.resize((size, size), Image.LANCZOS)


def save_jpeg_safe_png(img: Image.Image, path: str, opaque_bg=None):
    """Save a PNG. If opaque_bg is provided, flatten transparency onto it
    (required for the iOS App Store icon which forbids any alpha)."""
    if opaque_bg is None:
        img.save(path, "PNG")
        return
    base = Image.new("RGB", img.size, opaque_bg)
    if img.mode == "RGBA":
        base.paste(img, mask=img.split()[3])
    else:
        base.paste(img)
    base.save(path, "PNG")


if __name__ == "__main__":
    out_dir = "/app/frontend/assets/images"

    # 1) iOS main app icon — 1024×1024, NO alpha (Apple rejects transparency).
    icon = render_icon(1024, mode="full_bleed")
    save_jpeg_safe_png(icon, f"{out_dir}/icon.png", opaque_bg=BRAND_BLUE)

    # 2) Android adaptive foreground — 1024×1024 with the blue badge baked
    #    into the foreground so it works regardless of the device backdrop.
    adaptive = render_icon(1024, mode="badge")
    adaptive.save(f"{out_dir}/adaptive-icon.png", "PNG")

    # 3) Splash icon — same self-contained badge, transparent margins.
    splash = render_icon(1024, mode="badge")
    splash.save(f"{out_dir}/splash-icon.png", "PNG")

    # 4) Favicon — small, opaque, full-bleed.
    fav = render_icon(64, mode="full_bleed")
    save_jpeg_safe_png(fav, f"{out_dir}/favicon.png", opaque_bg=BRAND_BLUE)

    # 5) Google Play Store listing icon — 512×512 RGB, no alpha.
    play_store = render_icon(512, mode="full_bleed")
    save_jpeg_safe_png(play_store, f"{out_dir}/play-store-icon.png", opaque_bg=BRAND_BLUE)

    # 6) Marketing preview at 256 (handy for App Store screenshots / press kits)
    preview = render_icon(256, mode="full_bleed")
    save_jpeg_safe_png(preview, f"{out_dir}/marketing-icon-256.png", opaque_bg=BRAND_BLUE)

    print("Generated icons:")
    for name in (
        "icon.png",
        "adaptive-icon.png",
        "splash-icon.png",
        "favicon.png",
        "play-store-icon.png",
        "marketing-icon-256.png",
    ):
        path = f"{out_dir}/{name}"
        with Image.open(path) as im:
            print(f"  {name}: {im.size} {im.mode}")
