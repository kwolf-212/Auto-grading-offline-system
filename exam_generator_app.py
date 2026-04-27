# exam_generator_app.py (설정을 오른쪽으로 이동하고 다이얼로그로 변경)

import sys
import json
import qrcode
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon
from PyQt5.QtCore import Qt, QTimer
from reportlab.lib.pagesizes import A4, letter, A5, B5, legal, landscape
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, black, white, gray
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPM
import os
import tempfile

# PyMuPDF import for better PDF preview
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("Warning: PyMuPDF not installed. Install with: pip install PyMuPDF")

from database_manager import DatabaseManager

# ---------------- PAGE SIZE MAPPING ----------------
PAGE_SIZES = {
    "A4": A4,
    "Letter": letter,
    "A5": A5,
    "B5": B5,
    "Legal": legal,
    "A4 Landscape": landscape(A4),
    "Letter Landscape": landscape(letter),
}

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

# ---------------- SETTINGS DIALOG ----------------
class ExamSettingsDialog(QDialog):
    """Dialog for exam settings (page setup, student info, exam info)"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📐 Exam Settings")
        self.setGeometry(300, 300, 600, 500)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Tab widget for organized settings
        tab_widget = QTabWidget()
        
        # Tab 1: Exam Information
        exam_tab = QWidget()
        exam_layout = QFormLayout(exam_tab)
        
        self.exam_title_input = QLineEdit()
        self.exam_title_input.setPlaceholderText("e.g., Midterm Examination")
        exam_layout.addRow("Exam Title:", self.exam_title_input)
        
        self.exam_date_input = QLineEdit()
        self.exam_date_input.setPlaceholderText("e.g., December 15, 2024")
        exam_layout.addRow("Exam Date:", self.exam_date_input)
        
        self.exam_instruction = QTextEdit()
        self.exam_instruction.setMaximumHeight(100)
        self.exam_instruction.setPlaceholderText("Additional instructions for students...")
        exam_layout.addRow("Instructions:", self.exam_instruction)
        
        tab_widget.addTab(exam_tab, "📋 Exam Info")
        
        # Tab 2: Page Setup
        page_tab = QWidget()
        page_layout = QFormLayout(page_tab)
        
        self.page_size = QComboBox()
        for size_name in PAGE_SIZES.keys():
            self.page_size.addItem(size_name)
        self.page_size.setCurrentText("A4")
        page_layout.addRow("Paper Size:", self.page_size)
        
        self.layout_style = QComboBox()
        self.layout_style.addItems(["Standard (Single Column)", "Two Column", "Filled Line Format"])
        page_layout.addRow("Layout Style:", self.layout_style)
        
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(10, 80)
        self.margin_spin.setValue(50)
        self.margin_spin.setSuffix(" mm")
        page_layout.addRow("Margins:", self.margin_spin)
        
        self.line_spacing = QDoubleSpinBox()
        self.line_spacing.setRange(1.0, 3.0)
        self.line_spacing.setValue(1.5)
        self.line_spacing.setSingleStep(0.1)
        page_layout.addRow("Line Spacing:", self.line_spacing)
        
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 16)
        self.font_size.setValue(11)
        self.font_size.setSuffix(" pt")
        page_layout.addRow("Font Size:", self.font_size)
        
        self.title_font_size = QSpinBox()
        self.title_font_size.setRange(12, 24)
        self.title_font_size.setValue(18)
        self.title_font_size.setSuffix(" pt")
        page_layout.addRow("Title Font Size:", self.title_font_size)
        
        self.show_qr = QCheckBox("Show QR Code")
        self.show_qr.setChecked(True)
        page_layout.addRow("QR Code:", self.show_qr)
        
        self.essay_lines = QSpinBox()
        self.essay_lines.setRange(2, 10)
        self.essay_lines.setValue(4)
        page_layout.addRow("Essay Lines:", self.essay_lines)
        
        tab_widget.addTab(page_tab, "📄 Page Setup")
        
        # Tab 3: Student Information
        student_tab = QWidget()
        student_layout = QFormLayout(student_tab)
        
        self.include_student_info = QCheckBox("Include Student Information Section")
        self.include_student_info.setChecked(True)
        student_layout.addRow("", self.include_student_info)
        
        self.student_name = QLineEdit()
        self.student_name.setPlaceholderText("_________________________")
        student_layout.addRow("Student Name:", self.student_name)
        
        self.student_id = QLineEdit()
        self.student_id.setPlaceholderText("_________________________")
        student_layout.addRow("Student ID:", self.student_id)
        
        self.department = QLineEdit()
        self.department.setPlaceholderText("_________________________")
        student_layout.addRow("Department:", self.department)
        
        self.instructor = QLineEdit()
        self.instructor.setPlaceholderText("_________________________")
        student_layout.addRow("Instructor:", self.instructor)
        
        self.student_date = QLineEdit()
        self.student_date.setPlaceholderText("_________________________")
        student_layout.addRow("Date:", self.student_date)
        
        self.additional_info = QLineEdit()
        self.additional_info.setPlaceholderText("(Optional)")
        student_layout.addRow("Additional Info:", self.additional_info)
        
        tab_widget.addTab(student_tab, "👤 Student Info")
        
        # Tab 4: Advanced Options
        advanced_tab = QWidget()
        advanced_layout = QFormLayout(advanced_tab)
        
        self.show_points = QCheckBox("Show Points per Question")
        self.show_points.setChecked(True)
        advanced_layout.addRow("", self.show_points)
        
        self.show_answer_lines = QCheckBox("Show Answer Lines")
        self.show_answer_lines.setChecked(True)
        advanced_layout.addRow("", self.show_answer_lines)
        
        self.numbering_style = QComboBox()
        self.numbering_style.addItems(["1, 2, 3...", "1), 2), 3)...", "(1), (2), (3)...", "A, B, C..."])
        advanced_layout.addRow("Numbering Style:", self.numbering_style)
        
        tab_widget.addTab(advanced_tab, "⚙️ Advanced")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.setStyleSheet("background-color: #28a745;")
        self.save_btn.clicked.connect(self.accept)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def get_settings(self):
        return {
            'exam_title': self.exam_title_input.text(),
            'exam_date': self.exam_date_input.text(),
            'exam_instruction': self.exam_instruction.toPlainText(),
            'page_size': self.page_size.currentText(),
            'layout_style': self.layout_style.currentText(),
            'margin': self.margin_spin.value(),
            'line_spacing': self.line_spacing.value(),
            'font_size': self.font_size.value(),
            'title_font_size': self.title_font_size.value(),
            'show_qr': self.show_qr.isChecked(),
            'essay_lines': self.essay_lines.value(),
            'include_student_info': self.include_student_info.isChecked(),
            'student_name': self.student_name.text(),
            'student_id': self.student_id.text(),
            'department': self.department.text(),
            'instructor': self.instructor.text(),
            'student_date': self.student_date.text(),
            'additional_info': self.additional_info.text(),
            'show_points': self.show_points.isChecked(),
            'show_answer_lines': self.show_answer_lines.isChecked(),
            'numbering_style': self.numbering_style.currentText()
        }
    
    def set_settings(self, settings):
        self.exam_title_input.setText(settings.get('exam_title', ''))
        self.exam_date_input.setText(settings.get('exam_date', ''))
        self.exam_instruction.setText(settings.get('exam_instruction', ''))
        
        idx = self.page_size.findText(settings.get('page_size', 'A4'))
        if idx >= 0:
            self.page_size.setCurrentIndex(idx)
        
        idx = self.layout_style.findText(settings.get('layout_style', 'Standard (Single Column)'))
        if idx >= 0:
            self.layout_style.setCurrentIndex(idx)
        
        self.margin_spin.setValue(settings.get('margin', 50))
        self.line_spacing.setValue(settings.get('line_spacing', 1.5))
        self.font_size.setValue(settings.get('font_size', 11))
        self.title_font_size.setValue(settings.get('title_font_size', 18))
        self.show_qr.setChecked(settings.get('show_qr', True))
        self.essay_lines.setValue(settings.get('essay_lines', 4))
        
        self.include_student_info.setChecked(settings.get('include_student_info', True))
        self.student_name.setText(settings.get('student_name', ''))
        self.student_id.setText(settings.get('student_id', ''))
        self.department.setText(settings.get('department', ''))
        self.instructor.setText(settings.get('instructor', ''))
        self.student_date.setText(settings.get('student_date', ''))
        self.additional_info.setText(settings.get('additional_info', ''))
        
        self.show_points.setChecked(settings.get('show_points', True))
        self.show_answer_lines.setChecked(settings.get('show_answer_lines', True))
        
        idx = self.numbering_style.findText(settings.get('numbering_style', '1, 2, 3...'))
        if idx >= 0:
            self.numbering_style.setCurrentIndex(idx)


# ---------------- SETTINGS SUMMARY WIDGET ----------------
class SettingsSummaryWidget(QWidget):
    """Widget to show settings summary on the right panel"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.settings = {}
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title_label = QLabel("⚙️ Current Settings")
        title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #1a73e8;")
        layout.addWidget(title_label)
        
        # Settings display
        self.settings_text = QTextEdit()
        self.settings_text.setReadOnly(True)
        self.settings_text.setMaximumHeight(200)
        self.settings_text.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ddd; border-radius: 5px;")
        layout.addWidget(self.settings_text)
        
        # Edit button
        self.edit_btn = QPushButton("✏️ Edit Settings")
        self.edit_btn.setStyleSheet("background-color: #17a2b8;")
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self.edit_btn)
        
        self.setLayout(layout)
        
    def update_summary(self, settings):
        self.settings = settings
        
        summary = f"""
📋 Exam: {settings.get('exam_title', 'Not set') or 'Untitled'}
📅 Date: {settings.get('exam_date', 'Not set') or datetime.now().strftime('%B %d, %Y')}

📄 Page: {settings.get('page_size', 'A4')} | {settings.get('layout_style', 'Standard')}
📏 Margins: {settings.get('margin', 50)}mm | Line Spacing: {settings.get('line_spacing', 1.5)}x
🔤 Font: {settings.get('font_size', 11)}pt (Title: {settings.get('title_font_size', 18)}pt)

👤 Student Info: {'✓ Included' if settings.get('include_student_info', True) else '✗ Excluded'}
📊 Show Points: {'✓' if settings.get('show_points', True) else '✗'}
🔢 Numbering: {settings.get('numbering_style', '1, 2, 3...')}
        """
        
        if settings.get('include_student_info', True):
            summary += f"\n📝 Student fields: Name, ID, Department, Instructor, Date"
        
        self.settings_text.setText(summary)


# ---------------- PDF PREVIEW WIDGET (개선됨) ---------------- 
class PDFPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pdf_path = None
        self.current_page = 0
        self.total_pages = 0
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.zoom_label = QLabel("Zoom:")
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(30, 200)
        self.zoom_slider.setValue(80)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        
        self.zoom_value = QLabel("80%")
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setFixedWidth(80)
        
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_slider)
        toolbar.addWidget(self.zoom_value)
        toolbar.addStretch()
        
        # Page navigation
        self.prev_btn = QPushButton("◀ Prev")
        self.prev_btn.setFixedWidth(60)
        self.prev_btn.clicked.connect(self.prev_page)
        self.page_label = QLabel("Page 1 / 1")
        self.page_label.setMinimumWidth(80)
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setFixedWidth(60)
        self.next_btn.clicked.connect(self.next_page)
        
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.page_label)
        toolbar.addWidget(self.next_btn)
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
        self.preview_label.setMinimumHeight(500)
        self.preview_label.setScaledContents(False)
        
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
        self.update_navigation_buttons()
        
    def on_zoom_changed(self, value):
        self.zoom_value.setText(f"{value}%")
        self.update_preview()
        
    def update_navigation_buttons(self):
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
        self.page_label.setText(f"Page {self.current_page + 1} / {max(1, self.total_pages)}")
        
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_preview()
            
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
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
            self.status_label.setText(f"Preview loaded | Page {self.current_page + 1} | Zoom: {self.zoom_slider.value()}%")
        else:
            self.preview_label.setText("No preview available\nClick 'Refresh' to generate PDF preview")
            self.status_label.setText("No preview available")
            
    def update_preview(self):
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            self.preview_label.setText("No PDF generated yet.\nClick 'Refresh' to generate PDF preview.")
            self.status_label.setText("No PDF file available")
            self.current_page = 0
            self.total_pages = 0
            self.update_navigation_buttons()
            return
            
        if not PYMUPDF_AVAILABLE:
            file_size = os.path.getsize(self.current_pdf_path) / 1024
            self.preview_label.setText(
                f"PDF File: {os.path.basename(self.current_pdf_path)}\n"
                f"Size: {file_size:.1f} KB\n"
                f"Pages: {self.total_pages}\n\n"
                f"Install PyMuPDF for actual preview:\n"
                f"pip install PyMuPDF"
            )
            self.status_label.setText("PyMuPDF not installed - preview disabled")
            return
            
        try:
            doc = fitz.open(self.current_pdf_path)
            self.total_pages = len(doc)
            
            if self.current_page >= self.total_pages:
                self.current_page = 0
                
            self.update_navigation_buttons()
            
            if self.total_pages > 0:
                page = doc[self.current_page]
                zoom_matrix = fitz.Matrix(1.5, 1.5)
                pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)
                
                img_data = pix.tobytes("png")
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                
                self.set_preview_image(pixmap)
            else:
                self.preview_label.setText("PDF has no pages")
                
            doc.close()
            
        except Exception as e:
            self.status_label.setText(f"Preview error: {str(e)}")
            self.preview_label.setText(f"Failed to render PDF preview.\nError: {str(e)}")
            self.current_page = 0
            self.total_pages = 0
            self.update_navigation_buttons()
            
    def load_pdf(self, pdf_path):
        self.current_pdf_path = pdf_path
        self.current_page = 0
        self.total_pages = 0
        self.update_preview()


# ---------------- DATABASE BROWSER DIALOG ---------------- 
class DatabaseBrowserDialog(QDialog):
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
        
        title = QLabel("📚 Question Database")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #1a73e8; margin-bottom: 10px;")
        layout.addWidget(title)
        
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
        
        list_group = QGroupBox("Questions")
        list_layout = QVBoxLayout()
        
        select_layout = QHBoxLayout()
        self.select_all_cb = QCheckBox("Select All")
        self.select_all_cb.stateChanged.connect(self.toggle_select_all)
        select_layout.addWidget(self.select_all_cb)
        select_layout.addStretch()
        select_layout.addWidget(QLabel(f"Total: "))
        self.total_label = QLabel("0")
        select_layout.addWidget(self.total_label)
        list_layout.addLayout(select_layout)
        
        self.question_list = QListWidget()
        self.question_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        list_layout.addWidget(self.question_list)
        
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        stats_group = QGroupBox("Statistics")
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("")
        stats_layout.addWidget(self.stats_label)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
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
        self.temp_pdf_path = None
        self.settings = {
            'exam_title': 'Midterm Examination',
            'exam_date': datetime.now().strftime("%B %d, %Y"),
            'exam_instruction': '',
            'page_size': 'A4',
            'layout_style': 'Standard (Single Column)',
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
            'show_answer_lines': True,
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
        self.options_input.setPlaceholderText("Options (one per line)\nExample:\nA) Option 1\nB) Option 2\nC) Option 3")
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
        self.ordering_input.setPlaceholderText("Items to order (one per line)\nStep 1: ...\nStep 2: ...\nStep 3: ...")
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

        preview_title = QLabel("👁️ Live PDF Preview")
        preview_title.setObjectName("title")
        
        # Settings Summary
        self.settings_summary = SettingsSummaryWidget()
        self.settings_summary.edit_btn.clicked.connect(self.open_settings_dialog)
        self.settings_summary.update_summary(self.settings)
        
        # PDF Preview Widget
        self.pdf_preview = PDFPreviewWidget()
        self.pdf_preview.refresh_btn.clicked.connect(self.generate_live_preview)

        btn_pdf = QPushButton("📄 Save Exam PDF (with QR)")
        btn_pdf.clicked.connect(self.export_pdf)

        btn_answer = QPushButton("📝 Save Answer Sheet PDF")
        btn_answer.clicked.connect(self.export_answer_sheet)

        right_layout.addWidget(preview_title)
        right_layout.addWidget(self.settings_summary)
        right_layout.addWidget(self.pdf_preview, 1)
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

    def open_settings_dialog(self):
        """Open settings dialog"""
        dialog = ExamSettingsDialog(self)
        dialog.set_settings(self.settings)
        
        if dialog.exec_() == QDialog.Accepted:
            self.settings = dialog.get_settings()
            self.settings_summary.update_summary(self.settings)
            self.on_content_changed()
            QMessageBox.information(self, "Settings Updated", "Exam settings have been updated successfully.")

    def on_content_changed(self):
        self.preview_timer.start(1500)

    def on_list_reordered(self):
        for idx, q in enumerate(self.questions):
            q["id"] = idx + 1
        self.update_list_display()
        self.on_content_changed()

    def generate_live_preview(self):
        """Generate PDF and show in preview widget"""
        if not self.questions:
            self.pdf_preview.status_label.setText("No questions added yet. Add a question to see preview.")
            self.pdf_preview.preview_label.setText("No questions added.\nAdd questions to see live PDF preview.")
            self.pdf_preview.current_pdf_path = None
            self.pdf_preview.current_page = 0
            self.pdf_preview.total_pages = 0
            self.pdf_preview.update_navigation_buttons()
            return
        
        temp_dir = tempfile.gettempdir()
        self.temp_pdf_path = os.path.join(temp_dir, f"exam_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        
        try:
            self._generate_pdf_to_file(self.temp_pdf_path, is_preview=True)
            self.pdf_preview.load_pdf(self.temp_pdf_path)
            self.pdf_preview.status_label.setText(f"Live preview updated | {len(self.questions)} questions")
        except Exception as e:
            self.pdf_preview.status_label.setText(f"Preview error: {str(e)}")

    def _draw_student_info(self, c, width, height, margin, y):
        """Draw student information section on PDF"""
        if not self.settings.get('include_student_info', True):
            return y
        
        line_height = 18
        box_height = 120
        
        c.setStrokeColor(black)
        c.setLineWidth(1)
        c.rect(margin, y - box_height, width - 2*margin, box_height)
        
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin + 10, y - 15, "STUDENT INFORMATION")
        
        c.setFont("Helvetica", 10)
        current_y = y - 35
        
        name = self.settings.get('student_name', '') or "_________________________"
        student_id = self.settings.get('student_id', '') or "_________________________"
        dept = self.settings.get('department', '') or "_________________________"
        instructor = self.settings.get('instructor', '') or "_________________________"
        student_date = self.settings.get('student_date', '') or datetime.now().strftime("%Y-%m-%d")
        
        c.drawString(margin + 20, current_y, f"Name: {name}")
        current_y -= line_height
        c.drawString(margin + 20, current_y, f"Student ID: {student_id}")
        current_y -= line_height
        c.drawString(margin + 20, current_y, f"Department: {dept}")
        current_y -= line_height
        c.drawString(margin + 20, current_y, f"Instructor: {instructor}")
        current_y -= line_height
        c.drawString(margin + 20, current_y, f"Date: {student_date}")
        
        additional = self.settings.get('additional_info', '')
        if additional:
            current_y -= line_height
            c.drawString(margin + 20, current_y, f"Note: {additional}")
        
        return y - box_height - 20

    def _draw_question_standard(self, c, q, margin, y, width, line_height):
        """Draw question in standard layout"""
        numbering = self.settings.get('numbering_style', '1, 2, 3...')
        if numbering == "1), 2), 3)...":
            q_prefix = f"{q['id']})"
        elif numbering == "(1), (2), (3)...":
            q_prefix = f"({q['id']})"
        elif numbering == "A, B, C...":
            q_prefix = chr(64 + min(q['id'], 26))
        else:
            q_prefix = f"Q{q['id']}"
        
        c.setFont("Helvetica-Bold", self.settings.get('font_size', 11))
        q_text_display = q['text'][:80] + "..." if len(q['text']) > 80 else q['text']
        
        if self.settings.get('show_points', True):
            text_line = f"{q_prefix}. {q_text_display} ({q['score']} pts)"
        else:
            text_line = f"{q_prefix}. {q_text_display}"
        
        c.drawString(margin, y, text_line)
        y -= line_height

        c.setFont("Helvetica", self.settings.get('font_size', 11) - 1)
        
        if q["type"] == 0:
            for i, choice in enumerate(q.get("choices", []), 1):
                choice_display = choice[:60] + "..." if len(choice) > 60 else choice
                c.drawString(margin + 10, y, f"   {i}. {choice_display}")
                y -= line_height - 4
            if self.settings.get('show_answer_lines', True):
                y -= line_height - 4
                c.drawString(margin, y, f"Answer: ______")
            
        elif q["type"] == 1:
            c.drawString(margin, y, "( ) True   ( ) False")
            
        elif q["type"] == 2:
            blank_count = len(q.get("blanks", [])) or 3
            blanks = " ______ " * min(blank_count, 5)
            c.drawString(margin, y, blanks)
            
        elif q["type"] == 3:
            if self.settings.get('show_answer_lines', True):
                c.drawString(margin, y, "Answer: ____________________")
            
        elif q["type"] == 4:
            c.drawString(margin, y, "[Answer Space]")
            for _ in range(self.settings.get('essay_lines', 4)):
                y -= line_height
                c.line(margin, y, width - margin, y)
            
        elif q["type"] == 5:
            c.drawString(margin, y, "Match the following:")
            y -= line_height
            pairs = q.get("matching_pairs", [])[:4]
            for left, right in pairs:
                left_display = left[:30] + "..." if len(left) > 30 else left
                c.drawString(margin + 10, y, f"{left_display}  ↔  ______")
                y -= line_height - 4
                
        elif q["type"] == 6:
            c.drawString(margin, y, "Arrange in correct order: ___ , ___ , ___ , ___")
            
        elif q["type"] == 7:
            c.drawString(margin, y, "Write your code below:")
            y -= line_height * 2
            c.rect(margin, y - 40, width - margin*2, 40)
            
        elif q["type"] == 8:
            c.drawString(margin, y, "Show your work:")
            y -= line_height * 2
            c.line(margin, y, width - margin, y)

        return y

    def _generate_pdf_to_file(self, file_path, is_preview=False):
        exam_title = self.settings.get('exam_title', 'Untitled Exam') or "Untitled Exam"
        exam_date = self.settings.get('exam_date', '') or datetime.now().strftime("%B %d, %Y")
        
        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        margin = self.settings.get('margin', 50) * mm
        line_height = int(self.settings.get('line_spacing', 1.5) * self.settings.get('font_size', 11))
        layout_style = self.settings.get('layout_style', 'Standard (Single Column)')
        font_size = self.settings.get('font_size', 11)
        title_font_size = self.settings.get('title_font_size', 18)
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size
        
        y = height - margin
        
        # Title
        c.setFont("Helvetica-Bold", title_font_size)
        c.drawCentredString(width/2, height - 30, exam_title)
        c.setFont("Helvetica", 10)
        c.drawString(margin, height - 55, f"Date: {exam_date}")
        total_points = sum(q.get('score', 0) for q in self.questions)
        c.drawRightString(width - margin, height - 55, f"Total: {total_points} points")
        
        # Instructions
        instruction = self.settings.get('exam_instruction', '')
        if instruction:
            c.drawString(margin, height - 70, f"Instruction: {instruction[:80]}")
            y = height - 100
        else:
            y = height - 90
        
        # Student info section
        if not is_preview:
            y = self._draw_student_info(c, width, height, margin, y)
            y -= 30
        
        # QR Code
        if not is_preview and self.settings.get('show_qr', True):
            qr_data = json.dumps({
                "exam": exam_title,
                "date": exam_date,
                "questions": len(self.questions),
                "total_score": total_points
            })
            qr_path = generate_qr(qr_data, f"qr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            c.drawImage(qr_path, width - 80, height - 110, width=60, height=60)
            if os.path.exists(qr_path):
                os.remove(qr_path)

        c.line(margin, y, width - margin, y)
        y -= 20
        
        # Questions
        for q in self.questions:
            if y < margin + 100:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", font_size)
            
            y = self._draw_question_standard(c, q, margin, y, width, line_height)
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

            QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
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
            
            QCheckBox {
                spacing: 5px;
            }
        """)

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

        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        margin = self.settings.get('margin', 50) * mm
        line_height = int(self.settings.get('line_spacing', 1.5) * self.settings.get('font_size', 11))
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size

        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(width/2, height - 50, "ANSWER SHEET")
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height - 75, f"{self.settings.get('exam_title', 'Exam')}")

        y = height - 120
        
        # Student info on answer sheet
        if self.settings.get('include_student_info', True):
            c.setFont("Helvetica", 10)
            name = self.settings.get('student_name', '') or "_________________________"
            student_id = self.settings.get('student_id', '') or "_________________________"
            dept = self.settings.get('department', '') or "_________________________"
            instructor = self.settings.get('instructor', '') or "_________________________"
            
            c.drawString(margin, y, f"Name: {name}")
            c.drawString(margin + 250, y, f"Student ID: {student_id}")
            y -= 20
            c.drawString(margin, y, f"Department: {dept}")
            c.drawString(margin + 250, y, f"Instructor: {instructor}")
            y -= 40
        else:
            y -= 20

        c.setFont("Helvetica-Bold", 12)
        c.drawString(margin, y, "Write your answers below.")
        y -= line_height * 2

        c.setFont("Helvetica", 11)
        for q in self.questions:
            if y < margin + 50:
                c.showPage()
                y = height - margin
                c.setFont("Helvetica", 11)

            if q["type"] == 0:
                c.drawString(margin, y, f"Q{q['id']}.   (   )")
            elif q["type"] == 1:
                c.drawString(margin, y, f"Q{q['id']}.   (   )")
            elif q["type"] == 2:
                blank_count = len(q.get("blanks", [])) or 3
                blanks = " ______ " * blank_count
                c.drawString(margin, y, f"Q{q['id']}.   {blanks}")
            elif q["type"] in [3, 7, 8]:
                c.drawString(margin, y, f"Q{q['id']}.   ____________________")
            elif q["type"] == 4:
                c.drawString(margin, y, f"Q{q['id']}.")
                for _ in range(self.settings.get('essay_lines', 4)):
                    y -= line_height
                    c.line(margin, y, width - margin, y)
            elif q["type"] == 5:
                c.drawString(margin, y, f"Q{q['id']}.   1:__  2:__  3:__")
            elif q["type"] == 6:
                c.drawString(margin, y, f"Q{q['id']}.   ___ , ___ , ___ , ___")
            y -= line_height

        c.save()
        QMessageBox.information(self, "Success", f"Answer Sheet PDF has been created.\n{file_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorApp()
    window.show()
    sys.exit(app.exec_())