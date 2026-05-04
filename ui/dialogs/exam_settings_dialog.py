# ui/dialogs/exam_settings_dialog.py
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from common.constants import PAGE_SIZES


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