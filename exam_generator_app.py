# exam_generator_app.py (설정을 오른쪽으로 이동하고 다이얼로그로 변경)

import sys
import json
import qrcode
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QIcon, QPainter, QPen
from PyQt5.QtCore import Qt, QTimer, QRect, QPoint
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

        self.margin_preset = QComboBox()
        self.margin_preset.addItems(["Normal", "Compact", "Wide", "Print Optimized"])
        self.margin_preset.setCurrentText("Print Optimized")
        self.margin_preset.currentTextChanged.connect(self.on_margin_preset_changed)
        page_layout.addRow("Margin Preset:", self.margin_preset)

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
        if preset == "Normal":
            self.margin_spin.setValue(50)
        elif preset == "Compact":
            self.margin_spin.setValue(35)
        elif preset == "Wide":
            self.margin_spin.setValue(65)
        elif preset == "Print Optimized":
            self.margin_spin.setValue(45)
            
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
                background-color: #f0f2f5;
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 12px;
            }
        """)
        
        # Edit 버튼
        self.edit_btn = QPushButton("✏️ Edit Settings")
        self.edit_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                border-radius: 8px;
                padding: 6px 12px;
                font-weight: bold;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        self.edit_btn.setCursor(Qt.PointingHandCursor)
        self.edit_btn.setFixedWidth(100)
        
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
        self.zoom_factor = 1.0  # 줌 팩터 추가
        self.init_ui()
        # 스크롤 영역의 위치 저장 변수 추가
        self.last_scroll_pos = None
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # 상단 툴바 (더 컴팩트하게)
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        
        self.zoom_label = QLabel("Zoom:")
        self.zoom_label.setStyleSheet("font-size: 11px;")
        
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(30, 200)
        self.zoom_slider.setValue(85)
        self.zoom_slider.setTickPosition(QSlider.TicksBelow)
        self.zoom_slider.setTickInterval(25)
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self.on_zoom_changed)
        
        self.zoom_value = QLabel("85%")
        self.zoom_value.setFixedWidth(40)
        self.zoom_value.setStyleSheet("font-size: 11px;")
        
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setFixedSize(30, 28)
        self.prev_btn.setToolTip("Previous Page")
        self.prev_btn.clicked.connect(self.prev_page)
        
        self.page_label = QLabel("1 / 1")
        self.page_label.setMinimumWidth(60)
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("font-size: 11px; font-weight: bold;")
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setFixedSize(30, 28)
        self.next_btn.setToolTip("Next Page")
        self.next_btn.clicked.connect(self.next_page)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(28, 28)
        self.refresh_btn.setToolTip("Refresh Preview")
        self.refresh_btn.setStyleSheet("font-size: 14px;")
        
        toolbar.addWidget(self.zoom_label)
        toolbar.addWidget(self.zoom_slider)
        toolbar.addWidget(self.zoom_value)
        toolbar.addStretch()
        toolbar.addWidget(self.prev_btn)
        toolbar.addWidget(self.page_label)
        toolbar.addWidget(self.next_btn)
        toolbar.addWidget(self.refresh_btn)
        
        # 미리보기 영역 (확장됨)
        self.preview_label = PDFPreviewLabel(self)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        self.preview_label.setMinimumHeight(550)  # 높이 증가
        self.preview_label.setScaledContents(False)
        
        # 스크롤 영역
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.preview_label)
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignCenter)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
        """)
        
        # 상태 표시줄
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; padding: 4px; font-size: 10px;")
        
        layout.addLayout(toolbar)
        layout.addWidget(scroll_area, 1)  # 1 = stretch factor
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        self.update_navigation_buttons()
        
    def on_zoom_changed(self, value):
        self.zoom_value.setText(f"{value}%")
        self.update_preview()
        
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
            
    def set_preview_image(self, pixmap):
        if pixmap and not pixmap.isNull():
            zoom = self.zoom_slider.value() / 100.0
            
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
            
            # PDF 영역 사각형 계산 및 설정 (추가된 부분)
            # 라벨 내에서 이미지가 실제로 위치하는 영역 계산
            label_size = self.preview_label.size()
            pixmap_size = scaled_pixmap.size()
            
            x = (label_size.width() - pixmap_size.width()) // 2
            y = (label_size.height() - pixmap_size.height()) // 2
            
            pdf_rect = QRect(x, y, pixmap_size.width(), pixmap_size.height())
            self.preview_label.set_pdf_rect(pdf_rect)  # ← 사각형 설정
            
            self.preview_label.setPixmap(scaled_pixmap)
            self.status_label.setText(f"✅ Page {self.current_page + 1} | Zoom: {self.zoom_slider.value()}%")
        else:
            self.preview_label.set_pdf_rect(QRect())  # 사각형 초기화
            self.preview_label.setText("📄 No preview available\n\nClick 'Refresh' to generate PDF preview")
            self.status_label.setText("No preview available")
            
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
                
                # 스크롤 위치 복원 (추가된 부분)
                if self.last_scroll_pos is not None:
                    scroll_area = self.parent().findChild(QScrollArea)
                    if scroll_area:
                        scroll_area.verticalScrollBar().setValue(self.last_scroll_pos)
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
        right_layout.setSpacing(10)

        # Preview Title (간단하게)
        preview_title = QLabel("👁️ Live PDF Preview")
        preview_title.setObjectName("title")
        preview_title.setStyleSheet("""
            QLabel#title {
                font-size: 16px;
                font-weight: bold;
                color: #1a73e8;
                margin-bottom: 0px;
                border-bottom: none;
                padding-bottom: 0px;
            }
        """)
        right_layout.addWidget(preview_title)

        # Settings Summary (한 줄 + Edit 버튼)
        self.settings_summary = SettingsSummaryWidget(self)
        self.settings_summary.edit_btn.clicked.connect(self.open_settings_dialog)
        self.settings_summary.update_summary(self.settings)
        right_layout.addWidget(self.settings_summary)

        # PDF Preview Widget (확장된 영역)
        self.pdf_preview = PDFPreviewWidget()
        self.pdf_preview.refresh_btn.clicked.connect(self.generate_live_preview)

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
            self._generate_pdf_to_file(self.temp_pdf_path, is_preview=True)
            # 잠시 대기 후 미리보기 로드 (파일 쓰기 완료 보장)
            QTimer.singleShot(200, lambda: self.pdf_preview.load_pdf(self.temp_pdf_path))
            self.pdf_preview.status_label.setText(f"✅ Preview updated | {len(self.questions)} questions")
        except Exception as e:
            self.pdf_preview.status_label.setText(f"❌ Preview error: {str(e)[:50]}")
            import traceback
            traceback.print_exc()

    def _draw_student_info(self, c, width, height, margin_left, margin_right, current_y, available_width):
        """Draw student information section on PDF"""
        if not self.settings.get('include_student_info', True):
            return current_y
        
        line_height = 18
        box_height = 130
        
        c.setStrokeColor(black)
        c.setLineWidth(1)
        c.rect(margin_left, current_y - box_height, available_width, box_height)
        
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin_left + 10, current_y - 15, "STUDENT INFORMATION")
        
        c.setFont("Helvetica", 10)
        info_y = current_y - 35
        
        name = self.settings.get('student_name', '') or "_________________________"
        student_id = self.settings.get('student_id', '') or "_________________________"
        dept = self.settings.get('department', '') or "_________________________"
        instructor = self.settings.get('instructor', '') or "_________________________"
        student_date = self.settings.get('student_date', '') or datetime.now().strftime("%Y-%m-%d")
        
        # 좌우 2열로 배치
        col_width = (available_width - 30) // 2
        
        c.drawString(margin_left + 15, info_y, f"Name: {name}")
        c.drawString(margin_left + 15 + col_width, info_y, f"Student ID: {student_id}")
        info_y -= line_height
        
        c.drawString(margin_left + 15, info_y, f"Department: {dept}")
        c.drawString(margin_left + 15 + col_width, info_y, f"Instructor: {instructor}")
        info_y -= line_height
        
        c.drawString(margin_left + 15, info_y, f"Date: {student_date}")
        
        additional = self.settings.get('additional_info', '')
        if additional:
            info_y -= line_height
            c.drawString(margin_left + 15, info_y, f"Note: {additional[:50]}")
        
        return current_y - box_height - 15

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
        page_bottom_margin = 70
        
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
        """문제 유형별 내용 표시"""
        
        if q["type"] == 0:  # Multiple Choice
            for i, choice in enumerate(q.get("choices", []), 1):
                choice_display = choice[:70] + "..." if len(choice) > 70 else choice
                c.drawString(margin_left + 10, current_y, f"   {chr(96+i)}. {choice_display}")
                current_y -= line_height - 4
            if self.settings.get('show_answer_lines', True):
                current_y -= line_height - 4
                c.drawString(margin_left, current_y, f"Answer: ______")
        
        elif q["type"] == 1:  # True/False
            c.drawString(margin_left + 10, current_y, "( ) True   ( ) False")
            if self.settings.get('show_answer_lines', True):
                current_y -= line_height - 4
                c.drawString(margin_left, current_y, f"Answer: ______")
        
        elif q["type"] == 2:  # Fill in Blank
            blank_count = len(q.get("blanks", [])) or 3
            blanks = " ______ " * min(blank_count, 5)
            c.drawString(margin_left + 10, current_y, blanks)
        
        elif q["type"] == 3:  # Short Answer
            if self.settings.get('show_answer_lines', True):
                c.drawString(margin_left + 10, current_y, "Answer: ____________________")
        
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

    def _draw_question_two_column(self, c, questions, margin_left, margin_right, width, height,
                                line_height, font_size, available_width, start_y):
        """Two column layout으로 질문 표시 (자동 줄바꿈 및 페이지 분할 적용)"""
        
        col_gap = 20  # 두 컬럼 사이 간격
        col_width = (available_width - col_gap) // 2
        
        left_col_x = margin_left
        right_col_x = margin_left + col_width + col_gap
        
        # 각 컬럼의 현재 Y 위치
        left_y = start_y
        right_y = start_y
        
        page_bottom_margin = 70
        
        # 질문을 왼쪽/오른쪽 컬럼에 번갈아 배치
        for i, q in enumerate(questions):
            # 현재 컬럼 결정
            if i % 2 == 0:
                current_x = left_col_x
                current_y = left_y
                is_left = True
            else:
                current_x = right_col_x
                current_y = right_y
                is_left = False
            
            # 질문 높이 예측
            needed_height = self._estimate_question_height_two_col(q, line_height, font_size, col_width)
            
            # 현재 컬럼에 공간이 충분한지 확인
            if current_y - needed_height < page_bottom_margin:
                # 공간 부족 - 새 페이지 생성
                c.showPage()
                # 새 페이지에서 컬럼 위치 초기화
                left_y = height - 80
                right_y = height - 80
                
                if is_left:
                    current_y = left_y
                    left_y = current_y
                else:
                    current_y = right_y
                    right_y = current_y
                
                # 폰트 재설정
                c.setFont("Helvetica", font_size)
            
            # 질문 그리기
            new_y = self._draw_single_question_two_col(
                c, q, current_x, current_y, line_height, font_size, col_width, i+1
            )
            
            # 해당 컬럼의 Y 위치 업데이트
            if is_left:
                left_y = new_y - 15  # 질문 간 간격
            else:
                right_y = new_y - 15
        
        return min(left_y, right_y) if questions else start_y

    def _estimate_question_height_two_col(self, q, line_height, font_size, col_width):
        """Two column용 질문 높이 예측"""
        total_height = 0
        
        # 질문 텍스트 높이 (컬럼 너비에 맞게)
        question_text = q['text']
        approx_chars_per_line = max(10, int(col_width / (font_size * 0.6)))
        question_lines = max(1, (len(question_text) // approx_chars_per_line) + 1)
        total_height += question_lines * line_height + 10
        
        # 문제 유형별 추가 높이 (컬럼에 맞게 축소)
        if q["type"] == 0:  # Multiple Choice
            choices_count = min(len(q.get("choices", [])), 4)  # 컬럼에서는 최대 4개
            total_height += choices_count * (line_height - 4) + 15
        elif q["type"] == 1:  # True/False
            total_height += line_height
        elif q["type"] == 2:  # Fill in Blank
            total_height += line_height
        elif q["type"] == 3:  # Short Answer
            total_height += line_height
        elif q["type"] == 4:  # Essay
            essay_lines = min(3, self.settings.get('essay_lines', 4))  # 컬럼에서는 최대 3줄
            total_height += essay_lines * line_height
        elif q["type"] == 5:  # Matching
            pairs_count = min(len(q.get("matching_pairs", [])), 3)
            total_height += max(2, pairs_count) * (line_height - 4)
        elif q["type"] in [6, 7, 8]:
            total_height += line_height * 2
        
        return total_height + 25

    def _draw_single_question_two_col(self, c, q, x, y, line_height, font_size, col_width, q_num):
        """Two column에서 단일 질문 그리기"""
        current_y = y
        
        # 번호 스타일 적용
        numbering = self.settings.get('numbering_style', '1, 2, 3...')
        if numbering == "1), 2), 3)...":
            q_prefix = f"{q_num})"
        elif numbering == "(1), (2), (3)...":
            q_prefix = f"({q_num})"
        elif numbering == "A, B, C...":
            q_prefix = chr(64 + min(q_num, 26))
        else:
            q_prefix = f"Q{q_num}"
        
        # 질문 텍스트 자동 줄바꿈 (컬럼 너비에 맞게)
        points_text = f" ({q['score']} pts)" if self.settings.get('show_points', True) else ""
        full_question_text = f"{q_prefix}. {q['text']}{points_text}"
        
        c.setFont("Helvetica-Bold", font_size - 1)  # 컬럼에서는 폰트 약간 작게
        
        # 텍스트 줄바꿈
        question_lines = self._wrap_text(full_question_text, col_width - 10, font_size - 1)
        for line in question_lines:
            # 텍스트가 너무 길면 자르기
            if len(line) > 60:
                line = line[:57] + "..."
            c.drawString(x, current_y, line)
            current_y -= line_height
        
        current_y -= 5
        c.setFont("Helvetica", font_size - 2)
        
        # 문제 유형별 내용 표시 (컬럼 버전)
        current_y = self._draw_question_content_two_col(c, q, x, current_y, line_height, font_size, col_width)
        
        return current_y

    def _draw_question_content_two_col(self, c, q, x, current_y, line_height, font_size, col_width):
        """Two column용 문제 내용 표시"""
        
        if q["type"] == 0:  # Multiple Choice
            for i, choice in enumerate(q.get("choices", [])[:4], 1):  # 최대 4개만 표시
                choice_display = choice[:35] + "..." if len(choice) > 35 else choice
                c.drawString(x + 5, current_y, f"   {chr(96+i)}. {choice_display}")
                current_y -= line_height - 4
            if self.settings.get('show_answer_lines', True):
                current_y -= line_height - 4
                c.drawString(x, current_y, f"Ans: ___")
        
        elif q["type"] == 1:  # True/False
            c.drawString(x + 5, current_y, "T/F")
            if self.settings.get('show_answer_lines', True):
                current_y -= line_height - 4
                c.drawString(x, current_y, "Ans: ___")
        
        elif q["type"] == 2:  # Fill in Blank
            c.drawString(x + 5, current_y, "______")
        
        elif q["type"] == 3:  # Short Answer
            if self.settings.get('show_answer_lines', True):
                c.drawString(x + 5, current_y, "Ans: _________")
        
        elif q["type"] == 4:  # Essay
            c.drawString(x + 5, current_y, "[Answer]")
            essay_lines = min(3, self.settings.get('essay_lines', 4))
            for i in range(essay_lines):
                current_y -= line_height
                c.line(x + 5, current_y, x + col_width - 15, current_y)
        
        elif q["type"] == 5:  # Matching
            c.drawString(x + 5, current_y, "Match:")
            current_y -= line_height
            pairs = q.get("matching_pairs", [])[:3]
            for left, right in pairs:
                left_display = left[:20] + "..." if len(left) > 20 else left
                c.drawString(x + 10, current_y, f"{left_display} ↔ ___")
                current_y -= line_height - 4
        
        elif q["type"] == 6:  # Ordering
            c.drawString(x + 5, current_y, "Order: ___ , ___ , ___")
        
        elif q["type"] == 7:  # Code
            c.drawString(x + 5, current_y, "Code:")
            current_y -= line_height
            c.rect(x + 5, current_y - 30, col_width - 20, 30)
        
        elif q["type"] == 8:  # Calculation
            c.drawString(x + 5, current_y, "Work:")
            current_y -= line_height
            c.line(x + 5, current_y, x + col_width - 15, current_y)
        
        return current_y

    def _generate_pdf_to_file(self, file_path, is_preview=False):
        exam_title = self.settings.get('exam_title', 'Untitled Exam') or "Untitled Exam"
        exam_date = self.settings.get('exam_date', '') or datetime.now().strftime("%B %d, %Y")
        
        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        margin_mm = self.settings.get('margin', 50)
        
        # 여백 조정: 상단(margin_mm), 하단(margin_mm + 20), 좌우(margin_mm - 10)
        margin = margin_mm * mm
        margin_top = margin  # 상단 여백
        margin_bottom = (margin_mm + 25) * mm  # 하단 여백 증가 (인쇄 여유분)
        margin_left = (margin_mm - 10) * mm  # 좌측 여백 감소
        margin_right = (margin_mm - 10) * mm  # 우측 여백 감소
        
        line_height = int(self.settings.get('line_spacing', 1.5) * self.settings.get('font_size', 11))
        layout_style = self.settings.get('layout_style', 'Standard (Single Column)')
        font_size = self.settings.get('font_size', 11)
        title_font_size = self.settings.get('title_font_size', 18)
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size
        
        # 사용 가능한 영역 계산
        available_width = width - margin_left - margin_right
        available_height = height - margin_top - margin_bottom
        
        # Header section
        c.setFont("Helvetica-Bold", title_font_size)
        c.drawCentredString(width/2, height - margin_top + 15, exam_title)
        c.setFont("Helvetica", 10)
        c.drawString(margin_left, height - margin_top - 5, f"Date: {exam_date}")
        total_points = sum(q.get('score', 0) for q in self.questions)
        c.drawRightString(width - margin_right, height - margin_top - 5, f"Total: {total_points} points")
        
        # Instructions
        instruction = self.settings.get('exam_instruction', '')
        current_y = height - margin_top - 35
        
        if instruction:
            # 자동 줄바꿈 적용
            instruction_lines = self._wrap_text(instruction, available_width - 30, 10)
            c.setFont("Helvetica-Oblique", 9)
            for line in instruction_lines:
                c.drawString(margin_left, current_y, f"📌 {line}")
                current_y -= line_height - 4
            current_y -= 10
        
        # Student info section
        if not is_preview:
            current_y = self._draw_student_info(c, width, height, margin_left, margin_right, current_y, available_width)
            current_y -= 25
        
        # QR Code
        if not is_preview and self.settings.get('show_qr', True):
            qr_data = json.dumps({
                "exam": exam_title,
                "date": exam_date,
                "questions": len(self.questions),
                "total_score": total_points
            })
            qr_path = generate_qr(qr_data, f"qr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            c.drawImage(qr_path, width - 70, height - margin_top - 60, width=50, height=50)
            if os.path.exists(qr_path):
                os.remove(qr_path)
        
        # 구분선
        c.line(margin_left, current_y, width - margin_right, current_y)
        current_y -= 25
        
        # 질문 표시
        if layout_style == "Two Column":
            self._draw_question_two_column(c, self.questions, margin_left, margin_right, width, height, 
                                            line_height, font_size, available_width, current_y)
        else:
            self._draw_question_standard(c, self.questions, margin_left, margin_right, width, height,
                                        line_height, font_size, available_width, current_y)
        
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