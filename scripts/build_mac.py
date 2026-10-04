"""Build a standalone Finder app and a single downloadable disk image on macOS."""
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.platform != 'darwin':
        raise SystemExit('Phải đóng gói bản Mac trên macOS.')
    os.chdir(ROOT)
    arch = platform.machine()
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--onedir', '--windowed', '--noupx', '--name', 'WatermarkMinhDien',
               '--osx-bundle-identifier', 'vn.minhdien.watermark', '--target-arch', arch]
    try:
        import rembg, onnxruntime
    except ImportError:
        print('Đóng gói watermark và xóa nền nhanh; AI là tùy chọn.', flush=True)
    else:
        command += ['--collect-all', 'rembg', '--collect-all', 'onnxruntime']
    subprocess.run(command + ['main.py'], check=True)
    app = ROOT / 'dist' / 'WatermarkMinhDien.app'
    executable = app / 'Contents' / 'MacOS' / 'WatermarkMinhDien'
    result = subprocess.run([str(executable), '--smoke-test'], check=True,
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
                            capture_output=True, text=True, timeout=120)
    print(result.stdout, flush=True)
    if 'WATERMARK_SMOKE_OK' not in result.stdout:
        raise RuntimeError('Bản ứng dụng đóng gói chưa vượt qua kiểm tra mở giao diện.')
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    stage = ROOT / 'build' / 'mac-dmg'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    subprocess.run(['ditto', str(app), str(stage / app.name)], check=True)
    (stage / 'Applications').symlink_to('/Applications')
    (stage / 'HUONG_DAN.txt').write_text(
        'WATERMARK MINH ĐIẾN\n\n'
        'Kéo WatermarkMinhDien vào Applications (Ứng dụng), rồi nhấp đúp để mở.\n'
        'Không cần cài Python. Ảnh gốc được giữ nguyên.\n'
        'Nếu macOS chặn lần đầu: mở Cài đặt hệ thống > Quyền riêng tư & bảo mật > Mở vẫn được.\n'
        'Bản này chưa được công chứng Apple. Chỉ mở bản tải từ repo Minh Điến.\n', encoding='utf-8')
    dmg = ROOT / 'dist' / f'WatermarkMinhDien-Mac-{arch}.dmg'
    dmg.unlink(missing_ok=True)
    subprocess.run(['hdiutil', 'create', '-volname', 'WATERMARK MINH DIEN',
                    '-srcfolder', str(stage), '-ov', '-format', 'UDZO', str(dmg)], check=True)
    print(f'Hoàn thành: {app}\nFile tải về: {dmg}', flush=True)


if __name__ == '__main__':
    main()
