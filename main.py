# main.py
import sys
from PyQt5.QtWidgets import QApplication


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 모드 선택
    if len(sys.argv) > 1 and sys.argv[1] == "--grader":
        from ui.grader_main import GraderApp
        window = GraderApp()
    else:
        # 시험지 생성기 실행
        try:
            from ui.generator_main import GeneratorApp
            window = GeneratorApp()
        except ImportError:
            from exam_generator_app import GeneratorApp
            window = GeneratorApp()
    
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()