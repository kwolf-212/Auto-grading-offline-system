# test_grader_engine.py
import sys
import os
import json
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QImage, QPainter, QPen
from PyQt5.QtCore import Qt, QSize, QRect, QThread, pyqtSignal

# grader_engine.py의 기능 직접 import
from exam_grader.grader_engine import ExamGrader, AnswerParser, ScoringEngine

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


class GradingWorker(QThread):
    """채점 작업 스레드"""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, exam_data, pdf_path):
        super().__init__()
        self.exam_data = exam_data
        self.pdf_path = pdf_path
    
    def run(self):
        try:
            # ExamGrader 인스턴스 생성 (grader_engine.py 사용)
            grader = ExamGrader(self.exam_data)
            
            self.progress.emit(20, "Parsing PDF and detecting answers...")
            # PDF 파싱 및 채점 (텍스트 + 시각적 정보 모두 활용)
            scores = grader.grade_exam(self.pdf_path)
            
            self.progress.emit(60, "Getting student answers...")
            # 학생 답안 추출 (AnswerParser 직접 사용)
            answer_parser = AnswerParser(self.exam_data)
            student_answers = answer_parser.parse_from_pdf(self.pdf_path)
            
            self.progress.emit(80, "Calculating results...")
            total = grader.get_total_score(scores)
            max_score = grader.get_max_score()
            
            # 정답 정보 수집
            correct_answers = {}
            question_types = {}
            max_scores = {}
            for q in self.exam_data.get('answers', []):
                qid = q.get('question_id')
                if qid:
                    correct_answers[qid] = q.get('expected_answer', q.get('answer', ''))
                    question_types[qid] = q.get('question_type', 'unknown')
                    max_scores[qid] = q.get('score', 0)
            
            result = {
                'student_answers': student_answers,
                'scores': scores,
                'total': total,
                'max_score': max_score,
                'percentage': (total / max_score * 100) if max_score > 0 else 0,
                'correct_answers': correct_answers,
                'question_types': question_types,
                'max_scores': max_scores
            }
            
            self.progress.emit(100, "Complete!")
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))


class PDFPageViewer(QLabel):
    """PDF 페이지 뷰어 (문제 위치 표시) - 좌표 변환 수정"""
    
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
        self.current_page_rect = None  # PDF 페이지 크기
        self.answer_positions = {}
        self.student_answers = {}
        self.correct_answers = {}
        self.scores = {}
    
    def set_pdf_page(self, pdf_path, page_num, positions, student_answers, correct_answers, scores):
        """PDF 페이지 표시 및 답안 위치 표시"""
        self.answer_positions = positions
        self.student_answers = student_answers
        self.correct_answers = correct_answers
        self.scores = scores
        
        if not PYMUPDF_AVAILABLE:
            self.setText("PyMuPDF not installed")
            return
        
        try:
            doc = fitz.open(pdf_path)
            if page_num < len(doc):
                page = doc[page_num]
                
                # 페이지 크기 저장 (포인트 단위)
                self.current_page_rect = page.rect
                
                # 렌더링 해상도 (높을수록 선명하지만 느림)
                zoom = 2.0
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                img_data = pix.tobytes("png")
                qimage = QImage.fromData(img_data, "PNG")
                self.current_pixmap = QPixmap.fromImage(qimage)
                
                # 크기 조정
                scaled = self.current_pixmap.scaled(
                    self.width() - 20,
                    self.height() - 20,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.setPixmap(scaled)
                self.setFixedSize(scaled.size())
                
            doc.close()
            self.update()
            
        except Exception as e:
            self.setText(f"Error: {str(e)}")
    
    def _pdf_to_display_coords(self, pdf_x, pdf_y, pixmap_rect):
        """
        PDF 좌표를 화면 표시 좌표로 변환 (정확도 향상)
        
        PDF 좌표계: 원점 = 왼쪽 하단, Y축 위로 증가
        JSON 저장: Y좌표는 상단 기준 (0이 상단)
        """
        if not self.current_pixmap or not self.current_page_rect:
            return pdf_x, pdf_y
        
        # PDF 페이지 크기 (포인트)
        page_width = self.current_page_rect.width
        page_height = self.current_page_rect.height
        
        # 렌더링 시 사용한 줌 (2.0)
        render_zoom = 2.0
        render_width = page_width * render_zoom
        render_height = page_height * render_zoom
        
        # 실제 표시되는 이미지 크기
        display_width = pixmap_rect.width()
        display_height = pixmap_rect.height()
        
        # 표시 비율
        scale_x = display_width / render_width
        scale_y = display_height / render_height
        
        # PDF 좌표 -> 렌더링 이미지 좌표
        render_x = pdf_x * render_zoom
        
        # 중요: JSON 저장된 Y는 상단 기준, PDF 좌표계는 하단 기준이므로 변환
        # JSON Y (상단 기준) -> PDF Y (하단 기준) 변환
        pdf_y_from_bottom = page_height - pdf_y
        render_y = pdf_y_from_bottom * render_zoom
        
        # 렌더링 이미지 좌표 -> 화면 좌표
        display_x = pixmap_rect.x() + (render_x * scale_x)
        display_y = pixmap_rect.y() + (render_height - render_y) * scale_y
        
        return display_x, display_y
    
    def paintEvent(self, event):
        """문제 위치에 표시 그리기"""
        super().paintEvent(event)
        
        if not self.current_pixmap or not self.pixmap():
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 현재 표시된 pixmap의 위치 계산
        pixmap_rect = self.pixmap().rect()
        pixmap_rect.moveCenter(self.rect().center())
        
        # 각 문제 위치에 표시
        for qid, (x, y, _) in self.answer_positions.items():
            # PDF 좌표를 화면 좌표로 변환
            display_x, display_y = self._pdf_to_display_coords(x, y, pixmap_rect)
            
            # 학생 답안과 정답 비교
            student = self.student_answers.get(qid, "")
            correct = self.correct_answers.get(qid, "")
            score = self.scores.get(qid, 0)
            
            is_correct = (student == correct) if student and correct else False
            
            # 색상 결정
            if score > 0 and student and is_correct:
                color = QColor(76, 175, 80)  # 초록 (정답)
                pen_color = QColor(76, 175, 80)
            elif student:
                color = QColor(255, 152, 0)  # 주황 (답변 있음)
                pen_color = QColor(255, 152, 0)
            else:
                color = QColor(158, 158, 158)  # 회색 (미응답)
                pen_color = QColor(158, 158, 158)
            
            # 표시할 텍스트
            text = f"Q{qid}"
            if student:
                text += f": {student}"
            if correct and student and student != correct:
                text += f" (✓:{correct})"
            if score > 0:
                text += f" [{score:.0f}]" if score == int(score) else f" [{score:.1f}]"
            
            # 배경 원 그리기
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 100))
            painter.setPen(QPen(pen_color, 2))
            painter.drawEllipse(int(display_x - 20), int(display_y - 20), 40, 40)
            
            # 텍스트 그리기
            painter.setPen(QPen(Qt.white, 1))
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            painter.drawText(int(display_x - 30), int(display_y - 25), int(60), int(30), 
                            Qt.AlignCenter, text)
        
        painter.end()


class GraderTester(QMainWindow):
    """채점 엔진 테스터 (grader_engine.py 직접 사용)"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔬 채점 엔진 테스터")
        self.setGeometry(100, 100, 1400, 900)
        
        self.exam_data = None
        self.exam_path = None
        self.pdf_path = None
        self.grading_result = None
        self.worker = None
        
        self.init_ui()
        self.apply_style()
    
    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e1e;
            }
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
            QPushButton:hover {
                background-color: #14a085;
            }
            QPushButton#primary {
                background-color: #007acc;
            }
            QPushButton#primary:hover {
                background-color: #005a9e;
            }
            QTableWidget {
                background-color: #252526;
                alternate-background-color: #2d2d2d;
                gridline-color: #3d3d3d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #007acc;
                padding: 8px;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #252526;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                color: #e0e0e0;
                font-family: monospace;
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #007acc;
                border-radius: 6px;
            }
            QLabel {
                color: #e0e0e0;
            }
        """)
    
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # ===== 왼쪽: PDF 뷰어 =====
        left_panel = self._create_pdf_panel()
        main_layout.addWidget(left_panel, 5)
        
        # ===== 오른쪽: 컨트롤 및 결과 =====
        right_panel = self._create_control_panel()
        main_layout.addWidget(right_panel, 3)
        
        self.statusBar().showMessage("Ready")
    
    def _create_pdf_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        title = QLabel("📄 PDF Viewer with Answer Positions")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; padding: 5px;")
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setStyleSheet("border: 1px solid #3d3d3d; border-radius: 8px;")
        
        self.pdf_viewer = PDFPageViewer()
        scroll.setWidget(self.pdf_viewer)
        layout.addWidget(scroll, 1)
        
        # 페이지 컨트롤
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
        self.page_positions = {}
        
        return panel
    
    def _create_control_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        
        # ===== 파일 로드 =====
        file_group = QGroupBox("File Load")
        file_layout = QVBoxLayout(file_group)
        
        btn_row = QHBoxLayout()
        self.load_exam_btn = QPushButton("📋 Load Exam JSON")
        self.load_exam_btn.clicked.connect(self.load_exam)
        btn_row.addWidget(self.load_exam_btn)
        
        self.load_pdf_btn = QPushButton("📄 Load PDF")
        self.load_pdf_btn.clicked.connect(self.load_pdf)
        btn_row.addWidget(self.load_pdf_btn)
        file_layout.addLayout(btn_row)
        
        self.exam_info_label = QLabel("Exam: Not loaded")
        self.exam_info_label.setStyleSheet("font-size: 11px; color: #888; padding: 5px;")
        file_layout.addWidget(self.exam_info_label)
        
        self.pdf_info_label = QLabel("PDF: Not loaded")
        self.pdf_info_label.setStyleSheet("font-size: 11px; color: #888; padding: 5px;")
        file_layout.addWidget(self.pdf_info_label)
        
        layout.addWidget(file_group)
        
        # ===== 채점 실행 =====
        grade_group = QGroupBox("Grading")
        grade_layout = QVBoxLayout(grade_group)
        
        self.grade_btn = QPushButton("🚀 Start Grading")
        self.grade_btn.setObjectName("primary")
        self.grade_btn.clicked.connect(self.start_grading)
        self.grade_btn.setEnabled(False)
        grade_layout.addWidget(self.grade_btn)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        grade_layout.addWidget(self.progress_bar)
        
        self.grade_status = QLabel("Ready")
        self.grade_status.setAlignment(Qt.AlignCenter)
        grade_layout.addWidget(self.grade_status)
        
        layout.addWidget(grade_group)
        
        # ===== 채점 결과 =====
        result_group = QGroupBox("Grading Results")
        result_layout = QVBoxLayout(result_group)
        
        summary_layout = QHBoxLayout()
        self.total_score_label = QLabel("Total: - / -")
        self.total_score_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #007acc;")
        summary_layout.addWidget(self.total_score_label)
        
        self.percentage_label = QLabel("(-%)")
        self.percentage_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        summary_layout.addWidget(self.percentage_label)
        
        summary_layout.addStretch()
        result_layout.addLayout(summary_layout)
        
        # 결과 테이블
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(7)
        self.result_table.setHorizontalHeaderLabels(["Q#", "Type", "Student", "Correct", "Score", "Max", "Result"])
        self.result_table.setAlternatingRowColors(True)
        self.result_table.setColumnWidth(0, 50)
        self.result_table.setColumnWidth(1, 100)
        self.result_table.setColumnWidth(2, 80)
        self.result_table.setColumnWidth(3, 80)
        self.result_table.setColumnWidth(4, 60)
        self.result_table.setColumnWidth(5, 60)
        self.result_table.setColumnWidth(6, 80)
        result_layout.addWidget(self.result_table)
        
        layout.addWidget(result_group)
        
        # ===== 파싱 로그 =====
        log_group = QGroupBox("Parsing Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)
        
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.clicked.connect(lambda: self.log_text.clear())
        log_layout.addWidget(clear_log_btn)
        
        layout.addWidget(log_group)
        
        return panel
    
    def load_exam(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Exam JSON", "", "JSON (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.exam_data = json.load(f)
                self.exam_path = file_path
                
                exam_title = self.exam_data.get('exam_title', 'Unknown')
                total_q = len(self.exam_data.get('answers', []))
                total_pts = self.exam_data.get('total_points', 0)
                
                self.exam_info_label.setText(f"Exam: {exam_title} ({total_q} questions, {total_pts} pts)")
                self._add_log(f"✅ Loaded exam: {os.path.basename(file_path)}")
                
                self._check_ready()

                # 디버깅: 좌표 범위 확인
                min_x, max_x = float('inf'), float('-inf')
                min_y, max_y = float('inf'), float('-inf')
                for q in self.exam_data.get('answers', []):
                    pos = q.get('position')
                    if pos:
                        x, y = pos.get('x', 0), pos.get('y', 0)
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
                        min_y = min(min_y, y)
                        max_y = max(max_y, y)
                
                self._add_log(f"📐 좌표 범위: X={min_x:.1f}~{max_x:.1f}, Y={min_y:.1f}~{max_y:.1f}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load exam:\n{str(e)}")
                self._add_log(f"❌ Failed to load exam: {str(e)}")
    
    def load_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load PDF", "", "PDF (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self.pdf_info_label.setText(f"PDF: {os.path.basename(file_path)}")
            self._add_log(f"✅ Loaded PDF: {os.path.basename(file_path)}")
            
            # PDF 페이지 수 계산
            if PYMUPDF_AVAILABLE:
                doc = fitz.open(file_path)
                self.total_pages = len(doc)
                doc.close()
                self.page_label.setText(f"Page 1/{self.total_pages}")
                self.prev_btn.setEnabled(False)
                self.next_btn.setEnabled(self.total_pages > 1)
            
            # 문제 위치 정보 수집
            self._collect_positions()
            
            # 첫 페이지 표시
            self.current_page = 0
            self._display_current_page()
            
            self._check_ready()
    
    def _collect_positions(self):
        """JSON에서 문제 위치 정보 수집"""
        self.page_positions = {}
        
        if not self.exam_data:
            return
        
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            pos = q.get('position')
            
            if pos and qid:
                page = pos.get('page', 1)
                x = pos.get('x', 0)
                y = pos.get('y', 0)
                
                if page not in self.page_positions:
                    self.page_positions[page] = []
                self.page_positions[page].append((qid, x, y))
    
    def _display_current_page(self):
        """현재 페이지 표시 (디버깅용 로그 추가)"""
        if not self.pdf_path:
            return
        
        page_num = self.current_page + 1
        positions = self.page_positions.get(page_num, [])
        
        # PDF 페이지 크기 확인
        if PYMUPDF_AVAILABLE:
            doc = fitz.open(self.pdf_path)
            if self.current_page < len(doc):
                page_rect = doc[self.current_page].rect
                self._add_log(f"📄 Page {page_num} size: {page_rect.width:.1f} x {page_rect.height:.1f} pt")
            doc.close()
        
        self._add_log(f"📍 Page {page_num}: {len(positions)} positions found")
        for qid, x, y in positions:
            self._add_log(f"    Q{qid}: x={x:.2f}, y={y:.2f}")
        
        # 정답 정보
        correct_answers = {}
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            expected = q.get('expected_answer', q.get('answer', ''))
            correct_answers[qid] = expected
        
        # 학생 답안 및 점수
        student_answers = {}
        scores = {}
        if self.grading_result:
            student_answers = self.grading_result.get('student_answers', {})
            scores = self.grading_result.get('scores', {})
            self._add_log(f"📊 Grading results: {len(student_answers)} answers found")
            for qid, ans in student_answers.items():
                self._add_log(f"    Q{qid}: student='{ans}', correct='{correct_answers.get(qid, '')}'")
        
        # 위치 정보 변환
        pos_dict = {qid: (x, y, "") for qid, x, y in positions}
        
        self.pdf_viewer.set_pdf_page(
            self.pdf_path, 
            self.current_page, 
            pos_dict,
            student_answers,
            correct_answers,
            scores
        )
        
        self.page_label.setText(f"Page {page_num}/{self.total_pages}")
    
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._display_current_page()
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled(True)
    
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._display_current_page()
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
    
    def _check_ready(self):
        ready = self.exam_data is not None and self.pdf_path is not None
        self.grade_btn.setEnabled(ready)
        if ready:
            self.grade_status.setText("✅ Ready to grade")
            self.grade_status.setStyleSheet("color: #4caf50;")
        else:
            self.grade_status.setText("⚠️ Load both exam and PDF")
            self.grade_status.setStyleSheet("color: #ff9800;")
    
    def start_grading(self):
        if not self.exam_data or not self.pdf_path:
            QMessageBox.warning(self, "Warning", "Please load both exam JSON and PDF file.")
            return
        
        self.grade_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.grade_status.setText("⏳ Grading in progress...")
        self._add_log("🚀 Starting grading process...")
        
        self.worker = GradingWorker(self.exam_data, self.pdf_path)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_grading_finished)
        self.worker.error.connect(self.on_grading_error)
        self.worker.start()
    
    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.grade_status.setText(message)
        self._add_log(f"  {message}")
    
    def on_grading_finished(self, result):
        self.grading_result = result
        self.progress_bar.setVisible(False)
        self.grade_btn.setEnabled(True)
        
        total = result['total']
        max_score = result['max_score']
        percentage = result['percentage']
        
        self.total_score_label.setText(f"Total: {total:.1f} / {max_score}")
        self.percentage_label.setText(f"({percentage:.1f}%)")
        
        if percentage >= 90:
            self.percentage_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4caf50;")
        elif percentage >= 60:
            self.percentage_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff9800;")
        else:
            self.percentage_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f44336;")
        
        self._display_results(result)
        self._display_current_page()
        
        self.grade_status.setText(f"✅ Grading complete! Score: {total:.1f}/{max_score}")
        self._add_log(f"✅ Grading completed! Total: {total:.1f}/{max_score} ({percentage:.1f}%)")
    
    def on_grading_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.grade_btn.setEnabled(True)
        self.grade_status.setText("❌ Grading failed")
        self._add_log(f"❌ Error: {error_msg}")
        QMessageBox.critical(self, "Error", f"Grading failed:\n{error_msg}")
    
    def _display_results(self, result):
        scores = result['scores']
        student_answers = result.get('student_answers', {})
        correct_answers = result.get('correct_answers', {})
        question_types = result.get('question_types', {})
        max_scores = result.get('max_scores', {})
        
        all_qids = sorted(set(list(scores.keys()) + list(correct_answers.keys())))
        
        self.result_table.setRowCount(len(all_qids))
        
        for i, qid in enumerate(all_qids):
            student = student_answers.get(qid, '')
            correct = correct_answers.get(qid, '')
            qtype = question_types.get(qid, '')
            score = scores.get(qid, 0)
            max_score = max_scores.get(qid, 0)
            
            is_correct = (student == correct) if student and correct else False
            
            # Q#
            id_item = QTableWidgetItem(str(qid))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(i, 0, id_item)
            
            # Type
            type_item = QTableWidgetItem(qtype)
            type_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(i, 1, type_item)
            
            # Student Answer
            student_item = QTableWidgetItem(student if student else "-")
            student_item.setTextAlignment(Qt.AlignCenter)
            if is_correct:
                student_item.setForeground(QColor(76, 175, 80))
            elif student:
                student_item.setForeground(QColor(255, 152, 0))
            self.result_table.setItem(i, 2, student_item)
            
            # Correct Answer
            correct_item = QTableWidgetItem(correct if correct else "-")
            correct_item.setTextAlignment(Qt.AlignCenter)
            correct_item.setForeground(QColor(76, 175, 80))
            self.result_table.setItem(i, 3, correct_item)
            
            # Score
            score_item = QTableWidgetItem(f"{score:.1f}" if score % 1 else f"{int(score)}")
            score_item.setTextAlignment(Qt.AlignCenter)
            if score == max_score:
                score_item.setForeground(QColor(76, 175, 80))
            elif score > 0:
                score_item.setForeground(QColor(255, 152, 0))
            else:
                score_item.setForeground(QColor(244, 67, 54))
            self.result_table.setItem(i, 4, score_item)
            
            # Max
            max_item = QTableWidgetItem(str(max_score))
            max_item.setTextAlignment(Qt.AlignCenter)
            self.result_table.setItem(i, 5, max_item)
            
            # Result
            result_text = "✓ 정답" if is_correct else ("✗ 오답" if student else "미응답")
            result_item = QTableWidgetItem(result_text)
            result_item.setTextAlignment(Qt.AlignCenter)
            if is_correct:
                result_item.setForeground(QColor(76, 175, 80))
            elif student:
                result_item.setForeground(QColor(255, 152, 0))
            else:
                result_item.setForeground(QColor(158, 158, 158))
            self.result_table.setItem(i, 6, result_item)
        
        self.result_table.resizeColumnsToContents()
    
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