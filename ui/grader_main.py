# ui/grader_main.py
import sys
import json
import os
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QKeySequence, QImage
from PyQt5.QtCore import Qt, QSize

from exam_grader import ExamGrader, ResultExporter
from ui.grader_styles import GRADER_STYLE
from ui.student_manager import StudentManagerDialog, StudentInfoWidget
from ui.widgets.pdf_preview_widget import PDFPreviewWidget
from exam_grader.image_preprocessor import ImagePreprocessor

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


class GraderApp(QMainWindow):
    """시험 채점기 메인 윈도우 (PDFPreviewWidget 사용)"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Exam Grader")
        self.setMinimumSize(1200, 800)
        
        # Data
        self.exam_data = None
        self.exam_file_path = None
        self.pdf_files = []
        self.current_pdf_index = 0
        self.current_pdf_path = None
        self.grading_results = {}
        
        # 학생 관리
        self.students = []
        self.current_student = None
        self.student_pdf_mapping = {}
        self.result_exporter = ResultExporter()
        
        self.preprocessor = None  # 전처리 결과 저장
        self.debug_mode = False    # 디버그 모드 활성화

        self.init_ui()
        self.apply_style()
        self.showMaximized()
    
    def apply_style(self):
        self.setStyleSheet(GRADER_STYLE + """
            QToolBar {
                background-color: #2d2d2d;
                border: none;
                border-bottom: 1px solid #3d3d3d;
                spacing: 5px;
                padding: 4px;
            }
            QToolButton {
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: bold;
                color: #e0e0e0;
            }
            QToolButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
            QToolButton:pressed {
                background-color: #2a2a2a;
            }
            QToolButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
            QStatusBar {
                background-color: #1e1e1e;
                color: #007acc;
                border-top: 1px solid #3d3d3d;
            }
            QTableWidget {
                gridline-color: #3d3d3d;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                padding: 8px;
                font-weight: bold;
            }
        """)
    
    def init_ui(self):
        # 메인 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 상단 도구띠
        self._create_toolbar()
        
        # 분할 레이아웃 (PDF 뷰어 | 점수표)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("QSplitter::handle { background-color: #3d3d3d; }")
        
        # 왼쪽: PDF 뷰어 (PDFPreviewWidget 사용)
        pdf_panel = self._create_pdf_panel()
        splitter.addWidget(pdf_panel)
        
        # 오른쪽: 점수표
        score_panel = self._create_score_panel()
        splitter.addWidget(score_panel)
        
        splitter.setSizes([500, 700])
        main_layout.addWidget(splitter, 1)
        
        self.statusBar().showMessage("Ready")
        self._create_shortcuts()
    
    def _create_toolbar(self):
        """상단 도구띠 생성"""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # ===== 파일 그룹 =====
        toolbar.addWidget(QLabel("📁"))
        
        self.load_exam_btn = QToolButton()
        self.load_exam_btn.setText("Exam")
        self.load_exam_btn.setToolTip("Load Exam JSON (Ctrl+O)")
        self.load_exam_btn.clicked.connect(self.load_exam)
        toolbar.addWidget(self.load_exam_btn)
        
        self.load_pdf_btn = QToolButton()
        self.load_pdf_btn.setText("PDF Files")
        self.load_pdf_btn.setToolTip("Load PDF Files (Ctrl+F)")
        self.load_pdf_btn.clicked.connect(self.load_pdf_files)
        toolbar.addWidget(self.load_pdf_btn)
        
        self.load_folder_btn = QToolButton()
        self.load_folder_btn.setText("PDF Folder")
        self.load_folder_btn.setToolTip("Load PDF Folder")
        self.load_folder_btn.clicked.connect(self.load_pdf_folder)
        toolbar.addWidget(self.load_folder_btn)
        
        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setFixedSize(2, 24)
        sep.setStyleSheet("background-color: #3d3d3d;")
        toolbar.addWidget(sep)
        
        # ===== PDF 탐색 그룹 =====
        self.prev_file_btn = QToolButton()
        self.prev_file_btn.setText("◀◀")
        self.prev_file_btn.setToolTip("Previous PDF (Left)")
        self.prev_file_btn.clicked.connect(self.prev_pdf)
        self.prev_file_btn.setEnabled(False)
        toolbar.addWidget(self.prev_file_btn)
        
        self.file_counter_label = QLabel("0/0")
        self.file_counter_label.setFixedWidth(50)
        self.file_counter_label.setAlignment(Qt.AlignCenter)
        self.file_counter_label.setStyleSheet("font-weight: bold; color: #007acc;")
        toolbar.addWidget(self.file_counter_label)
        
        self.next_file_btn = QToolButton()
        self.next_file_btn.setText("▶▶")
        self.next_file_btn.setToolTip("Next PDF (Right)")
        self.next_file_btn.clicked.connect(self.next_pdf)
        self.next_file_btn.setEnabled(False)
        toolbar.addWidget(self.next_file_btn)
        
        # 구분선
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.VLine)
        sep2.setFixedSize(2, 24)
        sep2.setStyleSheet("background-color: #3d3d3d;")
        toolbar.addWidget(sep2)
        
        # ===== 채점 그룹 =====
        self.grade_current_btn = QToolButton()
        self.grade_current_btn.setText("✅ Grade")
        self.grade_current_btn.setToolTip("Grade Current PDF (Ctrl+G)")
        self.grade_current_btn.setObjectName("grade_btn")
        self.grade_current_btn.clicked.connect(self.grade_current_pdf)
        toolbar.addWidget(self.grade_current_btn)
        
        self.grade_all_btn = QToolButton()
        self.grade_all_btn.setText("🚀 Grade All")
        self.grade_all_btn.setToolTip("Grade All PDFs (Ctrl+A)")
        self.grade_all_btn.setObjectName("grade_btn")
        self.grade_all_btn.clicked.connect(self.grade_all_pdfs)
        toolbar.addWidget(self.grade_all_btn)
        
        # 구분선
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.VLine)
        sep3.setFixedSize(2, 24)
        sep3.setStyleSheet("background-color: #3d3d3d;")
        toolbar.addWidget(sep3)
        
        # ===== 학생 그룹 =====
        self.manage_students_btn = QToolButton()
        self.manage_students_btn.setText("👥 Roster")
        self.manage_students_btn.setToolTip("Manage Student Roster")
        self.manage_students_btn.clicked.connect(self.manage_students)
        toolbar.addWidget(self.manage_students_btn)
        
        self.auto_match_btn = QToolButton()
        self.auto_match_btn.setText("🤖 Auto Match")
        self.auto_match_btn.setToolTip("Auto-match Students")
        self.auto_match_btn.clicked.connect(self.auto_match_students)
        toolbar.addWidget(self.auto_match_btn)
        
        # 구분선
        sep4 = QFrame()
        sep4.setFrameShape(QFrame.VLine)
        sep4.setFixedSize(2, 24)
        sep4.setStyleSheet("background-color: #3d3d3d;")
        toolbar.addWidget(sep4)
        
        # ===== 내보내기 그룹 =====
        self.export_json_btn = QToolButton()
        self.export_json_btn.setText("💾 JSON")
        self.export_json_btn.setToolTip("Export as JSON")
        self.export_json_btn.clicked.connect(lambda: self._export_results('json'))
        toolbar.addWidget(self.export_json_btn)
        
        self.export_csv_btn = QToolButton()
        self.export_csv_btn.setText("📊 CSV")
        self.export_csv_btn.setToolTip("Export as CSV")
        self.export_csv_btn.clicked.connect(lambda: self._export_results('csv'))
        toolbar.addWidget(self.export_csv_btn)
        
        self.clear_btn = QToolButton()
        self.clear_btn.setText("🗑 Clear")
        self.clear_btn.setToolTip("Clear All Results")
        self.clear_btn.clicked.connect(self.clear_results)
        toolbar.addWidget(self.clear_btn)
        
        # 오른쪽 여백
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)
        
        # 시험 정보 표시
        self.exam_info_label = QLabel("⚡ No Exam")
        self.exam_info_label.setStyleSheet("color: #888; padding: 0 10px; font-size: 11px;")
        toolbar.addWidget(self.exam_info_label)
        
        # toolbar에 추가
        self.preprocess_status = QLabel("🔧 -")
        self.preprocess_status.setStyleSheet("color: #888; padding: 0 10px; font-size: 11px;")
        toolbar.addWidget(self.preprocess_status)

        # 학생 정보 표시
        self.student_info_label = QLabel("👤 -")
        self.student_info_label.setStyleSheet("color: #888; padding: 0 10px; font-size: 11px;")
        toolbar.addWidget(self.student_info_label)
    
    def _create_pdf_panel(self):
        """PDF 표시 패널 (PDFPreviewWidget 사용)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # PDFPreviewWidget 생성 및 설정
        self.pdf_preview = PDFPreviewWidget()
        self.pdf_preview.set_grader_mode(True)  # 채점기 모드
        self.pdf_preview.refresh_btn.setVisible(False)  # 새로고침 버튼 숨김
        
        # 페이지 변경 시그널 연결 (필요시)
        # self.pdf_preview.page_changed.connect(self.on_page_changed)
        
        layout.addWidget(self.pdf_preview)
        return panel
    
    def _create_score_panel(self):
        """점수표 패널 생성"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 헤더
        header_layout = QHBoxLayout()
        title_label = QLabel("📊 Grading Results")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #007acc;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.total_score_label = QLabel("0 / 0 pts")
        self.total_score_label.setAlignment(Qt.AlignRight)
        self.total_score_label.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            color: #007acc;
            padding: 5px 10px;
            background-color: #252526;
            border-radius: 8px;
        """)
        header_layout.addWidget(self.total_score_label)
        layout.addLayout(header_layout)
        
        # 점수표
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Q#", "Score", "Max", "Answer", ""])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        self.table.setColumnWidth(0, 60)
        self.table.setColumnWidth(1, 80)
        self.table.setColumnWidth(2, 60)
        self.table.setColumnWidth(3, 300)
        self.table.setColumnWidth(4, 60)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        
        layout.addWidget(self.table, 1)
        
        # 상태 표시줄
        status_layout = QHBoxLayout()
        self.grade_status_label = QLabel("● Ready")
        self.grade_status_label.setStyleSheet("font-size: 11px; color: #4caf50;")
        status_layout.addWidget(self.grade_status_label)
        status_layout.addStretch()
        self.file_status_label = QLabel("")
        self.file_status_label.setStyleSheet("font-size: 11px; color: #888;")
        status_layout.addWidget(self.file_status_label)
        layout.addLayout(status_layout)
        
        return panel
    
    def _create_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self.load_exam)
        QShortcut(QKeySequence("Ctrl+F"), self, self.load_pdf_files)
        QShortcut(QKeySequence("Ctrl+G"), self, self.grade_current_pdf)
        QShortcut(QKeySequence("Ctrl+A"), self, self.grade_all_pdfs)
        QShortcut(QKeySequence("Left"), self, self.prev_pdf)
        QShortcut(QKeySequence("Right"), self, self.next_pdf)
    
    # ===== 시험 로드 =====
    def load_exam(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Exam", "", "JSON (*.json)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.exam_data = json.load(f)
                self.exam_file_path = file_path
                
                exam_title = self.exam_data.get('exam_title', 'Unknown')
                total_questions = len(self.exam_data.get('answers', []))
                total_points = self.exam_data.get('total_points', 0)
                
                self.exam_info_label.setText(f"📋 {exam_title[:30]} | {total_questions}Q | {total_points}P")
                self.statusBar().showMessage(f"Loaded: {os.path.basename(file_path)}")
                QMessageBox.information(self, "Success", "✅ Exam loaded!")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
    
    # ===== PDF 로드 (PDFPreviewWidget 사용) =====
    def load_pdf_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Select PDFs", "", "PDF (*.pdf)")
        if files:
            self._load_pdfs(files)
    
    def load_pdf_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select PDF Folder")
        if folder:
            files = [os.path.join(folder, f) for f in os.listdir(folder) if f.lower().endswith('.pdf')]
            files.sort()
            if files:
                self._load_pdfs(files)
            else:
                QMessageBox.warning(self, "Warning", "No PDF files found.")
    
    def _load_pdfs(self, paths):
        """PDF 파일들 로드"""
        self.pdf_files = paths
        self.current_pdf_index = 0
        
        if self.pdf_files:
            self.current_pdf_path = self.pdf_files[0]
            # 🔑 PDF 로드 시 전처리 수행
            if self.exam_data:
                self._preprocess_current_pdf()

            self.pdf_preview.load_pdf(self.current_pdf_path, 0)
            
            # 파일 카운터 업데이트
            self.file_counter_label.setText(f"1/{len(paths)}")
            self.prev_file_btn.setEnabled(len(paths) > 1)
            self.next_file_btn.setEnabled(len(paths) > 1)
            
            # 학생 정보 표시
            if self.current_pdf_path in self.student_pdf_mapping:
                student = self.student_pdf_mapping[self.current_pdf_path]
                self.student_info_label.setText(f"👤 {student.get('name', '')[:15]}")
            else:
                self.student_info_label.setText("👤 -")
            
            # 채점 결과 로드
            self._load_results_for_current_pdf()
            
            self.statusBar().showMessage(f"Loaded {len(paths)} PDFs")
    
    def _preprocess_current_pdf(self):
        """현재 PDF에 대해 ArUco 기반 전처리 수행"""
        if not self.exam_data or not self.current_pdf_path:
            return
        
        try:
            self.statusBar().showMessage("🔄 Preprocessing PDF with ArUco...")
            self.preprocessor = ImagePreprocessor(zoom=1.5, debug_mode=self.debug_mode)
            success = self.preprocessor.preprocess_pdf(self.current_pdf_path, self.exam_data)
            
            if success:
                summary = self.preprocessor.get_preprocess_summary()
                self.statusBar().showMessage(
                    f"✅ Preprocessed: {summary['calibrated_pages']}/{summary['total_pages']} pages, "
                    f"{summary['total_choice_regions']} regions"
                )

                self.preprocess_status.setText("✅ Preprocessed")
                self.preprocess_status.setStyleSheet("color: #4caf50; padding: 0 10px; font-size: 11px;")
            else:
                self.statusBar().showMessage("⚠️ Preprocessing failed")
                self.preprocessor = None

                self.preprocess_status.setText("⚠️ Not preprocessed")
                self.preprocess_status.setStyleSheet("color: #ff9800; padding: 0 10px; font-size: 11px;")
        except Exception as e:
            self.statusBar().showMessage(f"❌ Preprocessing error: {str(e)}")
            self.preprocessor = None
            
    # ===== PDF 탐색 =====
    def prev_pdf(self):
        if self.current_pdf_index > 0:
            self.current_pdf_index -= 1
            self.current_pdf_path = self.pdf_files[self.current_pdf_index]

            # 전처리 갱신
            self._preprocess_current_pdf() 

            self.pdf_preview.load_pdf(self.current_pdf_path, 0)
            self.file_counter_label.setText(f"{self.current_pdf_index + 1}/{len(self.pdf_files)}")
            
            # 학생 정보 업데이트
            if self.current_pdf_path in self.student_pdf_mapping:
                student = self.student_pdf_mapping[self.current_pdf_path]
                self.student_info_label.setText(f"👤 {student.get('name', '')[:15]}")
            else:
                self.student_info_label.setText("👤 -")
            
            self._load_results_for_current_pdf()
    
    def next_pdf(self):
        if self.current_pdf_index < len(self.pdf_files) - 1:
            self.current_pdf_index += 1
            self.current_pdf_path = self.pdf_files[self.current_pdf_index]

            # 전처리 갱신
            self._preprocess_current_pdf()

            self.pdf_preview.load_pdf(self.current_pdf_path, 0)
            self.file_counter_label.setText(f"{self.current_pdf_index + 1}/{len(self.pdf_files)}")
            
            if self.current_pdf_path in self.student_pdf_mapping:
                student = self.student_pdf_mapping[self.current_pdf_path]
                self.student_info_label.setText(f"👤 {student.get('name', '')[:15]}")
            else:
                self.student_info_label.setText("👤 -")
            
            self._load_results_for_current_pdf()
    
    # ===== 학생 관리 =====
    def manage_students(self):
        dialog = StudentManagerDialog(self, self.students)
        dialog.student_data_saved.connect(self.on_students_updated)
        dialog.exec_()
    
    def on_students_updated(self, data):
        self.students = data.get('students', [])
        QMessageBox.information(self, "Success", f"Updated {len(self.students)} students")
    
    def auto_match_students(self):
        if not self.pdf_files or not self.students:
            QMessageBox.warning(self, "Warning", "No PDFs or students loaded.")
            return
        
        matched = 0
        for pdf_path in self.pdf_files:
            filename = os.path.basename(pdf_path).lower()
            for student in self.students:
                student_id = student.get('student_id', '').lower()
                student_name = student.get('name', '').lower()
                if student_id and student_id in filename:
                    self.student_pdf_mapping[pdf_path] = student
                    matched += 1
                    break
                elif student_name and student_name in filename:
                    self.student_pdf_mapping[pdf_path] = student
                    matched += 1
                    break
        
        self.statusBar().showMessage(f"Auto-matched {matched} students")
        if self.current_pdf_path in self.student_pdf_mapping:
            student = self.student_pdf_mapping[self.current_pdf_path]
            self.student_info_label.setText(f"👤 {student.get('name', '')[:15]}")
    
    # ===== 채점 =====
    def _load_results_for_current_pdf(self):
        if self.current_pdf_path and self.current_pdf_path in self.grading_results:
            self._display_results(self.grading_results[self.current_pdf_path]['results'])
            total = self.grading_results[self.current_pdf_path]['total']
            max_score = self.grading_results[self.current_pdf_path]['max']
            self.file_status_label.setText(f"✓ Graded: {total:.0f}/{max_score} pts")
        else:
            self._clear_table()
            self.file_status_label.setText("Not graded")
    
    def grade_current_pdf(self):
        if not self.exam_data:
            QMessageBox.warning(self, "Error", "Load exam JSON first")
            return
        if not self.current_pdf_path:
            QMessageBox.warning(self, "Error", "Load PDF first")
            return
        
        self.grade_current_btn.setEnabled(False)
        self.grade_status_label.setText("⏳ Grading...")
        self.grade_status_label.setStyleSheet("font-size: 11px; color: #ff9800;")
        QApplication.processEvents()
        
        try:
            # 🔑 전처리 결과를 사용한 채점
            grader = ExamGrader(self.exam_data, debug_mode=self.debug_mode)

            if self.preprocessor and self.preprocessor.is_processed:
                # 전처리 결과 사용
                grader.set_preprocessor(self.preprocessor)
                result = grader.grade_from_preprocessed()
                
                # 결과 변환 (기존 형식과 호환)
                results = result.get('scores', {})
                total = result.get('total', 0)
                max_score = result.get('max_score', 0)
            else:
                # 기존 방식 (fallback)
                results = grader.grade_exam(self.current_pdf_path)
                total = grader.get_total_score(results)
                max_score = grader.get_max_score()
                    
            self.grading_results[self.current_pdf_path] = {
                'results': results, 
                'total': total, 
                'max': max_score,
                'filename': os.path.basename(self.current_pdf_path)
            }
            
            self._display_results(results)
            self.grade_status_label.setText(f"✅ Score: {total:.0f}/{max_score}")
            self.grade_status_label.setStyleSheet("font-size: 11px; color: #4caf50;")
            self.file_status_label.setText(f"✓ Graded: {total:.0f}/{max_score} pts")
            self.statusBar().showMessage(f"Score: {total:.0f}/{max_score}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Grading failed:\n{str(e)}")
            self.grade_status_label.setText("❌ Failed")
            self.grade_status_label.setStyleSheet("font-size: 11px; color: #f44336;")
        finally:
            self.grade_current_btn.setEnabled(True)
    
    def grade_all_pdfs(self):
        if not self.exam_data:
            QMessageBox.warning(self, "Error", "Load exam JSON first")
            return
        if not self.pdf_files:
            QMessageBox.warning(self, "Error", "Load PDFs first")
            return
        
        reply = QMessageBox.question(self, "Grade All", 
            f"Grade {len(self.pdf_files)} PDFs?\nThis may take a while.",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        self.grade_all_btn.setEnabled(False)
        self.grade_status_label.setText("⏳ Grading all...")
        QApplication.processEvents()
        
        try:
            grader = ExamGrader(self.exam_data, debug_mode=self.debug_mode)
            max_score = grader.get_max_score()
            success_count = 0
            
            for idx, path in enumerate(self.pdf_files):
                self.grade_status_label.setText(f"⏳ {idx+1}/{len(self.pdf_files)}")
                QApplication.processEvents()
                
                try:
                    # 각 PDF에 대해 전처리 수행
                    preprocessor = ImagePreprocessor(zoom=1.5, debug_mode=self.debug_mode)
                    preprocessor.preprocess_pdf(path, self.exam_data)

                    if preprocessor.is_processed:
                        grader.set_preprocessor(preprocessor)
                        result = grader.grade_from_preprocessed()
                        results = result.get('scores', {})
                        total = result.get('total', 0)
                        max_score = result.get('max_score', 0)
                    else:
                        results = grader.grade_exam(path)
                        total = grader.get_total_score(results)
                        max_score = grader.get_max_score()
                
                    self.grading_results[path] = {
                        'results': results, 
                        'total': total, 
                        'max': max_score,
                        'filename': os.path.basename(path)
                    }
                    success_count += 1
                except Exception as e:
                    print(f"Failed: {path} - {e}")
                    self.grading_results[path] = {
                        'results': {}, 
                        'total': 0, 
                        'max': max_score,
                        'filename': os.path.basename(path),
                        'error': str(e)
                    }
            
            self._load_results_for_current_pdf()
            self.grade_status_label.setText(f"✅ Completed: {success_count}/{len(self.pdf_files)}")
            self.grade_status_label.setStyleSheet("font-size: 11px; color: #4caf50;")
            self.statusBar().showMessage(f"Graded {success_count} of {len(self.pdf_files)} PDFs")
            
            total_all = sum(r['total'] for r in self.grading_results.values())
            max_all = sum(r['max'] for r in self.grading_results.values())
            QMessageBox.information(self, "Grading Complete", 
                f"✅ Graded {success_count} PDFs\nTotal score sum: {total_all:.0f}/{max_all}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Batch grading failed:\n{str(e)}")
        finally:
            self.grade_all_btn.setEnabled(True)
    
    # ===== 결과 표시 =====
    def _display_results(self, results):
        if not results:
            self._clear_table()
            return
            
        self.table.setRowCount(len(results))
        total = 0
        max_total = 0
        
        for i, (qid, score) in enumerate(results.items()):
            max_q = 0
            if self.exam_data and "answers" in self.exam_data:
                for q in self.exam_data["answers"]:
                    if str(q.get("question_id")) == str(qid):
                        max_q = q.get("score", q.get("points", 0))
                        break
            
            # Question
            id_item = QTableWidgetItem(str(qid))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, id_item)
            
            # Score
            score_item = QTableWidgetItem(f"{score:.1f}" if score % 1 else f"{int(score)}")
            score_item.setTextAlignment(Qt.AlignCenter)
            if max_q > 0:
                pct = score / max_q
                if pct >= 0.9:
                    score_item.setForeground(QColor(76, 175, 80))
                elif pct >= 0.6:
                    score_item.setForeground(QColor(255, 152, 0))
                else:
                    score_item.setForeground(QColor(244, 67, 54))
            self.table.setItem(i, 1, score_item)
            
            # Max
            max_item = QTableWidgetItem(str(max_q))
            max_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 2, max_item)
            
            # Answer placeholder
            ans_item = QTableWidgetItem("-")
            self.table.setItem(i, 3, ans_item)
            
            # Edit button
            edit_btn = QPushButton("✏️")
            edit_btn.setFixedSize(40, 24)
            edit_btn.clicked.connect(lambda checked, row=i, q=str(qid): self._edit_score(row, q))
            self.table.setCellWidget(i, 4, edit_btn)
            
            total += score
            max_total += max_q
        
        pct = (total / max_total * 100) if max_total > 0 else 0
        self.total_score_label.setText(f"{total:.0f} / {max_total} pts ({pct:.0f}%)")
        
        if pct >= 90:
            self.total_score_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4caf50; padding: 5px 10px; background-color: #252526; border-radius: 8px;")
        elif pct >= 60:
            self.total_score_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff9800; padding: 5px 10px; background-color: #252526; border-radius: 8px;")
        else:
            self.total_score_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #f44336; padding: 5px 10px; background-color: #252526; border-radius: 8px;")
        
        self.table.resizeColumnsToContents()
    
    def _clear_table(self):
        self.table.setRowCount(0)
        self.total_score_label.setText("0 / 0 pts (0%)")
        self.total_score_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #007acc; padding: 5px 10px; background-color: #252526; border-radius: 8px;")
    
    def _edit_score(self, row, qid):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Score - Question {qid}")
        dialog.setModal(True)
        dialog.setMinimumWidth(250)
        
        layout = QVBoxLayout()
        current = self.table.item(row, 1).text()
        edit = QLineEdit(current)
        edit.setAlignment(Qt.AlignCenter)
        edit.setStyleSheet("font-size: 14px; padding: 8px;")
        layout.addWidget(edit)
        
        max_q = int(self.table.item(row, 2).text())
        info_label = QLabel(f"Max score: {max_q}")
        info_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(info_label)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        dialog.setLayout(layout)
        
        if dialog.exec_() == QDialog.Accepted:
            try:
                new_score = max(0, min(max_q, float(edit.text())))
                score_item = QTableWidgetItem(f"{new_score:.1f}" if new_score % 1 else f"{int(new_score)}")
                score_item.setTextAlignment(Qt.AlignCenter)
                
                if max_q > 0:
                    pct = new_score / max_q
                    if pct >= 0.9:
                        score_item.setForeground(QColor(76, 175, 80))
                    elif pct >= 0.6:
                        score_item.setForeground(QColor(255, 152, 0))
                    else:
                        score_item.setForeground(QColor(244, 67, 54))
                
                self.table.setItem(row, 1, score_item)
                
                if self.current_pdf_path in self.grading_results:
                    qid_int = int(qid)
                    self.grading_results[self.current_pdf_path]['results'][qid_int] = new_score
                    new_total = sum(self.grading_results[self.current_pdf_path]['results'].values())
                    self.grading_results[self.current_pdf_path]['total'] = new_total
                    
                    max_total = self.grading_results[self.current_pdf_path]['max']
                    pct = (new_total / max_total * 100) if max_total > 0 else 0
                    self.total_score_label.setText(f"{new_total:.0f} / {max_total} pts ({pct:.0f}%)")
                    
                    if pct >= 90:
                        self.total_score_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #4caf50; padding: 5px 10px; background-color: #252526; border-radius: 8px;")
                    elif pct >= 60:
                        self.total_score_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #ff9800; padding: 5px 10px; background-color: #252526; border-radius: 8px;")
                    else:
                        self.total_score_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #f44336; padding: 5px 10px; background-color: #252526; border-radius: 8px;")
                    
                    self.file_status_label.setText(f"✓ Score updated: {new_total:.0f} pts")
                    
            except ValueError:
                QMessageBox.warning(self, "Error", "Please enter a valid number")
    
    # ===== 내보내기 =====
    def _export_results(self, fmt):
        if not self.grading_results:
            QMessageBox.warning(self, "Warning", "No results to export")
            return
        
        ext = 'json' if fmt == 'json' else 'csv'
        path, _ = QFileDialog.getSaveFileName(self, "Export", "", f"{ext.upper()} (*.{ext})")
        if not path:
            return
        
        try:
            data = {
                'exam_title': self.exam_data.get('exam_title', 'Unknown') if self.exam_data else 'Unknown',
                'exported_at': datetime.now().isoformat(),
                'results': []
            }
            for pdf_path, d in self.grading_results.items():
                student = self.student_pdf_mapping.get(pdf_path, {})
                data['results'].append({
                    'filename': d['filename'],
                    'student_name': student.get('name', ''),
                    'student_id': student.get('student_id', ''),
                    'total_score': d['total'],
                    'max_score': d['max'],
                    'percentage': (d['total'] / d['max'] * 100) if d['max'] > 0 else 0,
                    'scores': d['results']
                })
            
            if fmt == 'json':
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            else:
                import csv
                with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                    w = csv.writer(f)
                    w.writerow(['Filename', 'Student', 'Score', 'Max', 'Percentage'])
                    for r in data['results']:
                        w.writerow([r['filename'], r['student_name'], f"{r['total_score']:.1f}", r['max_score'], f"{r['percentage']:.1f}%"])
            
            QMessageBox.information(self, "Success", f"Exported to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
    
    def clear_results(self):
        if self.grading_results:
            self.grading_results.clear()
            self._clear_table()
            self.grade_status_label.setText("● Ready")
            self.file_status_label.setText("")
            self.statusBar().showMessage("Results cleared")
    
    def closeEvent(self, event):
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = GraderApp()
    window.show()
    sys.exit(app.exec_())