from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

from core.config import Settings


@dataclass
class RenderResult:
    image: Image.Image
    boxes: dict[str, tuple[int, int, int, int]]


def font_for(settings: Settings, size: int):
    names = {'Arial': ('arial.ttf','arialbd.ttf'), 'Segoe UI': ('segoeui.ttf','segoeuib.ttf'),
             'Calibri': ('calibri.ttf','calibrib.ttf'), 'Tahoma': ('tahoma.ttf','tahomabd.ttf'),
             'Verdana': ('verdana.ttf','verdanab.ttf'), 'Times New Roman': ('times.ttf','timesbd.ttf')}
    pair = names.get(settings.font_name, names['Arial'])
    candidates = [settings.font_path, 'C:/Windows/Fonts/' + pair[int(settings.bold)],
                  'C:/Windows/Fonts/segoeuib.ttf' if settings.bold else 'C:/Windows/Fonts/segoeui.ttf',
                  '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if settings.bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for path in candidates:
        if path and Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


def render(image: Image.Image, settings: Settings, logo: Image.Image | None = None) -> RenderResult:
    base = ImageOps.exif_transpose(image).convert('RGBA')
    w, h = base.size
    scale = min(w, h)
    boxes = {}
    if settings.logo_enabled and (logo is not None or (settings.logo_path and Path(settings.logo_path).is_file())):
        if logo is None:
            with Image.open(settings.logo_path) as source:
                logo = source.convert('RGBA').copy()
        if logo.width and logo.height:
            lw = max(1, round(scale * max(.02, min(.9, settings.logo_size))))
            lh = max(1, round(lw * logo.height / logo.width))
            mark = logo.resize((lw, lh), Image.Resampling.LANCZOS)
            mark.putalpha(mark.getchannel('A').point(lambda a: a * max(0, min(100, settings.logo_opacity)) // 100))
            x = round(settings.logo_x * w - lw / 2)
            y = round(settings.logo_y * h - lh / 2)
            x, y = min(max(0, x), max(0, w-lw)), min(max(0, y), max(0, h-lh))
            base.alpha_composite(mark, (x, y))
            boxes['logo'] = (x, y, x+lw, y+lh)
    if settings.phone_enabled and settings.phone.strip():
        font_size = max(8, round(scale * max(.008, min(.3, settings.font_size))))
        stroke = max(0, round(scale * settings.stroke_width))
        font = font_for(settings, font_size)
        draw = ImageDraw.Draw(base)
        bbox = draw.textbbox((0, 0), settings.phone, font=font, stroke_width=stroke)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        x = min(max(0, round(settings.phone_x*w-tw/2)), max(0, w-tw))
        y = min(max(0, round(settings.phone_y*h-th/2)), max(0, h-th))
        actual = (x-bbox[0], y-bbox[1])
        if settings.shadow:
            off = max(1, round(scale*.003))
            draw.text((actual[0]+off, actual[1]+off), settings.phone, font=font, fill='#00000088', stroke_width=stroke, stroke_fill='#00000088')
        draw.text(actual, settings.phone, font=font, fill=settings.text_color,
                  stroke_width=stroke, stroke_fill=settings.stroke_color)
        boxes['phone'] = (x, y, x+tw, y+th)
    return RenderResult(base, boxes)
