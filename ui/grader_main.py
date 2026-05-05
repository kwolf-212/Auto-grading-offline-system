# ui/grader_main.py
import sys
import json
import os
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QKeySequence
from PyQt5.QtCore import Qt

from exam_grader import ExamGrader, ResultExporter
from ui.grader_styles import GRADER_STYLE


class GraderApp(QMainWindow):
    """시험 채점기 메인 윈도우 (대면부)"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Exam Grader")
        
        # Data
        self.exam_data = None
        self.image_files = []
        self.current_image_index = 0
        self.current_image_path = None
        self.grading_results = {}
        
        # Engines
        self.result_exporter = ResultExporter()
        
        self.init_ui()
        self.apply_style()
        self.showMaximized()
    
    def apply_style(self):
        self.setStyleSheet(GRADER_STYLE)
    
    def init_ui(self):
        central_widget = QWidget()
        central_widget.setObjectName("central")
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # ===== LEFT PANEL: Image Display =====
        left_panel = self._create_image_panel()
        
        # ===== RIGHT PANEL: Grading Controls and Results =====
        right_panel = self._create_control_panel()
        
        main_layout.addWidget(left_panel, 4)
        main_layout.addWidget(right_panel, 6)
        
        # Status bar
        self.statusBar().showMessage("Ready")
        
        # Shortcuts
        self._create_shortcuts()
    
    def _create_image_panel(self) -> QWidget:
        """이미지 표시 패널 생성"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Title
        title_label = QLabel("📷 Exam Paper Viewer")
        title_label.setObjectName("title")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # Image display area
        image_group = QGroupBox("Scan Image")
        image_layout = QVBoxLayout(image_group)
        
        self.image_label = QLabel("📷 No image\n\nSelect a folder containing exam images")
        self.image_label.setObjectName("image_label")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumHeight(500)
        self.image_label.setScaledContents(False)
        image_layout.addWidget(self.image_label)
        layout.addWidget(image_group)

        # Image navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)
        
        self.prev_btn = QPushButton("◀ Previous")
        self.prev_btn.setObjectName("nav_btn")
        self.prev_btn.clicked.connect(self.prev_image)
        self.prev_btn.setEnabled(False)
        
        self.page_info_label = QLabel("0 / 0")
        self.page_info_label.setAlignment(Qt.AlignCenter)
        self.page_info_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #007acc; padding: 5px;")
        
        self.next_btn = QPushButton("Next ▶")
        self.next_btn.setObjectName("nav_btn")
        self.next_btn.clicked.connect(self.next_image)
        self.next_btn.setEnabled(False)
        
        nav_layout.addWidget(self.prev_btn)
        nav_layout.addWidget(self.page_info_label)
        nav_layout.addWidget(self.next_btn)
        layout.addLayout(nav_layout)
        
        # Current file info
        self.file_info_label = QLabel("No folder selected")
        self.file_info_label.setAlignment(Qt.AlignCenter)
        self.file_info_label.setStyleSheet("font-size: 11px; color: #888; padding: 5px;")
        layout.addWidget(self.file_info_label)
        
        layout.addStretch()
        
        return panel
    
    def _create_control_panel(self) -> QWidget:
        """제어 패널 생성"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)

        # Title
        results_title = QLabel("📊 Exam Grader")
        results_title.setObjectName("title")
        results_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(results_title)

        # Control buttons
        control_group = QGroupBox("Controls")
        control_layout = QVBoxLayout(control_group)
        
        # Button row 1
        btn_row1 = QHBoxLayout()
        self.load_exam_btn = QPushButton("📂 Load Exam (JSON)")
        self.load_exam_btn.clicked.connect(self.load_exam)
        btn_row1.addWidget(self.load_exam_btn)
        
        self.load_folder_btn = QPushButton("📁 Load Image Folder")
        self.load_folder_btn.clicked.connect(self.load_image_folder)
        btn_row1.addWidget(self.load_folder_btn)
        control_layout.addLayout(btn_row1)
        
        # Button row 2
        btn_row2 = QHBoxLayout()
        self.grade_current_btn = QPushButton("✅ Grade Current Page")
        self.grade_current_btn.setObjectName("grade_btn")
        self.grade_current_btn.clicked.connect(self.grade_current_image)
        btn_row2.addWidget(self.grade_current_btn)
        
        self.grade_all_btn = QPushButton("🚀 Grade All Pages")
        self.grade_all_btn.setObjectName("grade_btn")
        self.grade_all_btn.clicked.connect(self.grade_all_images)
        btn_row2.addWidget(self.grade_all_btn)
        control_layout.addLayout(btn_row2)
        
        # Button row 3
        btn_row3 = QHBoxLayout()
        self.export_results_btn = QPushButton("💾 Export Results")
        self.export_results_btn.clicked.connect(self.export_results)
        btn_row3.addWidget(self.export_results_btn)
        
        self.clear_results_btn = QPushButton("🗑 Clear Results")
        self.clear_results_btn.clicked.connect(self.clear_results)
        btn_row3.addWidget(self.clear_results_btn)
        control_layout.addLayout(btn_row3)
        
        layout.addWidget(control_group)
        
        # Exam info display
        info_group = QGroupBox("Exam Information")
        info_layout = QVBoxLayout(info_group)
        self.exam_info_label = QLabel("No exam loaded")
        self.exam_info_label.setStyleSheet("font-size: 12px; padding: 5px;")
        self.exam_info_label.setWordWrap(True)
        info_layout.addWidget(self.exam_info_label)
        layout.addWidget(info_group)
        
        # Total score display
        self.total_score_label = QLabel("Total: - / - points")
        self.total_score_label.setAlignment(Qt.AlignCenter)
        self.total_score_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #007acc; padding: 10px; background-color: #252526; border-radius: 8px;")
        layout.addWidget(self.total_score_label)
        
        # Results table
        result_group = QGroupBox("Grading Results")
        result_layout = QVBoxLayout(result_group)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Question #", "Score", "Max Score", "Edit Score"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 120)
        
        result_layout.addWidget(self.table)
        layout.addWidget(result_group)
        
        # Status label
        self.grading_status_label = QLabel("Ready")
        self.grading_status_label.setAlignment(Qt.AlignCenter)
        self.grading_status_label.setStyleSheet("font-size: 11px; color: #888; padding: 5px;")
        layout.addWidget(self.grading_status_label)
        
        return panel
    
    def _create_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+O"), self, self.load_exam)
        QShortcut(QKeySequence("Ctrl+F"), self, self.load_image_folder)
        QShortcut(QKeySequence("Ctrl+G"), self, self.grade_current_image)
        QShortcut(QKeySequence("Ctrl+A"), self, self.grade_all_images)
        QShortcut(QKeySequence("Left"), self, self.prev_image)
        QShortcut(QKeySequence("Right"), self, self.next_image)
        QShortcut(QKeySequence("F5"), self, self.grade_current_image)
    
    # ===== Event Handlers =====
    
    def load_exam(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Exam File", "", "JSON (*.json)")
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.exam_data = json.load(f)
                
                exam_title = self.exam_data.get('exam_title', 'Unknown')
                total_questions = len(self.exam_data.get('answers', []))
                total_points = self.exam_data.get('total_points', 0)
                
                self.exam_info_label.setText(f"📋 {exam_title}\nQuestions: {total_questions}\nTotal Points: {total_points}")
                self.statusBar().showMessage(f"Exam loaded: {os.path.basename(file_path)}")
                QMessageBox.information(self, "Success", "✅ Exam loaded successfully!")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load exam:\n{str(e)}")
    
    def load_image_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder with Exam Images")
        if folder_path:
            image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif'}
            self.image_files = [
                os.path.join(folder_path, f) for f in os.listdir(folder_path)
                if os.path.splitext(f)[1].lower() in image_extensions
            ]
            self.image_files.sort()
            
            if not self.image_files:
                QMessageBox.warning(self, "Warning", "No image files found in the selected folder.")
                return
            
            self.current_image_index = 0
            self._display_current_image()
            
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            self._update_navigation_buttons()
            
            self.statusBar().showMessage(f"Loaded {len(self.image_files)} images from {os.path.basename(folder_path)}")
            QMessageBox.information(self, "Success", f"✅ Loaded {len(self.image_files)} exam images.")
    
    def _display_current_image(self):
        if 0 <= self.current_image_index < len(self.image_files):
            self.current_image_path = self.image_files[self.current_image_index]
            pixmap = QPixmap(self.current_image_path)
            
            label_width = self.image_label.width() - 20
            label_height = self.image_label.height() - 20
            scaled_pixmap = pixmap.scaled(label_width, label_height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setStyleSheet("""
                QLabel#image_label {
                    background-color: #252526;
                    border: 2px solid #007acc;
                    border-radius: 8px;
                }
            """)
            
            filename = os.path.basename(self.current_image_path)
            self.file_info_label.setText(f"📄 {filename} ({self.current_image_index + 1} of {len(self.image_files)})")
            self.page_info_label.setText(f"{self.current_image_index + 1} / {len(self.image_files)}")
            
            if self.current_image_path in self.grading_results:
                self.grading_status_label.setText(f"✅ Already graded - Score: {self.grading_results[self.current_image_path]['total']}")
            else:
                self.grading_status_label.setText("⏳ Not graded yet")
            
            self._update_navigation_buttons()
    
    def _update_navigation_buttons(self):
        self.prev_btn.setEnabled(self.current_image_index > 0)
        self.next_btn.setEnabled(self.current_image_index < len(self.image_files) - 1)
    
    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self._display_current_image()
            self._load_results_for_current_image()
    
    def next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self._display_current_image()
            self._load_results_for_current_image()
    
    def _load_results_for_current_image(self):
        if self.current_image_path in self.grading_results:
            results = self.grading_results[self.current_image_path]['results']
            self._display_results(results)
        else:
            self._clear_table()
    
    def grade_current_image(self):
        if not self.exam_data:
            QMessageBox.warning(self, "Error", "⚠️ No exam loaded.\nPlease load an exam JSON file first.")
            return
        
        if not self.current_image_path:
            QMessageBox.warning(self, "Error", "⚠️ No image selected.\nPlease load an image folder first.")
            return
        
        self.statusBar().showMessage("Grading current page...")
        self.grade_current_btn.setEnabled(False)
        self.grading_status_label.setText("⏳ Grading in progress...")
        
        try:
            grader = ExamGrader(self.exam_data)
            results = grader.grade_exam(self.current_image_path)
            
            total_score = grader.get_total_score(results)
            max_score = grader.get_max_score()
            
            self.grading_results[self.current_image_path] = {
                'results': results,
                'total': total_score,
                'max': max_score,
                'filename': os.path.basename(self.current_image_path)
            }
            
            self._display_results(results)
            self.grading_status_label.setText(f"✅ Graded! Score: {total_score:.1f} / {max_score}")
            self.statusBar().showMessage(f"Grading complete! Score: {total_score:.1f} / {max_score}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Grading failed:\n{str(e)}")
            self.grading_status_label.setText("❌ Grading failed")
            self.statusBar().showMessage("Grading failed")
        finally:
            self.grade_current_btn.setEnabled(True)
    
    def grade_all_images(self):
        if not self.exam_data:
            QMessageBox.warning(self, "Error", "⚠️ No exam loaded.\nPlease load an exam JSON file first.")
            return
        
        if not self.image_files:
            QMessageBox.warning(self, "Error", "⚠️ No images loaded.\nPlease load an image folder first.")
            return
        
        reply = QMessageBox.question(self, "Grade All", 
            f"Grade all {len(self.image_files)} images?\nThis may take a while.",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        self.statusBar().showMessage("Grading all images...")
        self.grade_all_btn.setEnabled(False)
        
        try:
            grader = ExamGrader(self.exam_data)
            max_score = grader.get_max_score()
            
            for idx, img_path in enumerate(self.image_files):
                self.grading_status_label.setText(f"⏳ Grading {idx + 1}/{len(self.image_files)}...")
                QApplication.processEvents()
                
                try:
                    results = grader.grade_exam(img_path)
                    total_score = grader.get_total_score(results)
                    
                    self.grading_results[img_path] = {
                        'results': results,
                        'total': total_score,
                        'max': max_score,
                        'filename': os.path.basename(img_path)
                    }
                except Exception as e:
                    print(f"Failed to grade {img_path}: {e}")
                    self.grading_results[img_path] = {
                        'results': {},
                        'total': 0,
                        'max': max_score,
                        'filename': os.path.basename(img_path),
                        'error': str(e)
                    }
            
            self._load_results_for_current_image()
            
            self.grading_status_label.setText(f"✅ Completed! Graded {len(self.image_files)} images")
            self.statusBar().showMessage(f"Grading complete! Processed {len(self.image_files)} images")
            
            total_all = sum(r['total'] for r in self.grading_results.values())
            max_all = sum(r['max'] for r in self.grading_results.values())
            QMessageBox.information(self, "Grading Complete", 
                f"✅ Grading completed!\n\n"
                f"Images processed: {len(self.image_files)}\n"
                f"Total score sum: {total_all:.1f} / {max_all}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Batch grading failed:\n{str(e)}")
        finally:
            self.grade_all_btn.setEnabled(True)
    
    def _display_results(self, results):
        self.table.setRowCount(len(results))
        
        total_score = 0
        max_score_total = 0
        
        for i, (qid, score) in enumerate(results.items()):
            # Question number
            id_item = QTableWidgetItem(str(qid))
            id_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, id_item)
            
            # Score display
            score_display = f"{score:.1f}" if score % 1 else f"{int(score)}"
            score_item = QTableWidgetItem(score_display)
            score_item.setTextAlignment(Qt.AlignCenter)
            
            # Find max score
            max_q_score = 0
            if self.exam_data and "answers" in self.exam_data:
                for q in self.exam_data["answers"]:
                    if str(q.get("question_id")) == str(qid):
                        max_q_score = q.get("score", q.get("points", 0))
                        break
            
            # Color coding
            if max_q_score > 0:
                percentage = score / max_q_score
                if percentage >= 0.9:
                    score_item.setForeground(QColor(76, 175, 80))
                elif percentage >= 0.6:
                    score_item.setForeground(QColor(255, 152, 0))
                else:
                    score_item.setForeground(QColor(244, 67, 54))
            
            self.table.setItem(i, 1, score_item)
            
            # Max score
            max_item = QTableWidgetItem(f"{max_q_score}")
            max_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 2, max_item)
            
            total_score += score
            max_score_total += max_q_score
            
            # Score edit widget
            edit = QLineEdit(str(score))
            edit.setAlignment(Qt.AlignCenter)
            edit.setMaximumWidth(100)
            edit.editingFinished.connect(lambda checked, row=i: self._update_scores(row))
            self.table.setCellWidget(i, 3, edit)
        
        total_display = f"{total_score:.1f}" if total_score % 1 else f"{int(total_score)}"
        self.total_score_label.setText(f"Total: {total_display} / {max_score_total} points")
        
        self.table.resizeColumnsToContents()
    
    def _clear_table(self):
        self.table.setRowCount(0)
        self.total_score_label.setText("Total: - / - points")
    
    def _update_scores(self, row):
        widget = self.table.cellWidget(row, 3)
        if widget:
            try:
                new_score = float(widget.text())
                formatted_score = f"{new_score:.1f}" if new_score % 1 else f"{int(new_score)}"
                score_item = QTableWidgetItem(formatted_score)
                score_item.setTextAlignment(Qt.AlignCenter)
                
                qid = self.table.item(row, 0).text()
                
                # Update color
                max_q_score = 0
                if self.exam_data and "answers" in self.exam_data:
                    for q in self.exam_data["answers"]:
                        if str(q.get("question_id")) == str(qid):
                            max_q_score = q.get("score", q.get("points", 0))
                            break
                
                if max_q_score > 0:
                    percentage = new_score / max_q_score
                    if percentage >= 0.9:
                        score_item.setForeground(QColor(76, 175, 80))
                    elif percentage >= 0.6:
                        score_item.setForeground(QColor(255, 152, 0))
                    else:
                        score_item.setForeground(QColor(244, 67, 54))
                
                self.table.setItem(row, 1, score_item)
                
                # Update stored results
                if self.current_image_path in self.grading_results:
                    qid_int = int(qid)
                    self.grading_results[self.current_image_path]['results'][qid_int] = new_score
                    
                    new_total = sum(self.grading_results[self.current_image_path]['results'].values())
                    self.grading_results[self.current_image_path]['total'] = new_total
                    
                    total_display = f"{new_total:.1f}" if new_total % 1 else f"{int(new_total)}"
                    max_total = self.grading_results[self.current_image_path]['max']
                    self.total_score_label.setText(f"Total: {total_display} / {max_total} points")
                    self.grading_status_label.setText(f"✅ Score updated: {total_display} / {max_total}")
                
            except ValueError:
                original = self.table.item(row, 1).text()
                widget.setText(original)
                QMessageBox.warning(self, "Error", "Please enter a valid number.")
    
    def export_results(self):
        if not self.grading_results:
            QMessageBox.warning(self, "Warning", "No grading results to export.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Results", "", "JSON (*.json);;CSV (*.csv)")
        if not file_path:
            return
        
        try:
            export_data = {
                'exam_title': self.exam_data.get('exam_title', 'Unknown') if self.exam_data else 'Unknown',
                'results': []
            }
            
            for img_path, data in self.grading_results.items():
                export_data['results'].append({
                    'filename': data['filename'],
                    'total_score': data['total'],
                    'max_score': data['max'],
                    'percentage': (data['total'] / data['max'] * 100) if data['max'] > 0 else 0,
                    'question_scores': data.get('results', {})
                })
            
            self.result_exporter.export_results(export_data, file_path)
            
            QMessageBox.information(self, "Success", f"Results exported successfully!\n{file_path}")
            self.statusBar().showMessage(f"Results exported to {os.path.basename(file_path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export results:\n{str(e)}")
    
    def clear_results(self):
        reply = QMessageBox.question(self, "Clear Results", 
            "Clear all grading results?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.grading_results.clear()
            self._clear_table()
            self.grading_status_label.setText("Results cleared")
            self.statusBar().showMessage("All grading results cleared")
            QMessageBox.information(self, "Complete", "All grading results have been cleared.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = GraderApp()
    window.show()
    sys.exit(app.exec_())