# ui/grader_styles.py

GRADER_STYLE = """
/* Global Background */
QWidget {
    background-color: #1e1e1e;
    font-family: 'Segoe UI', 'Malgun Gothic', Arial;
    font-size: 12px;
    color: #e0e0e0;
}

QMainWindow {
    background-color: #1e1e1e;
}

/* Card Style (GroupBox) */
QGroupBox {
    font-weight: bold;
    font-size: 12px;
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    color: #e0e0e0;
    background-color: #2d2d2d;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px 0 5px;
    color: #007acc;
}

/* Button Style */
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

QPushButton#grade_btn {
    background-color: #007acc;
}
QPushButton#grade_btn:hover {
    background-color: #005a9e;
}

QPushButton#nav_btn {
    background-color: #3c3c3c;
    font-size: 16px;
    padding: 8px;
    min-width: 60px;
}
QPushButton#nav_btn:hover {
    background-color: #4a4a4a;
}

/* Input Fields */
QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    padding: 8px;
    background: #252526;
    color: #e0e0e0;
    font-size: 12px;
    min-height: 20px;
}

QLineEdit:focus, QTextEdit:focus {
    border: 2px solid #007acc;
}

/* Table Widget */
QTableWidget {
    background-color: #252526;
    alternate-background-color: #2d2d2d;
    gridline-color: #3d3d3d;
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    color: #e0e0e0;
    font-size: 12px;
}

QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #3d3d3d;
}

QTableWidget::item:selected {
    background-color: #0d7377;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #2d2d2d;
    color: #007acc;
    padding: 8px;
    font-size: 12px;
    font-weight: bold;
    border: none;
    border-bottom: 2px solid #007acc;
}

/* Scrollbar */
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

/* Status Bar */
QStatusBar {
    background-color: #1e1e1e;
    color: #007acc;
    font-size: 11px;
    border-top: 1px solid #3d3d3d;
}

/* Label */
QLabel {
    font-size: 12px;
    color: #e0e0e0;
}

QLabel#title {
    font-size: 18px;
    font-weight: bold;
    color: #007acc;
    margin-bottom: 10px;
    border-bottom: 2px solid #007acc;
    padding-bottom: 8px;
}

QLabel#image_label {
    background-color: #252526;
    border: 2px dashed #3d3d3d;
    border-radius: 8px;
    color: #888;
    font-size: 14px;
}

/* Message Box */
QMessageBox {
    background-color: #2d2d2d;
    color: #e0e0e0;
}

QMessageBox QPushButton {
    min-width: 80px;
}

/* File Dialog */
QFileDialog {
    background-color: #2d2d2d;
    color: #e0e0e0;
}

QFileDialog QListView, QFileDialog QTreeView {
    background-color: #252526;
    color: #e0e0e0;
}

QFileDialog QComboBox {
    background-color: #252526;
}
"""