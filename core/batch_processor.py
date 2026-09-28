from __future__ import annotations

from pathlib import Path
from PIL import Image
from PySide6.QtCore import QThread, Signal

from core.config import Settings
from core.crop import CropRect, crop_normalized
from core.watermark_processor import render
from utils.image_utils import open_upright

FORMATS = {'JPG': ('.jpg', 'JPEG'), 'PNG': ('.png', 'PNG'), 'WEBP': ('.webp', 'WEBP'), 'BMP': ('.bmp', 'BMP')}


def unique_target(folder: Path, source: Path, fmt: str) -> Path:
    suffix = source.suffix.lower() if fmt == 'Giữ định dạng gốc' else FORMATS[fmt][0]
    if suffix == '.jpeg': suffix = '.jpg'
    candidate = folder / f'{source.stem}_watermark{suffix}'
    i = 2
    while candidate.exists() or candidate.resolve() == source.resolve():
        candidate = folder / f'{source.stem}_watermark_{i}{suffix}'
        i += 1
    return candidate


def export_one(source: str, folder: str, settings: Settings, logo: Image.Image | None = None,
               crop: CropRect | None = None) -> Path:
    src = Path(source).resolve()
    dest_dir = Path(folder).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    fmt = settings.output_format
    if fmt == 'Giữ định dạng gốc':
        fmt = {'.jpg':'JPG','.jpeg':'JPG','.png':'PNG','.webp':'WEBP','.bmp':'BMP'}[src.suffix.lower()]
    output = unique_target(dest_dir, src, settings.output_format)
    image = open_upright(src)
    image = crop_normalized(image, crop)
    result = render(image, settings, logo).image
    if fmt == 'JPG':
        result = result.convert('RGB')
    options = {'quality': settings.quality} if fmt in ('JPG','WEBP') else {}
    # Exclusive creation guarantees no overwrite even when source and output folders match.
    with output.open('xb') as stream:
        try:
            result.save(stream, format=FORMATS[fmt][1], **options)
        except Exception:
            stream.close()
            output.unlink(missing_ok=True)
            raise
    return output


class BatchWorker(QThread):
    progress = Signal(int, int, str)
    completed = Signal(list, list)

    def __init__(self, sources: list[str], folder: str, settings: Settings, logo: Image.Image | None,
                 crops: dict[str, CropRect] | None = None, shared_crop: CropRect | None = None):
        super().__init__()
        self.sources, self.folder, self.settings = sources, folder, settings
        self.logo = logo.copy() if logo is not None else None
        self.crops = dict(crops or {})
        self.shared_crop = shared_crop

    def run(self):
        outputs, errors = [], []
        for i, path in enumerate(self.sources, 1):
            try:
                region = self.shared_crop if self.shared_crop is not None else self.crops.get(path)
                outputs.append(str(export_one(path, self.folder, self.settings, self.logo, region)))
            except Exception as exc:
                errors.append(f'{Path(path).name}: {exc}')
            self.progress.emit(i, len(self.sources), Path(path).name)
        self.completed.emit(outputs, errors)
