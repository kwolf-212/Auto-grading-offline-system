# exam_grader_app.py

import sys
import json
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt

from grader import ExamGrader


class GraderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("시험채점기")
        self.setGeometry(200, 100, 800, 600)

        self.exam_data = None
        self.image_path = None

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        load_exam_btn = QPushButton("시험 불러오기 (JSON)")
        load_exam_btn.clicked.connect(self.load_exam)

        load_img_btn = QPushButton("시험지 업로드")
        load_img_btn.clicked.connect(self.load_image)

        grade_btn = QPushButton("채점 실행")
        grade_btn.clicked.connect(self.grade_exam)

        self.image_label = QLabel("이미지 없음")
        self.image_label.setAlignment(Qt.AlignCenter)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["문제", "점수", "수정"])

        layout.addWidget(load_exam_btn)
        layout.addWidget(load_img_btn)
        layout.addWidget(grade_btn)
        layout.addWidget(self.image_label)
        layout.addWidget(self.table)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def load_exam(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "시험 파일 선택", "", "JSON (*.json)")
        if file_path:
            with open(file_path, "r") as f:
                self.exam_data = json.load(f)

            QMessageBox.information(self, "완료", "시험 로드 완료")

    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "이미지 선택", "", "Images (*.png *.jpg)")
        if file_path:
            self.image_path = file_path
            pixmap = QPixmap(file_path).scaled(400, 300, Qt.KeepAspectRatio)
            self.image_label.setPixmap(pixmap)

    def grade_exam(self):
        if not self.exam_data or not self.image_path:
            QMessageBox.warning(self, "오류", "시험 또는 이미지 필요")
            return

        grader = ExamGrader(self.exam_data)
        results = grader.grade_exam(self.image_path)

        self.show_results(results)

    def show_results(self, results):
        self.table.setRowCount(len(results))

        for i, (qid, score) in enumerate(results.items()):
            self.table.setItem(i, 0, QTableWidgetItem(str(qid)))
            self.table.setItem(i, 1, QTableWidgetItem(str(score)))

            edit = QLineEdit(str(score))
            edit.editingFinished.connect(self.update_scores)
            self.table.setCellWidget(i, 2, edit)

    def update_scores(self):
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 2)
            try:
                new_score = float(widget.text())
                self.table.setItem(row, 1, QTableWidgetItem(str(new_score)))
            except:
                pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GraderApp()
    window.show()
    sys.exit(app.exec_())
