from pathlib import Path
from PIL import Image, ImageOps

SUPPORTED = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}


def collect_images(paths):
    result, seen = [], set()
    for raw in paths:
        path = Path(raw)
        try:
            items = path.rglob('*') if path.is_dir() else [path]
            for item in items:
                if item.is_file() and item.suffix.lower() in SUPPORTED:
                    resolved = str(item.resolve())
                    if resolved not in seen:
                        result.append(resolved)
                        seen.add(resolved)
        except OSError:
            continue
    return result


def open_upright(path):
    with Image.open(path) as im:
        return ImageOps.exif_transpose(im).copy()


def thumbnail(path, limit=1200):
    with Image.open(path) as im:
        upright = ImageOps.exif_transpose(im)
        upright.thumbnail((limit, limit), Image.Resampling.LANCZOS)
        return upright.convert('RGBA')
