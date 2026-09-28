from __future__ import annotations

from PIL import Image
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from core.config import Settings
from core.watermark_processor import render


class PreviewWidget(QWidget):
    changed = Signal()
    selected = Signal(str)
    cropSelected = Signal(tuple)

    def __init__(self):
        super().__init__()
        self.setMinimumSize(420, 420)
        self.setMouseTracking(True)
        self.settings = Settings()
        self.photo: Image.Image | None = None
        self.logo: Image.Image | None = None
        self.current: QImage | None = None
        self.original: QImage | None = None
        self.boxes = {}
        self.active = 'logo'
        self.dragging = ''
        self.show_original = False
        self.crop_mode = False
        self.crop_start = None
        self.crop_end = None

    @staticmethod
    def qimage(pil):
        rgba = pil.convert('RGBA')
        return QImage(rgba.tobytes(), rgba.width, rgba.height, QImage.Format.Format_RGBA8888).copy()

    def set_photo(self, photo):
        self.photo = photo
        if photo is None:
            self.current = None; self.original = None; self.boxes = {}
        self.redraw()

    def set_logo(self, logo):
        self.logo = logo
        self.redraw()

    def redraw(self):
        if self.photo is not None:
            result = render(self.photo, self.settings, self.logo)
            self.current = self.qimage(result.image)
            self.original = self.qimage(self.photo)
            self.boxes = result.boxes
        self.update()

    def photo_rect(self):
        if self.photo is None:
            return QRectF()
        w, h = self.photo.size
        factor = min((self.width()-24)/w, (self.height()-24)/h)
        dw, dh = w*factor, h*factor
        return QRectF((self.width()-dw)/2, (self.height()-dh)/2, dw, dh)

    def image_point(self, point):
        rect = self.photo_rect()
        if rect.isEmpty():
            return 0, 0
        return ((point.x()-rect.x())*self.photo.width/rect.width(),
                (point.y()-rect.y())*self.photo.height/rect.height())

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor('#e8ecf1'))
        if not self.current:
            p.setPen(QColor('#6b7280'))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, 'Thêm ảnh để xem trước')
            return
        rect = self.photo_rect()
        p.drawImage(rect, self.original if self.show_original or self.crop_mode else self.current)
        if self.crop_mode and self.crop_start is not None and self.crop_end is not None:
            x1,y1 = self.crop_start
            x2,y2 = self.crop_end
            selection = QRectF(rect.x()+min(x1,x2)*rect.width(), rect.y()+min(y1,y2)*rect.height(),
                               abs(x2-x1)*rect.width(), abs(y2-y1)*rect.height())
            p.fillRect(selection, QColor(37, 99, 235, 55))
            p.setPen(QPen(QColor('#2563eb'), 2, Qt.PenStyle.DashLine))
            p.drawRect(selection)
        if self.active in self.boxes and not self.show_original and not self.crop_mode:
            x1,y1,x2,y2 = self.boxes[self.active]
            sx, sy = rect.width()/self.photo.width, rect.height()/self.photo.height
            box = QRectF(rect.x()+x1*sx, rect.y()+y1*sy, (x2-x1)*sx, (y2-y1)*sy)
            p.setPen(QPen(QColor('#2563eb'), 2, Qt.PenStyle.DashLine))
            p.drawRect(box)
            if self.active == 'logo':
                p.fillRect(QRectF(box.right()-5, box.bottom()-5, 11, 11), QColor('#2563eb'))
        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.photo is None:
            return
        if self.crop_mode:
            self.crop_start = self.normalized_point(event.position())
            self.crop_end = self.crop_start
            self.update()
            return
        x, y = self.image_point(event.position())
        for key in ('custom','phone','logo'):
            if key in self.boxes:
                a,b,c,d = self.boxes[key]
                if key == 'logo' and abs(x-c)<18 and abs(y-d)<18:
                    self.active = key
                    self.dragging = 'resize'
                    self.selected.emit(key)
                    return
                if a <= x <= c and b <= y <= d:
                    self.active = key
                    self.dragging = key
                    self.selected.emit(key)
                    self.mouseMoveEvent(event)
                    return
        self.show_original = True
        self.update()

    def mouseMoveEvent(self, event):
        if self.crop_mode and self.crop_start is not None:
            self.crop_end = self.normalized_point(event.position())
            self.update()
            return
        if not self.dragging or self.photo is None:
            return
        x,y = self.image_point(event.position())
        w,h = self.photo.size
        if self.dragging == 'resize' and 'logo' in self.boxes:
            a,b,c,d = self.boxes['logo']
            self.settings.logo_size = min(.9, max(.02, (x-a)/min(w,h)))
        else:
            key = self.dragging
            a,b,c,d = self.boxes.get(key, (0,0,0,0))
            nx = min(max((c-a)/(2*w), x/w), 1-(c-a)/(2*w))
            ny = min(max((d-b)/(2*h), y/h), 1-(d-b)/(2*h))
            setattr(self.settings, key+'_x', nx)
            setattr(self.settings, key+'_y', ny)
        self.redraw()
        self.changed.emit()

    def mouseReleaseEvent(self, event):
        if self.crop_mode and self.crop_start is not None:
            self.crop_end = self.normalized_point(event.position())
            a,b = self.crop_start
            c,d = self.crop_end
            self.crop_start = self.crop_end = None
            if abs(c-a) >= .01 and abs(d-b) >= .01:
                self.crop_mode = False
                self.cropSelected.emit((min(a,c), min(b,d), max(a,c), max(b,d)))
            self.update()
            return
        self.dragging = ''
        self.show_original = False
        self.update()

    def resizeEvent(self, event):
        self.update()

    def normalized_point(self, position):
        x,y = self.image_point(position)
        return (min(1.0, max(0.0, x/self.photo.width)),
                min(1.0, max(0.0, y/self.photo.height)))
