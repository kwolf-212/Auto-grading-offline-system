#!/usr/bin/env python3
# question_creator.py
# Standalone Question Creator Application

import sys
import json
import os
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont

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

class Question:
    def __init__(self, qid=0, qtype=0, text="", score=5, choices=None, answer="",
                 blanks=None, matching_pairs=None, ordering_items=None,
                 code_template="", formula=""):
        self.id = qid
        self.type = qtype
        self.type_name = QUESTION_TYPES[qtype]["name"]
        self.type_icon = QUESTION_TYPES[qtype]["icon"]
        self.text = text
        self.score = score
        self.choices = choices or []
        self.answer = answer
        self.blanks = blanks or []
        self.matching_pairs = matching_pairs or []
        self.ordering_items = ordering_items or []
        self.code_template = code_template
        self.formula = formula
    
    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type,
            "type_name": self.type_name,
            "type_icon": self.type_icon,
            "text": self.text,
            "score": self.score,
            "choices": self.choices,
            "answer": self.answer,
            "blanks": self.blanks,
            "matching_pairs": self.matching_pairs,
            "ordering_items": self.ordering_items,
            "code_template": self.code_template,
            "formula": self.formula
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            qid=data.get("id", 0),
            qtype=data.get("type", 0),
            text=data.get("text", ""),
            score=data.get("score", 5),
            choices=data.get("choices", []),
            answer=data.get("answer", ""),
            blanks=data.get("blanks", []),
            matching_pairs=data.get("matching_pairs", []),
            ordering_items=data.get("ordering_items", []),
            code_template=data.get("code_template", ""),
            formula=data.get("formula", "")
        )

# ---------------- EXAMPLE QUESTIONS ----------------
def get_example_questions():
    return [
        Question(qtype=0, text="What is the capital of France?", 
                 choices=["London", "Berlin", "Paris", "Madrid"], answer="Paris", score=5),
        Question(qtype=1, text="The Earth is flat.", answer="False", score=3),
        Question(qtype=2, text="The _______ is the largest ocean on Earth.", 
                 blanks=["Pacific Ocean"], answer="Pacific Ocean", score=4),
        Question(qtype=3, text="What is the chemical symbol for Gold?", answer="Au", score=5),
        Question(qtype=4, text="Explain the theory of evolution.", 
                 answer="Charles Darwin's theory...", score=10),
        Question(qtype=5, text="Match the capitals:", 
                 matching_pairs=[("France", "Paris"), ("Germany", "Berlin"), ("Italy", "Rome")],
                 answer="1-A,2-B,3-C", score=6),
        Question(qtype=6, text="Arrange the planets from the Sun:", 
                 ordering_items=["Mercury", "Venus", "Earth", "Mars"], 
                 answer="Mercury, Venus, Earth, Mars", score=6),
    ]

# ---------------- MAIN QUESTION CREATOR APP ----------------
class QuestionCreatorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Question Creator - Standalone")
        self.setGeometry(100, 100, 1200, 800)
        self.questions = []
        self.init_ui()
        self.on_type_changed(0)

    def init_ui(self):
        container = QWidget()
        main_layout = QHBoxLayout()

        # ===== LEFT PANEL: QUESTION INPUT =====
        left_panel = QFrame()
        left_panel.setObjectName("card")
        left_layout = QVBoxLayout()

        # Header
        header = QLabel("✏️ Create New Question")
        header.setObjectName("title")

        # Question Type
        type_group = QGroupBox("Question Type")
        type_layout = QVBoxLayout()
        self.type_combo = QComboBox()
        for qid, qinfo in QUESTION_TYPES.items():
            self.type_combo.addItem(f"{qinfo['icon']} {qinfo['name']}")
        self.type_combo.currentIndexChanged.connect(self.on_type_changed)
        type_layout.addWidget(self.type_combo)
        type_group.setLayout(type_layout)

        # Question Text
        self.question_text = QTextEdit()
        self.question_text.setPlaceholderText("Enter your question here...")
        self.question_text.setMinimumHeight(100)

        # Dynamic fields container
        self.dynamic_container = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_container)

        # Options field (for MC)
        self.options_input = QTextEdit()
        self.options_input.setPlaceholderText("Options (one per line)\nA) Option 1\nB) Option 2\nC) Option 3")
        self.options_input.setMaximumHeight(100)

        # Blanks field
        self.blanks_input = QLineEdit()
        self.blanks_input.setPlaceholderText("Blank answers (comma separated)")

        # Matching fields
        self.matching_left = QTextEdit()
        self.matching_left.setPlaceholderText("Left column (one per line)")
        self.matching_left.setMaximumHeight(80)
        self.matching_right = QTextEdit()
        self.matching_right.setPlaceholderText("Right column (one per line)")
        self.matching_right.setMaximumHeight(80)

        # Ordering field
        self.ordering_input = QTextEdit()
        self.ordering_input.setPlaceholderText("Items to order (one per line)")
        self.ordering_input.setMaximumHeight(100)

        # Code field
        self.code_input = QTextEdit()
        self.code_input.setPlaceholderText("Code template or expected output")
        self.code_input.setMaximumHeight(100)

        # Formula field
        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("Formula or equation")

        # Answer
        self.answer_input = QTextEdit()
        self.answer_input.setPlaceholderText("Answer key")
        self.answer_input.setMaximumHeight(80)

        # Score
        score_layout = QHBoxLayout()
        score_layout.addWidget(QLabel("Points:"))
        self.score_spin = QSpinBox()
        self.score_spin.setRange(1, 100)
        self.score_spin.setValue(5)
        score_layout.addWidget(self.score_spin)

        # Buttons
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("➕ Add Question")
        self.add_btn.clicked.connect(self.add_question)
        self.clear_btn = QPushButton("🗑 Clear Form")
        self.clear_btn.clicked.connect(self.clear_form)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.clear_btn)

        # Assemble left panel
        left_layout.addWidget(header)
        left_layout.addWidget(type_group)
        left_layout.addWidget(QLabel("Question:"))
        left_layout.addWidget(self.question_text)
        left_layout.addWidget(self.dynamic_container)
        left_layout.addWidget(QLabel("Answer:"))
        left_layout.addWidget(self.answer_input)
        left_layout.addLayout(score_layout)
        left_layout.addLayout(btn_layout)
        left_layout.addStretch()
        left_panel.setLayout(left_layout)

        # ===== CENTER PANEL: QUESTION LIST =====
        center_panel = QFrame()
        center_panel.setObjectName("card")
        center_layout = QVBoxLayout()

        list_header = QLabel("📋 Question Bank")
        list_header.setObjectName("title")

        self.question_list = QListWidget()
        self.question_list.setAlternatingRowColors(True)
        self.question_list.itemClicked.connect(self.on_question_selected)

        list_btn_layout = QHBoxLayout()
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.clicked.connect(self.delete_question)
        self.duplicate_btn = QPushButton("📋 Duplicate Selected")
        self.duplicate_btn.clicked.connect(self.duplicate_question)
        list_btn_layout.addWidget(self.delete_btn)
        list_btn_layout.addWidget(self.duplicate_btn)

        center_layout.addWidget(list_header)
        center_layout.addWidget(self.question_list)
        center_layout.addLayout(list_btn_layout)
        center_panel.setLayout(center_layout)

        # ===== RIGHT PANEL: PREVIEW & EXPORT =====
        right_panel = QFrame()
        right_panel.setObjectName("card")
        right_layout = QVBoxLayout()

        preview_header = QLabel("👁️ Preview")
        preview_header.setObjectName("title")

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)

        self.preview_btn = QPushButton("Refresh Preview")
        self.preview_btn.clicked.connect(self.refresh_preview)

        export_group = QGroupBox("Export")
        export_layout = QVBoxLayout()
        self.export_json_btn = QPushButton("💾 Export to JSON")
        self.export_json_btn.clicked.connect(self.export_json)
        self.import_json_btn = QPushButton("📂 Import from JSON")
        self.import_json_btn.clicked.connect(self.import_json)
        export_layout.addWidget(self.export_json_btn)
        export_layout.addWidget(self.import_json_btn)
        export_group.setLayout(export_layout)

        example_group = QGroupBox("Examples")
        example_layout = QVBoxLayout()
        self.load_example_btn = QPushButton("📚 Load Example Questions")
        self.load_example_btn.clicked.connect(self.load_examples)
        self.clear_all_btn = QPushButton("🗑 Clear All Questions")
        self.clear_all_btn.clicked.connect(self.clear_all)
        example_layout.addWidget(self.load_example_btn)
        example_layout.addWidget(self.clear_all_btn)
        example_group.setLayout(example_layout)

        right_layout.addWidget(preview_header)
        right_layout.addWidget(self.preview_text)
        right_layout.addWidget(self.preview_btn)
        right_layout.addWidget(export_group)
        right_layout.addWidget(example_group)
        right_layout.addStretch()
        right_panel.setLayout(right_layout)

        # Add panels to main layout
        main_layout.addWidget(left_panel, 2)
        main_layout.addWidget(center_panel, 2)
        main_layout.addWidget(right_panel, 2)

        container.setLayout(main_layout)
        self.setCentralWidget(container)
        self.apply_styles()

    def on_type_changed(self, index):
        # Clear dynamic layout
        for i in reversed(range(self.dynamic_layout.count())):
            widget = self.dynamic_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        qtype = index

        if qtype == 0:  # Multiple Choice
            label = QLabel("Options (one per line):")
            self.dynamic_layout.addWidget(label)
            self.dynamic_layout.addWidget(self.options_input)
            self.options_input.show()
            self.answer_input.setPlaceholderText("Answer (e.g., A, B, C, D or option text)")

        elif qtype == 2:  # Fill in Blank
            label = QLabel("Blank answers (comma separated):")
            self.dynamic_layout.addWidget(label)
            self.dynamic_layout.addWidget(self.blanks_input)
            self.blanks_input.show()
            self.answer_input.setPlaceholderText("Answer key for blanks")

        elif qtype == 5:  # Matching
            label = QLabel("Matching Pairs:")
            self.dynamic_layout.addWidget(label)
            left_label = QLabel("Left column:")
            self.dynamic_layout.addWidget(left_label)
            self.dynamic_layout.addWidget(self.matching_left)
            right_label = QLabel("Right column:")
            self.dynamic_layout.addWidget(right_label)
            self.dynamic_layout.addWidget(self.matching_right)
            self.matching_left.show()
            self.matching_right.show()
            self.answer_input.setPlaceholderText("Matching pairs (e.g., 1-A,2-B,3-C)")

        elif qtype == 6:  # Ordering
            label = QLabel("Items to order (correct order):")
            self.dynamic_layout.addWidget(label)
            self.dynamic_layout.addWidget(self.ordering_input)
            self.ordering_input.show()
            self.answer_input.setPlaceholderText("Correct order (e.g., 3,1,4,2)")

        elif qtype == 7:  # Code
            label = QLabel("Code template / expected output:")
            self.dynamic_layout.addWidget(label)
            self.dynamic_layout.addWidget(self.code_input)
            self.code_input.show()
            self.answer_input.setPlaceholderText("Expected output or solution")

        elif qtype == 8:  # Calculation
            label = QLabel("Formula / equation:")
            self.dynamic_layout.addWidget(label)
            self.dynamic_layout.addWidget(self.formula_input)
            self.formula_input.show()
            self.answer_input.setPlaceholderText("Answer with steps")

        else:
            self.answer_input.setPlaceholderText("Answer key")

    def clear_form(self):
        self.question_text.clear()
        self.options_input.clear()
        self.blanks_input.clear()
        self.matching_left.clear()
        self.matching_right.clear()
        self.ordering_input.clear()
        self.code_input.clear()
        self.formula_input.clear()
        self.answer_input.clear()
        self.score_spin.setValue(5)

    def add_question(self):
        qtext = self.question_text.toPlainText().strip()
        if not qtext:
            QMessageBox.warning(self, "Warning", "Please enter question text.")
            return

        qtype = self.type_combo.currentIndex()
        score = self.score_spin.value()
        answer = self.answer_input.toPlainText().strip()

        # Parse type-specific fields
        choices = []
        blanks = []
        matching_pairs = []
        ordering_items = []
        code_template = ""
        formula = ""

        if qtype == 0:  # MC
            raw_choices = self.options_input.toPlainText().strip()
            if raw_choices:
                choices = [c.strip() for c in raw_choices.split('\n') if c.strip()]
            if len(choices) < 2:
                QMessageBox.warning(self, "Warning", "Multiple choice needs at least 2 options.")
                return

        elif qtype == 2:  # Fill blank
            raw_blanks = self.blanks_input.text().strip()
            if raw_blanks:
                blanks = [b.strip() for b in raw_blanks.split(',')]

        elif qtype == 5:  # Matching
            left_raw = self.matching_left.toPlainText().strip()
            right_raw = self.matching_right.toPlainText().strip()
            left_items = [l.strip() for l in left_raw.split('\n') if l.strip()]
            right_items = [r.strip() for r in right_raw.split('\n') if r.strip()]
            matching_pairs = list(zip(left_items, right_items))

        elif qtype == 6:  # Ordering
            order_raw = self.ordering_input.toPlainText().strip()
            if order_raw:
                ordering_items = [o.strip() for o in order_raw.split('\n') if o.strip()]

        elif qtype == 7:  # Code
            code_template = self.code_input.toPlainText().strip()

        elif qtype == 8:  # Calculation
            formula = self.formula_input.text().strip()

        qid = len(self.questions) + 1
        q = Question(
            qid=qid, qtype=qtype, text=qtext, score=score,
            choices=choices, answer=answer, blanks=blanks,
            matching_pairs=matching_pairs, ordering_items=ordering_items,
            code_template=code_template, formula=formula
        )
        self.questions.append(q)
        self.update_list_display()
        self.clear_form()
        self.refresh_preview()
        QMessageBox.information(self, "Success", f"Question {qid} added.")

    def update_list_display(self):
        self.question_list.clear()
        for q in self.questions:
            display = f"{q.type_icon} Q{q.id}. {q.text[:50]} ({q.score} pts)"
            if q.choices:
                display += f" [{len(q.choices)} opts]"
            self.question_list.addItem(display)

    def on_question_selected(self, item):
        row = self.question_list.currentRow()
        if 0 <= row < len(self.questions):
            q = self.questions[row]
            self.type_combo.setCurrentIndex(q.type)
            self.question_text.setText(q.text)
            self.score_spin.setValue(q.score)
            self.answer_input.setText(q.answer)
            
            if q.type == 0:
                self.options_input.setText("\n".join(q.choices))
            elif q.type == 2:
                self.blanks_input.setText(", ".join(q.blanks))
            elif q.type == 5:
                left = [p[0] for p in q.matching_pairs]
                right = [p[1] for p in q.matching_pairs]
                self.matching_left.setText("\n".join(left))
                self.matching_right.setText("\n".join(right))
            elif q.type == 6:
                self.ordering_input.setText("\n".join(q.ordering_items))
            elif q.type == 7:
                self.code_input.setText(q.code_template)
            elif q.type == 8:
                self.formula_input.setText(q.formula)

    def delete_question(self):
        row = self.question_list.currentRow()
        if row >= 0:
            del self.questions[row]
            for i, q in enumerate(self.questions):
                q.id = i + 1
            self.update_list_display()
            self.refresh_preview()
            QMessageBox.information(self, "Success", "Question deleted.")
        else:
            QMessageBox.warning(self, "Warning", "Select a question to delete.")

    def duplicate_question(self):
        row = self.question_list.currentRow()
        if row >= 0:
            import copy
            new_q = copy.deepcopy(self.questions[row])
            new_q.id = len(self.questions) + 1
            self.questions.append(new_q)
            self.update_list_display()
            self.refresh_preview()
            QMessageBox.information(self, "Success", "Question duplicated.")

    def clear_all(self):
        if self.questions:
            reply = QMessageBox.question(self, "Clear All", 
                f"Delete all {len(self.questions)} questions?", 
                QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.questions.clear()
                self.update_list_display()
                self.refresh_preview()

    def refresh_preview(self):
        if not self.questions:
            self.preview_text.setText("No questions yet. Add some questions to see preview.")
            return

        text = "=" * 60 + "\n"
        text += "QUESTION BANK PREVIEW\n"
        text += "=" * 60 + "\n\n"

        for q in self.questions:
            text += f"[{q.type_icon}] Q{q.id}. {q.text} ({q.score} pts)\n"
            
            if q.type == 0:  # MC
                for i, opt in enumerate(q.choices, 1):
                    text += f"   {i}. {opt}\n"
                text += f"   Answer: {q.answer}\n"
            elif q.type == 1:  # T/F
                text += f"   Answer: {q.answer}\n"
            elif q.type == 2:  # Fill blank
                blanks_str = " ______ " * (len(q.blanks) or 3)
                text += f"   {blanks_str}\n"
            elif q.type == 3:  # Short answer
                text += f"   Answer: ____________________\n"
            elif q.type == 4:  # Essay
                text += f"   [Answer Space]\n   ~~~~~~~~~~~~~~~~~~~~\n"
            elif q.type == 5:  # Matching
                for left, right in q.matching_pairs:
                    text += f"   {left}  ↔  {right}\n"
            elif q.type == 6:  # Ordering
                for i, item in enumerate(q.ordering_items, 1):
                    text += f"   {i}. {item}\n"
            elif q.type == 7:  # Code
                text += f"   Code: {q.code_template[:50]}...\n"
            elif q.type == 8:  # Calculation
                text += f"   Formula: {q.formula}\n"
            text += "\n"

        text += "-" * 60 + "\n"
        text += f"Total: {len(self.questions)} questions | Total Points: {sum(q.score for q in self.questions)}\n"
        self.preview_text.setText(text)

    def export_json(self):
        if not self.questions:
            QMessageBox.warning(self, "Warning", "No questions to export.")
            return

        filepath, _ = QFileDialog.getSaveFileName(self, "Export Questions", 
            f"questions_{datetime.now().strftime('%Y%m%d')}.json", "JSON (*.json)")
        if filepath:
            data = [q.to_dict() for q in self.questions]
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            QMessageBox.information(self, "Success", f"Exported {len(self.questions)} questions.")

    def import_json(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Questions", "", "JSON (*.json)")
        if filepath:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.questions = [Question.from_dict(d) for d in data]
            for i, q in enumerate(self.questions):
                q.id = i + 1
            self.update_list_display()
            self.refresh_preview()
            QMessageBox.information(self, "Success", f"Imported {len(self.questions)} questions.")

    def load_examples(self):
        if self.questions:
            reply = QMessageBox.question(self, "Load Examples", 
                "This will replace current questions. Continue?",
                QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

        self.questions = get_example_questions()
        for i, q in enumerate(self.questions):
            q.id = i + 1
        self.update_list_display()
        self.refresh_preview()
        QMessageBox.information(self, "Success", f"Loaded {len(self.questions)} example questions.")

    def apply_styles(self):
        self.setStyleSheet("""
            QWidget { background-color: #f5f5f5; font-family: 'Segoe UI', Arial; font-size: 12px; }
            #card {
                background: white;
                border-radius: 12px;
                padding: 15px;
                border: 1px solid #e0e0e0;
            }
            #title {
                font-size: 18px;
                font-weight: bold;
                color: #2c3e50;
                margin-bottom: 15px;
                border-bottom: 2px solid #3498db;
                padding-bottom: 8px;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
            QTextEdit, QLineEdit, QComboBox, QSpinBox {
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = QuestionCreatorApp()
    window.show()
    sys.exit(app.exec_())