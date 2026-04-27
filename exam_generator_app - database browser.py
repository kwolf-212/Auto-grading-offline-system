# exam_generator_app.py (修改后的完整代码)

import sys
import json
import qrcode
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon
from PyQt5.QtCore import Qt, QTimer
from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, black, white, gray
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPM
import os
import tempfile

from database_manager import DatabaseManager

# ---------------- QR ---------------- 
def generate_qr(data, filename="exam_qr.png"):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    return filename

# ---------------- PDF PREVIEW WIDGET ---------------- 
class PDFPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.current_pdf_path = None
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.zoom_label = QLabel("Zoom:")
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(50, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        
        self.zoom_value = QLabel("100%")
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setFixedWidth(80)
        
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_slider)
        toolbar.addWidget(self.zoom_value)
        toolbar.addStretch()
        toolbar.addWidget(self.refresh_btn)
        
        # Preview label (image display)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        self.preview_label.setMinimumHeight(400)
        
        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.preview_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; padding: 4px;")
        
        layout.addLayout(toolbar)
        layout.addWidget(scroll_area)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
    def on_zoom_changed(self, value):
        self.zoom_value.setText(f"{value}%")
        self.update_preview()
        
    def set_preview_image(self, pixmap):
        if pixmap and not pixmap.isNull():
            zoom = self.zoom_slider.value() / 100.0
            scaled_pixmap = pixmap.scaled(
                int(pixmap.width() * zoom),
                int(pixmap.height() * zoom),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled_pixmap)
            self.status_label.setText(f"Preview loaded | Zoom: {self.zoom_slider.value()}%")
        else:
            self.preview_label.setText("No preview available\nClick 'Refresh' to generate PDF preview")
            self.status_label.setText("No preview available")
            
    def update_preview(self):
        if self.current_pdf_path and os.path.exists(self.current_pdf_path):
            try:
                from reportlab.graphics import renderPM
                from reportlab.graphics.shapes import Drawing, String
                
                d = Drawing(400, 300)
                d.add(String(200, 150, "PDF Preview Available", fontSize=14, textAnchor='middle'))
                d.add(String(200, 120, f"File: {os.path.basename(self.current_pdf_path)}", fontSize=10, textAnchor='middle'))
                
                preview_path = tempfile.mktemp(suffix=".png")
                renderPM.drawToFile(d, preview_path, fmt='PNG')
                
                pixmap = QPixmap(preview_path)
                self.set_preview_image(pixmap)
                
                os.remove(preview_path)
            except Exception as e:
                self.status_label.setText(f"Preview error: {str(e)}")
        else:
            self.preview_label.setText("No PDF generated yet.\nClick 'Refresh Preview' to generate.")
            
    def load_pdf(self, pdf_path):
        self.current_pdf_path = pdf_path
        self.update_preview()

# ---------------- DATABASE BROWSER DIALOG ---------------- 
class DatabaseBrowserDialog(QDialog):
    """Dialog for browsing and selecting questions from database"""
    
    def __init__(self, db: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.selected_questions = []
        self.setWindowTitle("Browse Question Database")
        self.setGeometry(200, 200, 800, 600)
        self.init_ui()
        self.refresh_questions()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("📚 Question Database")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a73e8; margin-bottom: 10px;")
        layout.addWidget(title)
        
        # Search filters
        filter_group = QGroupBox("Search Filters")
        filter_layout = QGridLayout()
        
        filter_layout.addWidget(QLabel("Keyword:"), 0, 0)
        self.search_keyword = QLineEdit()
        self.search_keyword.setPlaceholderText("Search in question text, answer, or tags...")
        filter_layout.addWidget(self.search_keyword, 0, 1, 1, 2)
        
        filter_layout.addWidget(QLabel("Question Type:"), 1, 0)
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", -1)
        type_names = ["Multiple Choice", "True/False", "Fill in Blank", "Short Answer", 
                      "Essay", "Matching", "Ordering", "Code", "Calculation", "Diagram"]
        for i, name in enumerate(type_names):
            self.type_filter.addItem(name, i)
        filter_layout.addWidget(self.type_filter, 1, 1)
        
        filter_layout.addWidget(QLabel("Difficulty:"), 1, 2)
        self.difficulty_filter = QComboBox()
        self.difficulty_filter.addItem("All", "")
        self.difficulty_filter.addItem("Easy", "Easy")
        self.difficulty_filter.addItem("Medium", "Medium")
        self.difficulty_filter.addItem("Hard", "Hard")
        filter_layout.addWidget(self.difficulty_filter, 1, 3)
        
        self.search_btn = QPushButton("🔍 Search")
        self.search_btn.clicked.connect(self.refresh_questions)
        filter_layout.addWidget(self.search_btn, 2, 0, 1, 2)
        
        self.clear_btn = QPushButton("🗑 Clear Filters")
        self.clear_btn.clicked.connect(self.clear_filters)
        filter_layout.addWidget(self.clear_btn, 2, 2, 1, 2)
        
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)
        
        # Question list with checkboxes
        list_group = QGroupBox("Questions")
        list_layout = QVBoxLayout()
        
        # Select all controls
        select_layout = QHBoxLayout()
        self.select_all_cb = QCheckBox("Select All")
        self.select_all_cb.stateChanged.connect(self.toggle_select_all)
        select_layout.addWidget(self.select_all_cb)
        select_layout.addStretch()
        select_layout.addWidget(QLabel(f"Total: "))
        self.total_label = QLabel("0")
        select_layout.addWidget(self.total_label)
        list_layout.addLayout(select_layout)
        
        # Question list widget with checkboxes
        self.question_list = QListWidget()
        self.question_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.question_list.itemChanged.connect(self.on_item_changed)
        list_layout.addWidget(self.question_list)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("")
        stats_layout.addWidget(self.stats_label)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.load_selected_btn = QPushButton("✅ Load Selected Questions")
        self.load_selected_btn.setStyleSheet("background-color: #28a745;")
        self.load_selected_btn.clicked.connect(self.accept_selection)
        self.load_all_btn = QPushButton("📋 Load All Questions")
        self.load_all_btn.clicked.connect(self.load_all)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.load_selected_btn)
        btn_layout.addWidget(self.load_all_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def clear_filters(self):
        self.search_keyword.clear()
        self.type_filter.setCurrentIndex(0)
        self.difficulty_filter.setCurrentIndex(0)
        self.refresh_questions()
    
    def refresh_questions(self):
        self.question_list.clear()
        keyword = self.search_keyword.text() if self.search_keyword.text() else None
        qtype = self.type_filter.currentData()
        if qtype == -1:
            qtype = None
        difficulty = self.difficulty_filter.currentData()
        if not difficulty:
            difficulty = None
        
        questions = self.db.search_questions(
            keyword=keyword or "",
            question_type=qtype,
            difficulty=difficulty
        )
        
        self.all_questions = questions
        self.total_label.setText(str(len(questions)))
        
        # Update statistics
        total_score = sum(q.get('score', 0) for q in questions)
        self.stats_label.setText(f"📊 {len(questions)} questions | Total points: {total_score}")
        
        type_icons = ["🔘", "✓✗", "___", "📝", "📄", "🔗", "🔢", "💻", "🧮", "📊"]
        
        for q in questions:
            icon = type_icons[q['type']] if q['type'] < len(type_icons) else "❓"
            display_text = f"{icon} [{q['difficulty']}] {q['text'][:60]}... ({q['score']} pts)"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, q['db_id'])
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.question_list.addItem(item)
    
    def toggle_select_all(self, state):
        for i in range(self.question_list.count()):
            item = self.question_list.item(i)
            item.setCheckState(Qt.Checked if state else Qt.Unchecked)
    
    def on_item_changed(self, item):
        """Update selected questions when checkbox changes"""
        pass
    
    def get_selected_question_ids(self):
        selected_ids = []
        for i in range(self.question_list.count()):
            item = self.question_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_ids.append(item.data(Qt.UserRole))
        return selected_ids
    
    def accept_selection(self):
        selected_ids = self.get_selected_question_ids()
        if not selected_ids:
            QMessageBox.warning(self, "Warning", "Please select at least one question.")
            return
        
        self.selected_questions = []
        for qid in selected_ids:
            q = self.db.get_question_by_id(qid)
            if q:
                self.selected_questions.append(q)
        
        self.accept()
    
    def load_all(self):
        self.selected_questions = self.all_questions.copy()
        self.accept()

# ---------------- QUESTION TYPES ---------------- 
QUESTION_TYPES = {
    0: {"name": "Multiple Choice", "icon": "🔘", "has_options": True, "has_answer": True},
    1: {"name": "True/False", "icon": "✓✗", "has_options": False, "has_answer": True},
    2: {"name": "Fill in the Blank", "icon": "___", "has_options": False, "has_answer": True, "has_blanks": True},
    3: {"name": "Short Answer", "icon": "📝", "has_options": False, "has_answer": True},
    4: {"name": "Essay", "icon": "📄", "has_options": False, "has_answer": True, "has_lines": True},
    5: {"name": "Matching", "icon": "🔗", "has_options": True, "has_answer": True, "has_pairs": True},
    6: {"name": "Ordering/Ranking", "icon": "🔢", "has_options": True, "has_answer": True, "has_items": True},
    7: {"name": "Code Writing", "icon": "💻", "has_options": False, "has_answer": True, "has_code": True},
    8: {"name": "Calculation", "icon": "🧮", "has_options": False, "has_answer": True, "has_formula": True},
    9: {"name": "Diagram/Labeling", "icon": "📊", "has_options": False, "has_answer": True, "has_diagram": True},
}

# ---------------- MAIN APP ---------------- 
class GeneratorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Exam Generator - Professional")
        self.questions = []
        self.exam_title = "Midterm Examination"
        self.exam_date = datetime.now().strftime("%B %d, %Y")
        self.temp_pdf_path = None
        self.init_ui()
        self.showMaximized()
        
        # Auto-refresh timer for PDF preview
        self.preview_timer = QTimer()
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.generate_live_preview)

        self.db = DatabaseManager()

    def init_ui(self):
        container = QWidget()
        main_layout = QHBoxLayout()

        # ===== LEFT: INPUT CARD =====
        left_card = QFrame()
        left_card.setObjectName("card")
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)

        title = QLabel("📝 Add Question")
        title.setObjectName("title")

        # Exam Basic Information
        exam_info_group = QGroupBox("Exam Information")
        exam_info_layout = QVBoxLayout()
        self.exam_title_input = QLineEdit(self.exam_title)
        self.exam_title_input.setPlaceholderText("Exam Title")
        self.exam_title_input.textChanged.connect(self.on_content_changed)
        self.exam_date_input = QLineEdit(self.exam_date)
        self.exam_date_input.setPlaceholderText("Exam Date")
        self.exam_date_input.textChanged.connect(self.on_content_changed)
        exam_info_layout.addWidget(QLabel("Exam Title:"))
        exam_info_layout.addWidget(self.exam_title_input)
        exam_info_layout.addWidget(QLabel("Exam Date:"))
        exam_info_layout.addWidget(self.exam_date_input)
        exam_info_group.setLayout(exam_info_layout)
        
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

        # ===== DYNAMIC FIELDS =====
        self.dynamic_widgets = {}
        self.dynamic_container = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_container)
        self.dynamic_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.dynamic_container)

        # Options field
        self.options_input = QTextEdit()
        self.options_input.setPlaceholderText("Options (one per line)\nExample:\nA) Option 1\nB) Option 2\nC) Option 3")
        self.options_input.setMaximumHeight(100)
        self.options_input.textChanged.connect(self.on_content_changed)

        # Blank answers
        self.blanks_input = QLineEdit()
        self.blanks_input.setPlaceholderText("Blank answers (comma separated) e.g., Seoul, 42, True")
        self.blanks_input.textChanged.connect(self.on_content_changed)

        # Matching pairs
        self.matching_left = QTextEdit()
        self.matching_left.setPlaceholderText("Left column (one per line)\n1. Apple\n2. Carrot\n3. Cow")
        self.matching_left.setMaximumHeight(80)
        self.matching_left.textChanged.connect(self.on_content_changed)
        self.matching_right = QTextEdit()
        self.matching_right.setPlaceholderText("Right column (one per line)\nA. Fruit\nB. Vegetable\nC. Animal")
        self.matching_right.setMaximumHeight(80)
        self.matching_right.textChanged.connect(self.on_content_changed)

        # Ordering items
        self.ordering_input = QTextEdit()
        self.ordering_input.setPlaceholderText("Items to order (one per line)\nStep 1: ...\nStep 2: ...\nStep 3: ...")
        self.ordering_input.setMaximumHeight(100)
        self.ordering_input.textChanged.connect(self.on_content_changed)

        # Code block
        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText("Code template or expected output...")
        self.code_input.setMaximumHeight(100)
        self.code_input.textChanged.connect(self.on_content_changed)

        # Formula input
        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("Formula or equation (e.g., E = mc²)")
        self.formula_input.textChanged.connect(self.on_content_changed)

        # Answer input
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
        
        # Difficulty
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

        # ===== RIGHT: PREVIEW + ACTION =====
        right_card = QFrame()
        right_card.setObjectName("card")
        right_layout = QVBoxLayout()

        preview_title = QLabel("👁️ Live PDF Preview")
        preview_title.setObjectName("title")

        # PDF Preview Widget
        self.pdf_preview = PDFPreviewWidget()
        self.pdf_preview.refresh_btn.clicked.connect(self.generate_live_preview)

        btn_pdf = QPushButton("📄 Save Exam PDF (with QR)")
        btn_pdf.clicked.connect(self.export_pdf)

        btn_answer = QPushButton("📝 Save Answer Sheet PDF")
        btn_answer.clicked.connect(self.export_answer_sheet)

        right_layout.addWidget(preview_title)
        right_layout.addWidget(self.pdf_preview)
        right_layout.addWidget(btn_pdf)
        right_layout.addWidget(btn_answer)

        right_card.setLayout(right_layout)

        main_layout.addWidget(left_card, 2)
        main_layout.addWidget(center_card, 2)
        main_layout.addWidget(right_card, 3)

        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.on_type_changed(0)
        self.apply_style()
        
        QTimer.singleShot(500, self.generate_live_preview)

    def on_content_changed(self):
        self.preview_timer.start(1500)

    def on_list_reordered(self):
        for idx, q in enumerate(self.questions):
            q["id"] = idx + 1
        self.update_list_display()
        self.on_content_changed()

    def generate_live_preview(self):
        if not self.questions:
            self.pdf_preview.status_label.setText("No questions added yet. Add a question to see preview.")
            self.pdf_preview.preview_label.setText("No questions added.\nAdd questions to see live PDF preview.")
            return
        
        temp_dir = tempfile.gettempdir()
        self.temp_pdf_path = os.path.join(temp_dir, f"exam_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        
        try:
            self._generate_pdf_to_file(self.temp_pdf_path, is_preview=True)
            self.pdf_preview.load_pdf(self.temp_pdf_path)
            self.pdf_preview.status_label.setText(f"Live preview updated | {len(self.questions)} questions")
        except Exception as e:
            self.pdf_preview.status_label.setText(f"Preview error: {str(e)}")

    def _generate_pdf_to_file(self, file_path, is_preview=False):
        exam_title = self.exam_title_input.text() or "Untitled Exam"
        exam_date = self.exam_date_input.text() or datetime.now().strftime("%B %d, %Y")
        
        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        margin = 50
        y = height - margin
        line_height = 20

        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 40, exam_title)
        c.setFont("Helvetica", 10)
        c.drawString(margin, height - 65, f"Date: {exam_date}")
        total_points = sum(q['score'] for q in self.questions)
        c.drawRightString(width - margin, height - 65, f"Total: {total_points} pts")

        if not is_preview:
            qr_data = json.dumps({
                "exam": exam_title,
                "date": exam_date,
                "questions": len(self.questions),
                "total_score": total_points
            })
            qr_path = generate_qr(qr_data, f"qr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            c.drawImage(qr_path, width - 100, height - 100, width=60, height=60)
            if os.path.exists(qr_path):
                os.remove(qr_path)

        y -= 90

        for q in self.questions:
            if y < margin + 100:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 12)

            c.setFont("Helvetica-Bold", 12)
            text_line = f"Q{q['id']}. {q['text']} ({q['score']} pts)"
            c.drawString(margin, y, text_line)
            y -= line_height

            c.setFont("Helvetica", 11)
            
            if q["type"] == 0:  # Multiple Choice
                for i, choice in enumerate(q.get("choices", []), 1):
                    c.drawString(margin + 10, y, f"{i}. {choice}")
                    y -= line_height
                y -= line_height
                c.drawString(margin, y, f"Answer: ______")
                
            elif q["type"] == 1:  # True/False
                c.drawString(margin, y, "( ) True   ( ) False")
                
            elif q["type"] == 2:  # Fill in Blank
                blank_count = len(q.get("blanks", [])) or 3
                blanks = " ______ " * blank_count
                c.drawString(margin, y, blanks)
                
            elif q["type"] == 3:  # Short Answer
                c.drawString(margin, y, "Answer: ____________________")
                
            elif q["type"] == 4:  # Essay
                c.drawString(margin, y, "[Answer Space]")
                y -= line_height
                c.line(margin, y, width - margin, y)
                y -= line_height
                c.line(margin, y, width - margin, y)
                
            elif q["type"] == 5:  # Matching
                c.drawString(margin, y, "Match the following:")
                y -= line_height
                for left, right in q.get("matching_pairs", []):
                    c.drawString(margin + 10, y, f"{left}  ↔  ______")
                    y -= line_height
                    
            elif q["type"] == 6:  # Ordering
                c.drawString(margin, y, "Arrange in correct order: ___ , ___ , ___ , ___")
                
            elif q["type"] == 7:  # Code
                c.drawString(margin, y, "Write your code below:")
                y -= line_height * 2
                c.rect(margin, y - 40, width - margin*2, 40)
                
            elif q["type"] == 8:  # Calculation
                c.drawString(margin, y, "Show your work:")
                y -= line_height * 2
                c.line(margin, y, width - margin, y)

            y -= line_height * 2
            c.line(margin, y + 10, width - margin, y + 10)

        c.save()

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

        if qtype == 5:  # Matching
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

        if qtype == 6:  # Ordering
            order_label = QLabel("Items to Order (correct order):")
            self.dynamic_layout.addWidget(order_label)
            self.dynamic_layout.addWidget(self.ordering_input)
            self.ordering_input.show()
        else:
            self.ordering_input.hide()

        if qtype == 2:  # Fill in Blank
            blank_label = QLabel("Blank Answers (comma separated):")
            self.dynamic_layout.addWidget(blank_label)
            self.dynamic_layout.addWidget(self.blanks_input)
            self.blanks_input.show()
        else:
            self.blanks_input.hide()

        if qtype == 7:  # Code Writing
            code_label = QLabel("Code Template / Expected Output:")
            self.dynamic_layout.addWidget(code_label)
            self.dynamic_layout.addWidget(self.code_input)
            self.code_input.show()
        else:
            self.code_input.hide()

        if qtype == 8:  # Calculation
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
            QWidget { background-color: #f0f2f5; font-family: 'Segoe UI', Arial; font-size: 12px; }

            #card {
                background: white;
                border-radius: 16px;
                padding: 20px;
                border: 1px solid #e0e0e0;
            }

            #title {
                font-size: 18px;
                font-weight: bold;
                color: #1a73e8;
                margin-bottom: 16px;
                border-bottom: 2px solid #1a73e8;
                padding-bottom: 8px;
            }

            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }

            QPushButton {
                background-color: #1a73e8;
                color: white;
                border-radius: 8px;
                padding: 10px;
                font-weight: bold;
                border: none;
            }

            QPushButton:hover { background-color: #1557b0; }
            QPushButton:pressed { background-color: #0d3c7a; }

            QTextEdit, QLineEdit, QComboBox, QSpinBox {
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 8px;
                background: white;
                font-size: 12px;
            }

            QTextEdit:focus, QLineEdit:focus {
                border: 2px solid #1a73e8;
            }

            QListWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 5px;
            }

            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }

            QListWidget::item:selected {
                background-color: #e8f0fe;
                color: #1a73e8;
            }
        """)

    def duplicate_question(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0 and current_row < len(self.questions):
            q_copy = self.questions[current_row].copy()
            if 'db_id' in q_copy:
                del q_copy['db_id']  # Remove DB ID for duplicate
            q_copy["id"] = len(self.questions) + 1
            self.questions.append(q_copy)
            self.update_list_display()
            self.on_content_changed()
            QMessageBox.information(self, "Success", f"Question duplicated as Q{q_copy['id']}")
        else:
            QMessageBox.warning(self, "Notice", "Please select a question to duplicate.")
    
    def edit_question(self):
        """Edit selected question - load its data into input fields"""
        current_row = self.list_widget.currentRow()
        if current_row < 0 or current_row >= len(self.questions):
            QMessageBox.warning(self, "Notice", "Please select a question to edit.")
            return
        
        q = self.questions[current_row]
        self.edit_index = current_row  # Store for update
        
        # Load question data into input fields
        self.q_type.setCurrentIndex(q['type'])
        self.q_text.setText(q['text'])
        self.q_score.setValue(q.get('score', 5))
        self.q_difficulty.setCurrentText(q.get('difficulty', 'Medium'))
        
        # Load type-specific fields
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
        
        # Change add button to update button
        for btn in self.findChildren(QPushButton):
            if btn.text() == "➕ Add Question":
                self.add_btn = btn
                self.add_btn.setText("✏️ Update Question")
                self.add_btn.clicked.disconnect()
                self.add_btn.clicked.connect(self.update_question)
                break
        
        QMessageBox.information(self, "Edit Mode", f"Editing Q{q['id']}. Click 'Update Question' to save changes.")
    
    def update_question(self):
        """Update the edited question"""
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
        
        # Update the question
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
        
        # Clear inputs
        self.clear_question_inputs()
        
        # Restore add button
        if hasattr(self, 'add_btn'):
            self.add_btn.setText("➕ Add Question")
            self.add_btn.clicked.disconnect()
            self.add_btn.clicked.connect(self.add_question)
        
        self.update_list_display()
        self.on_content_changed()
        QMessageBox.information(self, "Success", "Question updated successfully.")
        delattr(self, 'edit_index')
    
    def clear_question_inputs(self):
        """Clear all question input fields"""
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
        for q in self.questions:
            qinfo = QUESTION_TYPES.get(q["type"], {})
            icon = qinfo.get("icon", "❓")
            display_text = f"{icon} Q{q['id']}. {q['text'][:50]}"
            if q.get("choices") and len(q.get("choices", [])) > 0:
                display_text += f" [{len(q['choices'])} options]"
            display_text += f" ({q['score']} pts)"
            self.list_widget.addItem(display_text)

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
        """Clear all questions from current exam"""
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
        """Open database browser dialog to load questions"""
        dialog = DatabaseBrowserDialog(self.db, self)
        if dialog.exec_() == QDialog.Accepted:
            selected = dialog.selected_questions
            if selected:
                for q in selected:
                    # Convert DB format to app format
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
        """Save current questions to database"""
        if not self.questions:
            QMessageBox.warning(self, "Warning", "No questions to save.")
            return
        
        count = 0
        for q in self.questions:
            # Prepare question dict for database
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
                # Update existing question
                self.db.update_question(q['db_id'], db_q)
            else:
                # Add new question
                db_id = self.db.add_question(db_q)
                q['db_id'] = db_id
            count += 1
        
        QMessageBox.information(self, "Success", f"Saved {count} questions to database.")

    def export_pdf(self):
        if not self.questions:
            QMessageBox.warning(self, "Notice", "Please add questions first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Exam PDF", "", "PDF (*.pdf)")
        if not file_path:
            return

        try:
            self._generate_pdf_to_file(file_path, is_preview=False)
            QMessageBox.information(self, "Success", f"Exam PDF has been created.\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create PDF: {str(e)}")

    def export_answer_sheet(self):
        if not self.questions:
            QMessageBox.warning(self, "Notice", "Please add questions first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Answer Sheet PDF", "", "PDF (*.pdf)")
        if not file_path:
            return

        c = canvas.Canvas(file_path, pagesize=A4)
        width, height = A4
        margin = 50
        y = height - margin
        line_height = 25

        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(width/2, height - 50, "ANSWER SHEET")
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height - 75, f"{self.exam_title_input.text() or 'Exam'}")

        y -= 100

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "Write your answers below.")
        y -= line_height * 2

        c.setFont("Helvetica", 11)
        for q in self.questions:
            if y < margin + 50:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 11)

            if q["type"] == 0:  # MC
                c.drawString(margin, y, f"Q{q['id']}.   (   )")
            elif q["type"] == 1:  # T/F
                c.drawString(margin, y, f"Q{q['id']}.   (   )")
            elif q["type"] == 2:  # Fill blank
                blank_count = len(q.get("blanks", [])) or 3
                blanks = " ______ " * blank_count
                c.drawString(margin, y, f"Q{q['id']}.   {blanks}")
            elif q["type"] in [3, 7, 8]:  # Short answer, Code, Calculation
                c.drawString(margin, y, f"Q{q['id']}.   ____________________")
            elif q["type"] == 4:  # Essay
                c.drawString(margin, y, f"Q{q['id']}.")
                y -= line_height
                c.line(margin, y, width - margin, y)
                y -= line_height
                c.line(margin, y, width - margin, y)
            elif q["type"] == 5:  # Matching
                c.drawString(margin, y, f"Q{q['id']}.   1:__  2:__  3:__")
            elif q["type"] == 6:  # Ordering
                c.drawString(margin, y, f"Q{q['id']}.   ___ , ___ , ___ , ___")
            y -= line_height

        c.save()
        QMessageBox.information(self, "Success", f"Answer Sheet PDF has been created.\n{file_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorApp()
    window.show()
    sys.exit(app.exec_())