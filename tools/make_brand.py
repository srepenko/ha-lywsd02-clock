"""Generate brand/ icons for the integration (LYWSD02 e-ink clock + sync badge).

python tools/make_brand.py  ->  custom_components/lywsd02_clock/brand/*.png
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parents[1] / "custom_components" / "lywsd02_clock" / "brand"
FONT_BOLD = "C:/Windows/Fonts/bahnschrift.ttf"  # DIN-like, good for clock digits
S = 1024  # draw large, downsample for anti-aliasing


def font(size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FONT_BOLD, size)
    try:
        f.set_variation_by_name(weight)
    except Exception:
        pass
    return f


def draw_icon(dark: bool) -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # soft shadow
    sh = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((92, 112, 932, 952), 150, fill=(0, 0, 0, 110 if dark else 70))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(28)))

    d = ImageDraw.Draw(img)
    body = (236, 239, 242) if not dark else (226, 230, 234)
    d.rounded_rectangle((80, 80, 944, 944), 150, fill=body, outline=(178, 186, 194), width=10)

    # e-ink screen
    screen = (205, 214, 200)
    d.rounded_rectangle((150, 150, 874, 874), 70, fill=screen)
    ink = (38, 44, 48)

    # time
    t = "12:34"
    f_time = font(300)
    w = d.textlength(t, font=f_time)
    d.text(((S - w) / 2, 200), t, font=f_time, fill=ink)

    # divider
    d.line((200, 560, 824, 560), fill=(150, 160, 150), width=8)

    # thermometer glyph
    tx, ty = 215, 615
    d.rounded_rectangle((tx, ty, tx + 44, ty + 150), 22, outline=ink, width=12)
    d.ellipse((tx - 22, ty + 130, tx + 66, ty + 218), fill=ink)
    d.rectangle((tx + 14, ty + 60, tx + 30, ty + 150), fill=ink)
    f_small = font(132, "SemiBold")
    d.text((tx + 80, ty + 40), "22°", font=f_small, fill=ink)

    # humidity droplet
    hx, hy = 505, 645
    d.polygon([(hx + 35, hy), (hx - 5, hy + 80), (hx + 75, hy + 80)], fill=ink)
    d.ellipse((hx - 12, hy + 50, hx + 82, hy + 144), fill=ink)
    d.text((hx + 92, ty + 40), "45", font=f_small, fill=ink)

    # sync badge (bottom-right)
    cx, cy, r = 858, 858, 128
    d.ellipse((cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), fill=body if not dark else (34, 38, 42))
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(3, 169, 244))
    a = 66
    white = (255, 255, 255)
    d.arc((cx - a, cy - a, cx + a, cy + a), 200, 340, fill=white, width=26)
    d.arc((cx - a, cy - a, cx + a, cy + a), 20, 160, fill=white, width=26)
    # arrow heads
    d.polygon([(cx + a + 1, cy - 50), (cx + a + 38, cy + 4), (cx + a - 36, cy + 4)], fill=white)
    d.polygon([(cx - a - 1, cy + 50), (cx - a - 38, cy - 4), (cx - a + 36, cy - 4)], fill=white)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for dark in (False, True):
        big = draw_icon(dark)
        prefix = "dark_" if dark else ""
        for name, size in (("icon", 256), ("icon@2x", 512), ("logo", 256), ("logo@2x", 512)):
            big.resize((size, size), Image.LANCZOS).save(OUT / f"{prefix}{name}.png", optimize=True)
    print("written to", OUT)


if __name__ == "__main__":
    main()
