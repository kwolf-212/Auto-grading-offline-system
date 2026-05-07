# ui/image_preprocessor_tester.py
import sys
import cv2
import numpy as np
import os
import re
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont

# image_preprocessor에서 전처리 함수들 import
from ui.image_preprocessor import (
    auto_rotate, extract_document_area, perspective_correction,
    deskew, enhance_image, create_binary, extract_student_info
)


class PreprocessTester(QMainWindow):
    """이미지 전처리 단계별 테스터"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔬 Image Preprocessor Tester")
        self.setGeometry(100, 100, 1400, 900)
        
        self.current_image = None
        self.original_image = None
        self.processed_images = {}  # stage_name -> image
        self.current_image_path = None
        self.last_bbox = None  # 마지막으로 추출된 bbox 저장
        
        self.init_ui()
        self.apply_style()
    
    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QGroupBox {
                font-weight: bold;
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
                padding: 0 5px;
                color: #007acc;
            }
            QPushButton {
                background-color: #0d7377;
                color: white;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background-color: #14a085; }
            QPushButton#primary { background-color: #007acc; }
            QPushButton#primary:hover { background-color: #005a9e; }
            QLabel { color: #e0e0e0; }
            QTextEdit {
                background-color: #252526;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                color: #e0e0e0;
                font-family: monospace;
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk { background-color: #007acc; border-radius: 6px; }
            QTabWidget::pane { border: 1px solid #3d3d3d; background-color: #1e1e1e; }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #e0e0e0;
                padding: 8px 12px;
                margin-right: 2px;
            }
            QTabBar::tab:selected { background-color: #007acc; color: white; }
            QTabBar::tab:hover:!selected { background-color: #3d3d3d; }
        """)
    
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        left_panel = self._create_image_panel()
        right_panel = self._create_control_panel()
        
        main_layout.addWidget(left_panel, 5)
        main_layout.addWidget(right_panel, 3)
        
        self.statusBar().showMessage("Ready. Load an image to begin.")
    
    def _create_image_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        title = QLabel("📷 Image Processing Stages")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; padding: 5px;")
        layout.addWidget(title)
        
        self.stage_tabs = QTabWidget()
        self.stage_tabs.setTabPosition(QTabWidget.North)
        
        self.tab_labels = []
        # Original 단계 제거 (6개 단계)
        stage_names = [
            "1. Auto Rotate", "2. Document Area",
            "3. Perspective", "4. Deskew", "5. Enhanced", "6. Final Binary"
        ]
        
        for name in stage_names:
            tab_widget, label = self._create_image_tab()
            self.stage_tabs.addTab(tab_widget, name)
            self.tab_labels.append(label)
        
        layout.addWidget(self.stage_tabs)
        
        self.image_info_label = QLabel("Image: -")
        self.image_info_label.setAlignment(Qt.AlignCenter)
        self.image_info_label.setStyleSheet("font-size: 11px; color: #888; padding: 5px;")
        layout.addWidget(self.image_info_label)
        
        return panel
    
    def _create_image_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        label.setMinimumHeight(500)
        label.setStyleSheet("""
            background-color: #1a1a1a;
            border: 1px solid #3d3d3d;
            border-radius: 8px;
        """)
        label.setScaledContents(False)
        
        layout.addWidget(label)
        return widget, label
    
    def _get_tab_label(self, tab_index):
        if 0 <= tab_index < len(self.tab_labels):
            return self.tab_labels[tab_index]
        return None
    
    def _create_control_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        
        # File Controls
        file_group = QGroupBox("File Controls")
        file_layout = QVBoxLayout(file_group)
        btn_load = QPushButton("📂 Load Image")
        btn_load.setObjectName("primary")
        btn_load.clicked.connect(self.load_image)
        file_layout.addWidget(btn_load)
        self.file_label = QLabel("No file loaded")
        self.file_label.setStyleSheet("font-size: 11px; color: #888;")
        file_layout.addWidget(self.file_label)
        layout.addWidget(file_group)
        
        # Process Controls
        process_group = QGroupBox("Processing")
        process_layout = QVBoxLayout(process_group)
        
        self.process_all_btn = QPushButton("▶ Run All Stages")
        self.process_all_btn.setObjectName("primary")
        self.process_all_btn.clicked.connect(self.process_all_stages)
        process_layout.addWidget(self.process_all_btn)
        
        stages_layout = QGridLayout()
        stages_layout.setSpacing(5)
        
        # 6개 단계 버튼 (Original 제거)
        self.btn_stage1 = QPushButton("1. Auto Rotate")
        self.btn_stage1.clicked.connect(lambda: self.run_single_stage(1))
        stages_layout.addWidget(self.btn_stage1, 0, 0)
        
        self.btn_stage2 = QPushButton("2. Document Area")
        self.btn_stage2.clicked.connect(lambda: self.run_single_stage(2))
        stages_layout.addWidget(self.btn_stage2, 0, 1)
        
        self.btn_stage3 = QPushButton("3. Perspective")
        self.btn_stage3.clicked.connect(lambda: self.run_single_stage(3))
        stages_layout.addWidget(self.btn_stage3, 1, 0)
        
        self.btn_stage4 = QPushButton("4. Deskew")
        self.btn_stage4.clicked.connect(lambda: self.run_single_stage(4))
        stages_layout.addWidget(self.btn_stage4, 1, 1)
        
        self.btn_stage5 = QPushButton("5. Enhance")
        self.btn_stage5.clicked.connect(lambda: self.run_single_stage(5))
        stages_layout.addWidget(self.btn_stage5, 2, 0)
        
        self.btn_stage6 = QPushButton("6. Final Binary")
        self.btn_stage6.clicked.connect(lambda: self.run_single_stage(6))
        stages_layout.addWidget(self.btn_stage6, 2, 1)
        
        process_layout.addLayout(stages_layout)
        layout.addWidget(process_group)
        
        # OCR Results
        ocr_group = QGroupBox("OCR Results (Student Info)")
        ocr_layout = QVBoxLayout(ocr_group)
        
        self.ocr_text = QTextEdit()
        self.ocr_text.setReadOnly(True)
        self.ocr_text.setMaximumHeight(150)
        ocr_layout.addWidget(self.ocr_text)
        
        info_layout = QFormLayout()
        self.name_label = QLabel("-")
        self.name_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        info_layout.addRow("Name:", self.name_label)
        
        self.student_id_label = QLabel("-")
        self.student_id_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        info_layout.addRow("Student ID:", self.student_id_label)
        
        self.dept_label = QLabel("-")
        self.dept_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        info_layout.addRow("Department:", self.dept_label)
        
        ocr_layout.addLayout(info_layout)
        layout.addWidget(ocr_group)
        
        # Processing Info
        info_group = QGroupBox("Processing Info")
        info_layout = QVBoxLayout(info_group)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        info_layout.addWidget(self.progress_bar)
        
        self.status_text = QTextEdit()
        self.status_text.setReadOnly(True)
        self.status_text.setMaximumHeight(100)
        self.status_text.setFont(QFont("Consolas", 9))
        info_layout.addWidget(self.status_text)
        
        self.time_label = QLabel("Processing time: -")
        self.time_label.setStyleSheet("font-size: 11px; color: #888;")
        info_layout.addWidget(self.time_label)
        
        layout.addWidget(info_group)
        
        export_btn = QPushButton("💾 Save Processed Image")
        export_btn.clicked.connect(self.save_processed_image)
        layout.addWidget(export_btn)
        
        layout.addStretch()
        return panel
    
    def load_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image", "", 
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff *.tif)"
        )
        
        if file_path:
            self.current_image_path = file_path
            self.original_image = cv2.imread(file_path)
            
            if self.original_image is None:
                QMessageBox.critical(self, "Error", f"Cannot read image: {file_path}")
                return
            
            self.current_image = self.original_image.copy()
            self.processed_images = {'original': self.original_image.copy()}
            self.last_bbox = None
            
            # 모든 탭 초기화 (6개 탭)
            for i in range(6):
                self._clear_tab_image(i)
            
            h, w = self.original_image.shape[:2]
            size_kb = os.path.getsize(file_path) / 1024
            self.file_label.setText(f"{os.path.basename(file_path)} ({w}x{h}, {size_kb:.1f} KB)")
            self.image_info_label.setText(f"Original: {w} x {h}")
            
            self.statusBar().showMessage(f"Loaded: {os.path.basename(file_path)}")
            self._add_status(f"✅ Loaded image: {os.path.basename(file_path)} ({w}x{h})")
    
    def _display_image_to_tab(self, tab_index, image):
        label = self._get_tab_label(tab_index)
        if label is None or image is None:
            return
        
        if len(image.shape) == 2:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        else:
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        h, w = rgb_image.shape[:2]
        label_width = label.width() - 20
        label_height = label.height() - 20
        
        if label_width > 0 and label_height > 0 and w > 0 and h > 0:
            scale = min(label_width / w, label_height / h)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            resized = cv2.resize(rgb_image, (new_w, new_h))
        else:
            resized = rgb_image
        
        bytes_per_line = 3 * resized.shape[1]
        qimage = QImage(resized.data, resized.shape[1], resized.shape[0], 
                        bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qimage)
        
        label.setPixmap(pixmap)
        label.setText("")
    
    def _clear_tab_image(self, tab_index):
        label = self._get_tab_label(tab_index)
        if label:
            label.setText("Not processed yet")
            label.setPixmap(QPixmap())
    
    def _add_status(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.status_text.append(f"[{timestamp}] {message}")
        scrollbar = self.status_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def process_all_stages(self):
        if self.original_image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
            return
        
        self.process_all_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._add_status("🚀 Starting full preprocessing pipeline...")
        
        import time
        start_time = time.time()
        
        try:
            # Stage 1: Auto Rotate (using imported function)
            self._add_status("  Stage 1: Auto Rotating...")
            rotated = auto_rotate(self.original_image)
            self.processed_images['rotated'] = rotated
            self._display_image_to_tab(0, rotated)
            self._add_status("    ✓ Auto rotate completed")
            self.progress_bar.setValue(15)
            QApplication.processEvents()
            
            # Stage 2: Document Area Extraction (using imported function)
            self._add_status("  Stage 2: Extracting document area...")
            doc_area, bbox = extract_document_area(rotated)
            self.processed_images['document'] = doc_area
            self.last_bbox = bbox
            self._display_image_to_tab(1, doc_area)
            self._add_status(f"    ✓ Document area extracted (4 corners: {bbox is not None})")
            self.progress_bar.setValue(35)
            QApplication.processEvents()
            
            # Stage 3: Perspective Correction (using imported function)
            self._add_status("  Stage 3: Applying perspective correction...")
            perspective = perspective_correction(doc_area, bbox) if bbox is not None else doc_area
            self.processed_images['perspective'] = perspective
            self._display_image_to_tab(2, perspective)
            self._add_status("    ✓ Perspective correction completed")
            self.progress_bar.setValue(50)
            QApplication.processEvents()
            
            # Stage 4: Deskew (using imported function)
            self._add_status("  Stage 4: Deskewing...")
            deskewed = deskew(perspective)
            self.processed_images['deskewed'] = deskewed
            self._display_image_to_tab(3, deskewed)
            self._add_status("    ✓ Deskew completed")
            self.progress_bar.setValue(65)
            QApplication.processEvents()
            
            # Stage 5: Image Enhancement (using imported function)
            self._add_status("  Stage 5: Enhancing image quality...")
            enhanced = enhance_image(deskewed)
            self.processed_images['enhanced'] = enhanced
            self._display_image_to_tab(4, enhanced)
            self._add_status("    ✓ Enhancement completed")
            self.progress_bar.setValue(80)
            QApplication.processEvents()
            
            # Stage 6: Final Binary (using imported function)
            self._add_status("  Stage 6: Creating final binary image...")
            binary = create_binary(enhanced)
            self.processed_images['binary'] = binary
            self._display_image_to_tab(5, binary)
            self._add_status("    ✓ Binary conversion completed")
            self.progress_bar.setValue(95)
            QApplication.processEvents()
            
            # OCR Extraction (using imported function)
            self._add_status("🔍 Extracting student info via OCR...")
            student_info, ocr_text = extract_student_info(enhanced)
            self.ocr_text.setText(ocr_text[:500] + ("..." if len(ocr_text) > 500 else ""))
            self._display_ocr_results(student_info)
            
            elapsed = time.time() - start_time
            self.time_label.setText(f"Processing time: {elapsed:.2f} seconds")
            self.progress_bar.setValue(100)
            
            self._add_status(f"✅ ALL STAGES COMPLETED! Total time: {elapsed:.2f}s")
            self.statusBar().showMessage(f"Processing completed in {elapsed:.2f}s")
            
        except Exception as e:
            self._add_status(f"❌ Error: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", str(e))
        finally:
            self.process_all_btn.setEnabled(True)
            QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
    
    def run_single_stage(self, stage):
        if self.original_image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
            return
        
        self._add_status(f"▶ Running stage {stage}...")
        
        try:
            if stage == 1:
                rotated = auto_rotate(self.original_image)
                self.processed_images['rotated'] = rotated
                self._display_image_to_tab(0, rotated)
                self._add_status("  Stage 1: Auto rotate completed")
            
            elif stage == 2:
                source = self.processed_images.get('rotated', self.original_image)
                doc_area, bbox = extract_document_area(source)
                self.processed_images['document'] = doc_area
                self.last_bbox = bbox
                self._display_image_to_tab(1, doc_area)
                self._add_status(f"  Stage 2: Document area extracted (4 corners: {bbox is not None})")
            
            elif stage == 3:
                source = self.processed_images.get('document', self.original_image)
                bbox = self.last_bbox
                perspective = perspective_correction(source, bbox) if bbox is not None else source
                self.processed_images['perspective'] = perspective
                self._display_image_to_tab(2, perspective)
                self._add_status("  Stage 3: Perspective correction completed")
            
            elif stage == 4:
                source = self.processed_images.get('perspective', self.original_image)
                deskewed = deskew(source)
                self.processed_images['deskewed'] = deskewed
                self._display_image_to_tab(3, deskewed)
                self._add_status("  Stage 4: Deskew completed")
            
            elif stage == 5:
                source = self.processed_images.get('deskewed', self.original_image)
                enhanced = enhance_image(source)
                self.processed_images['enhanced'] = enhanced
                self._display_image_to_tab(4, enhanced)
                self._add_status("  Stage 5: Image enhancement completed")
            
            elif stage == 6:
                source = self.processed_images.get('enhanced', self.original_image)
                binary = create_binary(source)
                self.processed_images['binary'] = binary
                self._display_image_to_tab(5, binary)
                self._add_status("  Stage 6: Binary conversion completed")
                
                # OCR 실행
                enhanced_source = self.processed_images.get('enhanced', source)
                student_info, ocr_text = extract_student_info(enhanced_source)
                self.ocr_text.setText(ocr_text[:500] + ("..." if len(ocr_text) > 500 else ""))
                self._display_ocr_results(student_info)
            
            self.statusBar().showMessage(f"Stage {stage} completed")
            
        except Exception as e:
            self._add_status(f"❌ Stage {stage} failed: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Stage {stage} failed:\n{str(e)}")
    
    def _display_ocr_results(self, info):
        self.name_label.setText(info.get('name', '-') or '-')
        self.student_id_label.setText(info.get('student_id', '-') or '-')
        self.dept_label.setText(info.get('department', '-') or '-')
        
        if info.get('name'):
            self._add_status(f"  📝 OCR extracted: Name={info['name']}, ID={info.get('student_id', 'N/A')}")
    
    def save_processed_image(self):
        current_tab = self.stage_tabs.currentIndex()
        stage_names = ["rotated", "document", "perspective", "deskewed", "enhanced", "binary"]
        
        image = None
        if 0 <= current_tab < len(stage_names):
            image = self.processed_images.get(stage_names[current_tab])
        
        if image is None:
            QMessageBox.warning(self, "Warning", "No processed image available for this stage.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Image", "", "PNG Image (*.png);;JPEG Image (*.jpg)"
        )
        
        if file_path:
            cv2.imwrite(file_path, image)
            self.statusBar().showMessage(f"Saved to {os.path.basename(file_path)}")
            self._add_status(f"💾 Saved {os.path.basename(file_path)}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    tester = PreprocessTester()
    tester.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()