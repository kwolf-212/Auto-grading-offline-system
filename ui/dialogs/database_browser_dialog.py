# ui/dialogs/database_browser_dialog.py
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from common.constants import QUESTION_TYPES


class DatabaseBrowserDialog(QDialog):
    def __init__(self, db, parent=None):
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