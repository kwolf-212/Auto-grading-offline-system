# exam_generator_app.py (수정된 버전 - 상단 import 및 PDF 함수 제거)
import sys
import json
import tempfile
import os
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon, QPainter, QPen
from PyQt5.QtCore import Qt, QTimer, QRect, QPoint, QSize
from reportlab.lib.pagesizes import A4, letter, A5, B5, legal, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import black
import tempfile

from common.constants import PAGE_SIZES, QUESTION_TYPES
from common.utils import generate_qr, wrap_text
from common.models import Question
from ui.widgets import PDFPreviewWidget, SettingsSummaryWidget
from ui.dialogs import ExamSettingsDialog, DatabaseBrowserDialog
from exam_generator import PDFEngine, AnswerSheetEngine

from database_manager import DatabaseManager

# PyMuPDF import
try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ---------------- MAIN APP ----------------
class GeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Exam Generator - Professional")
        self.questions = []
        self.temp_pdf_path = None
        self.settings = {
            'exam_title': 'Midterm Examination',
            'exam_date': datetime.now().strftime("%B %d, %Y"),
            'exam_instruction': '',
            'page_size': 'A4',
            'layout_style': 'Two Column',
            'margin': 50,
            'line_spacing': 1.5,
            'font_size': 11,
            'title_font_size': 18,
            'show_qr': True,
            'essay_lines': 4,
            'include_student_info': True,
            'student_name': '',
            'student_id': '',
            'department': '',
            'instructor': '',
            'student_date': '',
            'additional_info': '',
            'show_points': True,
            'numbering_style': '1, 2, 3...'
        }
        self.init_ui()
        self.showMaximized()
        
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.generate_live_preview)

        self.db = DatabaseManager()
        
        QTimer.singleShot(1000, self.generate_live_preview)

    def init_ui(self):
        container = QWidget()
        main_layout = QHBoxLayout()

        # ===== LEFT: QUESTION INPUT CARD =====
        left_card = QFrame()
        left_card.setObjectName("card")
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        title = QLabel("📝 Add Question")
        title.setObjectName("title")
        left_layout.addWidget(title)
        
        # Database toolbar
        db_toolbar = QHBoxLayout()
        self.load_db_btn = QPushButton("📚 Load from Database")
        self.load_db_btn.setStyleSheet("background-color: #17a2b8;")
        self.load_db_btn.clicked.connect(self.load_from_database)
        self.save_db_btn = QPushButton("💾 Save to Database")
        self.save_db_btn.setStyleSheet("background-color: #28a745;")
        self.save_db_btn.clicked.connect(self.save_current_to_database)
        self.clear_all_btn = QPushButton("🗑 Clear All")
        self.clear_all_btn.setStyleSheet("background-color: #dc3545;")
        self.clear_all_btn.clicked.connect(self.clear_all_questions)
        db_toolbar.addWidget(self.load_db_btn)
        db_toolbar.addWidget(self.save_db_btn)
        db_toolbar.addWidget(self.clear_all_btn)
        left_layout.addLayout(db_toolbar)

        # Question Type
        type_group = QGroupBox("Question Type")
        type_layout = QVBoxLayout()
        self.q_type = QComboBox()
        for qid, qinfo in QUESTION_TYPES.items():
            self.q_type.addItem(f"{qinfo['icon']} {qinfo['name']}")
        self.q_type.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.q_type)
        type_group.setLayout(type_layout)
        left_layout.addWidget(type_group)

        # Question Input
        left_layout.addWidget(QLabel("Question Text:"))
        self.q_text = QTextEdit()
        self.q_text.setPlaceholderText("Enter question here...")
        self.q_text.setMinimumHeight(100)
        self.q_text.textChanged.connect(self.on_content_changed)
        left_layout.addWidget(self.q_text)

        # Dynamic fields
        self.dynamic_container = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_container)
        self.dynamic_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.dynamic_container)

        self.options_input = QTextEdit()
        self.options_input.setPlaceholderText("Options (one per line)\nExample:\nOption 1\nOption 2\nOption 3")
        self.options_input.setMaximumHeight(100)
        self.options_input.textChanged.connect(self.on_content_changed)

        self.blanks_input = QLineEdit()
        self.blanks_input.setPlaceholderText("Blank answers (comma separated) e.g., Seoul, 42, True")
        self.blanks_input.textChanged.connect(self.on_content_changed)

        self.matching_left = QTextEdit()
        self.matching_left.setPlaceholderText("Left column (one per line)\n1. Apple\n2. Carrot\n3. Cow")
        self.matching_left.setMaximumHeight(80)
        self.matching_left.textChanged.connect(self.on_content_changed)
        self.matching_right = QTextEdit()
        self.matching_right.setPlaceholderText("Right column (one per line)\nA. Fruit\nB. Vegetable\nC. Animal")
        self.matching_right.setMaximumHeight(80)
        self.matching_right.textChanged.connect(self.on_content_changed)

        self.ordering_input = QTextEdit()
        self.ordering_input.setPlaceholderText("Items to order (one per line, correct order)\nStep 1: ...\nStep 2: ...\nStep 3: ...")
        self.ordering_input.setMaximumHeight(100)
        self.ordering_input.textChanged.connect(self.on_content_changed)

        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText("Code template or expected output...")
        self.code_input.setMaximumHeight(100)
        self.code_input.textChanged.connect(self.on_content_changed)

        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("Formula or equation (e.g., E = mc²)")
        self.formula_input.textChanged.connect(self.on_content_changed)

        left_layout.addWidget(QLabel("Answer Key:"))
        self.q_answer = QTextEdit()
        self.q_answer.setPlaceholderText("Answer key")
        self.q_answer.setMaximumHeight(80)
        self.q_answer.textChanged.connect(self.on_content_changed)
        left_layout.addWidget(self.q_answer)

        score_layout = QHBoxLayout()
        score_layout.addWidget(QLabel("Points:"))
        self.q_score = QSpinBox()
        self.q_score.setValue(5)
        self.q_score.setRange(1, 100)
        self.q_score.valueChanged.connect(self.on_content_changed)
        score_layout.addWidget(self.q_score)
        
        score_layout.addWidget(QLabel("Difficulty:"))
        self.q_difficulty = QComboBox()
        self.q_difficulty.addItems(["Easy", "Medium", "Hard"])
        self.q_difficulty.setCurrentText("Medium")
        score_layout.addWidget(self.q_difficulty)
        
        score_layout.addStretch()
        left_layout.addLayout(score_layout)

        add_btn = QPushButton("➕ Add Question")
        add_btn.clicked.connect(self.add_question)
        left_layout.addWidget(add_btn)
        
        left_layout.addStretch()
        left_card.setLayout(left_layout)

        # ===== CENTER: QUESTION LIST =====
        center_card = QFrame()
        center_card.setObjectName("card")
        center_layout = QVBoxLayout()

        list_title = QLabel("📋 Question List (Drag to Reorder)")
        list_title.setObjectName("title")

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QAbstractItemView.InternalMove)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.model().rowsMoved.connect(self.on_list_reordered)

        btn_layout_center = QHBoxLayout()
        btn_delete = QPushButton("🗑 Delete Selected")
        btn_delete.clicked.connect(self.delete_question)
        btn_duplicate = QPushButton("📋 Duplicate Question")
        btn_duplicate.clicked.connect(self.duplicate_question)
        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.clicked.connect(self.edit_question)
        btn_layout_center.addWidget(btn_delete)
        btn_layout_center.addWidget(btn_duplicate)
        btn_layout_center.addWidget(btn_edit)

        center_layout.addWidget(list_title)
        center_layout.addWidget(self.list_widget)
        center_layout.addLayout(btn_layout_center)
        center_card.setLayout(center_layout)

        # ===== RIGHT: PREVIEW + SETTINGS + ACTION =====
        right_card = QFrame()
        right_card.setObjectName("card")
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)

        preview_title = QLabel("👁️ Live PDF Preview")
        preview_title.setObjectName("title")
        right_layout.addWidget(preview_title)

        self.settings_summary = SettingsSummaryWidget(self)
        self.settings_summary.edit_btn.clicked.connect(self.open_settings_dialog)
        self.settings_summary.update_summary(self.settings)
        right_layout.addWidget(self.settings_summary)

        self.pdf_preview = PDFPreviewWidget()
        self.pdf_preview.refresh_btn.clicked.connect(self.generate_live_preview)
        self.pdf_preview.setFocusPolicy(Qt.StrongFocus)

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(10)

        btn_pdf = QPushButton("📄 Save Exam PDF")
        btn_pdf.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        btn_pdf.clicked.connect(self.export_pdf)

        btn_answer = QPushButton("📝 Save Answer Sheet")
        btn_answer.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        btn_answer.clicked.connect(self.export_answer_sheet)

        btn_answer_key = QPushButton("🔑 Export Answer Key")
        btn_answer_key.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e0a800; }
        """)
        btn_answer_key.clicked.connect(self.export_answer_key_with_positions)

        button_layout.addWidget(btn_pdf)
        button_layout.addWidget(btn_answer)
        button_layout.addWidget(btn_answer_key)

        right_layout.addWidget(self.pdf_preview, 1)
        right_layout.addWidget(button_container)

        right_card.setLayout(right_layout)

        main_layout.addWidget(left_card, 2)
        main_layout.addWidget(center_card, 2)
        main_layout.addWidget(right_card, 3)

        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.on_type_changed(0)
        self.apply_style()

    def open_settings_dialog(self):
        dialog = ExamSettingsDialog(self)
        dialog.set_settings(self.settings)
        
        if dialog.exec_() == QDialog.Accepted:
            self.settings = dialog.get_settings()
            self.settings_summary.update_summary(self.settings)
            self.on_content_changed()
            QMessageBox.information(self, "Settings Updated", "Exam settings have been updated successfully.")

    def on_content_changed(self):    
        self.preview_timer.start(800)

    def on_list_reordered(self):
        for idx, q in enumerate(self.questions):
            q["id"] = idx + 1
        self.update_list_display()
        self.on_content_changed()

    def generate_live_preview(self):
        """실시간 미리보기 생성"""
        if not self.questions:
            self.pdf_preview.status_label.setText("No questions added yet.")
            self.pdf_preview.preview_label.setText("📄 No questions added.\n\nAdd a question to see live PDF preview.")
            self.pdf_preview.current_pdf_path = None
            self.pdf_preview.current_page = 0
            self.pdf_preview.total_pages = 0
            self.pdf_preview.update_navigation_buttons()
            return
        
        self.pdf_preview.status_label.setText("⏳ Generating preview...")
        QApplication.processEvents()
        
        temp_dir = tempfile.gettempdir()
        self.temp_pdf_path = os.path.join(temp_dir, f"exam_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        
        try:
            # PDF 엔진 사용
            pdf_engine = PDFEngine(self.questions, self.settings)
            pdf_engine.generate_exam_pdf(self.temp_pdf_path)
            
            QTimer.singleShot(200, lambda: self.pdf_preview.load_pdf(self.temp_pdf_path))
            self.pdf_preview.status_label.setText(f"✅ Preview updated | {len(self.questions)} questions")
        except Exception as e:
            self.pdf_preview.status_label.setText(f"❌ Preview error: {str(e)[:50]}")
            import traceback
            traceback.print_exc()

    def _draw_student_info(self, c, width, height, margin_left, margin_right, current_y, available_width):
        if not self.settings.get('include_student_info', True):
            return current_y
        
        line_height = 20
        
        c.setStrokeColor(black)
        c.setLineWidth(0.5)
        c.rect(margin_left, current_y - 35, available_width, 35)
        
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin_left + 8, current_y - 12, "STUDENT INFO")
        
        c.setFont("Helvetica", 9)
        
        name = self.settings.get('student_name', '') or "_________________________"
        student_id = self.settings.get('student_id', '') or "_________________________"
        dept = self.settings.get('department', '') or "_________________________"
        
        col_width = (available_width - 40) // 3
        
        c.drawString(margin_left + 12, current_y - 28, f"Name: {name}")
        c.drawString(margin_left + 12 + col_width, current_y - 28, f"ID: {student_id}")
        c.drawString(margin_left + 12 + col_width * 2, current_y - 28, f"Dept: {dept}")
        
        return current_y - 45
        
    def _draw_question_standard(self, c, questions, margin_left, margin_right, width, height,
                            line_height, font_size, available_width, start_y):
        current_y = start_y
        page_bottom_margin = 0
        
        for q in questions:
            needed_height = self._estimate_question_height(q, line_height, font_size, available_width)
            
            if current_y - needed_height < page_bottom_margin:
                c.showPage()
                current_y = height - 80
                c.setFont("Helvetica", font_size)
            
            current_y = self._draw_single_question_standard(
                c, q, margin_left, current_y, line_height, font_size, available_width
            )
            
            current_y -= line_height
            c.line(margin_left, current_y + 10, width - margin_right, current_y + 10)
            current_y -= 10
        
        return current_y

    def _draw_single_question_standard(self, c, q, x, y, line_height, font_size, available_width):
        current_y = y
        
        numbering = self.settings.get('numbering_style', '1, 2, 3...')
        if numbering == "1), 2), 3)...":
            q_prefix = f"{q['id']})"
        elif numbering == "(1), (2), (3)...":
            q_prefix = f"({q['id']})"
        elif numbering == "A, B, C...":
            q_prefix = chr(64 + min(q['id'], 26))
        else:
            q_prefix = f"Q{q['id']}"
        
        points_text = f" ({q['score']} pts)" if self.settings.get('show_points', True) else ""
        full_question_text = f"{q_prefix}. {q['text']}{points_text}"
        
        c.setFont("Helvetica-Bold", font_size)
        question_lines = wrap_text(full_question_text, available_width - 20, font_size)
        
        for line in question_lines:
            c.drawString(x, current_y, line)
            current_y -= line_height
        
        current_y -= 5
        c.setFont("Helvetica", font_size - 1)
        
        current_y = self._draw_question_content(c, q, x, current_y, line_height, font_size, available_width)
        
        return current_y

    def _estimate_question_height(self, q, line_height, font_size, available_width):
        total_height = 0
        
        question_text = q['text']
        approx_chars_per_line = int(available_width / (font_size * 0.6))
        question_lines = max(1, (len(question_text) // approx_chars_per_line) + 1)
        total_height += question_lines * line_height + 10
        
        if q["type"] == 0:
            choices_count = len(q.get("choices", []))
            total_height += choices_count * (line_height - 4) + 20
        elif q["type"] == 1:
            total_height += line_height
        elif q["type"] == 2:
            total_height += line_height
        elif q["type"] == 3:
            total_height += line_height
        elif q["type"] == 4:
            total_height += self.settings.get('essay_lines', 4) * line_height
        elif q["type"] == 5:
            pairs_count = len(q.get("matching_pairs", []))
            total_height += max(3, pairs_count) * (line_height - 4)
        elif q["type"] == 6:
            total_height += line_height
        elif q["type"] == 7:
            total_height += 60
        elif q["type"] == 8:
            total_height += line_height * 2
        
        return total_height + 30

    def _draw_question_content(self, c, q, margin_left, current_y, line_height, font_size, available_width):
        """Display question content on exam paper (no answer spaces)"""
        
        if q["type"] == 0:  # Multiple Choice - show options with [] for marking
            for i, choice in enumerate(q.get("choices", []), 1):
                choice_display = choice[:70] + "..." if len(choice) > 70 else choice
                c.drawString(margin_left + 10, current_y, f"   {chr(96+i)}. {choice_display}")
                current_y -= line_height - 4
        
        elif q["type"] == 1:  # True/False - show as True / False
            c.drawString(margin_left + 10, current_y, f"   a. True")
            current_y -= line_height - 4
            c.drawString(margin_left + 10, current_y, f"   b. False")
        
        elif q["type"] == 2:  # Fill in the Blank - only show blanks, no answer space
            # blank_count = len(q.get("blanks", [])) or 3
            # # Display the question with blanks embedded
            # blanks_str = " ______ " * min(blank_count, 5)
            # c.drawString(margin_left + 10, current_y, blanks_str)
            pass
        
        elif q["type"] == 3:  # Short Answer - no answer space (only on answer sheet)
            # No blank line on exam paper
            pass
        
        elif q["type"] == 4:  # Essay - no writing space on exam paper
            # Just the instruction
            c.drawString(margin_left + 10, current_y, "[Essay question - answer on separate paper]")
            current_y -= line_height
        
        elif q["type"] == 5:  # Matching - show both columns for matching
            pairs = q.get("matching_pairs", [])[:8]
            if pairs:
                # Find maximum length of left items
                max_left_len = 0
                for left, right in pairs:
                    left_len = len(left[:30])
                    max_left_len = max(max_left_len, left_len)
                
                # Calculate column positions
                left_col_width = min(max_left_len * 4 + 20, available_width // 2)
                right_col_x = margin_left + left_col_width + 30
                
                c.setFont("Helvetica", font_size - 1)
                
                # Draw matching pairs side by side (no header, no instruction)
                for i, (left, right) in enumerate(pairs):
                    left_display = left[:35] + "..." if len(left) > 35 else left
                    right_display = right[:35] + "..." if len(right) > 35 else right
                    
                    # Left column with numbers
                    c.drawString(margin_left + 20, current_y, f"{i+1}. {left_display}")
                    # Right column with letters
                    c.drawString(right_col_x, current_y, f"{chr(97+i)}. {right_display}")
                    current_y -= line_height - 2
            else:
                c.drawString(margin_left + 10, current_y, "Match the following:")

        
        elif q["type"] == 6:  # Ordering - show items to order
            items = q.get("ordering_items", [])
            if items:
                c.drawString(margin_left + 10, current_y, "Arrange in correct order:")
                current_y -= line_height
                # 모든 항목 표시 ([:5] 제한 제거)
                for i, item in enumerate(items, 1):
                    item_display = item[:50] + "..." if len(item) > 50 else item
                    c.drawString(margin_left + 20, current_y, f"   {i}. {item_display}")
                    current_y -= line_height - 4
            else:
                c.drawString(margin_left + 10, current_y, "Arrange in correct order:")

        
        elif q["type"] == 7:  # Code - show code area
            c.drawString(margin_left + 10, current_y, "Write your code below:")
            current_y -= line_height * 2
            code_height = 50
            c.rect(margin_left + 10, current_y - code_height, available_width - 30, code_height)
        
        elif q["type"] == 8:  # Calculation - show work area            
            pass
        
        return current_y

    def _draw_question_two_column_v2(self, c, questions, margin_left, margin_right, width, height,
                                  line_height, font_size, available_width, start_y):
        col_gap = 15
        col_width = (available_width - col_gap) // 2
        
        left_col_x = margin_left
        right_col_x = margin_left + col_width + col_gap
        
        page_bottom_margin = 25
        
        current_y = start_y
        q_index = 0
        total_questions = len(questions)
        
        while q_index < total_questions:
            if q_index > 0:
                c.showPage()
                current_y = height - 35
            
            left_y = current_y
            left_q_indices = []
            
            temp_index = q_index
            while temp_index < total_questions:
                q = questions[temp_index]
                q_height = self._estimate_question_height_two_col_v2(q, line_height, font_size, col_width) + 15
                
                if left_y - q_height > page_bottom_margin:
                    left_q_indices.append(temp_index)
                    left_y -= q_height
                    temp_index += 1
                else:
                    break
            
            right_q_indices = []
            right_y = current_y
            
            temp_index2 = temp_index
            while temp_index2 < total_questions:
                q = questions[temp_index2]
                q_height = self._estimate_question_height_two_col_v2(q, line_height, font_size, col_width) + 15
                
                if right_y - q_height > page_bottom_margin:
                    right_q_indices.append(temp_index2)
                    right_y -= q_height
                    temp_index2 += 1
                else:
                    break
            
            if left_q_indices:
                y_pos = current_y
                for idx in left_q_indices:
                    q = questions[idx]
                    y_pos = self._draw_single_question_two_col_v3(
                        c, q, left_col_x, y_pos, line_height, font_size, col_width, idx + 1
                    )
                    y_pos -= 25
                    if idx != left_q_indices[-1]:
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.setLineWidth(0.5)
                        c.line(left_col_x, y_pos + 12, left_col_x + col_width, y_pos + 12)
                        c.setStrokeColor(black)
            
            if right_q_indices:
                y_pos = current_y
                for idx in right_q_indices:
                    q = questions[idx]
                    y_pos = self._draw_single_question_two_col_v3(
                        c, q, right_col_x, y_pos, line_height, font_size, col_width, idx + 1
                    )
                    y_pos -= 25
                    if idx != right_q_indices[-1]:
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.setLineWidth(0.5)
                        c.line(right_col_x, y_pos + 12, right_col_x + col_width, y_pos + 12)
                        c.setStrokeColor(black)
            
            if right_q_indices:
                q_index = right_q_indices[-1] + 1
            elif left_q_indices:
                q_index = left_q_indices[-1] + 1
            else:
                q_index = temp_index if temp_index > q_index else q_index + 1

    def _estimate_question_height_two_col_v2(self, q, line_height, font_size, col_width):
        total_height = 20
        
        question_text = q['text']
        chars_per_line = max(10, int(col_width / (font_size * 0.55)))
        question_lines = max(1, (len(question_text) // chars_per_line) + 1)
        total_height += question_lines * (line_height + 2)
        
        if q["type"] == 0:
            choices_count = min(len(q.get("choices", [])), 5)
            total_height += choices_count * (line_height - 2) + 10
        elif q["type"] == 1:
            total_height += (line_height - 2) * 2  # True and False
        elif q["type"] == 2:
            total_height += line_height - 2
        elif q["type"] == 3:
            total_height += 5  # minimal space
        elif q["type"] == 4:
            total_height += 20
        elif q["type"] == 5:
            pairs_count = min(len(q.get("matching_pairs", [])), 4)
            total_height += max(2, pairs_count) * (line_height - 2) + 20
        elif q["type"] == 6:
            items_count = min(len(q.get("ordering_items", [])), 4)
            total_height += items_count * (line_height - 2) + 15
        elif q["type"] == 7:
            total_height += 45
        elif q["type"] == 8:
            total_height += (line_height - 2) * 3 + 10
        
        return total_height

    def _draw_single_question_two_col_v3(self, c, q, x, y, line_height, font_size, col_width, q_num):
        current_y = y
        
        numbering = self.settings.get('numbering_style', '1, 2, 3...')
        if numbering == "1), 2), 3)...":
            q_prefix = f"{q_num})"
        elif numbering == "(1), (2), (3)...":
            q_prefix = f"({q_num})"
        elif numbering == "A, B, C...":
            q_prefix = chr(64 + min(q_num, 26))
        else:
            q_prefix = f"{q_num}."
        
        points_text = f" [{q['score']} pts]" if self.settings.get('show_points', True) else ""
        full_text = f"{q_prefix} {q['text']}{points_text}"
        
        c.setFont("Helvetica-Bold", font_size - 1)
        
        text_lines = wrap_text(full_text, col_width - 10, font_size - 1)
        for idx, line in enumerate(text_lines):
            if idx == 0:
                c.drawString(x, current_y, line)
            else:
                indent = " " * (len(str(q_prefix)) + 1)
                c.drawString(x, current_y, f"{indent}{line}")
            current_y -= line_height
        
        current_y -= 6
        c.setFont("Helvetica", font_size - 2)
        
        current_y = self._draw_question_content_two_col(c, q, x, current_y, line_height, font_size, col_width)
        
        return current_y

    def _draw_question_content_two_col(self, c, q, x, current_y, line_height, font_size, col_width):
        """Display question content in two-column layout on exam paper"""
        
        if q["type"] == 0:  # Multiple Choice - show [] for marking
            c.setFont("Helvetica", font_size - 2)
            for i, choice in enumerate(q.get("choices", [])[:5], 1):
                choice_display = choice[:30] + "..." if len(choice) > 30 else choice
                c.drawString(x + 8, current_y, f"   {chr(96+i)}. {choice_display}")
                current_y -= line_height - 2
        
        elif q["type"] == 1:  # True/False - show [ ] for marking
            c.drawString(x + 8, current_y, f"   a. True")
            current_y -= line_height - 2
            c.drawString(x + 8, current_y, f"   b. False")
            current_y -= 5
        
        elif q["type"] == 2:  # Fill in the Blank - only blanks
            # blank_count = min(len(q.get("blanks", [])), 4) or 3
            # blanks = " ______ " * blank_count
            # c.drawString(x + 8, current_y, blanks)
            # # NO additional answer space
            # current_y -= 5
            pass
        
        elif q["type"] == 3:  # Short Answer - no answer space on exam
            # Skip - no blank line
            pass
        
        elif q["type"] == 4:  # Essay - minimal space
            # c.drawString(x + 8, current_y, "[Answer on separate paper]")
            # current_y -= line_height
            pass
        
        elif q["type"] == 5:  # Matching - both columns for matching
            pairs = q.get("matching_pairs", [])[:5]
            if pairs:
                # Prepare display strings
                left_items = []
                right_items = []
                for i, (left, right) in enumerate(pairs):
                    left_display = left[:18] + ".." if len(left) > 18 else left
                    right_display = right[:18] + ".." if len(right) > 18 else right
                    left_items.append(f"{i+1}. {left_display}")
                    right_items.append(f"{chr(97+i)}. {right_display}")
                
                # Find maximum width of left column
                max_left_width = 0
                for item in left_items:
                    item_width = c.stringWidth(item, "Helvetica", font_size - 2)
                    max_left_width = max(max_left_width, item_width)
                
                c.setFont("Helvetica", font_size - 2)
                right_col_x = x + max_left_width + 25
                
                # Draw side by side - clean, no extra text
                for i in range(max(len(left_items), len(right_items))):
                    if i < len(left_items):
                        c.drawString(x + 15, current_y, left_items[i])
                    if i < len(right_items):
                        c.drawString(right_col_x, current_y, right_items[i])
                    current_y -= line_height - 2
            else:
                c.drawString(x + 8, current_y, "Match:")

        
        elif q["type"] == 6:  # Ordering - show items, order on answer sheet
            items = q.get("ordering_items", [])
            if items:
                c.drawString(x + 8, current_y, "Order:")
                current_y -= line_height
                # 모든 항목 표시 ([:4] 제한 제거)
                for i, item in enumerate(items, 1):
                    item_display = item[:25] + "..." if len(item) > 25 else item
                    c.drawString(x + 14, current_y, f"{i}. {item_display}")
                    current_y -= line_height - 2
            current_y -= 5

        
        elif q["type"] == 7:  # Code
            pass
        
        elif q["type"] == 8:  # Calculation
            pass
        
        return current_y

    def _generate_pdf_to_file(self, file_path, is_preview=False):
        exam_title = self.settings.get('exam_title', 'Untitled Exam') or "Untitled Exam"
        exam_date = self.settings.get('exam_date', '') or datetime.now().strftime("%B %d, %Y")
        
        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size

        margin_top = 25 * mm
        margin_bottom = 15 * mm
        margin_left = 20 * mm
        margin_right = 20 * mm
        
        available_width = width - margin_left - margin_right
        
        line_height = int(self.settings.get('line_spacing', 1.5) * self.settings.get('font_size', 11))
        layout_style = self.settings.get('layout_style', 'Two Column')
        font_size = self.settings.get('font_size', 11)
        title_font_size = self.settings.get('title_font_size', 18)
        
        # ===== Header =====
        current_y = height - margin_top
        
        c.setFont("Helvetica-Bold", title_font_size)
        c.drawCentredString(width/2, current_y, exam_title)
        current_y -= 22
        
        c.setFont("Helvetica", 10)
        total_points = sum(q.get('score', 0) for q in self.questions)
        
        if self.settings.get('show_qr', True):
            qr_data = json.dumps({
                "exam": exam_title,
                "date": exam_date,
                "questions": len(self.questions),
                "total_score": total_points
            })
            qr_path = generate_qr(qr_data, f"qr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            c.drawImage(qr_path, margin_left, current_y - 15, width=35, height=35)
            if os.path.exists(qr_path):
                os.remove(qr_path)
            c.drawRightString(width - margin_right, current_y, f"Total: {total_points} pts")
        else:
            c.drawRightString(width - margin_right, current_y, f"Total: {total_points} pts")
        
        current_y -= 18
        
        instruction = self.settings.get('exam_instruction', '')
        if instruction:
            c.setFont("Helvetica-Oblique", 9)
            instruction_lines = wrap_text(instruction, available_width - 20, 9)
            for line in instruction_lines:
                c.drawString(margin_left, current_y, f"※ {line}")
                current_y -= line_height - 4
            current_y -= 8
        
        c.line(margin_left, current_y, width - margin_right, current_y)
        current_y -= 15
        
        # ===== Student Info Section =====
        # if self.settings.get('include_student_info', True):
        #     current_y = self._draw_student_info(c, width, height, margin_left, margin_right, 
        #                                         current_y, available_width)
        
        # current_y -= 15
        
        # ===== Question Area =====
        if layout_style == "Two Column":
            self._draw_question_two_column_v2(c, self.questions, margin_left, margin_right, 
                                            width, height, line_height, font_size, 
                                            available_width, current_y)
        else:
            self._draw_question_standard(c, self.questions, margin_left, margin_right, width, height,
                                        line_height, font_size, available_width, current_y)
        
        c.save()

    def export_answer_sheet(self):
        """답안지 PDF 저장"""
        if not self.questions:
            QMessageBox.warning(self, "Notice", "Please add questions first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Answer Sheet PDF", "", "PDF (*.pdf)")
        if not file_path:
            return

        try:
            answer_sheet_engine = AnswerSheetEngine(self.questions, self.settings)
            answer_sheet_engine.generate_answer_sheet(file_path)
            QMessageBox.information(self, "Success", f"Answer Sheet PDF has been created.\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create answer sheet: {str(e)}")

    def _calculate_answer_sheet_height(self, q, col_width, line_height, small_line_height):
        """질문이 차지하는 높이 계산 - _draw_answer_sheet_question와 일치하도록"""
        qtype = q["type"]
        total_height = line_height  # 기본 질문 한 줄 높이 (질문 번호 라인)
        
        if qtype == 0:  # Multiple Choice
            choices = q.get("choices", [])
            # 옵션 체크박스 한 줄에 모든 옵션 표시
            total_height += small_line_height  # 체크박스 라인
            total_height += 5  # 여백
        
        elif qtype == 1:  # True/False
            total_height += 0  # 한 줄로 충분
        
        elif qtype == 2:  # Fill in the Blank
            total_height += 0  # 한 줄로 충분
        
        elif qtype == 3:  # Short Answer
            total_height += 0  # 한 줄로 충분
        
        elif qtype == 4:  # Essay
            essay_lines = min(self.settings.get('essay_lines', 6), 6)
            total_height += int(line_height * 0.7)  # 제목과의 간격
            total_height += essay_lines * line_height  # 에세이 라인
            total_height += 5  # 여백
        
        elif qtype == 5:  # Matching
            pairs = q.get("matching_pairs", [])
            total_height += line_height  # "Matching (Example...)" 라인
            # 매칭 항목들을 여러 줄로 표시
            lines_needed = (len(pairs) + 3) // 4  # 한 줄에 4개씩
            total_height += lines_needed * small_line_height
        
        elif qtype == 6:  # Ordering
            total_height += 0  # 한 줄로 충분
        
        elif qtype == 7:  # Code
            total_height += line_height  # "Q{n}. Write your code below:" 라인
            # 코드 영역 높이 계산
            answer_key = q.get('answer', '')
            if answer_key:
                answer_lines = len(answer_key.split('\n'))
                code_lines = max(3, answer_lines + 2)
            else:
                code_lines = 5  # 기본값
            code_height = min(code_lines * 15, 250)  # 최대 250px
            total_height += code_height + 10  # 코드 영역 + 여백
        
        elif qtype == 8:  # Calculation
            total_height += line_height  # "Q{n}. Work:" 라인
            total_height += line_height * 3  # 작업 공간 3줄
            total_height += small_line_height  # Answer 라인 간격
        
        else:
            total_height += 0
        
        return total_height

    def _draw_answer_sheet_question(self, c, q, x, y, col_width, line_height, small_line_height, width, margin, base_font_size):
        """Draw a single answer sheet question at specified position"""
        
        qtype = q["type"]
        
        c.setFont("Helvetica", base_font_size)
        
        if qtype == 0:  # Multiple Choice - [a] [b] [c] [d] 형태로만 표시
            choices = q.get("choices", [])
            # 질문 번호 표시
            c.drawString(x, y, f"Q{q['id']}.")
            
            # 옵션 체크박스만 표시 (한 줄에 모두 표시)
            line_text = "       "
            for i in range(len(choices)):
                line_text += f"  [{chr(97+i)}]"
            c.drawString(x, y, line_text)
            y -= line_height
            
            y -= 5  # 여백
        
        elif qtype == 1:  # True/False - [a] [b] 형태로만 표시
            c.drawString(x, y, f"Q{q['id']}.   [a]    [b]")
            y -= line_height
        
        elif qtype == 2:  # Fill in the Blank
            blank_count = len(q.get("blanks", [])) or 3
            blanks = " ______ " * blank_count
            c.drawString(x, y, f"Q{q['id']}.   {blanks}")
            y -= line_height
        
        elif qtype == 3:  # Short Answer
            c.drawString(x, y, f"Q{q['id']}.   ____________________")
            y -= line_height
        
        elif qtype == 4:  # Essay
            c.setFont("Helvetica", base_font_size)
            c.drawString(x, y, f"Q{q['id']}.")
            y -= int(line_height * 0.7)
            essay_lines = min(self.settings.get('essay_lines', 6), 6)
            for i in range(essay_lines):
                c.line(x, y, x + col_width - 10, y)
                y -= line_height
            y -= 5
        
        elif qtype == 5:  # Matching
            pairs = q.get("matching_pairs", [])
            c.drawString(x, y, f"Q{q['id']}.   Matching (Example: 1→a, 2→b):")
            y -= line_height
            # 여러 줄로 표시
            match_line = ""
            for i in range(len(pairs)):
                match_line += f"{i+1}→___  "
                if (i + 1) % 4 == 0 and i + 1 < len(pairs):
                    c.drawString(x + 25, y, match_line)
                    match_line = ""
                    y -= small_line_height
            if match_line:
                c.drawString(x + 25, y, match_line)
            y -= small_line_height
        
        elif qtype == 6:  # Ordering
            items = q.get("ordering_items", [])
            if items:
                blank_placeholders = ", ".join(["___"] * len(items))
                c.drawString(x, y, f"Q{q['id']}.   Correct order: {blank_placeholders}")
            else:
                c.drawString(x, y, f"Q{q['id']}.   Order: ___ , ___ , ___")
            y -= line_height
        
        elif qtype == 7:  # Code - 사각형 영역이 제대로 그려지도록 수정
            c.setFont("Helvetica", base_font_size)
            c.drawString(x, y, f"Q{q['id']}. Write your code below:")
            y -= line_height
            
            # answer key를 기준으로 코드 영역 크기 결정
            answer_key = q.get('answer', '')
            if answer_key:
                answer_lines = len(answer_key.split('\n'))
                code_lines = max(3, answer_lines + 2)
            else:
                code_lines = 5  # 기본값
            
            line_spacing = 14  # 줄 간격 (픽셀)
            code_height = min(code_lines * line_spacing + 10, 250)  # 최대 250px
            
            # 사각형 그리기
            rect_x = x
            rect_y = y - code_height  # 사각형의 하단 y 좌표
            rect_width = col_width - 10
            rect_height = code_height
            
            c.rect(rect_x, rect_y, rect_width, rect_height)
            
            # 라인 번호 표시 (위에서 아래로 1, 2, 3... 순서)
            # rect_y는 사각형의 하단이므로, 상단은 rect_y + rect_height
            c.setFont("Helvetica", 7)
            max_line_num = min(code_lines + 1, 15)
            for i in range(1, max_line_num + 1):
                # i번째 줄의 y 좌표: 사각형 상단에서 i번째 줄 위치 (위에서 아래로)
                # 사각형 상단 = rect_y + rect_height
                top_y = rect_y + rect_height
                line_y = top_y - (i * line_spacing) + 5
                # 사각형 하단을 넘지 않도록 체크
                if line_y > rect_y + 5:
                    c.drawString(rect_x + 5, line_y, f"{i}.")
            
            # y 위치 업데이트 (사각형 아래로 이동)
            y = rect_y - 10
            c.setFont("Helvetica", base_font_size)
        
        elif qtype == 8:  # Calculation - 작업 공간 3줄
            c.drawString(x, y, f"Q{q['id']}. Work:")
            y -= line_height
            for i in range(3):  # 3줄
                c.line(x, y, x + col_width - 10, y)
                y -= line_height
            y -= small_line_height
            c.drawString(x, y, "Answer: ")
            c.line(x + 45, y, x + col_width - 10, y)
            y -= small_line_height
        
        else:
            c.drawString(x, y, f"Q{q['id']}.   ____________________")
            y -= line_height
        
        return y
    
    def export_answer_key_with_positions(self):
        """Export answer key with positions to JSON file"""
        if not self.questions:
            QMessageBox.warning(self, "Notice", "No questions to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Answer Key with Positions", 
            "", 
            "JSON Files (*.json)"
        )
        if not file_path:
            return
        
        try:
            temp_dir = tempfile.gettempdir()
            temp_pdf = os.path.join(temp_dir, f"temp_positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
            
            position_data = []
            
            self._generate_pdf_with_positions(temp_pdf, position_data)
            
            answer_key = {
                "exam_title": self.settings.get('exam_title', 'Untitled Exam'),
                "exam_date": self.settings.get('exam_date', datetime.now().strftime("%Y-%m-%d")),
                "total_questions": len(self.questions),
                "total_points": sum(q.get('score', 0) for q in self.questions),
                "generated_at": datetime.now().isoformat(),
                "answers": []
            }
            
            for i, q in enumerate(self.questions):
                q_info = {
                    "question_id": q['id'],
                    "question_type": QUESTION_TYPES.get(q['type'], {}).get('name', 'Unknown'),
                    "score": q.get('score', 5),
                    "answer": self._get_answer_text(q),
                    "expected_answer": self._get_expected_answer(q),
                    "position": position_data[i] if i < len(position_data) else None
                }
                answer_key["answers"].append(q_info)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(answer_key, f, ensure_ascii=False, indent=2)
            
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
            
            QMessageBox.information(
                self, 
                "Success", 
                f"Answer key with positions has been saved.\n{file_path}\n\n"
                f"Total: {len(self.questions)} questions, {answer_key['total_points']} points"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export answer key: {str(e)}")
            import traceback
            traceback.print_exc()

    def _get_answer_text(self, q):
        """Return answer text for display"""
        qtype = q['type']
        
        if qtype == 0:
            answer = q.get('answer', '')
            choices = q.get('choices', [])
            if answer and choices:
                for i, choice in enumerate(choices):
                    if answer.lower() in choice.lower() or chr(65+i) == answer.upper():
                        return f"{chr(65+i)}. {choice}"
            return answer or "Not specified"
        
        elif qtype == 1:
            answer = q.get('answer', '')
            return "True" if answer.lower() in ['true', 't', 'o'] else "False"
        
        elif qtype == 2:
            blanks = q.get('blanks', [])
            answer = q.get('answer', '')
            if blanks:
                return ", ".join(blanks)
            return answer or "Not specified"
        
        elif qtype == 3:
            return q.get('answer', 'Not specified')
        
        elif qtype == 4:
            return "Essay - Manual grading required"
        
        elif qtype == 5:
            pairs = q.get('matching_pairs', [])
            if pairs:
                matches = []
                for i, (left, right) in enumerate(pairs):
                    matches.append(f"{i+1}-{chr(65+i)}")
                return "; ".join(matches)
            return q.get('answer', 'Not specified')
        
        elif qtype == 6:
            items = q.get('ordering_items', [])
            if items:
                return " → ".join(items)
            return q.get('answer', 'Not specified')
        
        elif qtype == 7:
            code = q.get('code_template', '')
            if code:
                return f"Expected output/implementation:\n{code[:200]}"
            return q.get('answer', 'Manual grading required')
        
        elif qtype == 8:
            formula = q.get('formula', '')
            if formula:
                return f"Formula: {formula}\nAnswer: {q.get('answer', 'Not specified')}"
            return q.get('answer', 'Not specified')
        
        else:
            return q.get('answer', 'Not specified')

    def _get_expected_answer(self, q):
        """Return simple expected answer for grading"""
        qtype = q['type']
        
        if qtype == 0:
            answer = q.get('answer', '')
            choices = q.get('choices', [])
            if answer and choices:
                for i, choice in enumerate(choices):
                    if answer.lower() in choice.lower():
                        return chr(65+i)
                    if answer.upper() == chr(65+i):
                        return answer.upper()
            return answer.upper() if answer else "?"
        
        elif qtype == 1:
            answer = q.get('answer', '')
            return "T" if answer.lower() in ['true', 't', 'o'] else "F"
        
        elif qtype == 2:
            blanks = q.get('blanks', [])
            return ", ".join(blanks) if blanks else q.get('answer', '')
        
        elif qtype == 3:
            return q.get('answer', '')
        
        elif qtype == 4:
            return "[ESSAY]"
        
        elif qtype == 5:
            pairs = q.get('matching_pairs', [])
            if pairs:
                match_list = []
                for idx, (left, right) in enumerate(pairs):
                    match_list.append(f"{idx+1}-{chr(65+idx) if idx < 26 else idx}")
                return "; ".join(match_list)
            return q.get('answer', '')
        
        elif qtype == 6:
            return " > ".join([str(i+1) for i in range(len(q.get('ordering_items', [])))])
        
        else:
            return q.get('answer', '')

    def _generate_pdf_with_positions(self, file_path, position_data):
        """Generate PDF with question position tracking"""
        exam_title = self.settings.get('exam_title', 'Untitled Exam') or "Untitled Exam"
        exam_date = self.settings.get('exam_date', '') or datetime.now().strftime("%B %d, %Y")
        
        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size
        
        class PositionTracker:
            def __init__(self):
                self.positions = []
                self.current_page = 0
                self.current_x = 0
                self.current_y = 0
            
            def add_position(self, q_id, x, y, page):
                self.positions.append({
                    'question_id': q_id,
                    'page': page,
                    'x': x,
                    'y': y
                })
        
        tracker = PositionTracker()
        
        margin_top = 25 * mm
        margin_bottom = 15 * mm
        margin_left = 20 * mm
        margin_right = 20 * mm
        
        available_width = width - margin_left - margin_right
        
        line_height = int(self.settings.get('line_spacing', 1.5) * self.settings.get('font_size', 11))
        layout_style = self.settings.get('layout_style', 'Two Column')
        font_size = self.settings.get('font_size', 11)
        title_font_size = self.settings.get('title_font_size', 18)
        
        current_y = height - margin_top
        current_page = 1
        
        c.setFont("Helvetica-Bold", title_font_size)
        c.drawCentredString(width/2, current_y, exam_title)
        current_y -= 22
        
        c.setFont("Helvetica", 10)
        total_points = sum(q.get('score', 0) for q in self.questions)
        
        if self.settings.get('show_qr', True):
            qr_data = json.dumps({
                "exam": exam_title,
                "date": exam_date,
                "questions": len(self.questions),
                "total_score": total_points
            })
            qr_path = generate_qr(qr_data, f"qr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            c.drawImage(qr_path, margin_left, current_y - 15, width=35, height=35)
            if os.path.exists(qr_path):
                os.remove(qr_path)
            c.drawRightString(width - margin_right, current_y, f"Total: {total_points} pts")
        else:
            c.drawRightString(width - margin_right, current_y, f"Total: {total_points} pts")
        
        current_y -= 18
        
        instruction = self.settings.get('exam_instruction', '')
        if instruction:
            c.setFont("Helvetica-Oblique", 9)
            instruction_lines = wrap_text(instruction, available_width - 20, 9)
            for line in instruction_lines:
                c.drawString(margin_left, current_y, f"※ {line}")
                current_y -= line_height - 4
            current_y -= 8
        
        c.line(margin_left, current_y, width - margin_right, current_y)
        current_y -= 15
        current_y -= 15
        
        if layout_style == "Two Column":
            self._draw_question_two_column_with_positions(
                c, self.questions, margin_left, margin_right, 
                width, height, line_height, font_size, 
                available_width, current_y, tracker
            )
        else:
            self._draw_question_standard_with_positions(
                c, self.questions, margin_left, margin_right, width, height,
                line_height, font_size, available_width, current_y, tracker, 40
            )
        
        c.save()
        
        for idx, pos in enumerate(tracker.positions):
            position_data.append(pos)

    def _draw_question_two_column_with_positions(self, c, questions, margin_left, margin_right, 
                                                width, height, line_height, font_size, 
                                                available_width, start_y, tracker):
        col_gap = 15
        col_width = (available_width - col_gap) // 2
        
        left_col_x = margin_left
        right_col_x = margin_left + col_width + col_gap
        
        page_bottom_margin = 25
        current_page = 1
        
        current_y = start_y
        q_index = 0
        total_questions = len(questions)
        
        while q_index < total_questions:
            if q_index > 0:
                c.showPage()
                current_page += 1
                current_y = height - 35
            
            left_y = current_y
            left_q_indices = []
            
            temp_index = q_index
            while temp_index < total_questions:
                q = questions[temp_index]
                q_height = self._estimate_question_height_two_col_v2(q, line_height, font_size, col_width) + 15
                
                if left_y - q_height > page_bottom_margin:
                    left_q_indices.append(temp_index)
                    left_y -= q_height
                    temp_index += 1
                else:
                    break
            
            right_q_indices = []
            right_y = current_y
            
            temp_index2 = temp_index
            while temp_index2 < total_questions:
                q = questions[temp_index2]
                q_height = self._estimate_question_height_two_col_v2(q, line_height, font_size, col_width) + 15
                
                if right_y - q_height > page_bottom_margin:
                    right_q_indices.append(temp_index2)
                    right_y -= q_height
                    temp_index2 += 1
                else:
                    break
            
            if left_q_indices:
                y_pos = current_y
                for idx in left_q_indices:
                    q = questions[idx]
                    tracker.add_position(q['id'], left_col_x, y_pos, current_page)
                    y_pos = self._draw_single_question_two_col_v3(
                        c, q, left_col_x, y_pos, line_height, font_size, col_width, idx + 1
                    )
                    y_pos -= 25
                    if idx != left_q_indices[-1]:
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.setLineWidth(0.5)
                        c.line(left_col_x, y_pos + 12, left_col_x + col_width, y_pos + 12)
                        c.setStrokeColor(black)
            
            if right_q_indices:
                y_pos = current_y
                for idx in right_q_indices:
                    q = questions[idx]
                    tracker.add_position(q['id'], right_col_x, y_pos, current_page)
                    y_pos = self._draw_single_question_two_col_v3(
                        c, q, right_col_x, y_pos, line_height, font_size, col_width, idx + 1
                    )
                    y_pos -= 25
                    if idx != right_q_indices[-1]:
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.setLineWidth(0.5)
                        c.line(right_col_x, y_pos + 12, right_col_x + col_width, y_pos + 12)
                        c.setStrokeColor(black)
            
            if right_q_indices:
                q_index = right_q_indices[-1] + 1
            elif left_q_indices:
                q_index = left_q_indices[-1] + 1
            else:
                q_index = temp_index if temp_index > q_index else q_index + 1

    def _draw_question_standard_with_positions(self, c, questions, margin_left, margin_right, width, height,
                                            line_height, font_size, available_width, start_y, tracker, page_bottom_margin=40):
        current_y = start_y
        current_page = 1
        
        for q in questions:
            needed_height = self._estimate_question_height(q, line_height, font_size, available_width)
            
            if current_y - needed_height < page_bottom_margin:
                c.showPage()
                current_page += 1
                current_y = height - 80
                c.setFont("Helvetica", font_size)
            
            tracker.add_position(q['id'], margin_left, current_y, current_page)
            
            current_y = self._draw_single_question_standard(
                c, q, margin_left, current_y, line_height, font_size, available_width
            )
            
            current_y -= line_height
            c.line(margin_left, current_y + 10, width - margin_right, current_y + 10)
            current_y -= 10

    def on_type_changed(self, index):
        for i in reversed(range(self.dynamic_layout.count())):
            widget = self.dynamic_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        qtype = index
        qinfo = QUESTION_TYPES.get(qtype, {})

        if qinfo.get("has_options", False):
            label = QLabel("Options:")
            self.dynamic_layout.addWidget(label)
            self.dynamic_layout.addWidget(self.options_input)
            self.options_input.show()
        else:
            self.options_input.hide()

        if qtype == 5:
            match_label = QLabel("Matching Pairs:")
            self.dynamic_layout.addWidget(match_label)
            left_label = QLabel("Left Column (Items):")
            self.dynamic_layout.addWidget(left_label)
            self.dynamic_layout.addWidget(self.matching_left)
            right_label = QLabel("Right Column (Matches):")
            self.dynamic_layout.addWidget(right_label)
            self.dynamic_layout.addWidget(self.matching_right)
            self.matching_left.show()
            self.matching_right.show()
        else:
            self.matching_left.hide()
            self.matching_right.hide()

        if qtype == 6:
            order_label = QLabel("Items to Order (correct order):")
            self.dynamic_layout.addWidget(order_label)
            self.dynamic_layout.addWidget(self.ordering_input)
            self.ordering_input.show()
        else:
            self.ordering_input.hide()

        if qtype == 2:
            blank_label = QLabel("Blank Answers (comma separated):")
            self.dynamic_layout.addWidget(blank_label)
            self.dynamic_layout.addWidget(self.blanks_input)
            self.blanks_input.show()
        else:
            self.blanks_input.hide()

        if qtype == 7:
            code_label = QLabel("Code Template / Expected Output:")
            self.dynamic_layout.addWidget(code_label)
            self.dynamic_layout.addWidget(self.code_input)
            self.code_input.show()
        else:
            self.code_input.hide()

        if qtype == 8:
            formula_label = QLabel("Formula / Equation:")
            self.dynamic_layout.addWidget(formula_label)
            self.dynamic_layout.addWidget(self.formula_input)
            self.formula_input.show()
        else:
            self.formula_input.hide()

        hints = {
            0: "Answer (e.g., A, B, C, D or option text)",
            1: "Answer (True/False)",
            2: "Answer key for blanks (or leave blank if using blanks field)",
            5: "Matching pairs (e.g., 1-A, 2-B, 3-C)",
            6: "Correct order (e.g., 3,1,4,2)",
            7: "Expected code output or solution",
        }
        self.q_answer.setPlaceholderText(hints.get(qtype, "Answer key"))

    def apply_style(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #1e1e1e;
                font-family: 'Segoe UI', 'Malgun Gothic', Arial;
                font-size: 12px;
                color: #e0e0e0;
            }

            QFrame#card, QWidget#card {
                background: #2d2d2d;
                border-radius: 16px;
                padding: 20px;
                border: 1px solid #3d3d3d;
            }

            QLabel#title {
                font-size: 18px;
                font-weight: bold;
                color: #007acc;
                margin-bottom: 16px;
                border-bottom: 2px solid #007acc;
                padding-bottom: 8px;
            }
            
            QLabel {
                font-size: 12px;
                color: #e0e0e0;
            }

            QGroupBox {
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                color: #e0e0e0;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #007acc;
                font-size: 12px;
            }

            QPushButton {
                background-color: #0d7377;
                color: white;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 13px;
                border: none;
                min-height: 20px;
            }

            QPushButton:hover {
                background-color: #14a085;
            }
            
            QPushButton:pressed {
                background-color: #0a5a5e;
            }

            QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 8px;
                background: #252526;
                color: #e0e0e0;
                font-size: 12px;
                min-height: 20px;
            }

            QTextEdit:focus, QLineEdit:focus {
                border: 2px solid #007acc;
            }
            
            QComboBox QAbstractItemView {
                background-color: #252526;
                color: #e0e0e0;
                selection-background-color: #007acc;
                border: 1px solid #3d3d3d;
                font-size: 12px;
            }
            
            QComboBox {
                font-size: 12px;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 30px;
                border-left: 1px solid #3d3d3d;
                border-radius: 0 8px 8px 0;
            }

            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
                background-color: #007acc;
                border-radius: 2px;
            }

            QListWidget, QListView, QAbstractItemView {
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                padding: 5px;
                font-size: 12px;
                background-color: #252526;
                color: #e0e0e0;
                alternate-background-color: #2d2d2d;
            }

            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #3d3d3d;
                background-color: #252526;
                color: #e0e0e0;
                font-size: 12px;
                min-height: 20px;
            }

            QListWidget::item:selected {
                background-color: #0d7377;
                color: #ffffff;
                font-size: 12px;
            }
            
            QListWidget::item:hover:!selected {
                background-color: #3d3d3d;
                color: #ffffff;
                font-size: 12px;
            }
            
            QListWidget * {
                font-size: 12px;
            }

            QCheckBox {
                spacing: 8px;
                font-size: 12px;
                color: #e0e0e0;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                border: 1px solid #3d3d3d;
                background-color: #252526;
            }
            
            QCheckBox::indicator:checked {
                background-color: #007acc;
                border: 1px solid #007acc;
            }

            QTabWidget::pane {
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                background: #2d2d2d;
            }
            
            QTabBar::tab {
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
                background-color: #252526;
                color: #e0e0e0;
                border-radius: 6px 6px 0 0;
            }
            
            QTabBar::tab:selected {
                background-color: #007acc;
                color: white;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #3d3d3d;
            }

            QScrollBar:vertical {
                background-color: #252526;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #3d3d3d;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #4d4d4d;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QScrollBar:horizontal {
                background-color: #252526;
                height: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:horizontal {
                background-color: #3d3d3d;
                border-radius: 6px;
                min-width: 20px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background-color: #4d4d4d;
            }
            
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }

            QDialog {
                background-color: #2d2d2d;
            }
            
            QMessageBox {
                background-color: #2d2d2d;
            }
            
            QMessageBox QPushButton {
                min-width: 80px;
                font-size: 13px;
            }
            
            QTreeWidget {
                font-size: 12px;
            }
            
            QTreeWidget::item {
                font-size: 12px;
            }
            
            QTableWidget {
                font-size: 12px;
            }
            
            QTableWidget::item {
                font-size: 12px;
            }
            
            QSpinBox, QDoubleSpinBox {
                font-size: 12px;
            }
            
            QTextEdit {
                font-size: 12px;
            }
            
            QLineEdit {
                font-size: 12px;
            }
        """)

        self.load_db_btn.setObjectName("db_load")
        self.save_db_btn.setObjectName("db_save")
        self.clear_all_btn.setObjectName("clear_all")

    def duplicate_question(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0 and current_row < len(self.questions):
            q_copy = self.questions[current_row].copy()
            if 'db_id' in q_copy:
                del q_copy['db_id']
            q_copy["id"] = len(self.questions) + 1
            self.questions.append(q_copy)
            self.update_list_display()
            self.on_content_changed()
            QMessageBox.information(self, "Success", f"Question duplicated as Q{q_copy['id']}")
        else:
            QMessageBox.warning(self, "Notice", "Please select a question to duplicate.")
    
    def edit_question(self):
        current_row = self.list_widget.currentRow()
        if current_row < 0 or current_row >= len(self.questions):
            QMessageBox.warning(self, "Notice", "Please select a question to edit.")
            return
        
        # 미리보기 타이머 일시 중지
        self.preview_timer.stop()

        q = self.questions[current_row]
        self.edit_index = current_row
        
        self.q_type.setCurrentIndex(q['type'])
        self.q_text.setText(q['text'])
        self.q_score.setValue(q.get('score', 5))
        self.q_difficulty.setCurrentText(q.get('difficulty', 'Medium'))
        
        if q.get('choices'):
            self.options_input.setText('\n'.join(q['choices']))
        else:
            self.options_input.clear()
        
        if q.get('blanks'):
            self.blanks_input.setText(', '.join(q['blanks']))
        else:
            self.blanks_input.clear()
        
        if q.get('matching_pairs'):
            left_items = [pair[0] for pair in q['matching_pairs']]
            right_items = [pair[1] for pair in q['matching_pairs']]
            self.matching_left.setText('\n'.join(left_items))
            self.matching_right.setText('\n'.join(right_items))
        
        if q.get('ordering_items'):
            self.ordering_input.setText('\n'.join(q['ordering_items']))
        else:
            self.ordering_input.clear()
        
        if q.get('code_template'):
            self.code_input.setText(q['code_template'])
        else:
            self.code_input.clear()
        
        if q.get('formula'):
            self.formula_input.setText(q['formula'])
        else:
            self.formula_input.clear()
        
        self.q_answer.setText(q.get('answer', ''))
        
        for btn in self.findChildren(QPushButton):
            if btn.text() == "➕ Add Question":
                self.add_btn = btn
                self.add_btn.setText("✏️ Update Question")
                self.add_btn.clicked.disconnect()
                self.add_btn.clicked.connect(self.update_question)
                break
        
        QMessageBox.information(self, "Edit Mode", f"Editing Q{q['id']}. Click 'Update Question' to save changes.")

        # 미리보기 타이머 재시작 (즉시 업데이트하지 않고 대기)
        self.preview_timer.start(800)
    
    def update_question(self):
        if not hasattr(self, 'edit_index'):
            return
        
        qtype = self.q_type.currentIndex()
        q_text_content = self.q_text.toPlainText().strip()
        if not q_text_content:
            QMessageBox.warning(self, "Notice", "Please enter question content.")
            return
        
        choices = []
        if QUESTION_TYPES.get(qtype, {}).get("has_options", False):
            choices_raw = self.options_input.toPlainText().strip()
            if choices_raw:
                choices = [c.strip() for c in choices_raw.split('\n') if c.strip()]
        
        matching_pairs = []
        if qtype == 5:
            left_raw = self.matching_left.toPlainText().strip()
            right_raw = self.matching_right.toPlainText().strip()
            left_items = [l.strip() for l in left_raw.split('\n') if l.strip()]
            right_items = [r.strip() for r in right_raw.split('\n') if r.strip()]
            matching_pairs = list(zip(left_items, right_items)) if left_items and right_items else []
        
        ordering_items = []
        if qtype == 6:
            order_raw = self.ordering_input.toPlainText().strip()
            ordering_items = [o.strip() for o in order_raw.split('\n') if o.strip()]
        
        blanks = []
        if qtype == 2:
            blanks_raw = self.blanks_input.text().strip()
            if blanks_raw:
                blanks = [b.strip() for b in blanks_raw.split(',')]
        
        self.questions[self.edit_index].update({
            "type": qtype,
            "type_name": QUESTION_TYPES[qtype]["name"],
            "type_icon": QUESTION_TYPES[qtype]["icon"],
            "text": q_text_content,
            "choices": choices,
            "matching_pairs": matching_pairs,
            "ordering_items": ordering_items,
            "blanks": blanks,
            "code_template": self.code_input.toPlainText().strip() if qtype == 7 else "",
            "formula": self.formula_input.text().strip() if qtype == 8 else "",
            "answer": self.q_answer.toPlainText().strip(),
            "score": self.q_score.value(),
            "difficulty": self.q_difficulty.currentText()
        })
        
        self.clear_question_inputs()
        
        if hasattr(self, 'add_btn'):
            self.add_btn.setText("➕ Add Question")
            self.add_btn.clicked.disconnect()
            self.add_btn.clicked.connect(self.add_question)
        
        self.update_list_display()
        self.on_content_changed()
        QMessageBox.information(self, "Success", "Question updated successfully.")
        delattr(self, 'edit_index')
    
    def clear_question_inputs(self):
        self.q_text.clear()
        self.options_input.clear()
        self.matching_left.clear()
        self.matching_right.clear()
        self.ordering_input.clear()
        self.blanks_input.clear()
        self.code_input.clear()
        self.formula_input.clear()
        self.q_answer.clear()
        self.q_score.setValue(5)
        self.q_difficulty.setCurrentText("Medium")

    def update_list_display(self):
        self.list_widget.clear()
        
        for idx, q in enumerate(self.questions):
            qinfo = QUESTION_TYPES.get(q["type"], {})
            icon = qinfo.get("icon", "❓")
            
            q_text_preview = q['text'][:60]
            if len(q['text']) > 60:
                q_text_preview += "..."
                
            option_info = ""
            if q.get("choices") and len(q.get("choices", [])) > 0:
                option_info = f" [{len(q['choices'])} options]"
                
            display_text = f"{icon} Q{q['id']}. {q_text_preview}{option_info} ({q['score']} pts) - {q.get('difficulty', 'Medium')}"
            
            item = QListWidgetItem(display_text)
            self.list_widget.addItem(item)

    def delete_question(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.list_widget.takeItem(current_row)
            del self.questions[current_row]
            for idx, q in enumerate(self.questions):
                q["id"] = idx + 1
            self.update_list_display()
            self.on_content_changed()
        else:
            QMessageBox.warning(self, "Notice", "Please select a question to delete.")
    
    def clear_all_questions(self):
        if not self.questions:
            return
        reply = QMessageBox.question(self, "Clear All", 
            "Are you sure you want to clear all questions? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.questions.clear()
            self.update_list_display()
            self.on_content_changed()
            QMessageBox.information(self, "Success", "All questions cleared.")

    def add_question(self):
        qid = len(self.questions) + 1
        qtype = self.q_type.currentIndex()
        qinfo = QUESTION_TYPES.get(qtype, {})

        q_text_content = self.q_text.toPlainText().strip()
        if not q_text_content:
            QMessageBox.warning(self, "Notice", "Please enter question content.")
            return

        choices = []
        if qinfo.get("has_options", False):
            choices_raw = self.options_input.toPlainText().strip()
            if choices_raw:
                choices = [c.strip() for c in choices_raw.split('\n') if c.strip()]

        matching_pairs = []
        if qtype == 5:
            left_raw = self.matching_left.toPlainText().strip()
            right_raw = self.matching_right.toPlainText().strip()
            left_items = [l.strip() for l in left_raw.split('\n') if l.strip()]
            right_items = [r.strip() for r in right_raw.split('\n') if r.strip()]
            matching_pairs = list(zip(left_items, right_items)) if left_items and right_items else []

        ordering_items = []
        if qtype == 6:
            order_raw = self.ordering_input.toPlainText().strip()
            ordering_items = [o.strip() for o in order_raw.split('\n') if o.strip()]

        blanks = []
        if qtype == 2:
            blanks_raw = self.blanks_input.text().strip()
            if blanks_raw:
                blanks = [b.strip() for b in blanks_raw.split(',')]

        q = {
            "id": qid,
            "type": qtype,
            "type_name": qinfo["name"],
            "type_icon": qinfo["icon"],
            "text": q_text_content,
            "choices": choices,
            "matching_pairs": matching_pairs,
            "ordering_items": ordering_items,
            "blanks": blanks,
            "code_template": self.code_input.toPlainText().strip() if qtype == 7 else "",
            "formula": self.formula_input.text().strip() if qtype == 8 else "",
            "answer": self.q_answer.toPlainText().strip(),
            "score": self.q_score.value(),
            "difficulty": self.q_difficulty.currentText()
        }

        self.questions.append(q)
        self.update_list_display()
        self.clear_question_inputs()
        self.on_content_changed()
        QMessageBox.information(self, "Success", f"Question {qid} ({qinfo['name']}) has been added.")

    def load_from_database(self):
        dialog = DatabaseBrowserDialog(self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.selected_questions
            if selected:
                for q in selected:
                    app_q = {
                        "id": len(self.questions) + 1,
                        "type": q['type'],
                        "type_name": QUESTION_TYPES.get(q['type'], {}).get('name', 'Unknown'),
                        "type_icon": QUESTION_TYPES.get(q['type'], {}).get('icon', '❓'),
                        "text": q['text'],
                        "score": q.get('score', 5),
                        "choices": q.get('choices', []),
                        "answer": q.get('answer', ''),
                        "blanks": q.get('blanks', []),
                        "matching_pairs": q.get('matching_pairs', []),
                        "ordering_items": q.get('ordering_items', []),
                        "code_template": q.get('code_template', ''),
                        "formula": q.get('formula', ''),
                        "difficulty": q.get('difficulty', 'Medium'),
                        "db_id": q['db_id']
                    }
                    self.questions.append(app_q)
                self.update_list_display()
                self.on_content_changed()
                QMessageBox.information(self, "Success", f"Loaded {len(selected)} questions from database.")
            else:
                QMessageBox.information(self, "Info", "No questions selected.")

    def save_current_to_database(self):
        if not self.questions:
            QMessageBox.warning(self, "Warning", "No questions to save.")
            return
        
        count = 0
        for q in self.questions:
            db_q = {
                'type': q['type'],
                'text': q['text'],
                'score': q.get('score', 5),
                'choices': q.get('choices', []),
                'answer': q.get('answer', ''),
                'blanks': q.get('blanks', []),
                'matching_pairs': q.get('matching_pairs', []),
                'ordering_items': q.get('ordering_items', []),
                'code_template': q.get('code_template', ''),
                'formula': q.get('formula', ''),
                'category': '',
                'difficulty': q.get('difficulty', 'Medium'),
                'tags': ''
            }
            
            if 'db_id' in q:
                self.db.update_question(q['db_id'], db_q)
            else:
                db_id = self.db.add_question(db_q)
                q['db_id'] = db_id
            count += 1
        
        QMessageBox.information(self, "Success", f"Saved {count} questions to database.")

    def export_pdf(self):
        """시험지 PDF 저장"""
        if not self.questions:
            QMessageBox.warning(self, "Notice", "Please add questions first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Exam PDF", "", "PDF (*.pdf)")
        if not file_path:
            return

        try:
            pdf_engine = PDFEngine(self.questions, self.settings)
            pdf_engine.generate_exam_pdf(file_path)
            QMessageBox.information(self, "Success", f"Exam PDF has been created.\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create PDF: {str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorApp()
    window.show()
    sys.exit(app.exec_())