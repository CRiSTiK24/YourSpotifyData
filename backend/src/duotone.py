import io


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _grayscale_to_palette_gradient_luts(
    palette_hex: list[str],
) -> tuple[list[int], list[int], list[int]]:
    stops = sorted((_hex_to_rgb(c) for c in palette_hex), key=_luminance)
    n = len(stops)
    lut_r, lut_g, lut_b = [], [], []
    for i in range(256):
        pos = i / 255 * (n - 1)
        lo = int(pos)
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        r = stops[lo][0] + (stops[hi][0] - stops[lo][0]) * frac
        g = stops[lo][1] + (stops[hi][1] - stops[lo][1]) * frac
        b = stops[lo][2] + (stops[hi][2] - stops[lo][2]) * frac
        lut_r.append(int(r))
        lut_g.append(int(g))
        lut_b.append(int(b))
    return lut_r, lut_g, lut_b


def recolor_image(image_bytes: bytes, palette_hex: list[str], size: int | None = None) -> bytes:
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    if size:
        img = ImageOps.fit(img, (size, size), Image.LANCZOS)
    lut_r, lut_g, lut_b = _grayscale_to_palette_gradient_luts(palette_hex)
    out = Image.merge("RGB", (img.point(lut_r), img.point(lut_g), img.point(lut_b)))
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def resize_image(image_bytes: bytes, size: int | None = None) -> bytes:
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    if size:
        img = ImageOps.fit(img, (size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
