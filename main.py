import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Watermark Minh Điến')
    if '--smoke-test' in sys.argv:
        from core.smoke_test import run
        return run(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
