# exam_generator_app.py (설정을 오른쪽으로 이동하고 다이얼로그로 변경)

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
# 페이지 여백 상수 (mm 단위)
MARGIN_TOP_COMPACT = 30      # 상단 여백
MARGIN_BOTTOM_COMPACT = 30   # 하단 여백  
MARGIN_LEFT_COMPACT = 20     # 좌측 여백
MARGIN_RIGHT_COMPACT = 20    # 우측 여백

# Two Column 설정
COLUMN_GAP_COMPACT = 15      # 컬럼 간 간격
PAGE_BOTTOM_MARGIN = 0      # 페이지 하단 여유 공간

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

        # 여백 프리셋 선택 추가
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
    
    def on_margin_preset_changed(self, preset):
        """여백 프리셋 변경 시"""
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


# ---------------- SETTINGS SUMMARY WIDGET (간단한 한 줄 형태) ----------------
class SettingsSummaryWidget(QWidget):
    """간단한 한 줄 설정 요약 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.settings = {}
        
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # 설정 정보 라벨
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
        
        # Edit 버튼 - Preview 도구 모음 버튼과 동일한 스타일 적용
        self.edit_btn = QPushButton("⚙️")
        self.edit_btn.setToolTip("시험 설정 편집")
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
            QPushButton:disabled {
                color: #666;
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


# ---------------- PDF PREVIEW LABEL (사각형 표시 및 휠 이벤트 지원) ----------------
class PDFPreviewLabel(QLabel):
    """PDF 미리보기 라벨 - 실제 PDF 영역을 사각형으로 표시하고 마우스 휠 지원"""
    
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
        
        # PDF 영역 관련 변수
        self.pdf_rect = None  # 실제 PDF가 그려지는 영역 (QRect)
        self.parent_widget = parent
        
        # 마우스 드래그로 스크롤
        self.drag_start_pos = None
        self.drag_start_scroll = None
        
    def set_pdf_rect(self, rect):
        """PDF 영역 사각형 설정"""
        self.pdf_rect = rect
        self.update()  # 다시 그리기
        
    def paintEvent(self, event):
        """페인트 이벤트 - PDF 영역 주변에 사각형 표시"""
        super().paintEvent(event)
        
        if self.pdf_rect and not self.pdf_rect.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 그림자 효과를 위한 반투명 사각형
            shadow_rect = QRect(self.pdf_rect.x() + 2, self.pdf_rect.y() + 2, 
                                self.pdf_rect.width(), self.pdf_rect.height())
            painter.fillRect(shadow_rect, QColor(0, 0, 0, 30))
            
            # PDF 영역 테두리 (파란색, 두꺼운 선)
            pen = QPen(QColor(33, 150, 243), 3)
            painter.setPen(pen)
            painter.drawRect(self.pdf_rect)
            
            # 모서리 둥글게 효과
            pen2 = QPen(QColor(33, 150, 243, 100), 1)
            painter.setPen(pen2)
            painter.drawRect(self.pdf_rect.adjusted(1, 1, -1, -1))
            
            painter.end()
    
    def wheelEvent(self, event):
        """마우스 휠로 페이지 전환"""
        # Ctrl 키와 함께 휠을 돌리면 확대/축소 대신 페이지 전환
        if event.modifiers() & Qt.ControlModifier:
            # Ctrl+휠: 확대/축소는 상위 위젯에 위임
            super().wheelEvent(event)
        else:
            # 일반 휠: 페이지 전환 이벤트 발생
            delta = event.angleDelta().y()
            if delta > 0:
                # 휠 업: 이전 페이지
                self.parent().prev_page() if hasattr(self.parent(), 'prev_page') else None
            else:
                # 휠 다운: 다음 페이지
                self.parent().next_page() if hasattr(self.parent(), 'next_page') else None

# ---------------- PDF PREVIEW WIDGET (미리보기 영역 확장) ---------------- 
class PDFPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pdf_path = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_factor = 1.0
        self.fit_mode = "none"  # none, width, height
        self.original_pixmap = None  # 원본 픽스맵 저장
        self.init_ui()
        self.last_scroll_pos = None
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 상단 툴바
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
        
        # 버튼 공통 스타일 (아이콘 버튼용)
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
        
        # 작은 버튼 스타일 (숫자 버튼용)
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
            QPushButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
        """
        
        # 줌 표시
        # self.zoom_label = QLabel("🔍")
        # self.zoom_label.setStyleSheet("font-size: 16px; color: #ffffff;")
        
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
        
        # 줌 버튼
        self.zoom_out_btn = QPushButton("🔍−")
        self.zoom_out_btn.setToolTip("축소 (Ctrl+Scroll Down)")
        self.zoom_out_btn.setStyleSheet(small_button_style)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        
        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.setToolTip("확대 (Ctrl+Scroll Up)")
        self.zoom_in_btn.setStyleSheet(small_button_style)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        
        self.reset_zoom_btn = QPushButton("↺")
        self.reset_zoom_btn.setToolTip("원래 크기로 (100%)")
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
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
        """)
        self.reset_zoom_btn.clicked.connect(self.reset_zoom)
        
        # 구분선
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        separator1.setFixedSize(2, 30)
        separator1.setStyleSheet("background-color: #555;")
        
        # Fit 버튼 (아이콘으로 변경)
        self.fit_width_btn = QPushButton("⬌")
        self.fit_width_btn.setToolTip("너비에 맞추기 (Ctrl+W)")
        self.fit_width_btn.setStyleSheet(icon_button_style)
        self.fit_width_btn.clicked.connect(self.fit_to_width)
        
        self.fit_height_btn = QPushButton("⬍")
        self.fit_height_btn.setToolTip("높이에 맞추기 (Ctrl+H)")
        self.fit_height_btn.setStyleSheet(icon_button_style)
        self.fit_height_btn.clicked.connect(self.fit_to_height)
        
        self.fit_page_btn = QPushButton("⊞")
        self.fit_page_btn.setToolTip("페이지 전체 맞추기 (Ctrl+F)")
        self.fit_page_btn.setStyleSheet(icon_button_style)
        self.fit_page_btn.clicked.connect(self.fit_to_page)
        
        # 구분선
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setFixedSize(2, 30)
        separator2.setStyleSheet("background-color: #555;")
        
        # 페이지 네비게이션 버튼 (아이콘으로 변경)
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setToolTip("이전 페이지 (←)")
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
            QPushButton:pressed {
                background-color: #2a2a2a;
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
        self.next_btn.setToolTip("다음 페이지 (→)")
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
            QPushButton:pressed {
                background-color: #2a2a2a;
            }
            QPushButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
        """)
        self.next_btn.clicked.connect(self.next_page)
                
        # 새로고침 버튼 (아이콘으로 변경)
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setToolTip("미리보기 새로고침 (Ctrl+R)")
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
            QPushButton:pressed {
                background-color: #004578;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_preview)
        
        # 툴바에 위젯 추가
        # toolbar_layout.addWidget(self.zoom_label)
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
        
        # 미리보기 영역 (스크롤 가능)
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
        
        # 상태 표시줄
        self.status_label = QLabel("준비됨")
        self.status_label.setStyleSheet("color: #cccccc; padding: 5px; font-size: 11px; background-color: #1e1e1e; border-radius: 4px;")
        
        layout.addWidget(toolbar_widget)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        self.update_navigation_buttons()
        
        # 마우스 트래킹 활성화
        self.preview_label.setMouseTracking(True)

    def refresh_preview(self):
        """미리보기 새로고침"""
        if hasattr(self.parent(), 'generate_live_preview'):
            self.parent().generate_live_preview() 
    
    def zoom_in(self):
        """확대"""
        current = int(self.zoom_value.text().rstrip('%'))
        new_value = min(300, current + 10)
        self.zoom_value.setText(f"{new_value}%")
        self.zoom_factor = new_value / 100.0
        self.fit_mode = "none"
        self.update_preview()
        
    def zoom_out(self):
        """축소"""
        current = int(self.zoom_value.text().rstrip('%'))
        new_value = max(30, current - 10)
        self.zoom_value.setText(f"{new_value}%")
        self.zoom_factor = new_value / 100.0
        self.fit_mode = "none"
        self.update_preview()
        
    def reset_zoom(self):
        """줌 리셋 (100%)"""
        self.zoom_value.setText("100%")
        self.zoom_factor = 1.0
        self.fit_mode = "none"
        self.update_preview()
        
    def fit_to_width(self):
        """너비에 맞추기"""
        if not self.original_pixmap:
            return
        self.fit_mode = "width"
        # 스크롤 영역의 가용 너비 계산
        available_width = self.scroll_area.viewport().width() - 20
        if available_width > 0:
            target_width = available_width
            zoom_percent = int((target_width / self.original_pixmap.width()) * 100)
            zoom_percent = min(300, max(30, zoom_percent))
            self.zoom_value.setText(f"{zoom_percent}%")
            self.zoom_factor = zoom_percent / 100.0
            self.update_preview()
            
    def fit_to_height(self):
        """높이에 맞추기"""
        if not self.original_pixmap:
            return
        self.fit_mode = "height"
        # 스크롤 영역의 가용 높이 계산
        available_height = self.scroll_area.viewport().height() - 20
        if available_height > 0:
            target_height = available_height
            zoom_percent = int((target_height / self.original_pixmap.height()) * 100)
            zoom_percent = min(300, max(30, zoom_percent))
            self.zoom_value.setText(f"{zoom_percent}%")
            self.zoom_factor = zoom_percent / 100.0
            self.update_preview()
            
    def fit_to_page(self):
        """페이지 전체에 맞추기"""
        if not self.original_pixmap:
            return
        self.fit_mode = "page"
        # 너비와 높이 모두 고려하여 더 작은 비율 선택
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
        """미리보기 이미지 설정"""
        if pixmap and not pixmap.isNull():
            self.original_pixmap = pixmap
            
            # zoom_factor 사용 (zoom_slider 대신)
            zoom = self.zoom_factor
            
            # 원본 크기 계산
            original_width = pixmap.width()
            original_height = pixmap.height()
            
            # 줌 적용
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
        """마우스 휠 이벤트 - Ctrl 키로 줌, 아니면 스크롤"""
        if event.modifiers() & Qt.ControlModifier:
            # Ctrl + 휠: 줌 인/아웃
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # 일반 휠: 스크롤 영역에 이벤트 전달
            QApplication.sendEvent(self.scroll_area.viewport(), event)
            
    def keyPressEvent(self, event):
        """키보드 단축키"""
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
                page = doc[self.current_page]
                zoom_matrix = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)
                
                img_data = pix.tobytes("png")
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                
                self.set_preview_image(pixmap)
                
                if self.last_scroll_pos is not None:
                    self.scroll_area.verticalScrollBar().setValue(self.last_scroll_pos)
                    self.last_scroll_pos = None
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
        self.current_page = 0
        self.total_pages = 0
        self.update_preview()


class PDFPreviewLabelEnhanced(QLabel):
    """향상된 PDF 미리보기 라벨 - 마우스 드래그 스크롤 지원"""
    
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
        
        # 마우스 드래그로 스크롤
        self.drag_start_pos = None
        self.drag_start_scroll = None
        self.setMouseTracking(True)
        
    def mousePressEvent(self, event):
        """마우스 버튼 클릭 - 드래그 시작 위치 저장"""
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPos()
            # 부모의 스크롤 영역 찾기
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            if scroll_area:
                self.drag_start_scroll = scroll_area.horizontalScrollBar().value(), scroll_area.verticalScrollBar().value()
            self.setCursor(Qt.ClosedHandCursor)
            
    def mouseMoveEvent(self, event):
        """마우스 이동 - 드래그로 스크롤"""
        if event.buttons() & Qt.LeftButton and self.drag_start_pos and self.drag_start_scroll:
            delta = event.globalPos() - self.drag_start_pos
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            if scroll_area:
                scroll_area.horizontalScrollBar().setValue(self.drag_start_scroll[0] - delta.x())
                scroll_area.verticalScrollBar().setValue(self.drag_start_scroll[1] - delta.y())
                
    def mouseReleaseEvent(self, event):
        """마우스 버튼 릴리스"""
        self.drag_start_pos = None
        self.drag_start_scroll = None
        self.setCursor(Qt.ArrowCursor)
        
    def wheelEvent(self, event):
        """마우스 휠 이벤트 - Ctrl 없으면 부모 스크롤 영역으로 전달"""
        if event.modifiers() & Qt.ControlModifier:
            # Ctrl+휠: 줌 이벤트는 상위 위젯으로
            super().wheelEvent(event)
        else:
            # 일반 휠: 스크롤 영역으로 전달
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
    
        # 다이얼로그 자체에 다크 스타일 적용
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
        self.list_widget.setAlternatingRowColors(True)  # 이미 True로 설정되어 있음
        self.list_widget.model().rowsMoved.connect(self.on_list_reordered)

        # list_font = QFont()
        # list_font.setPointSize(12)
        # self.list_widget.setFont(list_font)

        # 버튼 레이아웃 추가 (이 부분이 누락되었습니다!)
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
        center_layout.addLayout(btn_layout_center)  # 이 부분이 중요합니다!
        center_card.setLayout(center_layout)

        # ===== RIGHT: PREVIEW + SETTINGS + ACTION =====
        right_card = QFrame()
        right_card.setObjectName("card")
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)

        # Preview Title (간단하게)
        preview_title = QLabel("👁️ Live PDF Preview")
        preview_title.setObjectName("title")
        right_layout.addWidget(preview_title)

        # Settings Summary (한 줄 + Edit 버튼)
        self.settings_summary = SettingsSummaryWidget(self)
        self.settings_summary.edit_btn.clicked.connect(self.open_settings_dialog)
        self.settings_summary.update_summary(self.settings)
        right_layout.addWidget(self.settings_summary)

        # PDF Preview Widget (확장된 영역) - 키보드 포커스 설정
        self.pdf_preview = PDFPreviewWidget()
        self.pdf_preview.refresh_btn.clicked.connect(self.generate_live_preview)
        self.pdf_preview.setFocusPolicy(Qt.StrongFocus)  # 키보드 이벤트 받기

        # 버튼들을 하단에 배치
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

        button_layout.addWidget(btn_pdf)
        button_layout.addWidget(btn_answer)

        right_layout.addWidget(self.pdf_preview, 1)  # stretch factor를 1로 설정하여 최대한 확장
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
        """Open settings dialog"""
        dialog = ExamSettingsDialog(self)
        dialog.set_settings(self.settings)
        
        if dialog.exec_() == QDialog.Accepted:
            self.settings = dialog.get_settings()
            self.settings_summary.update_summary(self.settings)
            self.on_content_changed()
            QMessageBox.information(self, "Settings Updated", "Exam settings have been updated successfully.")

    def on_content_changed(self):    
        # Reduced delay for faster preview updates
        self.preview_timer.start(800)  # Changed from 1500 to 800ms

    def on_list_reordered(self):
        for idx, q in enumerate(self.questions):
            q["id"] = idx + 1
        self.update_list_display()
        self.on_content_changed()

    def generate_live_preview(self):
        """Generate PDF and show in preview widget"""
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
            # is_preview=False로 변경하여 저장용 PDF와 완전히 동일하게 생성
            self._generate_pdf_to_file(self.temp_pdf_path, is_preview=False)
            # 잠시 대기 후 미리보기 로드
            QTimer.singleShot(200, lambda: self.pdf_preview.load_pdf(self.temp_pdf_path))
            self.pdf_preview.status_label.setText(f"✅ Preview updated | {len(self.questions)} questions")
        except Exception as e:
            self.pdf_preview.status_label.setText(f"❌ Preview error: {str(e)[:50]}")
            import traceback
            traceback.print_exc()

    def _draw_student_info(self, c, width, height, margin_left, margin_right, current_y, available_width):
        """학생 정보 섹션 - 한 줄로 간략하게 배치"""
        if not self.settings.get('include_student_info', True):
            return current_y
        
        line_height = 20
        
        c.setStrokeColor(black)
        c.setLineWidth(0.5)
        c.rect(margin_left, current_y - 35, available_width, 35)
        
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin_left + 8, current_y - 12, "STUDENT INFO")
        
        c.setFont("Helvetica", 9)
        
        # 필드 값 가져오기
        name = self.settings.get('student_name', '') or "_________________________"
        student_id = self.settings.get('student_id', '') or "_________________________"
        dept = self.settings.get('department', '') or "_________________________"
        
        # 한 줄에 모두 배치 (컬럼 간격 균등하게)
        col_width = (available_width - 40) // 3
        
        c.drawString(margin_left + 12, current_y - 28, f"Name: {name}")
        c.drawString(margin_left + 12 + col_width, current_y - 28, f"ID: {student_id}")
        c.drawString(margin_left + 12 + col_width * 2, current_y - 28, f"Dept: {dept}")
        
        return current_y - 45  # 학생정보 박스 높이만큼 이동


    def _wrap_text(self, text, max_width, font_size=11):
        """텍스트를 주어진 너비에 맞게 자동 줄바꿈"""
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        words = text.split()
        lines = []
        current_line = []
        
        # 임시 캔버스로 텍스트 너비 측정
        temp_c = canvas.Canvas(tempfile.mktemp(suffix='.pdf'))
        temp_c.setFont("Helvetica", font_size)
        
        for word in words:
            current_line.append(word)
            test_line = ' '.join(current_line)
            text_width = temp_c.stringWidth(test_line, "Helvetica", font_size)
            
            if text_width > max_width and len(current_line) > 1:
                # 단어가 너무 길면 줄바꿈
                current_line.pop()
                lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        temp_c.save()
        return lines if lines else [text]
        
    def _draw_question_standard(self, c, questions, margin_left, margin_right, width, height,
                            line_height, font_size, available_width, start_y):
        """표준 레이아웃으로 질문 표시 (Two column과 일관성 유지)"""
        current_y = start_y
        page_bottom_margin = 0
        
        for q in questions:
            # 필요 높이 계산
            needed_height = self._estimate_question_height(q, line_height, font_size, available_width)
            
            # 새 페이지 필요 여부 확인
            if current_y - needed_height < page_bottom_margin:
                c.showPage()
                current_y = height - 80
                c.setFont("Helvetica", font_size)
            
            # 질문 그리기
            current_y = self._draw_single_question_standard(
                c, q, margin_left, current_y, line_height, font_size, available_width
            )
            
            # 구분선
            current_y -= line_height
            c.line(margin_left, current_y + 10, width - margin_right, current_y + 10)
            current_y -= 10
        
        return current_y

    def _draw_single_question_standard(self, c, q, x, y, line_height, font_size, available_width):
        """표준 레이아웃에서 단일 질문 그리기"""
        current_y = y
        
        # 번호 스타일 적용
        numbering = self.settings.get('numbering_style', '1, 2, 3...')
        if numbering == "1), 2), 3)...":
            q_prefix = f"{q['id']})"
        elif numbering == "(1), (2), (3)...":
            q_prefix = f"({q['id']})"
        elif numbering == "A, B, C...":
            q_prefix = chr(64 + min(q['id'], 26))
        else:
            q_prefix = f"Q{q['id']}"
        
        # 질문 텍스트 자동 줄바꿈
        points_text = f" ({q['score']} pts)" if self.settings.get('show_points', True) else ""
        full_question_text = f"{q_prefix}. {q['text']}{points_text}"
        
        c.setFont("Helvetica-Bold", font_size)
        question_lines = self._wrap_text(full_question_text, available_width - 20, font_size)
        
        for line in question_lines:
            c.drawString(x, current_y, line)
            current_y -= line_height
        
        current_y -= 5
        c.setFont("Helvetica", font_size - 1)
        
        # 문제 내용 표시
        current_y = self._draw_question_content(c, q, x, current_y, line_height, font_size, available_width)
        
        return current_y

    def _estimate_question_height(self, q, line_height, font_size, available_width):
        """질문의 예상 높이 계산 (페이지 분할용)"""
        total_height = 0
        
        # 질문 텍스트 높이
        question_text = q['text']
        approx_chars_per_line = int(available_width / (font_size * 0.6))
        question_lines = max(1, (len(question_text) // approx_chars_per_line) + 1)
        total_height += question_lines * line_height + 10
        
        # 문제 유형별 추가 높이
        if q["type"] == 0:  # Multiple Choice
            choices_count = len(q.get("choices", []))
            total_height += choices_count * (line_height - 4) + 20
        elif q["type"] == 1:  # True/False
            total_height += line_height
        elif q["type"] == 2:  # Fill in Blank
            total_height += line_height
        elif q["type"] == 3:  # Short Answer
            total_height += line_height
        elif q["type"] == 4:  # Essay
            total_height += self.settings.get('essay_lines', 4) * line_height
        elif q["type"] == 5:  # Matching
            pairs_count = len(q.get("matching_pairs", []))
            total_height += max(3, pairs_count) * (line_height - 4)
        elif q["type"] == 6:  # Ordering
            total_height += line_height
        elif q["type"] == 7:  # Code
            total_height += 60
        elif q["type"] == 8:  # Calculation
            total_height += line_height * 2
        
        return total_height + 30

    def _draw_question_content(self, c, q, margin_left, current_y, line_height, font_size, available_width):
        """문제 유형별 내용 표시 (Answer: ___ 제거)"""
        
        if q["type"] == 0:  # Multiple Choice
            for i, choice in enumerate(q.get("choices", []), 1):
                choice_display = choice[:70] + "..." if len(choice) > 70 else choice
                c.drawString(margin_left + 10, current_y, f"   {chr(96+i)}. {choice_display}")
                current_y -= line_height - 4
            # Answer: ___ 제거
        
        elif q["type"] == 1:  # True/False
            c.drawString(margin_left + 10, current_y, "( ) True   ( ) False")
            # Answer: ___ 제거
        
        elif q["type"] == 2:  # Fill in Blank
            blank_count = len(q.get("blanks", [])) or 3
            blanks = " ______ " * min(blank_count, 5)
            c.drawString(margin_left + 10, current_y, blanks)
        
        elif q["type"] == 3:  # Short Answer
            # Answer: ___ 제거
            c.drawString(margin_left + 10, current_y, "____________________")
        
        elif q["type"] == 4:  # Essay
            c.drawString(margin_left + 10, current_y, "[Write your answer below]")
            for i in range(self.settings.get('essay_lines', 4)):
                current_y -= line_height
                c.line(margin_left + 10, current_y, margin_left + available_width - 20, current_y)
        
        elif q["type"] == 5:  # Matching
            c.drawString(margin_left + 10, current_y, "Match the following:")
            current_y -= line_height
            pairs = q.get("matching_pairs", [])[:5]
            for left, right in pairs:
                left_display = left[:35] + "..." if len(left) > 35 else left
                right_display = right[:20] if right else "______"
                c.drawString(margin_left + 20, current_y, f"{left_display}  ↔  {right_display}")
                current_y -= line_height - 4
        
        elif q["type"] == 6:  # Ordering
            items = q.get("ordering_items", [])
            if items:
                c.drawString(margin_left + 10, current_y, "Arrange in correct order:")
                current_y -= line_height
                for i, item in enumerate(items[:4], 1):
                    item_display = item[:40] + "..." if len(item) > 40 else item
                    c.drawString(margin_left + 20, current_y, f"   {i}. {item_display}")
                    current_y -= line_height - 4
            else:
                c.drawString(margin_left + 10, current_y, "Order: ___ , ___ , ___ , ___")
        
        elif q["type"] == 7:  # Code
            c.drawString(margin_left + 10, current_y, "Write your code below:")
            current_y -= line_height * 2
            code_height = 50
            c.rect(margin_left + 10, current_y - code_height, available_width - 30, code_height)
        
        elif q["type"] == 8:  # Calculation
            formula = q.get('formula', '')
            if formula:
                c.drawString(margin_left + 10, current_y, f"Formula: {formula}")
                current_y -= line_height
            c.drawString(margin_left + 10, current_y, "Show your work:")
            current_y -= line_height * 2
            c.line(margin_left + 10, current_y, margin_left + available_width - 20, current_y)
        
        return current_y

    def _draw_question_two_column_v2(self, c, questions, margin_left, margin_right, width, height,
                                  line_height, font_size, available_width, start_y):
        """
        개선된 Two column layout - 문제 간 간격을 충분히 줌
        """
        col_gap = 15
        col_width = (available_width - col_gap) // 2
        
        left_col_x = margin_left
        right_col_x = margin_left + col_width + col_gap
        
        # 페이지 하단 마진
        page_bottom_margin = 25
        
        current_y = start_y
        q_index = 0
        total_questions = len(questions)
        
        while q_index < total_questions:
            # 새 페이지 시작
            if q_index > 0:
                c.showPage()
                current_y = height - 35
            
            # 왼쪽 컬럼 채우기
            left_y = current_y
            left_q_indices = []
            
            temp_index = q_index
            while temp_index < total_questions:
                q = questions[temp_index]
                # 문제 높이에 추가 간격 10pt 포함
                q_height = self._estimate_question_height_two_col_v2(q, line_height, font_size, col_width) + 15
                
                if left_y - q_height > page_bottom_margin:
                    left_q_indices.append(temp_index)
                    left_y -= q_height
                    temp_index += 1
                else:
                    break
            
            # 오른쪽 컬럼 채우기
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
            
            # 문제 그리기 (왼쪽 컬럼)
            if left_q_indices:
                y_pos = current_y
                for idx in left_q_indices:
                    q = questions[idx]
                    y_pos = self._draw_single_question_two_col_v3(
                        c, q, left_col_x, y_pos, line_height, font_size, col_width, idx + 1
                    )
                    y_pos -= 25  # 문제 간 간격을 25로 증가 (구분선을 위한 공간)
                    # 구분선 그리기 (마지막 문제 제외)
                    if idx != left_q_indices[-1]:
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.setLineWidth(0.5)
                        c.line(left_col_x, y_pos + 12, left_col_x + col_width, y_pos + 12)
                        c.setStrokeColor(black)
            
            # 문제 그리기 (오른쪽 컬럼)
            if right_q_indices:
                y_pos = current_y
                for idx in right_q_indices:
                    q = questions[idx]
                    y_pos = self._draw_single_question_two_col_v3(
                        c, q, right_col_x, y_pos, line_height, font_size, col_width, idx + 1
                    )
                    y_pos -= 25  # 문제 간 간격을 25로 증가
                    # 구분선 그리기 (마지막 문제 제외)
                    if idx != right_q_indices[-1]:
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.setLineWidth(0.5)
                        c.line(right_col_x, y_pos + 12, right_col_x + col_width, y_pos + 12)
                        c.setStrokeColor(black)
            
            # 다음 페이지로 이동할 인덱스 결정
            if right_q_indices:
                q_index = right_q_indices[-1] + 1
            elif left_q_indices:
                q_index = left_q_indices[-1] + 1
            else:
                q_index = temp_index if temp_index > q_index else q_index + 1

    def _estimate_question_height_two_col_v2(self, q, line_height, font_size, col_width):
        """개선된 Two column용 질문 높이 예측 (더 정확하게)"""
        total_height = 20  # 기본 여백
        
        # 질문 텍스트 높이
        question_text = q['text']
        # 한 줄당 평균 문자 수 (폰트 크기 11pt 기준)
        chars_per_line = max(10, int(col_width / (font_size * 0.55)))
        question_lines = max(1, (len(question_text) // chars_per_line) + 1)
        total_height += question_lines * (line_height + 2)
        
        # 문제 유형별 추가 높이
        if q["type"] == 0:  # Multiple Choice
            choices_count = min(len(q.get("choices", [])), 5)
            total_height += choices_count * (line_height - 2) + 10
        elif q["type"] == 1:  # True/False
            total_height += line_height - 2
        elif q["type"] == 2:  # Fill in Blank
            total_height += line_height - 2
        elif q["type"] == 3:  # Short Answer
            total_height += line_height - 2
        elif q["type"] == 4:  # Essay
            essay_lines = min(3, self.settings.get('essay_lines', 4))
            total_height += essay_lines * (line_height - 2) + 5
        elif q["type"] == 5:  # Matching
            pairs_count = min(len(q.get("matching_pairs", [])), 4)
            total_height += max(2, pairs_count) * (line_height - 2) + 10
        elif q["type"] == 6:  # Ordering
            total_height += line_height
        elif q["type"] == 7:  # Code
            total_height += 45
        elif q["type"] == 8:  # Calculation
            total_height += (line_height - 2) * 2 + 10
        
        return total_height

    def _draw_single_question_two_col_v3(self, c, q, x, y, line_height, font_size, col_width, q_num):
        """개선된 Two column용 단일 문제 그리기 (문제 간 간격 충분히 줌)"""
        current_y = y
        
        # 번호 스타일
        numbering = self.settings.get('numbering_style', '1, 2, 3...')
        if numbering == "1), 2), 3)...":
            q_prefix = f"{q_num})"
        elif numbering == "(1), (2), (3)...":
            q_prefix = f"({q_num})"
        elif numbering == "A, B, C...":
            q_prefix = chr(64 + min(q_num, 26))
        else:
            q_prefix = f"{q_num}."
        
        # 점수 표시
        points_text = f" [{q['score']} pts]" if self.settings.get('show_points', True) else ""
        full_text = f"{q_prefix} {q['text']}{points_text}"
        
        c.setFont("Helvetica-Bold", font_size - 1)
        
        # 텍스트 줄바꿈
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
        
        # 문제 내용
        current_y = self._draw_question_content_two_col_v3(c, q, x, current_y, line_height, font_size, col_width)
        
        return current_y

    def _draw_question_content_two_col_v3(self, c, q, x, current_y, line_height, font_size, col_width):
        """문제 내용 표시 (Answer: ___ 제거)"""
        bottom_margin = 8  # 내용 하단 여백 추가
        
        if q["type"] == 0:  # Multiple Choice
            c.setFont("Helvetica", font_size - 2)
            for i, choice in enumerate(q.get("choices", [])[:5], 1):
                choice_display = choice[:35] + "..." if len(choice) > 35 else choice
                c.drawString(x + 8, current_y, f"   {chr(96+i)}. {choice_display}")
                current_y -= line_height - 2
            # Answer: ___ 제거
            current_y -= bottom_margin
        
        elif q["type"] == 1:  # True/False
            c.drawString(x + 8, current_y, "   ( ) True   ( ) False")
            # Answer: ___ 제거
            current_y -= bottom_margin
        
        elif q["type"] == 2:  # Fill in Blank
            blank_count = min(len(q.get("blanks", [])), 4) or 3
            blanks = " ______ " * blank_count
            c.drawString(x + 8, current_y, blanks)
            current_y -= bottom_margin
        
        elif q["type"] == 3:  # Short Answer
            # Answer: ___ 제거 - 빈 줄만 남김
            c.drawString(x + 8, current_y, "   _______________")
            current_y -= bottom_margin
        
        elif q["type"] == 4:  # Essay
            c.drawString(x + 8, current_y, "   [Write your answer below]")
            essay_lines = min(3, self.settings.get('essay_lines', 4))
            for i in range(essay_lines):
                current_y -= line_height
                c.line(x + 8, current_y, x + col_width - 15, current_y)
            current_y -= bottom_margin
        
        elif q["type"] == 5:  # Matching
            c.drawString(x + 8, current_y, "   Match:")
            current_y -= line_height
            pairs = q.get("matching_pairs", [])[:4]
            for left, right in pairs:
                left_display = left[:20] + "..." if len(left) > 20 else left
                c.drawString(x + 14, current_y, f"   {left_display} → _____")
                current_y -= line_height - 2
            current_y -= bottom_margin
        
        elif q["type"] == 6:  # Ordering
            c.drawString(x + 8, current_y, "   Order: ___ , ___ , ___ , ___")
            current_y -= bottom_margin
        
        elif q["type"] == 7:  # Code
            c.drawString(x + 8, current_y, "   Code:")
            current_y -= line_height
            c.rect(x + 8, current_y - 30, col_width - 20, 30)
            current_y -= bottom_margin + 30
        
        elif q["type"] == 8:  # Calculation
            formula = q.get('formula', '')
            if formula:
                formula_display = formula[:25] + "..." if len(formula) > 25 else formula
                c.drawString(x + 8, current_y, f"   Formula: {formula_display}")
                current_y -= line_height
            c.drawString(x + 8, current_y, "   Show your work:")
            current_y -= line_height
            c.line(x + 8, current_y, x + col_width - 15, current_y)
            current_y -= bottom_margin
        
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
        
        # ===== 헤더 영역 =====
        current_y = height - margin_top
        
        # 시험 제목
        c.setFont("Helvetica-Bold", title_font_size)
        c.drawCentredString(width/2, current_y, exam_title)
        current_y -= 22
        
        # 날짜 및 QR 코드, 총점 표시
        c.setFont("Helvetica", 10)
        
        # 날짜 대신 QR 코드를 왼쪽에 표시
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
            
            # 오른쪽에 총점만 표시
            c.drawRightString(width - margin_right, current_y, f"Total: {total_points} pts")
        else:
            c.drawRightString(width - margin_right, current_y, f"Total: {total_points} pts")
        
        current_y -= 18
        
        # 시험지 설명
        instruction = self.settings.get('exam_instruction', '')
        if instruction:
            c.setFont("Helvetica-Oblique", 9)
            instruction_lines = self._wrap_text(instruction, available_width - 20, 9)
            for line in instruction_lines:
                c.drawString(margin_left, current_y, f"※ {line}")
                current_y -= line_height - 4
            current_y -= 8
        
        # 구분선
        c.line(margin_left, current_y, width - margin_right, current_y)
        current_y -= 15
        
        # ===== 학생 정보 영역 제거 (주석 처리 또는 삭제) =====
        # current_y = self._draw_student_info(c, width, height, margin_left, margin_right, 
        #                                     current_y, available_width)
        
        # 학생정보와 문제영역 사이 간격 조정 (제거했으므로 간격 축소)
        current_y -= 15
        
        # ===== 질문 영역 =====
        if layout_style == "Two Column":
            self._draw_question_two_column_v2(c, self.questions, margin_left, margin_right, 
                                            width, height, line_height, font_size, 
                                            available_width, current_y)
        else:
            self._draw_question_standard(c, self.questions, margin_left, margin_right, width, height,
                                        line_height, font_size, available_width, current_y, 40)
        
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
            /* 전체 배경 */
            QWidget {
                background-color: #1e1e1e;
                font-family: 'Segoe UI', 'Malgun Gothic', Arial;
                font-size: 12px;  /* 기본 폰트 크기 */
                color: #e0e0e0;
            }

            /* 카드 스타일 */
            QFrame#card, QWidget#card {
                background: #2d2d2d;
                border-radius: 16px;
                padding: 20px;
                border: 1px solid #3d3d3d;
            }

            /* Title - 가장 크게 (18px) */
            QLabel#title {
                font-size: 18px;
                font-weight: bold;
                color: #007acc;
                margin-bottom: 16px;
                border-bottom: 2px solid #007acc;
                padding-bottom: 8px;
            }
            
            /* 일반 Label - 적당한 크기 (12px) */
            QLabel {
                font-size: 12px;
                color: #e0e0e0;
            }

            /* GroupBox */
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

            /* 버튼 - 약간 크게 (13px) */
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

            /* 데이터베이스 버튼 스타일 */
            QPushButton#db_load {
                background-color: #007acc;
                font-size: 13px;
            }
            QPushButton#db_load:hover {
                background-color: #005a9e;
            }
            
            QPushButton#db_save {
                background-color: #28a745;
                font-size: 13px;
            }
            QPushButton#db_save:hover {
                background-color: #218838;
            }
            
            QPushButton#clear_all {
                background-color: #dc3545;
                font-size: 13px;
            }
            QPushButton#clear_all:hover {
                background-color: #c82333;
            }

            /* 텍스트 입력 필드 */
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
            /* 드롭다운 버튼 (화살표 부분) 스타일 */
            QComboBox::drop-down {
                border: none;
                width: 30px;
                border-left: 1px solid #3d3d3d;
                border-radius: 0 8px 8px 0;
            }

            /* 드롭다운 버튼 내부 화살표 아이콘 */
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
                background-color: #007acc;  /* 파란색 화살표 배경 */
                border-radius: 2px;
            }

            /* ===== 리스트 위젯 - 폰트 크기 강제 적용 ===== */
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
            
            /* QListWidget 내 모든 텍스트에 강제 적용 */
            QListWidget * {
                font-size: 12px;
            }

            /* 체크박스 */
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

            /* 탭 위젯 스타일 */
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

            /* 스크롤바 */
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

            /* 다이얼로그 */
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
            
            /* Tree Widget (Database Browser 등) */
            QTreeWidget {
                font-size: 12px;
            }
            
            QTreeWidget::item {
                font-size: 12px;
            }
            
            /* Table Widget */
            QTableWidget {
                font-size: 12px;
            }
            
            QTableWidget::item {
                font-size: 12px;
            }
            
            /* SpinBox 내부 텍스트 */
            QSpinBox, QDoubleSpinBox {
                font-size: 12px;
            }
            
            /* TextEdit 내부 텍스트 */
            QTextEdit {
                font-size: 12px;
            }
            
            /* LineEdit 내부 텍스트 */
            QLineEdit {
                font-size: 12px;
            }
        """)

        # Database 버튼들에 objectName 설정
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
        # font = QFont()
        # font.setPointSize(12)  # 적당한 크기 (12pt)
        
        for idx, q in enumerate(self.questions):
            qinfo = QUESTION_TYPES.get(q["type"], {})
            icon = qinfo.get("icon", "❓")
            
            # 텍스트를 더 읽기 쉽게 구성
            q_text_preview = q['text'][:60]
            if len(q['text']) > 60:
                q_text_preview += "..."
                
            option_info = ""
            if q.get("choices") and len(q.get("choices", [])) > 0:
                option_info = f" [{len(q['choices'])} options]"
                
            display_text = f"{icon} Q{q['id']}. {q_text_preview}{option_info} ({q['score']} pts) - {q.get('difficulty', 'Medium')}"
            
            item = QListWidgetItem(display_text)
            # 폰트 직접 설정 (스타일시트보다 우선 적용됨)
            # item.setFont(font)
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