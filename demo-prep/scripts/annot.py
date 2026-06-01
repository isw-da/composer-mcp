"""Annotation helper: dim outside a box, fuchsia border, optional crop-zoom and label.

Usage:
    from annot import focus, crop_to
    focus('raw.png', 'out.png', box=(0.1, 0.2, 0.5, 0.4),
          label='Edit Calculations OFF', zoom=(1.6, 'right'))
    crop_to('raw.png', 'out.png', box=(0.1, 0.05, 0.9, 0.95),
            label='Branches Fields')

Box: (x1, y1, x2, y2) as pixels (ints) or relative floats all in [0, 1].
"""
from PIL import Image, ImageDraw, ImageFont

FUCHSIA = (197, 38, 126)   # D+A
SLATE = (46, 46, 45)
WHITE = (255, 255, 255)

FONT_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _font(size=18):
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _resolve_box(W, H, box):
    x1, y1, x2, y2 = box
    if all(isinstance(v, float) and 0 <= v <= 1 for v in box):
        return int(x1 * W), int(y1 * H), int(x2 * W), int(y2 * H)
    return int(x1), int(y1), int(x2), int(y2)


def _draw_label(im, x, y, text, font_size=20, anchor="bl"):
    """Draw a fuchsia pill with white text. anchor=bl|tl|br|tr|bc|tc."""
    d = ImageDraw.Draw(im)
    font = _font(font_size)
    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 10, 6
    bw, bh = tw + 2 * pad_x, th + 2 * pad_y
    if anchor == "bl":
        lx, ly = x, y - bh - 4
    elif anchor == "tl":
        lx, ly = x, y + 4
    elif anchor == "br":
        lx, ly = x - bw, y - bh - 4
    elif anchor == "tr":
        lx, ly = x - bw, y + 4
    elif anchor == "bc":
        lx, ly = x - bw // 2, y - bh - 4
    elif anchor == "tc":
        lx, ly = x - bw // 2, y + 4
    else:
        lx, ly = x, y
    lx = max(8, min(im.width - bw - 8, lx))
    ly = max(8, min(im.height - bh - 8, ly))
    d.rectangle((lx, ly, lx + bw, ly + bh), fill=FUCHSIA)
    d.text((lx + pad_x - bbox[0], ly + pad_y - bbox[1]), text, fill=WHITE, font=font)


def focus(src, dst, box, label=None, label_anchor="bl",
          zoom=None, dim=0.55, border=4, pad=0):
    """Dim outside `box`, draw a fuchsia border around it.

    zoom: None or (scale, side) where side in {right,left,top,bottom}.
    pad:  optional inflate of the box in pixels before drawing.
    """
    im = Image.open(src).convert("RGB")
    W, H = im.size
    x1, y1, x2, y2 = _resolve_box(W, H, box)
    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
    x2, y2 = min(W, x2 + pad), min(H, y2 + pad)

    dim_mask = Image.new("L", (W, H), int(255 * dim))
    ImageDraw.Draw(dim_mask).rectangle((x1, y1, x2, y2), fill=0)
    dim_layer = Image.new("RGB", (W, H), (0, 0, 0))
    im = Image.composite(dim_layer, im, dim_mask)

    d = ImageDraw.Draw(im)
    d.rectangle((x1, y1, x2, y2), outline=FUCHSIA, width=border)

    if zoom:
        scale, side = zoom
        raw = Image.open(src).convert("RGB").crop((x1, y1, x2, y2))
        zw = int(raw.width * scale)
        zh = int(raw.height * scale)
        max_w, max_h = int(W * 0.55), int(H * 0.7)
        if zw > max_w or zh > max_h:
            s = min(max_w / zw, max_h / zh)
            zw, zh = int(zw * s), int(zh * s)
        raw = raw.resize((zw, zh), Image.LANCZOS)
        ImageDraw.Draw(raw).rectangle((0, 0, zw - 1, zh - 1),
                                      outline=FUCHSIA, width=border)
        margin = 24
        if side == "right":
            px, py = W - zw - margin, max(margin, (H - zh) // 2)
        elif side == "left":
            px, py = margin, max(margin, (H - zh) // 2)
        elif side == "top":
            px, py = max(margin, (W - zw) // 2), margin
        else:
            px, py = max(margin, (W - zw) // 2), H - zh - margin
        im.paste(raw, (px, py))

    if label:
        anchor_x = x1
        anchor_y = y1
        if label_anchor in ("br", "tr"):
            anchor_x = x2
        if label_anchor in ("tl", "tr", "tc"):
            anchor_y = y2
        if label_anchor == "bc":
            anchor_x = (x1 + x2) // 2
        _draw_label(im, anchor_x, anchor_y, label, anchor=label_anchor)

    im.save(dst)
    return dst


def crop_to(src, dst, box, label=None, pad=0, target=(1280, 720)):
    """Crop to box (with pad), letterbox onto a slate canvas at `target` size."""
    im = Image.open(src).convert("RGB")
    W, H = im.size
    x1, y1, x2, y2 = _resolve_box(W, H, box)
    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
    x2, y2 = min(W, x2 + pad), min(H, y2 + pad)
    crop = im.crop((x1, y1, x2, y2))
    tw, th = target
    cw, ch = crop.size
    s = min(tw / cw, th / ch)
    nw, nh = int(cw * s), int(ch * s)
    crop = crop.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", target, (13, 13, 13))
    canvas.paste(crop, ((tw - nw) // 2, (th - nh) // 2))
    if label:
        _draw_label(canvas, 20, target[1] - 20, label, anchor="bl", font_size=22)
    canvas.save(dst)
    return dst
