# ui/generator_main.py
import sys
import os

# 상위 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

# 기존 코드 import (리팩토링 전까지는 기존 파일 사용)
# 파일이 분리되기 전까지는 기존 GeneratorApp 클래스를 그대로 사용
from exam_generator_app import GeneratorApp as BaseGeneratorApp


class GeneratorApp(BaseGeneratorApp):
    """확장된 시험지 생성기 (필요시 오버라이드)"""
    
    def __init__(self):
        super().__init__()
        # 추가 기능이 필요하면 여기에 구현


# 테스트용 직접 실행
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorApp()
    window.show()
    sys.exit(app.exec_())