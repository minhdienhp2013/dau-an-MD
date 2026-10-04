from __future__ import annotations

from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter


def remove_solid_background(image: Image.Image, tolerance: int = 32, softness: int = 2) -> Image.Image:
    src = image.convert('RGBA')
    w, h = src.size
    margin = max(1, min(w, h)//15)
    corners = [src.getpixel((x, y))[:3] for x,y in ((0,0),(w-1,0),(0,h-1),(w-1,h-1))]
    color = tuple(sorted(c[i] for c in corners)[1:3][0] for i in range(3))
    pixels = src.load()
    mask = Image.new('L', (w,h), 0)
    mp = mask.load()
    tol = max(0, min(255, int(tolerance)))
    for y in range(h):
        for x in range(w):
            rgb = pixels[x,y][:3]
            if max(abs(rgb[i]-color[i]) for i in range(3)) <= tol:
                mp[x,y] = 255
    # Only remove pixels connected to the exterior, preserving similarly colored logo details.
    from collections import deque
    q = deque()
    for x in range(w):
        q.extend(((x,0),(x,h-1)))
    for y in range(h):
        q.extend(((0,y),(w-1,y)))
    exterior = Image.new('L', (w,h), 0)
    out = exterior.load()
    while q:
        x,y = q.popleft()
        if mp[x,y] != 255 or out[x,y]:
            continue
        out[x,y] = 255
        if x: q.append((x-1,y))
        if x+1<w: q.append((x+1,y))
        if y: q.append((x,y-1))
        if y+1<h: q.append((x,y+1))
    if softness:
        exterior = exterior.filter(ImageFilter.GaussianBlur(min(10, max(0, softness)) * .5))
    original_alpha = src.getchannel('A')
    from PIL import ImageChops
    src.putalpha(ImageChops.multiply(original_alpha, ImageChops.invert(exterior)))
    return src


def remove_ai_background(image: Image.Image) -> Image.Image:
    try:
        from rembg import remove
    except ImportError as exc:
        import sys
        if sys.platform == 'darwin':
            message = 'Bản Mac này chưa có AI xóa nền. Xóa nền nhanh vẫn dùng được. Để dùng AI, cài từ source bằng CAI_XOA_NEN_AI_MAC.command rồi build lại.'
        else:
            message = 'Chưa cài AI xóa nền. Hãy chạy CAI_XOA_NEN_AI.bat trên Windows và mở lại ứng dụng.'
        raise RuntimeError(message) from exc
    buf = BytesIO()
    image.save(buf, 'PNG')
    output = remove(buf.getvalue())
    return Image.open(BytesIO(output)).convert('RGBA')
