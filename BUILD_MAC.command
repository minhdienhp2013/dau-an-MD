#!/bin/bash
set -euo pipefail
trap 'code=$?; echo "Build gặp lỗi ($code). Hãy gửi ảnh cửa sổ này để kiểm tra."; read -r -p "Nhấn Enter để đóng..." _' ERR
cd "$(dirname "$0")"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Phải build ứng dụng Mac trên máy Mac."
  read -r -p "Nhấn Enter để đóng..." _
  exit 1
fi

WMD_ENV="$PWD/.venv-mac"
if [[ ! -x "$WMD_ENV/bin/python" ]]; then
  WMD_PYTHON=''
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && \
       "$candidate" -c 'import sys; assert (3, 11) <= sys.version_info[:2] < (3, 13)' >/dev/null 2>&1; then
      WMD_PYTHON="$candidate"
      break
    fi
  done
  if [[ -z "$WMD_PYTHON" ]]; then
    echo "Cần Python 3.11 hoặc 3.12 cho macOS."
    read -r -p "Nhấn Enter để đóng..." _
    exit 1
  fi
  "$WMD_PYTHON" -m venv "$WMD_ENV"
fi

"$WMD_ENV/bin/python" -m pip install -r requirements.txt -r requirements-build.txt
"$WMD_ENV/bin/python" scripts/build_mac.py

echo "Hoàn thành: $PWD/dist/WatermarkMinhDien.app"
echo "File gửi sang máy khác: $PWD/dist/WatermarkMinhDien-Mac-$(uname -m).dmg"
read -r -p "Nhấn Enter để đóng..." _
