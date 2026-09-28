# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

hiddenimports = []
datas = []
binaries = []
try:
    import rembg, onnxruntime
except ImportError:
    pass
else:
    for module in ('rembg','onnxruntime'):
        d, b, h = collect_all(module)
        datas += d; binaries += b; hiddenimports += h

a = Analysis(['main.py'], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='WatermarkMinhDien',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
