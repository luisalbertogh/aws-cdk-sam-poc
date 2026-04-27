"""
Chef Assistant Logo Generator
Generates light and dark PNG logo variants.
"""
from PIL import Image, ImageDraw, ImageFont
import math

# ── Canvas config ──────────────────────────────────────────────────────────────
W, H = 560, 160
ICON_SIZE = 100          # icon bounding box
ICON_X, ICON_Y = 30, 30  # icon top-left
PAD = 20                 # gap between icon and text

FONT_BOLD   = "C:/Windows/Fonts/segoeuib.ttf"
FONT_LIGHT  = "C:/Windows/Fonts/segoeuil.ttf"
FONT_REG    = "C:/Windows/Fonts/segoeui.ttf"

# ── Colour palettes ────────────────────────────────────────────────────────────
THEMES = {
    "light": {
        "bg":          (255, 255, 255, 255),
        "hat_body":    (30,  58,  95,  255),   # deep navy
        "hat_band":    (255, 107, 53,  255),   # warm orange
        "bubble_bg":   (30,  58,  95,  255),
        "bubble_dot":  (255, 255, 255, 255),
        "title_chef":  (30,  58,  95,  255),
        "title_asst":  (255, 107, 53,  255),
        "subtitle":    (100, 116, 139, 255),
    },
    "dark": {
        "bg":          (15,  23,  42,  255),   # dark slate
        "hat_body":    (255, 255, 255, 255),
        "hat_band":    (255, 107, 53,  255),
        "bubble_bg":   (255, 107, 53,  255),
        "bubble_dot":  (255, 255, 255, 255),
        "title_chef":  (255, 255, 255, 255),
        "title_asst":  (255, 107, 53,  255),
        "subtitle":    (148, 163, 184, 255),
    },
}


def draw_chef_hat(draw, ox, oy, size, hat_color, band_color):
    """
    Draw a simplified toque (chef hat):
      - Puffy dome on top
      - Cylindrical body
      - Contrasting band at the bottom
    """
    s = size
    # -- dome (ellipse, slightly wider than body)
    dome_w, dome_h = int(s * 0.72), int(s * 0.50)
    dome_x = ox + (s - dome_w) // 2
    dome_y = oy
    draw.ellipse([dome_x, dome_y, dome_x + dome_w, dome_y + dome_h],
                 fill=hat_color)

    # -- body (rectangle connecting dome to band)
    body_w = int(s * 0.60)
    body_x = ox + (s - body_w) // 2
    body_top    = dome_y + dome_h // 2
    body_bottom = oy + int(s * 0.80)
    draw.rectangle([body_x, body_top, body_x + body_w, body_bottom],
                   fill=hat_color)

    # -- band / brim (slightly wider rounded rect)
    band_h = int(s * 0.18)
    band_w = int(s * 0.72)
    band_x = ox + (s - band_w) // 2
    band_y = body_bottom
    draw.rounded_rectangle([band_x, band_y, band_x + band_w, band_y + band_h],
                            radius=6, fill=band_color)


def draw_chat_bubble(draw, ox, oy, size, bubble_color, dot_color):
    """
    Small chat bubble overlapping the lower-right of the hat.
    """
    bw, bh = int(size * 0.46), int(size * 0.32)
    bx = ox + size - bw + int(size * 0.06)
    by = oy + size - bh - int(size * 0.04)

    # rounded rect bubble body
    draw.rounded_rectangle([bx, by, bx + bw, by + bh],
                            radius=bh // 3, fill=bubble_color)

    # tail (small triangle at bottom-left of bubble)
    tail_x, tail_y = bx + int(bw * 0.22), by + bh
    draw.polygon(
        [(tail_x, tail_y),
         (tail_x + int(bw * 0.18), tail_y),
         (tail_x + int(bw * 0.06), tail_y + int(size * 0.10))],
        fill=bubble_color,
    )

    # three dots inside bubble
    dot_r = max(3, int(bh * 0.15))
    dot_y_c = by + bh // 2
    spacing = bw // 4
    for i in range(3):
        cx = bx + spacing * (i + 1) - dot_r // 2 + int(bw * 0.02)
        draw.ellipse([cx - dot_r, dot_y_c - dot_r,
                      cx + dot_r, dot_y_c + dot_r],
                     fill=dot_color)


def make_logo(theme_name: str, out_path: str):
    colors = THEMES[theme_name]

    img  = Image.new("RGBA", (W, H), colors["bg"])
    draw = ImageDraw.Draw(img)

    # ── Icon ──────────────────────────────────────────────────────────────────
    draw_chef_hat(draw, ICON_X, ICON_Y, ICON_SIZE,
                  colors["hat_body"], colors["hat_band"])
    draw_chat_bubble(draw, ICON_X, ICON_Y, ICON_SIZE,
                     colors["bubble_bg"], colors["bubble_dot"])

    # ── Text ──────────────────────────────────────────────────────────────────
    tx = ICON_X + ICON_SIZE + PAD

    # "Chef" – bold, large
    font_chef = ImageFont.truetype(FONT_BOLD, 62)
    # "Assistant" – light, same line, slightly smaller
    font_asst = ImageFont.truetype(FONT_LIGHT, 48)
    # Tagline
    font_tag  = ImageFont.truetype(FONT_REG, 18)

    # measure widths to place side-by-side
    chef_bbox = draw.textbbox((0, 0), "Chef", font=font_chef)
    chef_w    = chef_bbox[2] - chef_bbox[0]

    # vertical center
    text_top = (H - 90) // 2

    draw.text((tx, text_top),           "Chef",      font=font_chef, fill=colors["title_chef"])
    draw.text((tx + chef_w + 8, text_top + 12), "Assistant", font=font_asst, fill=colors["title_asst"])

    # tagline
    draw.text((tx + 2, text_top + 68), "Your smart recipe guide",
              font=font_tag, fill=colors["subtitle"])

    # ── Save ──────────────────────────────────────────────────────────────────
    img.save(out_path, "PNG")
    print(f"Saved: {out_path}")


def make_favicon(out_path: str, size: int = 64):
    """
    Icon-only favicon rendered at `size`×`size` px on a transparent background.
    Uses the dark-theme palette (navy hat + orange band/bubble) so it reads well
    on both browser tabs (typically light) and dark-mode tabs.
    """
    colors = THEMES["light"]

    # Render at 4× for anti-aliasing, then downscale
    scale  = 4
    canvas = size * scale
    img    = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)

    margin  = int(canvas * 0.04)
    ic_size = canvas - 2 * margin

    draw_chef_hat(draw, margin, margin, ic_size,
                  colors["hat_body"], colors["hat_band"])
    draw_chat_bubble(draw, margin, margin, ic_size,
                     colors["bubble_bg"], colors["bubble_dot"])

    # Downscale with high-quality resampling
    img = img.resize((size, size), Image.LANCZOS)
    img.save(out_path, "PNG")
    print(f"Saved: {out_path}")


def draw_robot_head(draw, cx, face_top, face_bottom, face_color, eye_color, border_color):
    """
    Draw a robot face centred at cx, spanning face_top..face_bottom.
    Includes: rounded rectangular head, glowing eyes, LED mouth, side ear panels.
    """
    fh = face_bottom - face_top          # face height
    fw = int(fh * 0.92)                  # face width (slightly narrower)
    fl = cx - fw // 2
    fr = cx + fw // 2

    # ── Head body ─────────────────────────────────────────────────────────────
    draw.rounded_rectangle(
        [fl, face_top, fr, face_bottom],
        radius=int(fw * 0.16),
        fill=face_color,
        outline=border_color,
        width=max(2, int(fw * 0.025)),
    )

    # ── Side ear panels ───────────────────────────────────────────────────────
    ear_w = int(fw * 0.09)
    ear_h = int(fh * 0.24)
    ear_y = face_top + int(fh * 0.30)
    for ex_l, ex_r in [(fl - ear_w, fl), (fr, fr + ear_w)]:
        draw.rounded_rectangle(
            [ex_l, ear_y, ex_r, ear_y + ear_h],
            radius=max(2, int(ear_w * 0.35)),
            fill=face_color,
            outline=border_color,
            width=max(2, int(fw * 0.022)),
        )

    # ── Eyes ──────────────────────────────────────────────────────────────────
    eye_cy  = face_top + int(fh * 0.40)
    eye_r   = int(fw * 0.14)
    eye_gap = int(fw * 0.24)

    for ecx in [cx - eye_gap, cx + eye_gap]:
        # dark socket
        draw.ellipse(
            [ecx - eye_r, eye_cy - eye_r, ecx + eye_r, eye_cy + eye_r],
            fill=(8, 15, 35, 255),
        )
        # orange iris
        ir = int(eye_r * 0.68)
        draw.ellipse(
            [ecx - ir, eye_cy - ir, ecx + ir, eye_cy + ir],
            fill=eye_color,
        )
        # white glint
        gr = int(eye_r * 0.22)
        draw.ellipse(
            [ecx - ir // 2 - gr, eye_cy - ir // 2 - gr,
             ecx - ir // 2 + gr, eye_cy - ir // 2 + gr],
            fill=(255, 255, 255, 230),
        )

    # ── LED mouth ─────────────────────────────────────────────────────────────
    mh = int(fh * 0.11)
    mw = int(fw * 0.56)
    my = face_top + int(fh * 0.70)
    mx = cx - mw // 2
    draw.rounded_rectangle(
        [mx, my, mx + mw, my + mh],
        radius=mh // 2,
        fill=(8, 15, 35, 255),
    )
    # four LED dots inside the mouth bar
    dr = int(mh * 0.28)
    for i in range(4):
        dx = mx + int(mw * (i + 0.5) / 4)
        dy = my + mh // 2
        draw.ellipse([dx - dr, dy - dr, dx + dr, dy + dr], fill=eye_color)


def make_favicon_robot(out_path: str, size: int = 64):
    """
    Favicon showing a robot head wearing a chef hat.
    Rendered at 4× for anti-aliasing, then downscaled to `size`×`size` px.
    """
    HAT_COLOR    = (30,  58,  95,  255)   # deep navy
    BAND_COLOR   = (255, 107, 53,  255)   # warm orange
    FACE_COLOR   = (20,  40,  75,  255)   # slightly lighter navy for the face
    BORDER_COLOR = (70, 110, 170,  255)   # mid-blue border
    EYE_COLOR    = (255, 107, 53,  255)   # orange glow

    scale  = 4
    canvas = size * scale          # e.g. 256 × 256

    img  = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    cx = canvas // 2               # horizontal centre

    # ── Robot face occupies lower ~62 % ───────────────────────────────────────
    face_top    = int(canvas * 0.38)
    face_bottom = int(canvas * 0.97)

    draw_robot_head(draw, cx, face_top, face_bottom,
                    FACE_COLOR, EYE_COLOR, BORDER_COLOR)

    # ── Chef hat sits on top of the head ──────────────────────────────────────
    # Position hat so its band (at 80–98 % of hat_size) lands ~at face_top
    hat_size = int(canvas * 0.70)
    hat_ox   = cx - hat_size // 2
    # band_bottom = hat_oy + hat_size * 0.98  →  set that equal to face_top + overlap
    overlap  = int(canvas * 0.06)
    hat_oy   = face_top + overlap - int(hat_size * 0.98)

    draw_chef_hat(draw, hat_ox, hat_oy, hat_size, HAT_COLOR, BAND_COLOR)

    # ── Downscale ─────────────────────────────────────────────────────────────
    img = img.resize((size, size), Image.LANCZOS)
    img.save(out_path, "PNG")
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    out_dir = "chef-ui/public"
    make_logo("light", f"{out_dir}/chef_assistant_logo_light.png")
    make_logo("dark",  f"{out_dir}/chef_assistant_logo_dark.png")
    make_favicon(f"{out_dir}/favicon.png", size=64)

    # Robot-head favicon for the app
    make_favicon_robot("chef-ui/src/public/favicon.png", size=64)
    print("Done.")
