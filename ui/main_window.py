from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
from PIL import Image
from PySide6.QtCore import Qt, QTimer, Signal, QEvent
from PySide6.QtGui import QColor, QDragEnterEvent, QPalette
from PySide6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel, QListWidget,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox,
    QSplitter, QVBoxLayout, QWidget, QLineEdit, QTextEdit)

from core.background_remove import remove_ai_background, remove_solid_background
from core.batch_processor import BatchWorker
from core.config import Settings
from core.crop import crop_normalized
from core.presets import PresetStore
from ui.preview_scene import PreviewWidget
from utils.image_utils import SUPPORTED, collect_images, thumbnail


class DropList(QListWidget):
    dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setAlternatingRowColors(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
        else: super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            self.dropped.emit([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])
            event.acceptProposedAction()
        else: super().dropEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Keep the light interface readable when macOS uses a dark system palette.
        palette = QPalette()
        colors = {
            QPalette.ColorRole.Window: '#f6f7f9',
            QPalette.ColorRole.WindowText: '#1f2937',
            QPalette.ColorRole.Base: '#ffffff',
            QPalette.ColorRole.AlternateBase: '#f1f5f9',
            QPalette.ColorRole.Text: '#1f2937',
            QPalette.ColorRole.Button: '#ffffff',
            QPalette.ColorRole.ButtonText: '#1f2937',
            QPalette.ColorRole.ToolTipBase: '#ffffff',
            QPalette.ColorRole.ToolTipText: '#1f2937',
            QPalette.ColorRole.Highlight: '#1d4ed8',
            QPalette.ColorRole.HighlightedText: '#ffffff',
            QPalette.ColorRole.PlaceholderText: '#64748b',
            QPalette.ColorRole.Light: '#ffffff',
            QPalette.ColorRole.Midlight: '#e2e8f0',
            QPalette.ColorRole.Mid: '#cbd5e1',
            QPalette.ColorRole.Dark: '#94a3b8',
            QPalette.ColorRole.Shadow: '#64748b',
        }
        for role, color in colors.items():
            palette.setColor(role, QColor(color))
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                     QPalette.ColorRole.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor('#64748b'))
        app = QApplication.instance()
        app.setStyle('Fusion')
        app.setPalette(palette)
        self.setPalette(palette)
        self.setWindowTitle('WATERMARK MINH ĐIẾN')
        self.resize(1400, 850)
        self.store = PresetStore()
        self.preset_name, self.settings = self.store.current()
        self.preview = PreviewWidget()
        self.preview.settings = self.settings
        self.logo = None
        self.logo_dirty = False
        self.sources = []
        self.crop_regions = {}
        self.shared_crop = None
        self.worker = None
        self.suppress = False
        self.autosave = QTimer(self)
        self.autosave.setSingleShot(True)
        self.autosave.setInterval(650)
        self.autosave.timeout.connect(self.save_current)
        self.build_ui()
        self.setAcceptDrops(True)
        QApplication.instance().installEventFilter(self)
        self.apply_settings()
        self.load_logo()

    def eventFilter(self, watched, event):
        # Catch Explorer drops before controls such as QLineEdit consume file URLs.
        # Only handle this application's window, leaving native file dialogs alone.
        if (event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove, QEvent.Type.Drop)
                and isinstance(watched, QWidget) and watched.window() is self
                and event.mimeData().hasUrls()):
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if any(Path(path).is_dir() or Path(path).suffix.lower() in SUPPORTED for path in paths):
                if event.type() == QEvent.Type.Drop:
                    self.add_paths(paths)
                event.acceptProposedAction()
                return True
        return super().eventFilter(watched, event)

    def button(self, label, action):
        b = QPushButton(label)
        b.clicked.connect(action)
        return b

    def build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(splitter)
        left = QWidget(); ll = QVBoxLayout(left)
        ll.addWidget(QLabel('ẢNH SẢN PHẨM'))
        ll.addWidget(QLabel('Kéo ảnh hoặc thư mục vào danh sách bên dưới'))
        self.list = DropList()
        self.list.dropped.connect(self.add_paths)
        self.list.currentRowChanged.connect(self.show_photo)
        ll.addWidget(self.list)
        row = QHBoxLayout()
        row.addWidget(self.button('＋ Thêm ảnh', self.choose_images))
        row.addWidget(self.button('Thêm thư mục', self.choose_folder))
        ll.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(self.button('Xóa ảnh', self.remove_one))
        row.addWidget(self.button('Xóa tất cả', self.clear_images))
        ll.addLayout(row)
        splitter.addWidget(left)

        center = QWidget(); cl = QVBoxLayout(center)
        cl.addWidget(QLabel('XEM TRƯỚC — kéo logo và số điện thoại; kéo ô xanh để đổi cỡ logo'))
        cl.addWidget(self.preview, 1)
        self.preview.changed.connect(self.preview_changed)
        self.preview.selected.connect(self.set_selected)
        self.preview.cropSelected.connect(self.crop_selected)
        crop_row = QHBoxLayout()
        crop_row.addWidget(self.button('✂ Cắt ảnh', self.start_crop))
        crop_row.addWidget(self.button('Bỏ cắt', self.clear_crop))
        cl.addLayout(crop_row)
        self.crop_all = QCheckBox('Áp dụng khung cắt cho tất cả ảnh')
        self.crop_all.toggled.connect(self.toggle_crop_all)
        cl.addWidget(self.crop_all)
        self.object_choice = QComboBox(); self.object_choice.addItems(['Logo','Số điện thoại','Nội dung tùy chỉnh'])
        self.object_choice.currentIndexChanged.connect(self.select_object)
        cl.addWidget(self.object_choice)
        grid = QGridLayout()
        labels = ['↖','↑','↗','←','●','→','↙','↓','↘']
        for i,label in enumerate(labels):
            grid.addWidget(self.button(label, lambda checked=False, n=i: self.align(n)), i//3, i%3)
        cl.addLayout(grid)
        compare = QPushButton('Giữ chuột để xem ảnh gốc')
        compare.pressed.connect(lambda: self.compare(True))
        compare.released.connect(lambda: self.compare(False))
        cl.addWidget(compare)
        splitter.addWidget(center)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        panel = QWidget(); right = QVBoxLayout(panel)
        preset_box = QGroupBox('MẪU WATERMARK'); p = QVBoxLayout(preset_box)
        self.preset_combo = QComboBox(); self.preset_combo.addItems(self.store.names())
        self.preset_combo.setCurrentText(self.preset_name)
        self.preset_combo.currentTextChanged.connect(self.change_preset)
        p.addWidget(self.preset_combo)
        r = QHBoxLayout()
        for label,method in [('Tạo',self.new_preset),('Đổi tên',self.rename_preset),('💾 Lưu mẫu',self.save_current),('Xóa',self.delete_preset)]:
            r.addWidget(self.button(label, method))
        p.addLayout(r); right.addWidget(preset_box)

        logo_box = QGroupBox('LOGO'); form = QFormLayout(logo_box)
        form.addRow(self.button('🖼 Chọn logo', self.choose_logo))
        self.logo_on = QCheckBox('Hiện logo'); form.addRow(self.logo_on)
        self.logo_size = self.slider(2, 90); form.addRow('Kích thước %', self.logo_size)
        self.opacity = self.slider(0, 100); form.addRow('Độ mờ %', self.opacity)
        self.tolerance = self.slider(0, 100); form.addRow('Ngưỡng xóa nền', self.tolerance)
        self.softness = self.slider(0, 10); form.addRow('Mềm viền', self.softness)
        r = QHBoxLayout()
        r.addWidget(self.button('✨ Xóa nền nhanh', self.quick_remove))
        r.addWidget(self.button('Xóa nền AI', self.ai_remove))
        form.addRow(r)
        form.addRow(self.button('Lưu logo PNG trong suốt', self.save_logo_png))
        right.addWidget(logo_box)

        phone_box = QGroupBox('SỐ ĐIỆN THOẠI'); form = QFormLayout(phone_box)
        self.phone_on = QCheckBox('Hiện số điện thoại'); form.addRow(self.phone_on)
        self.phone = QLineEdit(); self.phone.setPlaceholderText('0912 345 678'); form.addRow('Số điện thoại', self.phone)
        self.font_combo = QComboBox()
        fonts = (['Arial','Helvetica','Times New Roman','Verdana','Tahoma'] if sys.platform == 'darwin'
                 else ['Arial','Segoe UI','Calibri','Tahoma','Verdana','Times New Roman'])
        self.font_combo.addItems(fonts)
        form.addRow('Font chữ', self.font_combo)
        self.font_size = self.slider(1, 25); form.addRow('Cỡ chữ %', self.font_size)
        self.bold = QCheckBox('Chữ đậm'); form.addRow(self.bold)
        self.text_color = self.color_button('Màu chữ', 'text_color'); form.addRow(self.text_color)
        self.stroke_color = self.color_button('Màu viền', 'stroke_color'); form.addRow(self.stroke_color)
        self.stroke = self.slider(0, 20); form.addRow('Độ dày viền ‰', self.stroke)
        self.shadow = QCheckBox('Đổ bóng'); form.addRow(self.shadow)
        right.addWidget(phone_box)

        custom_box = QGroupBox('NỘI DUNG TÙY CHỈNH'); form = QFormLayout(custom_box)
        self.custom_on = QCheckBox('Hiện nội dung'); form.addRow(self.custom_on)
        self.custom_text = QTextEdit(); self.custom_text.setPlaceholderText('Nhập câu giới thiệu, địa chỉ, Zalo... Có thể xuống dòng.')
        self.custom_text.setFixedHeight(82); form.addRow('Nội dung', self.custom_text)
        self.custom_size = self.slider(1, 25); form.addRow('Cỡ chữ %', self.custom_size)
        self.custom_bold = QCheckBox('Chữ đậm'); form.addRow(self.custom_bold)
        self.custom_color = self.color_button('Màu chữ', 'custom_color'); form.addRow(self.custom_color)
        self.custom_stroke_color = self.color_button('Màu viền', 'custom_stroke_color'); form.addRow(self.custom_stroke_color)
        self.custom_stroke = self.slider(0, 20); form.addRow('Độ dày viền ‰', self.custom_stroke)
        right.addWidget(custom_box)

        out_box = QGroupBox('XUẤT ẢNH'); form = QFormLayout(out_box)
        self.output_label = QLabel('Chưa chọn'); self.output_label.setWordWrap(True)
        form.addRow('Thư mục', self.output_label)
        form.addRow(self.button('Chọn thư mục xuất', self.choose_output))
        self.output_format = QComboBox(); self.output_format.addItems(['Giữ định dạng gốc','JPG','PNG','WEBP'])
        form.addRow('Định dạng', self.output_format)
        self.quality = QComboBox(); self.quality.addItems(['80','90','95','100']); form.addRow('Chất lượng', self.quality)
        right.addWidget(out_box)
        self.export = self.button('✅ XỬ LÝ TẤT CẢ ẢNH', self.start_export)
        self.export.setObjectName('primary'); right.addWidget(self.export)
        self.progress = QProgressBar(); right.addWidget(self.progress)
        self.status = QLabel('Sẵn sàng'); self.status.setWordWrap(True); right.addWidget(self.status)
        right.addStretch()
        scroll.setWidget(panel); splitter.addWidget(scroll)
        splitter.setSizes([290, 710, 400])
        self.setStyleSheet('''
            QWidget {color:#1f2937;selection-background-color:#1d4ed8;selection-color:white}
            QMainWindow {background:#f6f7f9}
            QGroupBox {font-weight:600;border:1px solid #d9dee6;border-radius:8px;margin-top:12px;padding:12px;background:white;color:#1f2937}
            QGroupBox::title {subcontrol-origin:margin;left:12px;padding:0 4px;color:#1f2937}
            QPushButton {padding:7px;border:1px solid #cbd5e1;border-radius:6px;background:white;color:#1f2937}
            QPushButton:hover {background:#eff6ff}
            QPushButton:disabled {color:#64748b;background:#f1f5f9}
            QPushButton#primary {background:#1d4ed8;color:white;font-weight:bold;padding:14px}
            QPushButton#primary:disabled {background:#94a3b8;color:white}
            QLineEdit,QTextEdit,QComboBox,QListWidget,QSpinBox {
                padding:5px;border:1px solid #cbd5e1;border-radius:5px;
                background:white;color:#1f2937
            }
            QComboBox QAbstractItemView {background:white;color:#1f2937;selection-background-color:#1d4ed8;selection-color:white}
            QListWidget {alternate-background-color:#f1f5f9}
            QListWidget::item:selected {background:#1d4ed8;color:white}
            QProgressBar {border:1px solid #cbd5e1;border-radius:5px;background:white;color:#1f2937;text-align:center}
            QProgressBar::chunk {background:#93c5fd}
            QToolTip {background:white;color:#1f2937;border:1px solid #cbd5e1}
        ''')
        for widget, signal in [(self.logo_on,self.logo_on.toggled),(self.phone_on,self.phone_on.toggled),(self.bold,self.bold.toggled),(self.shadow,self.shadow.toggled),
                               (self.phone,self.phone.textChanged),(self.font_combo,self.font_combo.currentTextChanged),
                               (self.output_format,self.output_format.currentTextChanged),(self.quality,self.quality.currentTextChanged),
                               (self.logo_size,self.logo_size.valueChanged),(self.opacity,self.opacity.valueChanged),
                               (self.font_size,self.font_size.valueChanged),(self.stroke,self.stroke.valueChanged),
                               (self.tolerance,self.tolerance.valueChanged),(self.softness,self.softness.valueChanged)]:
            signal.connect(self.controls_changed)
        for signal in (self.custom_on.toggled, self.custom_text.textChanged,
                       self.custom_size.valueChanged, self.custom_bold.toggled,
                       self.custom_stroke.valueChanged):
            signal.connect(self.controls_changed)

    def slider(self, low, high):
        s = QSlider(Qt.Orientation.Horizontal); s.setRange(low,high); return s

    def color_button(self, label, attr):
        return self.button(label, lambda: self.pick_color(attr))

    def pick_color(self, attr):
        chosen = QColorDialog.getColor(QColor(getattr(self.settings, attr)), self, 'Chọn màu')
        if chosen.isValid():
            setattr(self.settings, attr, chosen.name()); self.preview_changed()

    def apply_settings(self):
        self.suppress = True
        s = self.settings
        self.logo_on.setChecked(s.logo_enabled); self.logo_size.setValue(round(s.logo_size*100))
        self.opacity.setValue(s.logo_opacity); self.phone_on.setChecked(s.phone_enabled)
        self.phone.setText(s.phone); self.font_combo.setCurrentText(s.font_name)
        self.font_size.setValue(round(s.font_size*100)); self.bold.setChecked(s.bold)
        self.stroke.setValue(round(s.stroke_width*1000)); self.shadow.setChecked(s.shadow)
        self.custom_on.setChecked(s.custom_enabled); self.custom_text.setPlainText(s.custom_text)
        self.custom_size.setValue(round(s.custom_font_size*100)); self.custom_bold.setChecked(s.custom_bold)
        self.custom_stroke.setValue(round(s.custom_stroke_width*1000))
        self.tolerance.setValue(s.quick_tolerance); self.softness.setValue(s.quick_softness)
        self.output_format.setCurrentText(s.output_format); self.quality.setCurrentText(str(s.quality))
        self.output_label.setText(s.output_dir or 'Chưa chọn')
        self.preview.settings = s; self.preview.redraw()
        self.suppress = False

    def controls_changed(self, *args):
        if self.suppress: return
        s = self.settings
        s.logo_enabled = self.logo_on.isChecked(); s.logo_size = self.logo_size.value()/100
        s.logo_opacity = self.opacity.value(); s.phone_enabled = self.phone_on.isChecked()
        s.phone = self.phone.text(); s.font_name = self.font_combo.currentText()
        s.font_size = self.font_size.value()/100; s.bold = self.bold.isChecked()
        s.stroke_width = self.stroke.value()/1000; s.shadow = self.shadow.isChecked()
        s.custom_enabled = self.custom_on.isChecked(); s.custom_text = self.custom_text.toPlainText()
        s.custom_font_size = self.custom_size.value()/100; s.custom_bold = self.custom_bold.isChecked()
        s.custom_stroke_width = self.custom_stroke.value()/1000
        s.quick_tolerance = self.tolerance.value(); s.quick_softness = self.softness.value()
        s.output_format = self.output_format.currentText(); s.quality = int(self.quality.currentText())
        self.preview_changed()

    def preview_changed(self):
        self.preview.redraw()
        self.autosave.start()

    def set_selected(self, key):
        self.object_choice.setCurrentIndex({'logo': 0, 'phone': 1, 'custom': 2}[key])

    def select_object(self, index):
        self.preview.active = ('logo', 'phone', 'custom')[index]
        self.preview.update()

    def align(self, n):
        key = ('logo', 'phone', 'custom')[self.object_choice.currentIndex()]
        setattr(self.settings, key+'_x', (.08,.5,.92)[n%3])
        setattr(self.settings, key+'_y', (.08,.5,.92)[n//3])
        self.preview.active = key; self.preview_changed()

    def compare(self, state):
        self.preview.show_original = state; self.preview.update()

    def add_paths(self, paths):
        found = collect_images(paths)
        existing = set(self.sources)
        for path in found:
            if path not in existing:
                self.sources.append(path); self.list.addItem(Path(path).name)
        if self.list.currentRow() < 0 and self.sources: self.list.setCurrentRow(0)
        self.status.setText(f'Đã thêm {len(found)} ảnh; tổng {len(self.sources)} ảnh.')

    def choose_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, 'Thêm ảnh', '', 'Ảnh (*.jpg *.jpeg *.png *.webp *.bmp)')
        self.add_paths(paths)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Chọn thư mục ảnh')
        if folder: self.add_paths([folder])

    def remove_one(self):
        row = self.list.currentRow()
        if row >= 0:
            self.crop_regions.pop(self.sources[row], None)
            self.sources.pop(row); self.list.takeItem(row)
            if not self.sources: self.preview.set_photo(None)

    def clear_images(self):
        self.sources.clear(); self.crop_regions.clear(); self.shared_crop = None
        self.list.clear(); self.preview.set_photo(None)

    def show_photo(self, row):
        if row >= 0 and row < len(self.sources):
            try:
                self.preview.crop_mode = False
                self.preview.crop_start = self.preview.crop_end = None
                region = self.shared_crop if self.crop_all.isChecked() else self.crop_regions.get(self.sources[row])
                self.preview.set_photo(crop_normalized(thumbnail(self.sources[row]), region))
            except Exception as exc: QMessageBox.warning(self, 'Không thể mở ảnh', str(exc))

    def start_crop(self):
        row = self.list.currentRow()
        if row < 0 or row >= len(self.sources):
            return QMessageBox.information(self, 'Chưa có ảnh', 'Hãy chọn ảnh để cắt.')
        if self.preview.crop_mode:
            self.preview.crop_mode = False
            self.show_photo(row)
            self.status.setText('Đã hủy thao tác cắt.')
            return
        try:
            # Always draw the selection on the original upright image, never on a prior crop.
            self.preview.set_photo(thumbnail(self.sources[row]))
            self.preview.crop_mode = True
            self.preview.update()
            self.status.setText('Kéo chuột trên ảnh để khoanh vùng muốn giữ lại.')
        except Exception as exc:
            QMessageBox.warning(self, 'Không thể mở ảnh', str(exc))

    def crop_selected(self, region):
        row = self.list.currentRow()
        if row < 0 or row >= len(self.sources): return
        if self.crop_all.isChecked(): self.shared_crop = region
        else: self.crop_regions[self.sources[row]] = region
        self.show_photo(row)
        self.status.setText('Đã cắt trong preview. Ảnh gốc không thay đổi; khung cắt sẽ dùng khi xuất.')

    def toggle_crop_all(self, checked):
        row = self.list.currentRow()
        if checked and 0 <= row < len(self.sources):
            self.shared_crop = self.crop_regions.get(self.sources[row])
        self.preview.crop_mode = False
        self.preview.crop_start = self.preview.crop_end = None
        self.show_photo(row)

    def clear_crop(self):
        row = self.list.currentRow()
        self.preview.crop_mode = False
        self.preview.crop_start = self.preview.crop_end = None
        if self.crop_all.isChecked(): self.shared_crop = None
        elif 0 <= row < len(self.sources): self.crop_regions.pop(self.sources[row], None)
        self.show_photo(row)
        self.status.setText('Đã bỏ khung cắt.')

    def load_logo(self):
        self.logo = None
        self.logo_dirty = False
        if self.settings.logo_path:
            try:
                with Image.open(self.settings.logo_path) as im: self.logo = im.convert('RGBA').copy()
            except Exception as exc: self.status.setText(f'Không mở được logo: {exc}')
        self.preview.set_logo(self.logo)

    def choose_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Chọn logo', '', 'Logo (*.png *.jpg *.jpeg *.webp)')
        if path:
            self.settings.logo_path = path; self.load_logo(); self.autosave.start()

    def quick_remove(self):
        if self.logo is None: return QMessageBox.information(self, 'Logo', 'Hãy chọn logo trước.')
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.logo = remove_solid_background(self.logo, self.tolerance.value(), self.softness.value())
            self.logo_dirty = True
            self.preview.set_logo(self.logo); self.status.setText('Đã xóa nền nhanh. Hãy lưu logo PNG hoặc lưu mẫu để giữ kết quả.')
        finally: QApplication.restoreOverrideCursor()

    def ai_remove(self):
        if self.logo is None: return QMessageBox.information(self, 'Logo', 'Hãy chọn logo trước.')
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.logo = remove_ai_background(self.logo)
            self.logo_dirty = True
            self.preview.set_logo(self.logo)
            self.status.setText('Đã xóa nền AI. Hãy lưu logo PNG để giữ kết quả.')
        except Exception as exc: QMessageBox.warning(self, 'Xóa nền AI', str(exc))
        finally: QApplication.restoreOverrideCursor()

    def save_logo_png(self):
        if self.logo is None: return QMessageBox.information(self, 'Logo', 'Chưa có logo.')
        path, _ = QFileDialog.getSaveFileName(self, 'Lưu logo PNG', 'logo_minh_dien.png', 'PNG (*.png)')
        if path:
            dest = Path(path)
            if dest.exists():
                return QMessageBox.warning(self, 'Đã tồn tại', 'Hãy chọn tên khác để không ghi đè tệp hiện có.')
            with dest.open('xb') as stream: self.logo.save(stream, 'PNG')
            self.settings.logo_path = str(dest); self.logo_dirty = False; self.autosave.start()

    def save_current(self):
        if self.logo_dirty and self.logo is not None:
            # Modified in-memory logos are persisted in AppData, even without explicit PNG export.
            import uuid
            from core.config import data_dir
            folder = data_dir() / 'logos'; folder.mkdir(exist_ok=True)
            path = folder / (uuid.uuid4().hex + '.png')
            self.logo.save(path, 'PNG')
            self.settings.logo_path = str(path)
            self.logo_dirty = False
        self.settings = self.store.put(self.preset_name, self.settings)
        self.preview.settings = self.settings
        self.status.setText(f'Đã lưu mẫu: {self.preset_name}')

    def change_preset(self, name):
        if not name or self.suppress: return
        self.autosave.stop()
        self.preset_name = name; self.settings = self.store.select(name)
        self.apply_settings(); self.load_logo()

    def new_preset(self):
        name, ok = QInputDialog.getText(self, 'Tạo mẫu', 'Tên mẫu mới:')
        if ok and name.strip():
            if name in self.store.names(): return QMessageBox.warning(self, 'Trùng tên', 'Mẫu này đã có.')
            try:
                self.preset_name = name.strip(); self.save_current()
                self.suppress = True; self.preset_combo.addItem(self.preset_name); self.preset_combo.setCurrentText(self.preset_name); self.suppress = False
            except ValueError as exc: QMessageBox.warning(self, 'Tên mẫu', str(exc))

    def rename_preset(self):
        name, ok = QInputDialog.getText(self, 'Đổi tên mẫu', 'Tên mới:', text=self.preset_name)
        if ok and name.strip() and name.strip() != self.preset_name:
            try:
                old = self.preset_name; self.store.rename(old, name.strip())
                self.preset_name = name.strip(); self.refresh_presets()
            except ValueError as exc: QMessageBox.warning(self, 'Tên mẫu', str(exc))

    def delete_preset(self):
        if QMessageBox.question(self, 'Xóa mẫu', f'Xóa mẫu “{self.preset_name}”?') != QMessageBox.StandardButton.Yes: return
        try:
            self.store.delete(self.preset_name)
            self.preset_name, self.settings = self.store.current()
            self.refresh_presets(); self.apply_settings(); self.load_logo()
        except ValueError as exc: QMessageBox.warning(self, 'Xóa mẫu', str(exc))

    def refresh_presets(self):
        self.suppress = True
        self.preset_combo.clear(); self.preset_combo.addItems(self.store.names())
        self.preset_combo.setCurrentText(self.preset_name); self.suppress = False

    def choose_output(self):
        folder = QFileDialog.getExistingDirectory(self, 'Thư mục xuất', self.settings.output_dir)
        if folder:
            self.settings.output_dir = folder; self.output_label.setText(folder); self.autosave.start()

    def start_export(self):
        if not self.sources: return QMessageBox.information(self, 'Chưa có ảnh', 'Hãy thêm ảnh trước.')
        if not self.settings.output_dir: self.choose_output()
        if not self.settings.output_dir: return
        self.autosave.stop(); self.save_current()
        self.progress.setRange(0, len(self.sources)); self.progress.setValue(0)
        self.export.setEnabled(False)
        shared = self.shared_crop if self.crop_all.isChecked() else None
        crops = {} if self.crop_all.isChecked() else self.crop_regions
        self.worker = BatchWorker(self.sources.copy(), self.settings.output_dir, replace(self.settings),
                                  self.logo, crops, shared)
        self.worker.progress.connect(self.on_progress)
        self.worker.completed.connect(self.on_completed)
        self.worker.start()

    def on_progress(self, done, total, name):
        self.progress.setValue(done); self.status.setText(f'Đang xử lý {done} / {total}: {name}')

    def on_completed(self, outputs, errors):
        self.export.setEnabled(True)
        self.status.setText(f'Hoàn thành {len(outputs)} / {len(self.sources)} ảnh; lỗi {len(errors)}.')
        msg = f'Đã xuất {len(outputs)} ảnh vào:\n{self.settings.output_dir}'
        if errors: msg += '\n\nLỗi:\n' + '\n'.join(errors[:15])
        QMessageBox.information(self, 'Xử lý hoàn tất', msg)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, 'Đang xử lý', 'Vui lòng chờ xử lý ảnh hoàn tất.')
            event.ignore(); return
        self.autosave.stop(); self.save_current()
        QApplication.instance().removeEventFilter(self)
        super().closeEvent(event)
