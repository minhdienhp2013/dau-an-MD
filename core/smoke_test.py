"""Check the packaged app without changing the customer's saved presets."""
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image


def run(app):
    from core import presets
    from core.batch_processor import export_one
    from core.config import Settings
    from core.background_remove import remove_solid_background
    from ui.main_window import MainWindow
    from PySide6.QtGui import QPalette, QColor

    with TemporaryDirectory() as temp:
        folder = Path(temp)
        previous = presets.data_dir
        presets.data_dir = lambda: folder
        window = None
        original_palette = app.palette()
        dark_palette = QPalette(original_palette)
        for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base,
                     QPalette.ColorRole.Button):
            dark_palette.setColor(role, QColor('#202020'))
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                     QPalette.ColorRole.ButtonText):
            dark_palette.setColor(role, QColor('#ffffff'))
        app.setPalette(dark_palette)
        try:
            window = MainWindow()
            window.show()
            files = []
            for suffix in ('jpg', 'png'):
                source = folder / ('sample.' + suffix)
                Image.new('RGB', (400, 300), 'navy').save(source)
                files.append(str(source))
            window.add_paths(files)
            window.phone.setText('0904 101 034')
            window.custom_text.setPlainText('Nội thất Minh Điến')
            logo = Image.new('RGBA', (80, 40), 'red')
            window.logo = logo
            window.preview.set_logo(logo)
            app.processEvents()
            # A dark system theme must not produce white text on our light controls.
            for widget in (window.phone, window.custom_text, window.font_combo):
                palette = widget.palette()
                assert palette.color(QPalette.ColorRole.Text).lightness() < 100
                assert palette.color(QPalette.ColorRole.Base).lightness() > 200
            assert window.list.count() == 2
            assert 'phone' in window.preview.boxes
            assert 'logo' in window.preview.boxes
            assert 'custom' in window.preview.boxes
            settings = Settings(phone='0904 101 034', custom_text='Minh Điến')
            outputs = [export_one(source, temp, settings, logo) for source in files]
            duplicate = export_one(files[0], temp, settings, logo)
            assert duplicate.name == 'sample_watermark_2.jpg'
            for output in outputs:
                with Image.open(output) as image:
                    assert image.size == (400, 300)
            assert remove_solid_background(Image.new('RGB', (20, 20), 'white'), 32, 0).getpixel((0, 0))[3] == 0
            window.close()
            window = None
        finally:
            if window is not None:
                window.close()
            presets.data_dir = previous
            app.setPalette(original_palette)
    print('WATERMARK_SMOKE_OK', flush=True)
    return 0
