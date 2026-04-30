# exam_generator_app.py (Updated with new question formats)

import sys
import json
import qrcode
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon, QPainter, QPen
from PyQt5.QtCore import Qt, QTimer, QRect, QPoint, QSize
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

# ---------------- CONSTANTS ----------------
MARGIN_TOP_COMPACT = 30
MARGIN_BOTTOM_COMPACT = 30  
MARGIN_LEFT_COMPACT = 20
MARGIN_RIGHT_COMPACT = 20
COLUMN_GAP_COMPACT = 15
PAGE_BOTTOM_MARGIN = 0

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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📐 Exam Settings")
        self.setGeometry(300, 300, 600, 500)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
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

        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Margin Preset:"))
        self.margin_preset = QComboBox()
        self.margin_preset.addItems(["Compact", "Normal", "Wide", "Print Optimized"])
        self.margin_preset.setCurrentText("Print Optimized")
        self.margin_preset.currentTextChanged.connect(self.on_margin_preset_changed)
        preset_layout.addWidget(self.margin_preset)
        preset_layout.addStretch()
        page_layout.addRow("", preset_layout)

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
        
        self.numbering_style = QComboBox()
        self.numbering_style.addItems(["1, 2, 3...", "1), 2), 3)...", "(1), (2), (3)...", "A, B, C..."])
        advanced_layout.addRow("Numbering Style:", self.numbering_style)
        
        tab_widget.addTab(advanced_tab, "⚙️ Advanced")
        
        layout.addWidget(tab_widget)
        
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
    
    def on_margin_preset_changed(self, preset):
        if preset == "Compact":
            self.margin_spin.setValue(30)
        elif preset == "Normal":
            self.margin_spin.setValue(45)
        elif preset == "Wide":
            self.margin_spin.setValue(60)
        elif preset == "Print Optimized":
            self.margin_spin.setValue(40)
                        
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
        
        idx = self.numbering_style.findText(settings.get('numbering_style', '1, 2, 3...'))
        if idx >= 0:
            self.numbering_style.setCurrentIndex(idx)


# ---------------- SETTINGS SUMMARY WIDGET ----------------
class SettingsSummaryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.settings = {}
        
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        self.settings_label = QLabel()
        self.settings_label.setStyleSheet("""
            QLabel {
                background-color: #252526;
                color: #e0e0e0;
                padding: 10px 14px;
                border-radius: 8px;
                font-size: 12px;
                border: 1px solid #3d3d3d;
            }
        """)
        
        self.edit_btn = QPushButton("⚙️")
        self.edit_btn.setToolTip("Edit Exam Settings")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 44px;
                max-width: 44px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        
        layout.addWidget(self.settings_label, 1)
        layout.addWidget(self.edit_btn)
        
        self.setLayout(layout)
        
    def update_summary(self, settings):
        self.settings = settings
        exam_title = settings.get('exam_title', 'Untitled') or 'Untitled'
        exam_date = settings.get('exam_date', '') or datetime.now().strftime('%Y-%m-%d')
        page_size = settings.get('page_size', 'A4')
        layout_style = settings.get('layout_style', 'Standard')
        
        summary_text = f"📋 {exam_title}  |  📅 {exam_date}  |  📄 {page_size}  |  📐 {layout_style}"
        self.settings_label.setText(summary_text)


# ---------------- PDF PREVIEW LABEL ----------------
class PDFPreviewLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: none;
            }
        """)
        self.setMinimumHeight(550)
        self.setScaledContents(False)
        self.pdf_rect = None
        self.parent_widget = parent
        self.drag_start_pos = None
        self.drag_start_scroll = None
        
    def set_pdf_rect(self, rect):
        self.pdf_rect = rect
        self.update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pdf_rect and not self.pdf_rect.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            shadow_rect = QRect(self.pdf_rect.x() + 2, self.pdf_rect.y() + 2, 
                                self.pdf_rect.width(), self.pdf_rect.height())
            painter.fillRect(shadow_rect, QColor(0, 0, 0, 30))
            pen = QPen(QColor(33, 150, 243), 3)
            painter.setPen(pen)
            painter.drawRect(self.pdf_rect)
            pen2 = QPen(QColor(33, 150, 243, 100), 1)
            painter.setPen(pen2)
            painter.drawRect(self.pdf_rect.adjusted(1, 1, -1, -1))
            painter.end()
    
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            super().wheelEvent(event)
        else:
            delta = event.angleDelta().y()
            if delta > 0:
                self.parent().prev_page() if hasattr(self.parent(), 'prev_page') else None
            else:
                self.parent().next_page() if hasattr(self.parent(), 'next_page') else None


# ---------------- PDF PREVIEW WIDGET ----------------
class PDFPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pdf_path = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_factor = 1.0
        self.fit_mode = "none"
        self.original_pixmap = None
        self.saved_page = 0  # 페이지 저장을 위한 변수 추가
        self.init_ui()
        self.last_scroll_pos = None
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        toolbar_widget = QWidget()
        toolbar_widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
                margin: 2px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(8)
        
        icon_button_style = """
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 44px;
                max-width: 44px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
        """
        
        small_button_style = """
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 40px;
                max-width: 40px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """
        
        self.zoom_value = QLabel("100%")
        self.zoom_value.setFixedWidth(55)
        self.zoom_value.setAlignment(Qt.AlignCenter)
        self.zoom_value.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #555;
            border-radius: 6px;
            padding: 5px;
        """)
        
        self.zoom_out_btn = QPushButton("🔍−")
        self.zoom_out_btn.setToolTip("Zoom Out (Ctrl+Scroll Down)")
        self.zoom_out_btn.setStyleSheet(small_button_style)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        
        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.setToolTip("Zoom In (Ctrl+Scroll Up)")
        self.zoom_in_btn.setStyleSheet(small_button_style)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        
        self.reset_zoom_btn = QPushButton("↺")
        self.reset_zoom_btn.setToolTip("Reset to 100%")
        self.reset_zoom_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 44px;
                max-width: 44px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
        """)
        self.reset_zoom_btn.clicked.connect(self.reset_zoom)
        
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        separator1.setFixedSize(2, 30)
        separator1.setStyleSheet("background-color: #555;")
        
        self.fit_width_btn = QPushButton("⬌")
        self.fit_width_btn.setToolTip("Fit to Width")
        self.fit_width_btn.setStyleSheet(icon_button_style)
        self.fit_width_btn.clicked.connect(self.fit_to_width)
        
        self.fit_height_btn = QPushButton("⬍")
        self.fit_height_btn.setToolTip("Fit to Height")
        self.fit_height_btn.setStyleSheet(icon_button_style)
        self.fit_height_btn.clicked.connect(self.fit_to_height)
        
        self.fit_page_btn = QPushButton("⊞")
        self.fit_page_btn.setToolTip("Fit to Page")
        self.fit_page_btn.setStyleSheet(icon_button_style)
        self.fit_page_btn.clicked.connect(self.fit_to_page)
        
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setFixedSize(2, 30)
        separator2.setStyleSheet("background-color: #555;")
        
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setToolTip("Previous Page (←)")
        self.prev_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 50px;
                max-width: 50px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
            QPushButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
        """)
        self.prev_btn.clicked.connect(self.prev_page)
        
        self.page_label = QLabel("1 / 1")
        self.page_label.setFixedWidth(70)
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #555;
            border-radius: 6px;
            padding: 5px;
        """)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setToolTip("Next Page (→)")
        self.next_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 50px;
                max-width: 50px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
            QPushButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
        """)
        self.next_btn.clicked.connect(self.next_page)
                
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setToolTip("Refresh Preview")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #007acc;
                border: 1px solid #005a9e;
                border-radius: 6px;
                padding: 4px;
                min-width: 44px;
                max-width: 44px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_preview)
        
        toolbar_layout.addWidget(self.zoom_out_btn)
        toolbar_layout.addWidget(self.zoom_value)
        toolbar_layout.addWidget(self.zoom_in_btn)
        toolbar_layout.addWidget(self.reset_zoom_btn)
        toolbar_layout.addWidget(separator1)
        toolbar_layout.addWidget(self.fit_width_btn)
        toolbar_layout.addWidget(self.fit_height_btn)
        toolbar_layout.addWidget(self.fit_page_btn)
        toolbar_layout.addWidget(separator2)
        toolbar_layout.addWidget(self.prev_btn)
        toolbar_layout.addWidget(self.page_label)
        toolbar_layout.addWidget(self.next_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.refresh_btn)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
        """)
        
        self.preview_label = PDFPreviewLabelEnhanced(self)
        self.preview_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
        """)
        self.scroll_area.setWidget(self.preview_label)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #cccccc; padding: 5px; font-size: 11px; background-color: #1e1e1e; border-radius: 4px;")
        
        layout.addWidget(toolbar_widget)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        self.update_navigation_buttons()
        self.preview_label.setMouseTracking(True)

    def refresh_preview(self):
        if hasattr(self.parent(), 'generate_live_preview'):
            self.parent().generate_live_preview() 
    
    def zoom_in(self):
        current = int(self.zoom_value.text().rstrip('%'))
        new_value = min(300, current + 10)
        self.zoom_value.setText(f"{new_value}%")
        self.zoom_factor = new_value / 100.0
        self.fit_mode = "none"
        self.update_preview()
        
    def zoom_out(self):
        current = int(self.zoom_value.text().rstrip('%'))
        new_value = max(30, current - 10)
        self.zoom_value.setText(f"{new_value}%")
        self.zoom_factor = new_value / 100.0
        self.fit_mode = "none"
        self.update_preview()
        
    def reset_zoom(self):
        self.zoom_value.setText("100%")
        self.zoom_factor = 1.0
        self.fit_mode = "none"
        self.update_preview()
        
    def fit_to_width(self):
        if not self.original_pixmap:
            return
        self.fit_mode = "width"
        available_width = self.scroll_area.viewport().width() - 20
        if available_width > 0:
            target_width = available_width
            zoom_percent = int((target_width / self.original_pixmap.width()) * 100)
            zoom_percent = min(300, max(30, zoom_percent))
            self.zoom_value.setText(f"{zoom_percent}%")
            self.zoom_factor = zoom_percent / 100.0
            self.update_preview()
            
    def fit_to_height(self):
        if not self.original_pixmap:
            return
        self.fit_mode = "height"
        available_height = self.scroll_area.viewport().height() - 20
        if available_height > 0:
            target_height = available_height
            zoom_percent = int((target_height / self.original_pixmap.height()) * 100)
            zoom_percent = min(300, max(30, zoom_percent))
            self.zoom_value.setText(f"{zoom_percent}%")
            self.zoom_factor = zoom_percent / 100.0
            self.update_preview()
            
    def fit_to_page(self):
        if not self.original_pixmap:
            return
        self.fit_mode = "page"
        available_width = self.scroll_area.viewport().width() - 20
        available_height = self.scroll_area.viewport().height() - 20
        
        if available_width > 0 and available_height > 0:
            width_ratio = available_width / self.original_pixmap.width()
            height_ratio = available_height / self.original_pixmap.height()
            zoom_ratio = min(width_ratio, height_ratio)
            zoom_percent = int(zoom_ratio * 100)
            zoom_percent = min(300, max(30, zoom_percent))
            self.zoom_value.setText(f"{zoom_percent}%")
            self.zoom_factor = zoom_percent / 100.0
            self.update_preview()
            
    def set_preview_image(self, pixmap):
        if pixmap and not pixmap.isNull():
            self.original_pixmap = pixmap
            zoom = self.zoom_factor
            original_width = pixmap.width()
            original_height = pixmap.height()
            
            scaled_pixmap = pixmap.scaled(
                int(original_width * zoom),
                int(original_height * zoom),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            self.preview_label.setPixmap(scaled_pixmap)
            self.preview_label.setFixedSize(scaled_pixmap.size())
            
            zoom_percent = int(zoom * 100)
            self.status_label.setText(f"✅ Page {self.current_page + 1} | Zoom: {zoom_percent}% | Size: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
        else:
            self.original_pixmap = None
            self.preview_label.setText("📄 No preview available\n\nClick 'Refresh' to generate PDF preview")
            self.preview_label.setFixedSize(400, 300)
            self.status_label.setText("No preview available")
                    
    def update_navigation_buttons(self):
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
        self.page_label.setText(f"{self.current_page + 1} / {max(1, self.total_pages)}")
        
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_preview()
            
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_preview()
            
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            QApplication.sendEvent(self.scroll_area.viewport(), event)
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.prev_page()
        elif event.key() == Qt.Key_Right:
            self.next_page()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key_Home:
            self.current_page = 0
            self.update_preview()
        elif event.key() == Qt.Key_End:
            self.current_page = self.total_pages - 1
            self.update_preview()
        elif event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_W:
                self.fit_to_width()
            elif event.key() == Qt.Key_H:
                self.fit_to_height()
            elif event.key() == Qt.Key_F:
                self.fit_to_page()
            elif event.key() == Qt.Key_R:
                self.refresh_btn.click()
        else:
            super().keyPressEvent(event)
            
    def update_preview(self):
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            self.preview_label.setText("📄 No PDF generated yet.\n\nAdd questions and click 'Refresh' to see preview.")
            self.status_label.setText("No PDF file available")
            self.current_page = 0
            self.total_pages = 0
            self.update_navigation_buttons()
            return
            
        if not PYMUPDF_AVAILABLE:
            file_size = os.path.getsize(self.current_pdf_path) / 1024
            self.preview_label.setText(
                f"📄 PDF File: {os.path.basename(self.current_pdf_path)}\n"
                f"📊 Size: {file_size:.1f} KB\n"
                f"📑 Pages: {self.total_pages}\n\n"
                f"⚠️ Install PyMuPDF for actual preview:\n"
                f"💻 pip install PyMuPDF"
            )
            self.status_label.setText("PyMuPDF not installed")
            return
            
        try:
            doc = fitz.open(self.current_pdf_path)
            self.total_pages = len(doc)
            
            if self.current_page >= self.total_pages:
                self.current_page = 0
                
            self.update_navigation_buttons()
            
            if self.total_pages > 0:
                # 현재 페이지의 스크롤 위치 저장 (선택사항)
                current_scroll = self.scroll_area.verticalScrollBar().value()

                page = doc[self.current_page]
                zoom_matrix = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)
                
                img_data = pix.tobytes("png")
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                
                self.set_preview_image(pixmap)
                
                # 스크롤 위치 복원 (선택사항)
                if current_scroll > 0:
                    QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(current_scroll))
            else:
                self.preview_label.setText("PDF has no pages")
                
            doc.close()
            
        except Exception as e:
            self.status_label.setText(f"Preview error: {str(e)}")
            self.preview_label.setText(f"Failed to render PDF preview.\n\nError: {str(e)}")
            self.current_page = 0
            self.total_pages = 0
            self.update_navigation_buttons()
            
    def load_pdf(self, pdf_path):
        self.current_pdf_path = pdf_path
        # 저장된 페이지가 있으면 그 페이지로 이동, 없으면 0
        self.current_page = self.saved_page if hasattr(self, 'saved_page') else 0
        self.total_pages = 0
        self.update_preview()

    def save_current_page(self):
        """현재 페이지 번호를 저장"""
        self.saved_page = self.current_page
    
    def refresh_preview(self):
        """미리보기 새로고침 시 현재 페이지 유지"""
        self.save_current_page()  # 현재 페이지 저장
        if hasattr(self.parent(), 'generate_live_preview'):
            self.parent().generate_live_preview()


class PDFPreviewLabelEnhanced(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        self.setMinimumSize(100, 100)
        self.drag_start_pos = None
        self.drag_start_scroll = None
        self.setMouseTracking(True)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPos()
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            if scroll_area:
                self.drag_start_scroll = scroll_area.horizontalScrollBar().value(), scroll_area.verticalScrollBar().value()
            self.setCursor(Qt.ClosedHandCursor)
            
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_start_pos and self.drag_start_scroll:
            delta = event.globalPos() - self.drag_start_pos
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            if scroll_area:
                scroll_area.horizontalScrollBar().setValue(self.drag_start_scroll[0] - delta.x())
                scroll_area.verticalScrollBar().setValue(self.drag_start_scroll[1] - delta.y())
                
    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        self.drag_start_scroll = None
        self.setCursor(Qt.ArrowCursor)
        
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            super().wheelEvent(event)
        else:
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            if scroll_area:
                QApplication.sendEvent(scroll_area.viewport(), event)


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
    
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
            }
            QLabel {
                color: #e0e0e0;
            }
            QGroupBox {
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 10px;
            }
            QGroupBox::title {
                color: #007acc;
            }
            QListWidget {
                background-color: #252526;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
            QListWidget::item:selected {
                background-color: #0d7377;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)
        
        title = QLabel("📚 Question Database")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #007acc; margin-bottom: 10px;")
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
            self._generate_pdf_to_file(self.temp_pdf_path, is_preview=False)
            # 저장된 페이지가 있으면 해당 페이지로 이동하도록 load_pdf에서 처리됨
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

    def _wrap_text(self, text, max_width, font_size=11):
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        words = text.split()
        lines = []
        current_line = []
        
        temp_c = canvas.Canvas(tempfile.mktemp(suffix='.pdf'))
        temp_c.setFont("Helvetica", font_size)
        
        for word in words:
            current_line.append(word)
            test_line = ' '.join(current_line)
            text_width = temp_c.stringWidth(test_line, "Helvetica", font_size)
            
            if text_width > max_width and len(current_line) > 1:
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        temp_c.save()
        return lines if lines else [text]
        
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
        question_lines = self._wrap_text(full_question_text, available_width - 20, font_size)
        
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
        
        text_lines = self._wrap_text(full_text, col_width - 10, font_size - 1)
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
            instruction_lines = self._wrap_text(instruction, available_width - 20, 9)
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
        """Export answer sheet with proper answer spaces for each question type - Two Column Layout"""
        if not self.questions:
            QMessageBox.warning(self, "Notice", "Please add questions first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Answer Sheet PDF", "", "PDF (*.pdf)")
        if not file_path:
            return

        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        margin = 35  # 여백
        col_gap = 20  # 두 컬럼 간 간격
        col_width = (page_size[0] - (margin * 2) - col_gap) // 2
        
        base_font_size = 12  # 기본 폰트 크기 12pt
        line_height = int(self.settings.get('line_spacing', 1.5) * base_font_size)
        small_line_height = line_height - 3
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size

        # 타이틀
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 35, "ANSWER SHEET")
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height - 55, f"{self.settings.get('exam_title', 'Exam')}")

        y = height - 85
        
        # Student info - 중앙에 한 줄로
        if self.settings.get('include_student_info', True):
            c.setFont("Helvetica", 10)
            name = self.settings.get('student_name', '') or "_________________________"
            student_id = self.settings.get('student_id', '') or "_________________________"
            dept = self.settings.get('department', '') or "_________________________"
            
            total_width = width - (margin * 2)
            col_width_student = total_width // 3
            
            x1 = margin
            x2 = margin + col_width_student
            x3 = margin + (col_width_student * 2)
            
            c.drawString(x1, y, f"Name: {name}")
            c.drawString(x2, y, f"ID: {student_id}")
            c.drawString(x3, y, f"Dept: {dept}")
            
            y -= 25
        else:
            y -= 15

        y -= 15

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Write your answers below:")
        y -= line_height

        c.setFont("Helvetica", base_font_size)
        
        # Two Column 배치 - 왼쪽 컬럼에 가능한 한 많이 배치
        left_x = margin
        right_x = margin + col_width + col_gap
        
        # 각 질문의 필요 높이 계산
        question_heights = []
        for q in self.questions:
            height_needed = self._calculate_answer_sheet_height(q, col_width, line_height, small_line_height)
            question_heights.append(height_needed)
        
        # 왼쪽 컬럼에 배치할 질문 결정
        left_indices = []
        right_indices = []
        current_height = 0
        page_height = height - margin - 100  # 페이지 하단 여백 고려
        
        for idx, q_height in enumerate(question_heights):
            if current_height + q_height <= page_height:
                left_indices.append(idx)
                current_height += q_height + small_line_height  # 문제 간 간격 추가
            else:
                # 왼쪽 컬럼이 가득 차면 오른쪽 컬럼에 배치
                right_indices.append(idx)
        
        # 나머지 질문들을 오른쪽 컬럼에 순차적으로 배치 (여러 페이지에 걸쳐)
        all_pages = []
        current_page_indices = []
        current_page_height = 0
        
        for idx in right_indices:
            q_height = question_heights[idx]
            if current_page_height + q_height <= page_height:
                current_page_indices.append(idx)
                current_page_height += q_height + small_line_height
            else:
                if current_page_indices:
                    all_pages.append(current_page_indices)
                current_page_indices = [idx]
                current_page_height = q_height + small_line_height
        
        if current_page_indices:
            all_pages.append(current_page_indices)
        
        # 첫 페이지: 왼쪽 컬럼 그리기
        current_y_left = y
        for idx in left_indices:
            q = self.questions[idx]
            if current_y_left < margin + 50:
                # 새 페이지가 필요하면 다음 페이지로 넘김
                c.showPage()
                current_y_left = height - margin
                c.setFont("Helvetica", base_font_size)
            
            current_y_left = self._draw_answer_sheet_question(
                c, q, left_x, current_y_left, col_width, line_height, small_line_height, width, margin, base_font_size
            )
            current_y_left -= small_line_height
        
        # 오른쪽 컬럼: 여러 페이지에 걸쳐 그리기
        for page_idx, page_indices in enumerate(all_pages):
            if page_idx > 0:
                c.showPage()
            
            current_y_right = y
            for idx in page_indices:
                q = self.questions[idx]
                if current_y_right < margin + 50:
                    c.showPage()
                    current_y_right = height - margin
                    c.setFont("Helvetica", base_font_size)
                
                current_y_right = self._draw_answer_sheet_question(
                    c, q, right_x, current_y_right, col_width, line_height, small_line_height, width, margin, base_font_size
                )
                current_y_right -= small_line_height

        c.save()
        QMessageBox.information(self, "Success", f"Answer Sheet PDF has been created.\n{file_path}")

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
            instruction_lines = self._wrap_text(instruction, available_width - 20, 9)
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorApp()
    window.show()
    sys.exit(app.exec_())