# ui/widgets/settings_summary_widget.py
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt


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