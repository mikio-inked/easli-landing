"""Generate 3 on-brand onboarding illustrations for KlarPost using Gemini
Nano Banana (gemini-3.1-flash-image-preview) via the Emergent LLM key.

Run once to populate /app/frontend/assets/images/onb_*.png. Re-run any time
you want new variants — output is deterministic enough for our purposes but
each call produces fresh artwork.
"""

import asyncio
import base64
import os
import sys
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage

load_dotenv("/app/backend/.env")

OUT_DIR = "/app/frontend/assets/images"
MODEL = "gemini-3.1-flash-image-preview"

# A shared style preamble that anchors all 3 illustrations to the same brand
# language so they feel like a coherent set.
STYLE = (
    "Soft 3D illustration, friendly minimal modern flat-3D style with subtle "
    "soft shadows. Calm blue and white palette using exactly these colors: "
    "primary blue #2563EB and #1D4ED8, light backdrop #EFF4FF to #F8FAFC "
    "gradient, accents in white. Ultra clean, generous whitespace, centered "
    "composition, square 1:1 aspect ratio, NO text or letters or numbers "
    "anywhere in the image. Soft glow / subtle highlights. No people faces. "
    "Looks like a premium iOS app onboarding illustration. Avoid stock "
    "photo look. Avoid checkmarks. Avoid 3D-render plastic look. Optimised "
    "for white app background."
)

PROMPTS = [
    (
        "onb1_translate.png",
        f"{STYLE} A calm illustration of a paper letter with a few abstract "
        "lines of text being gently translated: one side shows German-style "
        "abstract script, the other side a softer simplified script, with a "
        "translucent speech bubble in soft blue floating above the letter "
        "indicating clarity. The whole composition feels reassuring and "
        "approachable, no stress, no exclamation marks. Subject centered.",
    ),
    (
        "onb2_deadlines.png",
        f"{STYLE} A clean calendar block illustration with a soft blue "
        "highlighted day, paired with a floating tiny clock and a stylized "
        "to-do list panel beside it showing abstract horizontal lines (no "
        "real text). Optional gentle pencil. Friendly, calm, organised "
        "feeling — implies 'next steps and deadlines under control'. "
        "Elements grouped together centred in frame.",
    ),
    (
        "onb3_privacy.png",
        f"{STYLE} A soft glassy blue padlock floating gently over a folded "
        "letter, surrounded by a faint protective halo or shield outline. "
        "Implies privacy and safety without being aggressive. The padlock "
        "is rounded, friendly, premium-feeling, and partially translucent. "
        "Centred composition, no chains, no faces, no text.",
    ),
]


async def gen_one(filename: str, prompt: str):
    api_key = os.getenv("EMERGENT_LLM_KEY")
    if not api_key:
        raise RuntimeError("EMERGENT_LLM_KEY not set in /app/backend/.env")

    chat = LlmChat(
        api_key=api_key,
        session_id=f"klarpost-onb-{filename}",
        system_message=(
            "You are an art director generating premium iOS app onboarding "
            "illustrations. Always return one image."
        ),
    )
    chat.with_model("gemini", MODEL).with_params(modalities=["image", "text"])

    msg = UserMessage(text=prompt)
    text, images = await chat.send_message_multimodal_response(msg)
    print(f"[{filename}] text reply: {text[:120] if text else '(none)'}")
    if not images:
        raise RuntimeError(f"No image returned for {filename}")
    img = images[0]
    image_bytes = base64.b64decode(img["data"])
    out_path = os.path.join(OUT_DIR, filename)
    # Gemini Nano Banana sometimes returns JPEG bytes regardless of the
    # requested file extension. Always re-encode through PIL to guarantee
    # we save a real PNG (Android AAPT2 rejects JPEG-in-PNG files at build
    # time with "file failed to compile").
    from io import BytesIO
    from PIL import Image
    pil_img = Image.open(BytesIO(image_bytes)).convert("RGB")
    pil_img.save(out_path, "PNG", optimize=True)
    size = os.path.getsize(out_path)
    print(f"[{filename}] saved {size // 1024} KB -> {out_path}")


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    # Run sequentially to avoid rate-limiting and to keep logs readable.
    for filename, prompt in PROMPTS:
        try:
            await gen_one(filename, prompt)
        except Exception as e:
            print(f"[{filename}] FAILED: {e}", file=sys.stderr)
            raise


if __name__ == "__main__":
    asyncio.run(main())
