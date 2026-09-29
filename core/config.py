from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import json
import os
import sys
from pathlib import Path


def data_dir() -> Path:
    if sys.platform == 'darwin':
        base = Path.home() / 'Library' / 'Application Support'
    else:
        base = Path(os.environ.get('APPDATA', Path.home() / '.config'))
    path = base / 'WatermarkMinhDien'
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Settings:
    logo_path: str = ''
    logo_enabled: bool = True
    logo_x: float = .78
    logo_y: float = .82
    logo_size: float = .25
    logo_opacity: int = 75
    phone: str = ''
    phone_enabled: bool = True
    phone_x: float = .78
    phone_y: float = .94
    font_path: str = ''
    font_name: str = 'Arial'
    font_size: float = .045
    bold: bool = True
    text_color: str = '#ffffff'
    stroke_color: str = '#000000'
    stroke_width: float = .003
    shadow: bool = False
    custom_text: str = ''
    custom_enabled: bool = True
    custom_x: float = .5
    custom_y: float = .5
    custom_font_size: float = .045
    custom_bold: bool = True
    custom_color: str = '#ffffff'
    custom_stroke_color: str = '#000000'
    custom_stroke_width: float = .003
    output_dir: str = ''
    output_format: str = 'Giữ định dạng gốc'
    quality: int = 95
    quick_tolerance: int = 32
    quick_softness: int = 2

    @classmethod
    def from_dict(cls, value: dict) -> 'Settings':
        allowed = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in value.items() if k in allowed})

    def to_dict(self) -> dict:
        return asdict(self)


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError, TypeError):
        return default


def atomic_json(path: Path, value) -> None:
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)
