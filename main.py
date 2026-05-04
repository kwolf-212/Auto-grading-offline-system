# main.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# 분리된 모듈 import
from common.constants import DEFAULT_EXAM_SETTINGS
from exam_generator.pdf_engine import PDFEngine
from ui.widgets.pdf_preview_widget import PDFPreviewWidget
from ui.dialogs.exam_settings_dialog import ExamSettingsDialog

# 아직 분리되지 않은 부분은 기존 파일에서 import
from exam_generator_app import GeneratorApp as BaseGeneratorApp


class GeneratorApp(BaseGeneratorApp):
    """통합된 시험지 생성기"""
    
    def __init__(self):
        super().__init__()
        # 분리된 컴포넌트 사용
        self.pdf_engine = PDFEngine(self.questions, self.settings)


def main():
    app = QApplication(sys.argv)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    
    window = GeneratorApp()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()