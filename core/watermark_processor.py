from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

from core.config import Settings


@dataclass
class RenderResult:
    image: Image.Image
    boxes: dict[str, tuple[int, int, int, int]]


def font_for(settings: Settings, size: int, bold: bool | None = None):
    if bold is None:
        bold = settings.bold
    names = {'Arial': ('arial.ttf','arialbd.ttf'), 'Segoe UI': ('segoeui.ttf','segoeuib.ttf'),
             'Calibri': ('calibri.ttf','calibrib.ttf'), 'Tahoma': ('tahoma.ttf','tahomabd.ttf'),
             'Verdana': ('verdana.ttf','verdanab.ttf'), 'Times New Roman': ('times.ttf','timesbd.ttf')}
    pair = names.get(settings.font_name, names['Arial'])
    mac_names = {
        'Arial': ('Arial.ttf', 'Arial Bold.ttf'),
        'Helvetica': ('Helvetica.ttc', 'Helvetica.ttc'),
        'Times New Roman': ('Times New Roman.ttf', 'Times New Roman Bold.ttf'),
        'Verdana': ('Verdana.ttf', 'Verdana Bold.ttf'),
        'Tahoma': ('Tahoma.ttf', 'Tahoma Bold.ttf'),
    }
    mac_pair = mac_names.get(settings.font_name, mac_names['Arial'])
    candidates = [settings.font_path if bold == settings.bold else '',
                  '/System/Library/Fonts/Supplemental/' + mac_pair[int(bold)],
                  '/Library/Fonts/' + mac_pair[int(bold)],
                  '/System/Library/Fonts/Helvetica.ttc',
                  'C:/Windows/Fonts/' + pair[int(bold)],
                  'C:/Windows/Fonts/segoeuib.ttf' if bold else 'C:/Windows/Fonts/segoeui.ttf',
                  '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
    for path in candidates:
        if path and Path(path).is_file():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)


def wrap_text(text: str, draw: ImageDraw.ImageDraw, font, max_width: int) -> str:
    """Keep explicit line breaks and wrap long lines to the image width."""
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
            continue
        line = ''
        for word in paragraph.split(' '):
            proposed = f'{line} {word}' if line else word
            if line and draw.textlength(proposed, font=font) > max_width:
                lines.append(line)
                line = word
            else:
                line = proposed
            # Split a word that is itself wider than the available image width.
            while line and draw.textlength(line, font=font) > max_width:
                cut = max(1, len(line) - 1)
                while cut > 1 and draw.textlength(line[:cut], font=font) > max_width:
                    cut -= 1
                lines.append(line[:cut])
                line = line[cut:]
        lines.append(line)
    return '\n'.join(lines)


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
    if settings.custom_enabled and settings.custom_text.strip():
        font_size = max(8, round(scale * max(.008, min(.3, settings.custom_font_size))))
        stroke = max(0, round(scale * settings.custom_stroke_width))
        font = font_for(settings, font_size, settings.custom_bold)
        draw = ImageDraw.Draw(base)
        content = wrap_text(settings.custom_text, draw, font, max(1, round(w * .88)))
        spacing = max(2, round(font_size * .15))
        bbox = draw.multiline_textbbox((0, 0), content, font=font, spacing=spacing,
                                       stroke_width=stroke, align='center')
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        x = min(max(0, round(settings.custom_x*w-tw/2)), max(0, w-tw))
        y = min(max(0, round(settings.custom_y*h-th/2)), max(0, h-th))
        draw.multiline_text((x-bbox[0], y-bbox[1]), content, font=font, spacing=spacing,
                            align='center', fill=settings.custom_color, stroke_width=stroke,
                            stroke_fill=settings.custom_stroke_color)
        boxes['custom'] = (x, y, x+tw, y+th)
    return RenderResult(base, boxes)
