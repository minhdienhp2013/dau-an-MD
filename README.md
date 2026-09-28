# WATERMARK MINH ĐIẾN

Ứng dụng Windows 10/11 để đóng logo và số điện thoại lên ảnh sản phẩm. Ảnh gốc luôn được giữ nguyên.

## Chạy trên Windows

Cài Python 3.11 hoặc 3.12 từ python.org (chọn **Add Python to PATH**). Nhấp đúp `RUN.bat`; lần đầu chương trình tự tạo `.venv` và cài PySide6, Pillow. Sau đó kéo ảnh/thư mục từ Explorer vào bất kỳ vùng nào của cửa sổ (kể cả preview), hoặc dùng nút Thêm ảnh; chọn logo và nhập số điện thoại, kéo trực tiếp trên ảnh, chọn thư mục xuất, nhấn **XỬ LÝ TẤT CẢ ẢNH**.

Chọn đối tượng ở dưới preview rồi dùng 9 nút căn nhanh. Kéo góc xanh dưới phải logo để đổi kích thước; có thể dùng thanh trượt. Giữ nút xem ảnh gốc để đối chiếu. Mẫu tự lưu trong `%APPDATA%\WatermarkMinhDien` và được nhớ khi mở lại; có thể tạo, đổi tên hoặc xóa mẫu.

## Xóa nền logo

**Xóa nền nhanh** dùng màu ở góc ảnh, giữ các vùng màu tương tự nằm tách khỏi mép. Chỉnh ngưỡng và độ mềm trước khi bấm. Dùng **Lưu logo PNG trong suốt** nếu muốn sử dụng riêng tệp đó. Kết quả trong mẫu được tự lưu trong AppData.

**Xóa nền AI** là tùy chọn. Chạy `CAI_XOA_NEN_AI.bat` rồi mở lại chương trình. Lần đầu rembg có thể tải mô hình qua Internet. Nếu muốn AI hoạt động trong `.exe`, cài AI **trước khi** chạy `BUILD_EXE.bat`; sau đó exe có thể lớn hơn. Nếu không cài, nút AI báo rõ tình trạng và những chức năng khác vẫn chạy.

## Build .exe

Trên Windows, nhấp đúp `BUILD_EXE.bat`; kết quả `dist\WatermarkMinhDien.exe`. Máy dùng exe không cần cài Python. Build phải thực hiện trên Windows để tạo bản Windows; bản build trên Linux không phải `.exe` cho Windows.

## Thiết kế và an toàn

Vị trí tâm logo/chữ và kích thước được lưu theo tỷ lệ ảnh; preview và export dùng chung bộ dựng ảnh. Tên ảnh xuất có `_watermark`, file trùng tự thêm `_2`, `_3`. Có thể chọn chính thư mục ảnh gốc để xuất, nhưng ứng dụng không sửa ảnh gốc. Ảnh xuất giữ định dạng hoặc chọn JPG/PNG/WEBP; JPG chuyển sang RGB. EXIF orientation được sửa trước khi dựng watermark.

Hàng trăm ảnh được đọc lần lượt trong QThread; preview giới hạn 1200 px. Các ảnh quá lớn vẫn cần đủ RAM cho **một ảnh gốc** khi xuất. AI và xóa nền nhanh xử lý logo trong cửa sổ chính nên logo rất lớn có thể mất vài giây.

## Kiểm tra

`python -m unittest discover -s tests -v` sau khi cài requirements. Kiểm tra UI headless với `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v` trên máy có Qt.
