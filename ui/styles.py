# ui/styles.py

MAIN_STYLE = """
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

QGroupBox {
    font-weight: bold;
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 10px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #007acc;
}

QPushButton {
    background-color: #0d7377;
    color: white;
    border-radius: 8px;
    padding: 10px 16px;
    font-weight: bold;
    border: none;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #14a085;
}

QTextEdit, QLineEdit, QComboBox, QSpinBox {
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    padding: 8px;
    background: #252526;
    color: #e0e0e0;
}

QListWidget {
    border: 1px solid #3d3d3d;
    border-radius: 8px;
    background-color: #252526;
}

QListWidget::item {
    padding: 10px;
    border-bottom: 1px solid #3d3d3d;
}

QListWidget::item:selected {
    background-color: #0d7377;
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
"""