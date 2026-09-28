from __future__ import annotations

from PIL import Image

CropRect = tuple[float, float, float, float]


def crop_normalized(image: Image.Image, region: CropRect | None) -> Image.Image:
    """Crop an upright image using fractions of its width and height."""
    if region is None:
        return image
    if len(region) != 4:
        raise ValueError('Khung cắt không hợp lệ.')
    x1, y1, x2, y2 = (max(0.0, min(1.0, float(v))) for v in region)
    if x2 <= x1 or y2 <= y1:
        raise ValueError('Khung cắt không hợp lệ.')
    width, height = image.size
    left = min(width - 1, max(0, round(x1 * width)))
    top = min(height - 1, max(0, round(y1 * height)))
    right = min(width, max(left + 1, round(x2 * width)))
    bottom = min(height, max(top + 1, round(y2 * height)))
    return image.crop((left, top, right, bottom))
