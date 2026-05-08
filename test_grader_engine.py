# test_grader_engine.py - 문제 영역별 텍스트 추출 디버깅 추가
import sys
import os
import json
import re  # ⬅️ 추가: re 모듈 import
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QImage, QPainter, QPen, QBrush
from PyQt5.QtCore import Qt, QSize, QRect, QThread, pyqtSignal, QTimer

from exam_grader.grader_engine import ExamGrader

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    import io
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class GradingWorker(QThread):
    progress = pyqtSignal(int, str)
    question_progress = pyqtSignal(int, int, str, str, str, float, str, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, exam_data, pdf_path, use_ocr=True, use_dynamic_detection=True):
        super().__init__()
        self.exam_data = exam_data
        self.pdf_path = pdf_path
        self.use_ocr = use_ocr
        self.use_dynamic_detection = use_dynamic_detection  # 추가
    
    def run(self):
        try:
            self.progress.emit(10, "Processing PDF...")
            
            # ExamGrader 사용 (동적 검출 활성화)
            from exam_grader.grader_engine import ExamGrader
            grader = ExamGrader(self.exam_data, use_detection=self.use_dynamic_detection)
            
            # 채점 실행
            result = grader.grade_from_pdf(self.pdf_path)
            
            # 진행 신호 전송
            total_questions = len(result['max_scores'])
            for idx, qid in enumerate(sorted(result['max_scores'].keys())):
                student = result['student_answers'].get(qid, '')
                correct = result['correct_answers'].get(qid, '')
                score = result['scores'].get(qid, 0)
                max_score = result['max_scores'].get(qid, 0)
                region_text = result['region_texts'].get(qid, "")
                qtype = result['question_types'].get(qid, "")
                
                if student and correct:
                    is_correct = (str(student).upper() == str(correct).upper())
                    result_text = "✓ 정답" if is_correct else "✗ 오답"
                elif student:
                    result_text = "⚠️ 답변 있음"
                else:
                    result_text = "❌ 미응답"
                
                self.question_progress.emit(
                    qid, total_questions, 
                    str(student) if student else "(없음)",
                    str(correct) if correct else "(없음)",
                    result_text, score, region_text, qtype
                )
                
                progress_pct = 50 + int((idx + 1) / total_questions * 45)
                self.progress.emit(progress_pct, f"Grading Q{qid}...")
                self.msleep(30)
            
            self.progress.emit(100, "Complete!")
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))


class QuestionDetailWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 헤더
        header_layout = QHBoxLayout()
        self.qid_label = QLabel("Q?")
        self.qid_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; background: transparent;")
        self.qid_label.setFixedWidth(60)
        header_layout.addWidget(self.qid_label)
        
        self.type_label = QLabel("-")
        self.type_label.setStyleSheet("font-size: 12px; color: #888; background: transparent;")
        header_layout.addWidget(self.type_label)
        
        header_layout.addStretch()
        
        self.score_label = QLabel("0 / 0 pts")
        self.score_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #e0e0e0; background: transparent;")
        header_layout.addWidget(self.score_label)
        
        layout.addLayout(header_layout)
        
        # 문제 영역 텍스트
        region_frame = QFrame()
        region_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-radius: 8px;
                padding: 8px;
                border: 1px solid #3d3d3d;
            }
        """)
        region_layout = QVBoxLayout(region_frame)
        
        region_title = QLabel("📌 문제 영역 추출 텍스트")
        region_title.setStyleSheet("font-size: 11px; color: #ff9800; font-weight: bold; background: transparent;")
        region_layout.addWidget(region_title)
        
        self.region_text_label = QLabel("-")
        self.region_text_label.setWordWrap(True)
        self.region_text_label.setStyleSheet("""
            font-size: 10px; 
            font-family: monospace; 
            color: #e0e0e0; 
            background-color: #0d0d1a; 
            padding: 8px; 
            border-radius: 4px;
        """)
        region_layout.addWidget(self.region_text_label)
        
        layout.addWidget(region_frame)
        
        # 답안 비교 영역
        answer_frame = QFrame()
        answer_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        answer_layout = QHBoxLayout(answer_frame)
        
        # 학생 답변
        student_frame = QFrame()
        student_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 6px; padding: 8px;")
        student_layout = QVBoxLayout(student_frame)
        
        student_title = QLabel("📝 추출된 학생 답변:")
        student_title.setStyleSheet("font-size: 11px; color: #aaa; background: transparent;")
        student_layout.addWidget(student_title)
        
        self.student_answer_label = QLabel("-")
        self.student_answer_label.setStyleSheet("font-size: 13px; font-family: monospace; font-weight: bold; color: #e0e0e0; background: transparent;")
        self.student_answer_label.setWordWrap(True)
        student_layout.addWidget(self.student_answer_label)
        answer_layout.addWidget(student_frame, 1)
        
        vs_label = QLabel(" VS ")
        vs_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff9800; background: transparent;")
        vs_label.setAlignment(Qt.AlignCenter)
        answer_layout.addWidget(vs_label)
        
        # 정답
        correct_frame = QFrame()
        correct_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 6px; padding: 8px;")
        correct_layout = QVBoxLayout(correct_frame)
        
        correct_title = QLabel("✓ 정답:")
        correct_title.setStyleSheet("font-size: 11px; color: #aaa; background: transparent;")
        correct_layout.addWidget(correct_title)
        
        self.correct_answer_label = QLabel("-")
        self.correct_answer_label.setStyleSheet("font-size: 13px; font-family: monospace; color: #4caf50; font-weight: bold; background: transparent;")
        self.correct_answer_label.setWordWrap(True)
        correct_layout.addWidget(self.correct_answer_label)
        answer_layout.addWidget(correct_frame, 1)
        
        layout.addWidget(answer_frame)
        
        # 결과
        result_frame = QFrame()
        result_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; padding: 8px;")
        result_layout = QHBoxLayout(result_frame)
        
        self.result_icon = QLabel("●")
        self.result_icon.setStyleSheet("font-size: 20px; background: transparent;")
        result_layout.addWidget(self.result_icon)
        
        self.result_text = QLabel("Waiting...")
        self.result_text.setStyleSheet("font-size: 12px; color: #e0e0e0; background: transparent;")
        result_layout.addWidget(self.result_text)
        
        result_layout.addStretch()
        
        self.points_earned_label = QLabel("0 pts")
        self.points_earned_label.setStyleSheet("font-size: 12px; font-weight: bold; color: #e0e0e0; background: transparent;")
        result_layout.addWidget(self.points_earned_label)
        
        layout.addWidget(result_frame)
        
        self.setLayout(layout)
    
    def update_question(self, qid, qtype, student, correct, score, max_score, result_text, region_text):
        self.qid_label.setText(f"Q{qid}")
        self.type_label.setText(f"[{qtype}]")
        
        # 영역 텍스트 표시 (최대 500자)
        display_text = region_text[:500] + ("..." if len(region_text) > 500 else "")
        self.region_text_label.setText(display_text if display_text else "(텍스트 없음)")
        
        self.student_answer_label.setText(student if student else "(없음)")
        self.correct_answer_label.setText(correct if correct else "(없음)")
        
        score_display = f"{score:.1f}" if score % 1 else f"{int(score)}"
        max_display = f"{max_score:.1f}" if max_score % 1 else f"{int(max_score)}"
        self.score_label.setText(f"{score_display} / {max_display} pts")
        self.points_earned_label.setText(f"+{score_display} pts")
        
        if "정답" in result_text:
            self.result_icon.setText("✅")
            self.result_text.setText(result_text)
            self.result_text.setStyleSheet("font-size: 12px; color: #4caf50; font-weight: bold;")
            self.score_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4caf50;")
        elif "오답" in result_text:
            self.result_icon.setText("❌")
            self.result_text.setText(result_text)
            self.result_text.setStyleSheet("font-size: 12px; color: #f44336; font-weight: bold;")
            self.score_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f44336;")
        elif "답변" in result_text:
            self.result_icon.setText("⚠️")
            self.result_text.setText(result_text)
            self.result_text.setStyleSheet("font-size: 12px; color: #ff9800; font-weight: bold;")
            self.score_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff9800;")
        else:
            self.result_icon.setText("❓")
            self.result_text.setText(result_text)
            self.result_text.setStyleSheet("font-size: 12px; color: #888;")

class PDFImageViewer(QLabel):
    """PDF 페이지 이미지 뷰어 - 문제 영역 박스 표시"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setMinimumSize(600, 800)
        self.setStyleSheet("""
            background-color: #1e1e1e;
            border: 1px solid #3d3d3d;
            border-radius: 8px;
        """)
        self.current_pixmap = None
        self.question_boxes = []
    
    def set_pdf_page_with_boxes(self, pdf_path, page_num, question_boxes):
        """PDF 페이지 이미지와 문제 영역 박스 표시"""
        self.question_boxes = question_boxes
        
        if not PYMUPDF_AVAILABLE:
            self.setText("PyMuPDF not installed")
            return
        
        try:
            doc = fitz.open(pdf_path)
            if page_num < len(doc):
                page = doc[page_num]
                zoom = 1.5
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                qimage = QImage.fromData(img_data, "PNG")
                pixmap = QPixmap.fromImage(qimage)
                
                # 박스 그리기
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.Antialiasing)
                
                for box in question_boxes:
                    x, y, w, h, qid, qtype = box
                    
                    # 문제 유형별 색상
                    if qtype in ['Multiple Choice', 'True/False']:
                        color = QColor(33, 150, 243)  # 파랑
                    elif qtype in ['Matching', 'Ordering']:
                        color = QColor(156, 39, 176)  # 보라
                    elif qtype == 'Code Writing':
                        color = QColor(76, 175, 80)   # 초록
                    elif qtype == 'Calculation':
                        color = QColor(255, 152, 0)   # 주황
                    else:
                        color = QColor(158, 158, 158)  # 회색
                    
                    pen = QPen(color, 2)
                    painter.setPen(pen)
                    painter.setBrush(QColor(color.red(), color.green(), color.blue(), 30))
                    painter.drawRect(x, y, w, h)
                    
                    # 문제 번호 표시
                    painter.setBrush(QColor(33, 150, 243, 200))
                    painter.setPen(Qt.NoPen)
                    painter.drawRect(x + 2, y + 2, 35, 18)
                    
                    painter.setPen(QPen(Qt.white, 1))
                    painter.setFont(QFont("Arial", 9, QFont.Bold))
                    painter.drawText(x + 5, y + 16, f"Q{qid}")
                
                painter.end()
                
                self.current_pixmap = pixmap
                scaled = pixmap.scaled(
                    self.width() - 20,
                    self.height() - 20,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.setPixmap(scaled)
            doc.close()
        except Exception as e:
            self.setText(f"Error: {str(e)}")
    
    def resizeEvent(self, event):
        """윈도우 크기 변경 시 이미지 다시 스케일"""
        if self.current_pixmap:
            scaled = self.current_pixmap.scaled(
                self.width() - 20,
                self.height() - 20,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.setPixmap(scaled)
        super().resizeEvent(event)
        
class GraderTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔬 채점 엔진 테스터 - 문제 영역별 분석")
        self.setGeometry(100, 100, 1600, 950)
        
        self.exam_data = None
        self.pdf_path = None
        self.grading_result = None
        self.worker = None
        self.all_questions_list = []
        
        self.init_ui()
        self.apply_style()
        
        if sys.platform == 'win32':
            tesseract_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            ]
            for path in tesseract_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
    
    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #2d2d2d;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #007acc;
            }
            QPushButton {
                background-color: #0d7377;
                color: white;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #14a085; }
            QPushButton#primary { background-color: #007acc; }
            QPushButton#primary:hover { background-color: #005a9e; }
            QTableWidget {
                background-color: #252526;
                alternate-background-color: #2d2d2d;
                gridline-color: #3d3d3d;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #007acc;
                padding: 8px;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #252526;
                color: #e0e0e0;          /* ← 추가: 텍스트 색상 흰색 계열 */
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                font-family: monospace;
            }
            QTextEdit:read-only {
                color: #e0e0e0;          /* ← 추가: 읽기 전용 상태에서도 적용 */
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                text-align: center;
            }
            QProgressBar::chunk { background-color: #007acc; border-radius: 6px; }
            QListWidget {
                background-color: #252526;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background-color: #0d7377;
            }
            QListWidget::item:hover:!selected {
                background-color: #3d3d3d;
            }
            QLabel { color: #e0e0e0; }
            QScrollArea { border: none; }
        """)
    
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(10)
        
        # 왼쪽: PDF 이미지 뷰어
        left_panel = self._create_image_panel()
        main_layout.addWidget(left_panel, 4)
        
        # 중간: 문제 목록
        middle_panel = self._create_question_list_panel()
        main_layout.addWidget(middle_panel, 2)
        
        # 오른쪽: 상세 정보
        right_panel = self._create_detail_panel()
        main_layout.addWidget(right_panel, 4)
        
        self.statusBar().showMessage("Ready - Load exam JSON and PDF")
    
    def _create_image_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        title = QLabel("📄 PDF 이미지 (문제 영역 표시)")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #007acc; padding: 5px;")
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setStyleSheet("border: 1px solid #3d3d3d; border-radius: 8px;")
        
        # PDFImageViewer 사용
        self.image_viewer = PDFImageViewer()
        scroll.setWidget(self.image_viewer)
        layout.addWidget(scroll, 1)
        
        # 페이지 탐색
        page_layout = QHBoxLayout()
        page_layout.addStretch()
        self.prev_btn = QPushButton("◀ Previous Page")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)
        page_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Page 1")
        self.page_label.setFixedWidth(80)
        self.page_label.setAlignment(Qt.AlignCenter)
        page_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Next Page ▶")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)
        page_layout.addWidget(self.next_btn)
        page_layout.addStretch()
        layout.addLayout(page_layout)
        
        self.current_page = 0
        self.total_pages = 0
        
        return panel
    
    def _create_question_list_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        title = QLabel("📋 문제 목록 (클릭하여 분석)")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #007acc; padding: 5px;")
        layout.addWidget(title)
        
        self.question_list = QListWidget()
        self.question_list.itemClicked.connect(self.on_question_selected)
        layout.addWidget(self.question_list)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.grade_status = QLabel("Ready")
        self.grade_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.grade_status)
        
        return panel
    
    def _create_detail_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        title = QLabel("🔍 문제 상세 분석")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #007acc; padding: 5px;")
        layout.addWidget(title)
        
        self.question_detail = QuestionDetailWidget()
        layout.addWidget(self.question_detail)
        
        control_group = QGroupBox("Controls")
        control_layout = QVBoxLayout(control_group)
        
        btn_row1 = QHBoxLayout()
        self.load_exam_btn = QPushButton("📋 Load Exam JSON")
        self.load_exam_btn.clicked.connect(self.load_exam)
        btn_row1.addWidget(self.load_exam_btn)
        
        self.load_pdf_btn = QPushButton("📄 Load PDF")
        self.load_pdf_btn.clicked.connect(self.load_pdf)
        btn_row1.addWidget(self.load_pdf_btn)
        control_layout.addLayout(btn_row1)
        
        btn_row2 = QHBoxLayout()
        self.grade_btn = QPushButton("🚀 Start Grading")
        self.grade_btn.setObjectName("primary")
        self.grade_btn.clicked.connect(self.start_grading)
        self.grade_btn.setEnabled(False)
        btn_row2.addWidget(self.grade_btn)
        
        self.clear_btn = QPushButton("🗑 Clear Results")
        self.clear_btn.clicked.connect(self.clear_results)
        btn_row2.addWidget(self.clear_btn)
        control_layout.addLayout(btn_row2)
        
        layout.addWidget(control_group)
        
        info_group = QGroupBox("Exam Information")
        info_layout = QVBoxLayout(info_group)
        self.exam_info_label = QLabel("Exam: Not loaded")
        self.exam_info_label.setStyleSheet("font-size: 11px; color: #888; padding: 5px;")
        self.exam_info_label.setWordWrap(True)
        info_layout.addWidget(self.exam_info_label)
        layout.addWidget(info_group)
        
        summary_group = QGroupBox("Grading Summary")
        summary_layout = QVBoxLayout(summary_group)
        
        self.total_score_label = QLabel("Total: 0 / 0 points (0%)")
        self.total_score_label.setAlignment(Qt.AlignCenter)
        self.total_score_label.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        summary_layout.addWidget(self.total_score_label)
        
        stats_layout = QHBoxLayout()
        self.correct_count_label = QLabel("✅ Correct: 0")
        self.correct_count_label.setStyleSheet("color: #4caf50;")
        stats_layout.addWidget(self.correct_count_label)
        
        self.incorrect_count_label = QLabel("❌ Incorrect: 0")
        self.incorrect_count_label.setStyleSheet("color: #f44336;")
        stats_layout.addWidget(self.incorrect_count_label)
        
        self.empty_count_label = QLabel("⚪ No Answer: 0")
        self.empty_count_label.setStyleSheet("color: #888;")
        stats_layout.addWidget(self.empty_count_label)
        
        summary_layout.addLayout(stats_layout)
        layout.addWidget(summary_group)
        
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_log_btn)
        layout.addWidget(log_group)
        
        return panel
    
    def _display_current_page_with_boxes(self):
        """PDF 페이지에 문제 영역 박스 표시 - OCR 지원"""
        if not self.pdf_path or not self.exam_data or not PYMUPDF_AVAILABLE:
            return
        
        try:
            from exam_grader.answer_parser import DynamicQuestionDetector
            detector = DynamicQuestionDetector(use_ocr=True)
            question_regions = detector.detect_all_questions(self.pdf_path, self.exam_data)
            
            if not question_regions:
                self._add_log("⚠️ No questions detected dynamically, using JSON coordinates")
                self._display_boxes_from_json()  # fallback
                return
            
            doc = fitz.open(self.pdf_path)
            if self.current_page < len(doc):
                page = doc[self.current_page]
                page_number = self.current_page + 1
                zoom = 1.5
                
                question_boxes = []
                
                for qid, info in question_regions.items():
                    if info.get('page_display') != page_number:
                        continue
                    
                    region = info['region']
                    qtype = info['question_type']
                    
                    box_x = int(region.x0 * zoom)
                    box_y = int(region.y0 * zoom)
                    box_w = int(region.width * zoom)
                    box_h = int(region.height * zoom)
                    
                    question_boxes.append((box_x, box_y, box_w, box_h, qid, qtype))
                
                self.image_viewer.set_pdf_page_with_boxes(self.pdf_path, self.current_page, question_boxes)
                
            doc.close()
        except Exception as e:
            self._add_log(f"❌ Dynamic display error: {str(e)}")

    def load_exam(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Exam JSON", "", "JSON (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.exam_data = json.load(f)
                
                exam_title = self.exam_data.get('exam_title', 'Unknown')
                total_q = len(self.exam_data.get('answers', []))
                total_pts = self.exam_data.get('total_points', 0)
                
                self.exam_info_label.setText(f"Exam: {exam_title} ({total_q} questions, {total_pts} pts)")
                self._add_log(f"✅ Loaded exam: {os.path.basename(file_path)}")
                
                self.all_questions_list = []
                self.question_list.clear()
                for q in self.exam_data.get('answers', []):
                    qid = q.get('question_id')
                    qtype = q.get('question_type', 'unknown')
                    score = q.get('score', 0)
                    item_text = f"Q{qid} [{qtype}] ({score} pts)"
                    self.question_list.addItem(item_text)
                    self.all_questions_list.append(qid)
                
                self._check_ready()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load exam:\n{str(e)}")
                self._add_log(f"❌ Failed: {str(e)}")
    
    def load_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load PDF", "", "PDF (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self._add_log(f"✅ Loaded PDF: {os.path.basename(file_path)}")
            
            if PYMUPDF_AVAILABLE:
                doc = fitz.open(file_path)
                self.total_pages = len(doc)
                doc.close()
                self.page_label.setText(f"Page 1/{self.total_pages}")
                self.prev_btn.setEnabled(False)
                self.next_btn.setEnabled(self.total_pages > 1)
                self.current_page = 0
                self._display_current_page_with_boxes()  # 변경: 박스 표시 사용
            
            if TESSERACT_AVAILABLE:
                self._add_log("📌 Tesseract OCR is available.")
            
            self._check_ready()
    
    def _display_current_page(self):
        if not self.pdf_path or not PYMUPDF_AVAILABLE:
            return
        
        try:
            doc = fitz.open(self.pdf_path)
            if self.current_page < len(doc):
                page = doc[self.current_page]
                zoom = 1.5
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                qimage = QImage.fromData(img_data, "PNG")
                pixmap = QPixmap.fromImage(qimage)
                
                scaled = pixmap.scaled(600, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.image_viewer.setPixmap(scaled)
            doc.close()
        except Exception as e:
            self.image_viewer.setText(f"Error: {str(e)}")
        
        self.page_label.setText(f"Page {self.current_page + 1}/{self.total_pages}")
    
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._display_current_page_with_boxes()  # 변경
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled(True)

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._display_current_page_with_boxes()  # 변경
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
    
    def _check_ready(self):
        ready = self.exam_data is not None and self.pdf_path is not None
        self.grade_btn.setEnabled(ready)
        self.grade_status.setText("✅ Ready to grade" if ready else "⚠️ Load both exam and PDF")
    
    def on_question_selected(self, item):
        row = self.question_list.row(item)
        if row < len(self.all_questions_list):
            qid = self.all_questions_list[row]
            self._display_question_detail(qid)
    
    def _display_question_detail(self, qid):
        if not self.exam_data:
            return
        
        q_info = None
        for q in self.exam_data.get('answers', []):
            if q.get('question_id') == qid:
                q_info = q
                break
        
        if not q_info:
            return
        
        qtype = q_info.get('question_type', 'unknown')
        max_score = q_info.get('score', 0)
        
        student = ""
        correct = q_info.get('expected_answer', q_info.get('answer', ''))
        score = 0
        result_text = "Not graded yet"
        region_text = ""
        
        if self.grading_result:
            student = self.grading_result.get('student_answers', {}).get(qid, '')
            score = self.grading_result.get('scores', {}).get(qid, 0)
            region_text = self.grading_result.get('region_texts', {}).get(qid, '')
            
            if student and correct:
                is_correct = (student.upper() == correct.upper())
                result_text = "✓ 정답" if is_correct else f"✗ 오답 (정답: {correct})"
            elif student:
                result_text = "⚠️ 답변 있음"
            else:
                result_text = "❌ 미응답"
        
        self.question_detail.update_question(qid, qtype, student, correct, score, max_score, result_text, region_text)
    
    def start_grading(self):
        if not self.exam_data or not self.pdf_path:
            QMessageBox.warning(self, "Warning", "Please load both exam JSON and PDF file.")
            return
        
        self.grade_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.grade_status.setText("⏳ Grading in progress...")
        self._add_log("🚀 Starting grading process (per-question region extraction)...")
        
        self.grading_result = None
        self.question_list.clear()
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            qtype = q.get('question_type', 'unknown')
            score = q.get('score', 0)
            item_text = f"Q{qid} [{qtype}] ({score} pts)"
            self.question_list.addItem(item_text)
        
        self.worker = GradingWorker(self.exam_data, self.pdf_path, use_ocr=True)
        self.worker.progress.connect(self.update_progress)
        self.worker.question_progress.connect(self.update_question_progress)
        self.worker.finished.connect(self.on_grading_finished)
        self.worker.error.connect(self.on_grading_error)
        self.worker.start()
    
    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.grade_status.setText(message)
        self._add_log(f"  {message}")
    
    def update_question_progress(self, qid, total, student, correct, result, score, region_text, qtype):
        for i in range(self.question_list.count()):
            item = self.question_list.item(i)
            if item.text().startswith(f"Q{qid}"):
                if "정답" in result:
                    item.setForeground(QColor(76, 175, 80))
                    item.setText(f"✓ {item.text()} → {score:.0f} pts")
                elif "오답" in result:
                    item.setForeground(QColor(244, 67, 54))
                    item.setText(f"✗ {item.text()} → {score:.0f} pts")
                elif "답변" in result:
                    item.setForeground(QColor(255, 152, 0))
                    item.setText(f"⚠️ {item.text()} → {score:.0f} pts")
                else:
                    item.setForeground(QColor(158, 158, 158))
                    item.setText(f"❌ {item.text()} → {score:.0f} pts")
                break
        
        # 로그에 영역 텍스트 기록
        self._add_log(f"  Q{qid}: {result} (Student: '{student}', Correct: '{correct}', Score: {score})")
        if region_text and len(region_text) > 0:
            preview = region_text[:150].replace('\n', ' ')
            self._add_log(f"       Region text: {preview}...")
        
        self._display_question_detail(qid)
        QApplication.processEvents()
    
    def on_grading_finished(self, result):
        self.grading_result = result
        self.progress_bar.setVisible(False)
        self.grade_btn.setEnabled(True)
        
        # 채점 후 페이지 갱신 (박스 색상 업데이트 등)
        self._display_current_page_with_boxes()  # 추가

        total = result['total']
        max_score = result['max_score']
        percentage = result['percentage']
        
        self.total_score_label.setText(f"Total: {total:.1f} / {max_score} points ({percentage:.1f}%)")
        
        student_answers = result.get('student_answers', {})
        correct_answers = result.get('correct_answers', {})
        
        correct_count = 0
        incorrect_count = 0
        empty_count = 0
        
        for qid in result['max_scores']:
            student = student_answers.get(qid, '')
            correct = correct_answers.get(qid, '')
            if not student:
                empty_count += 1
            elif student == correct:
                correct_count += 1
            else:
                incorrect_count += 1
        
        self.correct_count_label.setText(f"✅ Correct: {correct_count}")
        self.incorrect_count_label.setText(f"❌ Incorrect: {incorrect_count}")
        self.empty_count_label.setText(f"⚪ No Answer: {empty_count}")
        
        if percentage >= 90:
            self.total_score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #4caf50; padding: 10px;")
        elif percentage >= 60:
            self.total_score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ff9800; padding: 10px;")
        else:
            self.total_score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f44336; padding: 10px;")
        
        self.grade_status.setText(f"✅ Grading complete! Score: {total:.1f}/{max_score}")
        self._add_log(f"✅ Grading completed! Correct={correct_count}, Incorrect={incorrect_count}, Empty={empty_count}")
        
        if self.all_questions_list:
            self._display_question_detail(self.all_questions_list[0])
    
    def on_grading_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.grade_btn.setEnabled(True)
        self.grade_status.setText("❌ Grading failed")
        self._add_log(f"❌ Error: {error_msg}")
        QMessageBox.critical(self, "Error", f"Grading failed:\n{error_msg}")
    
    def clear_results(self):
        self.grading_result = None
        self._add_log("🗑 Cleared all results")
        
        self.question_list.clear()
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            qtype = q.get('question_type', 'unknown')
            score = q.get('score', 0)
            item_text = f"Q{qid} [{qtype}] ({score} pts)"
            self.question_list.addItem(item_text)
        
        self.total_score_label.setText("Total: 0 / 0 points (0%)")
        self.total_score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; padding: 10px;")
        self.correct_count_label.setText("✅ Correct: 0")
        self.incorrect_count_label.setText("❌ Incorrect: 0")
        self.empty_count_label.setText("⚪ No Answer: 0")
        self.grade_status.setText("Ready")
        
        self.question_detail.update_question(0, "", "", "", 0, 0, "No grading yet", "")
    
    def _add_log(self, message):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = GraderTester()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()