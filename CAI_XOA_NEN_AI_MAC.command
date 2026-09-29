#!/bin/bash
set -euo pipefail
trap 'code=$?; echo "Cài AI gặp lỗi ($code). Hãy gửi ảnh cửa sổ này để kiểm tra."; read -r -p "Nhấn Enter để đóng..." _' ERR
cd "$(dirname "$0")"

WMD_ENV="$PWD/.venv-mac"
if [[ ! -x "$WMD_ENV/bin/python" ]]; then
  echo "Hãy chạy RUN_MAC.command một lần trước khi cài AI."
  read -r -p "Nhấn Enter để đóng..." _
  exit 1
fi
"$WMD_ENV/bin/python" -m pip install -r requirements-ai.txt
echo "Đã cài AI. Mở lại ứng dụng; lần đầu dùng có thể tải mô hình."
read -r -p "Nhấn Enter để đóng..." _
