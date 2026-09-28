import os
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw

from core.config import Settings
from core.background_remove import remove_solid_background
from core.batch_processor import export_one
from core.crop import crop_normalized
from core.watermark_processor import render


class ImageTests(unittest.TestCase):
    def test_render_and_scaled_positions(self):
        s = Settings(phone='0912 345 678', logo_x=.7, logo_y=.7, phone_x=.5, phone_y=.9,
                     custom_text='Cửa hàng Minh Điến\nĐại Lộc 1 - Kiến Hải - Hải Phòng')
        logo = Image.new('RGBA', (100, 50), 'red')
        for size in [(900,600),(600,900),(700,700)]:
            result = render(Image.new('RGB', size, 'navy'), s, logo)
            self.assertEqual(result.image.size, size)
            self.assertIn('logo', result.boxes)
            self.assertIn('phone', result.boxes)
            self.assertIn('custom', result.boxes)
            a,b,c,d = result.boxes['logo']
            self.assertTrue(0 <= a < c <= size[0] and 0 <= b < d <= size[1])
            a,b,c,d = result.boxes['custom']
            self.assertTrue(0 <= a < c <= size[0] and 0 <= b < d <= size[1])

    def test_remove_background_preserves_internal_white(self):
        image = Image.new('RGB', (60,60), 'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((10,10,50,50), fill='red')
        draw.rectangle((20,20,40,40), fill='white')
        result = remove_solid_background(image, 20, 0)
        self.assertEqual(result.getpixel((0,0))[3], 0)
        self.assertEqual(result.getpixel((30,30))[3], 255)

    def test_jpg_png_exif_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            jpg = folder/'product.jpg'; png = folder/'other.png'
            im = Image.new('RGB', (160,80), 'blue')
            exif = Image.Exif(); exif[274] = 6
            im.save(jpg, exif=exif)
            Image.new('RGBA', (120,120), 'green').save(png)
            s = Settings(phone='0123')
            outputs = [export_one(str(jpg), tmp, s), export_one(str(jpg), tmp, s), export_one(str(png), tmp, s)]
            self.assertEqual([p.name for p in outputs], ['product_watermark.jpg','product_watermark_2.jpg','other_watermark.png'])
            with Image.open(jpg) as original, Image.open(outputs[0]) as exported, Image.open(outputs[2]) as other:
                self.assertEqual(original.size, (160,80))
                self.assertEqual(exported.size, (80,160))
                self.assertEqual(other.format, 'PNG')
            self.assertEqual(len(list(folder.glob('*watermark*'))), 3)

    def test_crop_before_watermark_and_keep_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'sofa.png'
            Image.new('RGB', (400, 200), 'blue').save(source)
            region = (.25, .1, .75, .9)
            preview = crop_normalized(Image.open(source), region)
            output = export_one(str(source), tmp, Settings(phone='0912 345 678'), crop=region)
            with Image.open(output) as exported, Image.open(source) as original:
                self.assertEqual(preview.size, exported.size)
                self.assertEqual(exported.size, (200, 160))
                self.assertEqual(original.size, (400, 200))


if __name__ == '__main__': unittest.main()


class UiTests(unittest.TestCase):
    def test_crop_selection_and_apply_to_all(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from ui.main_window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get('APPDATA')
            os.environ['APPDATA'] = tmp
            try:
                app = QApplication.instance() or QApplication([])
                window = MainWindow(); window.show()
                a, b = Path(tmp)/'a.png', Path(tmp)/'b.png'
                Image.new('RGB', (400, 300), 'red').save(a)
                Image.new('RGB', (300, 400), 'blue').save(b)
                window.add_paths([str(a), str(b)])
                app.processEvents()
                window.start_crop()
                widget = window.preview
                rect = widget.photo_rect()
                def at(x, y):
                    return QPoint(round(rect.x()+rect.width()*x), round(rect.y()+rect.height()*y))
                QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=at(.2,.2))
                QTest.mouseMove(widget, at(.8,.8))
                QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=at(.8,.8))
                self.assertEqual(len(window.crop_regions), 1)
                self.assertEqual(widget.photo.size, (240,180))
                window.list.setCurrentRow(1)
                self.assertEqual(widget.photo.size, (300,400))
                window.list.setCurrentRow(0)
                window.crop_all.setChecked(True)
                window.list.setCurrentRow(1)
                self.assertEqual(widget.photo.size, (180,240))
                window.clear_crop()
                self.assertEqual(widget.photo.size, (300,400))
                window.close()
            finally:
                if old is None: os.environ.pop('APPDATA', None)
                else: os.environ['APPDATA'] = old

    def test_explorer_drop_on_preview_and_text_field(self):
        from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        from PySide6.QtWidgets import QApplication
        from ui.main_window import MainWindow
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get('APPDATA')
            os.environ['APPDATA'] = tmp
            try:
                app = QApplication.instance() or QApplication([])
                window = MainWindow(); window.show(); app.processEvents()
                image = Path(tmp)/'a.jpg'
                Image.new('RGB', (80, 80), 'red').save(image)
                nested = Path(tmp)/'folder'; nested.mkdir()
                Image.new('RGB', (80, 80), 'blue').save(nested/'b.png')
                mime = QMimeData()
                mime.setUrls([QUrl.fromLocalFile(str(image)), QUrl.fromLocalFile(str(nested))])
                enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime,
                                       Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                app.sendEvent(window.preview, enter)
                self.assertTrue(enter.isAccepted())
                drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                                  Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
                app.sendEvent(window.preview, drop)
                self.assertEqual(window.list.count(), 2)
                app.sendEvent(window.phone, QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                              Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier))
                self.assertEqual(window.list.count(), 2)  # no duplicates
                window.close()
            finally:
                if old is None: os.environ.pop('APPDATA', None)
                else: os.environ['APPDATA'] = old

    def test_preview_drag_resize_and_preset_persistence(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest
        from ui.main_window import MainWindow
        from core.presets import PresetStore
        with tempfile.TemporaryDirectory() as tmp:
            prior = os.environ.get('APPDATA')
            os.environ['APPDATA'] = tmp
            try:
                app = QApplication.instance() or QApplication([])
                window = MainWindow()
                source = Path(tmp) / 'sample.png'
                Image.new('RGB', (400, 300), 'navy').save(source)
                window.add_paths([str(source)])
                window.logo = Image.new('RGBA', (100, 40), 'red')
                window.phone.setText('0912 345 678')
                window.custom_text.setPlainText('Nội thất Minh Điến\nZalo 0912 345 678')
                window.preview.set_logo(window.logo)
                window.preview.resize(700, 550)
                window.show(); app.processEvents()
                widget = window.preview
                rect = widget.photo_rect()
                def point(x, y):
                    return QPoint(round(rect.x()+x*rect.width()/400), round(rect.y()+y*rect.height()/300))
                a,b,c,d = widget.boxes['logo']
                QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=point((a+c)//2,(b+d)//2))
                QTest.mouseMove(widget, point(120, 90))
                QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=point(120,90))
                self.assertLess(window.settings.logo_x, .5)
                a,b,c,d = widget.boxes['logo']
                old_size = window.settings.logo_size
                QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=point(c,d))
                QTest.mouseMove(widget, point(c+30,d+10))
                QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=point(c+30,d+10))
                self.assertGreater(window.settings.logo_size, old_size)
                a,b,c,d = widget.boxes['phone']
                QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=point((a+c)//2,(b+d)//2))
                QTest.mouseMove(widget, point(160,100))
                QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=point(160,100))
                self.assertLess(window.settings.phone_x, .6)
                a,b,c,d = widget.boxes['custom']
                QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=point((a+c)//2,(b+d)//2))
                QTest.mouseMove(widget, point(180,140))
                QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=point(180,140))
                self.assertLess(window.settings.custom_x, .6)
                window.save_current()
                self.assertAlmostEqual(PresetStore().current()[1].phone_x, window.settings.phone_x)
                self.assertEqual(PresetStore().current()[1].custom_text, 'Nội thất Minh Điến\nZalo 0912 345 678')
                window.close()
            finally:
                if prior is None: os.environ.pop('APPDATA', None)
                else: os.environ['APPDATA'] = prior
