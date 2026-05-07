# ui/student_manager.py
import json
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

class StudentManagerDialog(QDialog):
    """학생 명단 관리 대화상자"""
    
    student_data_saved = pyqtSignal(dict)  # 학생 데이터 저장 시그널
    
    def __init__(self, parent=None, student_list=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Student Roster Manager")
        self.setGeometry(300, 200, 800, 600)
        
        self.students = student_list or []
        self.init_ui()
        self.load_students()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 상단 버튼 영역
        btn_layout = QHBoxLayout()
        
        self.add_btn = QPushButton("➕ Add Student")
        self.add_btn.clicked.connect(self.add_student)
        btn_layout.addWidget(self.add_btn)
        
        self.delete_btn = QPushButton("🗑 Delete Selected")
        self.delete_btn.clicked.connect(self.delete_student)
        btn_layout.addWidget(self.delete_btn)
        
        self.import_btn = QPushButton("📂 Import CSV")
        self.import_btn.clicked.connect(self.import_csv)
        btn_layout.addWidget(self.import_btn)
        
        self.export_btn = QPushButton("💾 Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        btn_layout.addWidget(self.export_btn)
        
        self.save_btn = QPushButton("💾 Save to JSON")
        self.save_btn.clicked.connect(self.save_to_json)
        btn_layout.addWidget(self.save_btn)
        
        layout.addLayout(btn_layout)
        
        # 학생 목록 테이블
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Department", "Student ID"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        
        # 컬럼 너비 설정
        self.table.setColumnWidth(0, 80)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 150)
        
        layout.addWidget(self.table)
        
        # 하단 버튼
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        self.setLayout(layout)
    
    def load_students(self):
        """학생 목록 테이블에 로드"""
        self.table.setRowCount(len(self.students))
        
        for idx, student in enumerate(self.students):
            # ID (자동 증가)
            id_item = QTableWidgetItem(str(idx + 1))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(idx, 0, id_item)
            
            # Name
            name_item = QTableWidgetItem(student.get('name', ''))
            self.table.setItem(idx, 1, name_item)
            
            # Department
            dept_item = QTableWidgetItem(student.get('department', ''))
            self.table.setItem(idx, 2, dept_item)
            
            # Student ID
            student_id_item = QTableWidgetItem(student.get('student_id', ''))
            self.table.setItem(idx, 3, student_id_item)
    
    def add_student(self):
        """새 학생 추가"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # ID 자동 설정
        id_item = QTableWidgetItem(str(row + 1))
        id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(row, 0, id_item)
        
        # 빈 값으로 초기화
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem(""))
        self.table.setItem(row, 3, QTableWidgetItem(""))
        
        # 이름 입력 셀로 포커스
        self.table.editItem(self.table.item(row, 1))
    
    def delete_student(self):
        """선택한 학생 삭제"""
        selected_rows = set()
        for item in self.table.selectedItems():
            selected_rows.add(item.row())
        
        # 내림차순으로 삭제
        for row in sorted(selected_rows, reverse=True):
            self.table.removeRow(row)
        
        # ID 재정렬
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setText(str(row + 1))
    
    def import_csv(self):
        """CSV 파일에서 학생 목록 가져오기"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Import CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return
        
        try:
            import csv
            students = []
            
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    student = {
                        'name': row.get('name', row.get('Name', '')),
                        'department': row.get('department', row.get('Department', '')),
                        'student_id': row.get('student_id', row.get('Student ID', row.get('ID', '')))
                    }
                    if student['name']:
                        students.append(student)
            
            self.students = students
            self.load_students()
            QMessageBox.information(self, "Success", f"Imported {len(students)} students.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to import CSV: {str(e)}")
    
    def export_csv(self):
        """학생 목록 CSV로 내보내기"""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No students to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return
        
        try:
            import csv
            students = self.get_students_from_table()
            
            with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['name', 'department', 'student_id'])
                writer.writeheader()
                for student in students:
                    writer.writerow(student)
            
            QMessageBox.information(self, "Success", f"Exported {len(students)} students to CSV.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export CSV: {str(e)}")
    
    def save_to_json(self):
        """학생 목록 JSON으로 저장"""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "Warning", "No students to save.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Student Roster", "", "JSON Files (*.json)")
        if not file_path:
            return
        
        try:
            students = self.get_students_from_table()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(students, f, ensure_ascii=False, indent=2)
            
            QMessageBox.information(self, "Success", f"Saved {len(students)} students to JSON.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save: {str(e)}")
    
    def get_students_from_table(self):
        """테이블에서 학생 목록 추출"""
        students = []
        for row in range(self.table.rowCount()):
            student = {
                'name': self.table.item(row, 1).text() if self.table.item(row, 1) else "",
                'department': self.table.item(row, 2).text() if self.table.item(row, 2) else "",
                'student_id': self.table.item(row, 3).text() if self.table.item(row, 3) else "",
            }
            if student['name']:
                students.append(student)
        return students
    
    def accept_data(self):
        """데이터 저장 및 닫기"""
        self.students = self.get_students_from_table()
        self.student_data_saved.emit({'students': self.students})
        self.accept()


class StudentInfoWidget(QWidget):
    """학생 정보 표시 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.group = QGroupBox("Current Student")
        group_layout = QVBoxLayout()
        
        self.info_label = QLabel("No student selected")
        self.info_label.setStyleSheet("font-size: 12px; padding: 5px;")
        self.info_label.setWordWrap(True)
        group_layout.addWidget(self.info_label)
        
        self.group.setLayout(group_layout)
        layout.addWidget(self.group)
        self.setLayout(layout)
    
    def set_student(self, student):
        """학생 정보 표시"""
        if student:
            text = f"📌 {student.get('name', '')}\n"
            text += f"🆔 ID: {student.get('student_id', '')}\n"
            text += f"🏛️ Dept: {student.get('department', '')}"
            self.info_label.setText(text)
        else:
            self.info_label.setText("No student selected")