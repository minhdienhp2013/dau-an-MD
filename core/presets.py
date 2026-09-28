from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from core.config import Settings, atomic_json, data_dir, read_json


@dataclass
class PresetStore:
    def __post_init__(self):
        self.folder = data_dir()
        self.file = self.folder / 'presets.json'
        self.data = read_json(self.file, {})
        if not isinstance(self.data, dict):
            self.data = {}
        self.data.setdefault('presets', {})
        self.data.setdefault('current', 'Mặc định')
        if not self.data['presets']:
            self.data['presets'] = {'Mặc định': Settings().to_dict()}
            self.save()

    def save(self):
        atomic_json(self.file, self.data)

    def names(self):
        return list(self.data['presets'])

    def current(self):
        name = self.data.get('current', 'Mặc định')
        if name not in self.data['presets']:
            name = next(iter(self.data['presets']))
        return name, Settings.from_dict(self.data['presets'][name])

    def select(self, name):
        self.data['current'] = name
        self.save()
        return Settings.from_dict(self.data['presets'][name])

    def put(self, name, settings: Settings):
        name = name.strip()
        if not name or len(name) > 80 or re.search(r'[\\/:*?"<>|]', name):
            raise ValueError('Tên mẫu không hợp lệ.')
        saved = settings.to_dict()
        logo = Path(saved['logo_path']) if saved['logo_path'] else None
        if logo and logo.is_file() and self.folder / 'logos' not in logo.parents:
            folder = self.folder / 'logos'
            folder.mkdir(exist_ok=True)
            dest = folder / (uuid4().hex + logo.suffix.lower())
            shutil.copy2(logo, dest)
            saved['logo_path'] = str(dest)
        self.data['presets'][name] = saved
        self.data['current'] = name
        self.save()
        return Settings.from_dict(saved)

    def rename(self, old, new):
        new = new.strip()
        if not new or new in self.data['presets'] or len(new) > 80:
            raise ValueError('Tên mẫu đã có hoặc không hợp lệ.')
        self.data['presets'][new] = self.data['presets'].pop(old)
        self.data['current'] = new
        self.save()

    def delete(self, name):
        if len(self.data['presets']) == 1:
            raise ValueError('Cần giữ ít nhất một mẫu.')
        del self.data['presets'][name]
        self.data['current'] = next(iter(self.data['presets']))
        self.save()
