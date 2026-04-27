#!/usr/bin/env python3
# database_manager.py
# Standalone Database Manager for Exam Questions

import sqlite3
import json
import os, sys
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap
from PyQt5.QtCore import Qt, QTimer

class DatabaseManager:
    """Main database manager for exam questions"""
    
    def __init__(self, db_path: str = "exam_questions.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with all required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Questions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question_type INTEGER NOT NULL,
                text TEXT NOT NULL,
                score INTEGER DEFAULT 5,
                choices TEXT,
                answer TEXT,
                blanks TEXT,
                matching_pairs TEXT,
                ordering_items TEXT,
                code_template TEXT,
                formula TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category TEXT,
                difficulty TEXT DEFAULT 'Medium',
                tags TEXT,
                usage_count INTEGER DEFAULT 0,
                last_used TIMESTAMP
            )
        ''')
        
        # Question banks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS question_banks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Bank questions junction table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bank_questions (
                bank_id INTEGER,
                question_id INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (bank_id) REFERENCES question_banks(id) ON DELETE CASCADE,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
                PRIMARY KEY (bank_id, question_id)
            )
        ''')
        
        # Exams table (saved exams)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                date TEXT,
                description TEXT,
                total_points INTEGER,
                question_ids TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tags table for better organization
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        
        # Question-tag junction
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS question_tags (
                question_id INTEGER,
                tag_id INTEGER,
                FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE,
                PRIMARY KEY (question_id, tag_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    # ==================== QUESTION CRUD OPERATIONS ====================
    
    def add_question(self, question_dict: Dict) -> int:
        """Add a question to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO questions (
                question_type, text, score, choices, answer, blanks, 
                matching_pairs, ordering_items, code_template, formula,
                category, difficulty, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            question_dict.get('type', 0),
            question_dict.get('text', ''),
            question_dict.get('score', 5),
            json.dumps(question_dict.get('choices', []), ensure_ascii=False),
            question_dict.get('answer', ''),
            json.dumps(question_dict.get('blanks', []), ensure_ascii=False),
            json.dumps(question_dict.get('matching_pairs', []), ensure_ascii=False),
            json.dumps(question_dict.get('ordering_items', []), ensure_ascii=False),
            question_dict.get('code_template', ''),
            question_dict.get('formula', ''),
            question_dict.get('category', ''),
            question_dict.get('difficulty', 'Medium'),
            question_dict.get('tags', '')
        ))
        
        question_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return question_id
    
    def get_all_questions(self, limit: int = None, offset: int = 0, 
                          category: str = None, difficulty: str = None) -> List[Dict]:
        """Get all questions from database with optional filters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM questions WHERE 1=1'
        params = []
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        
        if difficulty:
            query += ' AND difficulty = ?'
            params.append(difficulty)
        
        query += ' ORDER BY created_at DESC'
        
        if limit:
            query += ' LIMIT ? OFFSET ?'
            params.extend([limit, offset])
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        questions = self._rows_to_questions(rows)
        conn.close()
        return questions
    
    def get_question_by_id(self, qid: int) -> Optional[Dict]:
        """Get a specific question by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM questions WHERE id = ?', (qid,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return self._row_to_question(row)
        return None
    
    def update_question(self, qid: int, question_dict: Dict) -> bool:
        """Update an existing question"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE questions SET
                question_type = ?, text = ?, score = ?, choices = ?, answer = ?,
                blanks = ?, matching_pairs = ?, ordering_items = ?, 
                code_template = ?, formula = ?, category = ?, difficulty = ?, tags = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            question_dict.get('type', 0),
            question_dict.get('text', ''),
            question_dict.get('score', 5),
            json.dumps(question_dict.get('choices', []), ensure_ascii=False),
            question_dict.get('answer', ''),
            json.dumps(question_dict.get('blanks', []), ensure_ascii=False),
            json.dumps(question_dict.get('matching_pairs', []), ensure_ascii=False),
            json.dumps(question_dict.get('ordering_items', []), ensure_ascii=False),
            question_dict.get('code_template', ''),
            question_dict.get('formula', ''),
            question_dict.get('category', ''),
            question_dict.get('difficulty', 'Medium'),
            question_dict.get('tags', ''),
            qid
        ))
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def delete_question(self, qid: int) -> bool:
        """Delete a question from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM questions WHERE id = ?', (qid,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def delete_questions_batch(self, qids: List[int]) -> int:
        """Delete multiple questions"""
        if not qids:
            return 0
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(qids))
        cursor.execute(f'DELETE FROM questions WHERE id IN ({placeholders})', qids)
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted
    
    # ==================== SEARCH OPERATIONS ====================
    
    def search_questions(self, keyword: str = "", question_type: int = None, 
                         difficulty: str = None, category: str = None) -> List[Dict]:
        """Search questions by various criteria"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = '''SELECT * FROM questions WHERE 1=1'''
        params = []
        
        if keyword:
            query += ' AND (text LIKE ? OR answer LIKE ? OR tags LIKE ?)'
            params.extend([f'%{keyword}%', f'%{keyword}%', f'%{keyword}%'])
        
        if question_type is not None:
            query += ' AND question_type = ?'
            params.append(question_type)
        
        if difficulty:
            query += ' AND difficulty = ?'
            params.append(difficulty)
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        
        query += ' ORDER BY created_at DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        questions = self._rows_to_questions(rows)
        conn.close()
        return questions
    
    def search_by_tag(self, tag: str) -> List[Dict]:
        """Search questions by tag"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT q.* FROM questions q
            JOIN question_tags qt ON q.id = qt.question_id
            JOIN tags t ON qt.tag_id = t.id
            WHERE t.name = ?
            ORDER BY q.created_at DESC
        ''', (tag,))
        
        rows = cursor.fetchall()
        questions = self._rows_to_questions(rows)
        conn.close()
        return questions
    
    # ==================== CATEGORY & DIFFICULTY OPERATIONS ====================
    
    def get_categories(self) -> List[str]:
        """Get all unique categories"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT category FROM questions WHERE category != "" ORDER BY category')
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        return categories
    
    def get_difficulties(self) -> List[str]:
        """Get all unique difficulty levels"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT difficulty FROM questions ORDER BY difficulty')
        difficulties = [row[0] for row in cursor.fetchall()]
        conn.close()
        return difficulties
    
    def get_question_types_stats(self) -> Dict[int, int]:
        """Get count of questions by type"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT question_type, COUNT(*) FROM questions GROUP BY question_type')
        stats = dict(cursor.fetchall())
        conn.close()
        return stats
    
    # ==================== STATISTICS ====================
    
    def get_statistics(self) -> Dict:
        """Get comprehensive database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM questions')
        total = cursor.fetchone()[0]
        
        cursor.execute('SELECT question_type, COUNT(*) FROM questions GROUP BY question_type')
        by_type = dict(cursor.fetchall())
        
        cursor.execute('SELECT difficulty, COUNT(*) FROM questions GROUP BY difficulty')
        by_difficulty = dict(cursor.fetchall())
        
        cursor.execute('SELECT category, COUNT(*) FROM questions WHERE category != "" GROUP BY category')
        by_category = dict(cursor.fetchall())
        
        cursor.execute('SELECT COUNT(*) FROM question_banks')
        total_banks = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM exams')
        total_exams = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_questions': total,
            'by_type': by_type,
            'by_difficulty': by_difficulty,
            'by_category': by_category,
            'total_banks': total_banks,
            'total_exams': total_exams,
            'db_path': self.db_path,
            'db_size': self._get_db_size()
        }
    
    def _get_db_size(self) -> str:
        """Get database file size"""
        if os.path.exists(self.db_path):
            size = os.path.getsize(self.db_path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        return "0 B"
    
    def increment_usage(self, qid: int):
        """Increment usage count for a question"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE questions 
            SET usage_count = usage_count + 1, last_used = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (qid,))
        conn.commit()
        conn.close()
    
    # ==================== QUESTION BANK OPERATIONS ====================
    
    def create_bank(self, name: str, description: str = "") -> Optional[int]:
        """Create a new question bank"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO question_banks (name, description) VALUES (?, ?)', 
                          (name, description))
            bank_id = cursor.lastrowid
            conn.commit()
            return bank_id
        except sqlite3.IntegrityError:
            return None
        finally:
            conn.close()
    
    def get_banks(self) -> List[Dict]:
        """Get all question banks"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, COUNT(bq.question_id) as question_count
            FROM question_banks b
            LEFT JOIN bank_questions bq ON b.id = bq.bank_id
            GROUP BY b.id
            ORDER BY b.name
        ''')
        banks = [{'id': row[0], 'name': row[1], 'description': row[2], 
                  'created_at': row[3], 'updated_at': row[4], 'question_count': row[5]} 
                 for row in cursor.fetchall()]
        conn.close()
        return banks
    
    def update_bank(self, bank_id: int, name: str = None, description: str = None) -> bool:
        """Update a question bank"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        updates = []
        params = []
        if name:
            updates.append('name = ?')
            params.append(name)
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        
        if updates:
            updates.append('updated_at = CURRENT_TIMESTAMP')
            query = f'UPDATE question_banks SET {", ".join(updates)} WHERE id = ?'
            params.append(bank_id)
            cursor.execute(query, params)
        
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def delete_bank(self, bank_id: int) -> bool:
        """Delete a question bank"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM question_banks WHERE id = ?', (bank_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def add_to_bank(self, bank_id: int, question_id: int) -> bool:
        """Add a question to a bank"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT OR IGNORE INTO bank_questions (bank_id, question_id) VALUES (?, ?)',
                          (bank_id, question_id))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()
    
    def remove_from_bank(self, bank_id: int, question_id: int) -> bool:
        """Remove a question from a bank"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM bank_questions WHERE bank_id = ? AND question_id = ?',
                      (bank_id, question_id))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    def get_bank_questions(self, bank_id: int) -> List[Dict]:
        """Get all questions in a bank"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT q.* FROM questions q
            JOIN bank_questions bq ON q.id = bq.question_id
            WHERE bq.bank_id = ?
            ORDER BY bq.added_at DESC
        ''', (bank_id,))
        rows = cursor.fetchall()
        questions = self._rows_to_questions(rows)
        conn.close()
        return questions
    
    # ==================== EXAM OPERATIONS ====================
    
    def save_exam(self, title: str, question_ids: List[int], date: str = None,
                  description: str = "", total_points: int = 0) -> int:
        """Save an exam to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO exams (title, date, description, total_points, question_ids)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, date or datetime.now().strftime("%Y-%m-%d"), 
              description, total_points, json.dumps(question_ids)))
        
        exam_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return exam_id
    
    def get_exams(self) -> List[Dict]:
        """Get all saved exams"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM exams ORDER BY created_at DESC')
        rows = cursor.fetchall()
        
        exams = []
        for row in rows:
            exams.append({
                'id': row[0],
                'title': row[1],
                'date': row[2],
                'description': row[3],
                'total_points': row[4],
                'question_ids': json.loads(row[5]) if row[5] else [],
                'created_at': row[6]
            })
        conn.close()
        return exams
    
    def load_exam(self, exam_id: int) -> Tuple[Dict, List[Dict]]:
        """Load an exam and its questions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM exams WHERE id = ?', (exam_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None, None
        
        exam = {
            'id': row[0],
            'title': row[1],
            'date': row[2],
            'description': row[3],
            'total_points': row[4],
            'question_ids': json.loads(row[5]) if row[5] else [],
            'created_at': row[6]
        }
        
        questions = []
        for qid in exam['question_ids']:
            q = self.get_question_by_id(qid)
            if q:
                questions.append(q)
        
        conn.close()
        return exam, questions
    
    def delete_exam(self, exam_id: int) -> bool:
        """Delete a saved exam"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM exams WHERE id = ?', (exam_id,))
        success = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return success
    
    # ==================== TAG OPERATIONS ====================
    
    def add_tag(self, tag_name: str) -> int:
        """Add a new tag"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT OR IGNORE INTO tags (name) VALUES (?)', (tag_name,))
            cursor.execute('SELECT id FROM tags WHERE name = ?', (tag_name,))
            tag_id = cursor.fetchone()[0]
            conn.commit()
            return tag_id
        finally:
            conn.close()
    
    def add_tag_to_question(self, question_id: int, tag_name: str):
        """Add a tag to a question"""
        tag_id = self.add_tag(tag_name)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO question_tags (question_id, tag_id) VALUES (?, ?)',
                      (question_id, tag_id))
        conn.commit()
        conn.close()
    
    def get_tags_for_question(self, question_id: int) -> List[str]:
        """Get all tags for a question"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT t.name FROM tags t
            JOIN question_tags qt ON t.id = qt.tag_id
            WHERE qt.question_id = ?
        ''', (question_id,))
        tags = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tags
    
    def get_all_tags(self) -> List[str]:
        """Get all tags"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM tags ORDER BY name')
        tags = [row[0] for row in cursor.fetchall()]
        conn.close()
        return tags
    
    # ==================== IMPORT/EXPORT ====================
    
    def export_to_json(self, filepath: str, question_ids: List[int] = None):
        """Export questions to JSON file"""
        if question_ids:
            questions = [self.get_question_by_id(qid) for qid in question_ids if self.get_question_by_id(qid)]
        else:
            questions = self.get_all_questions()
        
        export_data = {
            'export_date': datetime.now().isoformat(),
            'version': '1.0',
            'total_questions': len(questions),
            'questions': questions
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return len(questions)
    
    def import_from_json(self, filepath: str) -> int:
        """Import questions from JSON file"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        questions = data.get('questions', [])
        imported = 0
        
        for q in questions:
            # Remove id to let DB assign new one
            q.pop('db_id', None)
            q.pop('id', None)
            q.pop('created_at', None)
            q.pop('updated_at', None)
            q.pop('usage_count', None)
            q.pop('last_used', None)
            
            self.add_question(q)
            imported += 1
        
        return imported
    
    # ==================== HELPER METHODS ====================
    
    def _row_to_question(self, row) -> Dict:
        """Convert a database row to a question dictionary"""
        return {
            'db_id': row[0],
            'type': row[1],
            'text': row[2],
            'score': row[3],
            'choices': json.loads(row[4]) if row[4] else [],
            'answer': row[5] or '',
            'blanks': json.loads(row[6]) if row[6] else [],
            'matching_pairs': json.loads(row[7]) if row[7] else [],
            'ordering_items': json.loads(row[8]) if row[8] else [],
            'code_template': row[9] or '',
            'formula': row[10] or '',
            'created_at': row[11],
            'updated_at': row[12],
            'category': row[13] or '',
            'difficulty': row[14] or 'Medium',
            'tags': row[15] or '',
            'usage_count': row[16] or 0,
            'last_used': row[17]
        }
    
    def _rows_to_questions(self, rows) -> List[Dict]:
        """Convert multiple database rows to question dictionaries"""
        return [self._row_to_question(row) for row in rows]

# ==================== DATABASE MANAGER GUI ====================

class DatabaseManagerGUI(QMainWindow):
    """Standalone GUI for database management"""
    
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.setWindowTitle("Database Manager - Exam Question Bank")
        self.setGeometry(100, 100, 1200, 800)
        self.init_ui()
        self.refresh_all()
    
    def init_ui(self):
        central = QWidget()
        layout = QHBoxLayout()
        
        # Left Panel - Statistics & Controls
        left_panel = QFrame()
        left_panel.setObjectName("card")
        left_layout = QVBoxLayout()
        
        # Title
        title = QLabel("🗄️ Database Manager")
        title.setObjectName("title")
        left_layout.addWidget(title)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(200)
        stats_layout.addWidget(self.stats_text)
        stats_group.setLayout(stats_layout)
        left_layout.addWidget(stats_group)
        
        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()
        
        self.refresh_btn = QPushButton("🔄 Refresh Statistics")
        self.refresh_btn.clicked.connect(self.refresh_stats)
        actions_layout.addWidget(self.refresh_btn)
        
        self.export_btn = QPushButton("💾 Export All Questions")
        self.export_btn.clicked.connect(self.export_all)
        actions_layout.addWidget(self.export_btn)
        
        self.import_btn = QPushButton("📂 Import Questions")
        self.import_btn.clicked.connect(self.import_questions)
        actions_layout.addWidget(self.import_btn)
        
        self.backup_btn = QPushButton("💿 Backup Database")
        self.backup_btn.clicked.connect(self.backup_database)
        actions_layout.addWidget(self.backup_btn)
        
        actions_group.setLayout(actions_layout)
        left_layout.addWidget(actions_group)
        
        # Bank Management
        bank_group = QGroupBox("Question Banks")
        bank_layout = QVBoxLayout()
        
        self.bank_list = QListWidget()
        self.bank_list.itemClicked.connect(self.on_bank_selected)
        bank_layout.addWidget(self.bank_list)
        
        bank_btn_layout = QHBoxLayout()
        self.new_bank_btn = QPushButton("➕ New Bank")
        self.new_bank_btn.clicked.connect(self.create_bank)
        self.del_bank_btn = QPushButton("🗑 Delete Bank")
        self.del_bank_btn.clicked.connect(self.delete_bank)
        bank_btn_layout.addWidget(self.new_bank_btn)
        bank_btn_layout.addWidget(self.del_bank_btn)
        bank_layout.addLayout(bank_btn_layout)
        
        bank_group.setLayout(bank_layout)
        left_layout.addWidget(bank_group)
        
        left_layout.addStretch()
        left_panel.setLayout(left_layout)
        
        # Right Panel - Questions
        right_panel = QFrame()
        right_panel.setObjectName("card")
        right_layout = QVBoxLayout()
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search questions...")
        self.search_input.textChanged.connect(self.search_questions)
        search_layout.addWidget(self.search_input)
        
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", -1)
        type_names = ["Multiple Choice", "True/False", "Fill in Blank", "Short Answer", 
                      "Essay", "Matching", "Ordering", "Code", "Calculation", "Diagram"]
        for i, name in enumerate(type_names):
            self.type_filter.addItem(name, i)
        self.type_filter.currentIndexChanged.connect(self.search_questions)
        search_layout.addWidget(self.type_filter)
        
        self.difficulty_filter = QComboBox()
        self.difficulty_filter.addItem("All Difficulties", "")
        self.difficulty_filter.addItem("Easy", "Easy")
        self.difficulty_filter.addItem("Medium", "Medium")
        self.difficulty_filter.addItem("Hard", "Hard")
        self.difficulty_filter.currentIndexChanged.connect(self.search_questions)
        search_layout.addWidget(self.difficulty_filter)
        
        right_layout.addLayout(search_layout)
        
        # Question list
        self.question_list = QListWidget()
        self.question_list.setAlternatingRowColors(True)
        self.question_list.itemDoubleClicked.connect(self.view_question)
        right_layout.addWidget(self.question_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.view_btn = QPushButton("👁️ View Selected")
        self.view_btn.clicked.connect(self.view_question)
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.clicked.connect(self.delete_question)
        self.add_to_bank_btn = QPushButton("📚 Add to Bank")
        self.add_to_bank_btn.clicked.connect(self.add_to_bank_dialog)
        btn_layout.addWidget(self.view_btn)
        btn_layout.addWidget(self.delete_btn)
        btn_layout.addWidget(self.add_to_bank_btn)
        right_layout.addLayout(btn_layout)
        
        right_panel.setLayout(right_layout)
        
        layout.addWidget(left_panel, 1)
        layout.addWidget(right_panel, 2)
        central.setLayout(layout)
        self.setCentralWidget(central)
        
        self.apply_style()
    
    def apply_style(self):
        self.setStyleSheet("""
            QWidget { background-color: #f0f2f5; font-family: 'Segoe UI', Arial; font-size: 12px; }
            #card {
                background: white;
                border-radius: 12px;
                padding: 15px;
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
            }
            QPushButton {
                background-color: #1a73e8;
                color: white;
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1557b0; }
            QLineEdit, QComboBox {
                border: 1px solid #ccc;
                border-radius: 6px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e8f0fe;
                color: #1a73e8;
            }
        """)
    
    def refresh_all(self):
        self.refresh_stats()
        self.refresh_banks()
        self.refresh_questions()
    
    def refresh_stats(self):
        stats = self.db.get_statistics()
        text = f"""
        📊 Database Statistics
        {'='*40}
        
        📝 Total Questions: {stats['total_questions']}
        
        📁 Question Banks: {stats['total_banks']}
        📋 Saved Exams: {stats['total_exams']}
        
        📏 Database Size: {stats['db_size']}
        📍 Database Path: {stats['db_path']}
        
        {'='*40}
        📚 By Type:
        """
        type_names = {0: "MC", 1: "T/F", 2: "Fill", 3: "Short", 4: "Essay",
                      5: "Match", 6: "Order", 7: "Code", 8: "Calc", 9: "Diagram"}
        for t, count in stats['by_type'].items():
            text += f"\n   • {type_names.get(t, 'Other')}: {count}"
        
        text += f"\n\n{'='*40}\n⭐ By Difficulty:"
        for d, count in stats['by_difficulty'].items():
            text += f"\n   • {d}: {count}"
        
        self.stats_text.setText(text)
    
    def refresh_banks(self):
        self.bank_list.clear()
        banks = self.db.get_banks()
        for bank in banks:
            self.bank_list.addItem(f"📚 {bank['name']} ({bank['question_count']} questions)")
            self.bank_list.item(self.bank_list.count()-1).setData(Qt.UserRole, bank['id'])
    
    def refresh_questions(self, questions=None):
        self.question_list.clear()
        if questions is None:
            questions = self.db.get_all_questions(limit=100)
        
        type_icons = ["🔘", "✓✗", "___", "📝", "📄", "🔗", "🔢", "💻", "🧮", "📊"]
        
        for q in questions:
            icon = type_icons[q['type']] if q['type'] < len(type_icons) else "❓"
            text = f"{icon} [{q['difficulty']}] {q['text'][:60]}... ({q['score']} pts)"
            self.question_list.addItem(text)
            self.question_list.item(self.question_list.count()-1).setData(Qt.UserRole, q['db_id'])
    
    def search_questions(self):
        keyword = self.search_input.text()
        type_filter = self.type_filter.currentData()
        difficulty = self.difficulty_filter.currentData()
        
        if type_filter == -1:
            type_filter = None
        
        results = self.db.search_questions(keyword, type_filter, difficulty if difficulty else None)
        self.refresh_questions(results)
    
    def on_bank_selected(self, item):
        bank_id = item.data(Qt.UserRole)
        questions = self.db.get_bank_questions(bank_id)
        self.refresh_questions(questions)
    
    def view_question(self):
        current = self.question_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Warning", "Please select a question to view.")
            return
        
        qid = current.data(Qt.UserRole)
        q = self.db.get_question_by_id(qid)
        
        if q:
            text = f"""
            📋 Question Details
            {'='*50}
            
            ID: {q['db_id']}
            Type: {q['type']}
            Difficulty: {q['difficulty']}
            Score: {q['score']} pts
            
            Question:
            {q['text']}
            
            Answer: {q['answer']}
            """
            if q['choices']:
                text += f"\nOptions:\n" + "\n".join(f"  {i+1}. {c}" for i, c in enumerate(q['choices']))
            
            QMessageBox.information(self, "Question Details", text)
    
    def delete_question(self):
        current = self.question_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Warning", "Please select a question to delete.")
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", 
            "Are you sure you want to delete this question? This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            qid = current.data(Qt.UserRole)
            self.db.delete_question(qid)
            self.refresh_all()
            QMessageBox.information(self, "Success", "Question deleted successfully.")
    
    def create_bank(self):
        name, ok = QInputDialog.getText(self, "New Bank", "Enter bank name:")
        if ok and name:
            desc, ok = QInputDialog.getText(self, "Bank Description", "Enter description (optional):")
            bank_id = self.db.create_bank(name, desc if ok else "")
            if bank_id:
                self.refresh_banks()
                QMessageBox.information(self, "Success", f"Bank '{name}' created.")
            else:
                QMessageBox.warning(self, "Error", "Bank name already exists.")
    
    def delete_bank(self):
        current = self.bank_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Warning", "Please select a bank to delete.")
            return
        
        reply = QMessageBox.question(self, "Confirm Delete", 
            "Are you sure you want to delete this bank? Questions will not be deleted.",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            bank_id = current.data(Qt.UserRole)
            self.db.delete_bank(bank_id)
            self.refresh_banks()
            self.refresh_questions()
    
    def add_to_bank_dialog(self):
        current = self.question_list.currentItem()
        if not current:
            QMessageBox.warning(self, "Warning", "Please select a question to add.")
            return
        
        qid = current.data(Qt.UserRole)
        banks = self.db.get_banks()
        
        if not banks:
            QMessageBox.warning(self, "Warning", "No banks available. Create a bank first.")
            return
        
        items = [f"{b['name']} ({b['question_count']} questions)" for b in banks]
        selected, ok = QInputDialog.getItem(self, "Select Bank", "Choose a bank:", items, 0, False)
        
        if ok and selected:
            idx = items.index(selected)
            bank_id = banks[idx]['id']
            self.db.add_to_bank(bank_id, qid)
            QMessageBox.information(self, "Success", f"Question added to {banks[idx]['name']}")
    
    def export_all(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Questions", 
            f"questions_export_{datetime.now().strftime('%Y%m%d')}.json", "JSON (*.json)")
        if filepath:
            count = self.db.export_to_json(filepath)
            QMessageBox.information(self, "Success", f"Exported {count} questions to {filepath}")
    
    def import_questions(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Import Questions", "", "JSON (*.json)")
        if filepath:
            count = self.db.import_from_json(filepath)
            self.refresh_all()
            QMessageBox.information(self, "Success", f"Imported {count} questions from {filepath}")
    
    def backup_database(self):
        import shutil
        backup_path = f"exam_questions_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(self.db.db_path, backup_path)
        QMessageBox.information(self, "Success", f"Database backed up to {backup_path}")

# ==================== MAIN ====================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DatabaseManagerGUI()
    window.show()
    sys.exit(app.exec_())