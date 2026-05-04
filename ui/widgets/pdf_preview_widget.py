# ui/widgets/pdf_preview_widget.py
import os
import tempfile
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QTimer, QRect

try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


class PDFPreviewLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: #f5f5f5;
                border: none;
            }
        """)
        self.setMinimumHeight(550)
        self.setScaledContents(False)
        self.pdf_rect = None
        self.parent_widget = parent
        self.drag_start_pos = None
        self.drag_start_scroll = None
        
    def set_pdf_rect(self, rect):
        self.pdf_rect = rect
        self.update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.pdf_rect and not self.pdf_rect.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            shadow_rect = QRect(self.pdf_rect.x() + 2, self.pdf_rect.y() + 2, 
                                self.pdf_rect.width(), self.pdf_rect.height())
            painter.fillRect(shadow_rect, QColor(0, 0, 0, 30))
            pen = QPen(QColor(33, 150, 243), 3)
            painter.setPen(pen)
            painter.drawRect(self.pdf_rect)
            pen2 = QPen(QColor(33, 150, 243, 100), 1)
            painter.setPen(pen2)
            painter.drawRect(self.pdf_rect.adjusted(1, 1, -1, -1))
            painter.end()
    
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            super().wheelEvent(event)
        else:
            delta = event.angleDelta().y()
            if delta > 0:
                self.parent().prev_page() if hasattr(self.parent(), 'prev_page') else None
            else:
                self.parent().next_page() if hasattr(self.parent(), 'next_page') else None


class PDFPreviewLabelEnhanced(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.setStyleSheet("""
            QLabel {
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 8px;
            }
        """)
        self.setMinimumSize(100, 100)
        self.drag_start_pos = None
        self.drag_start_scroll = None
        self.setMouseTracking(True)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.globalPos()
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            if scroll_area:
                self.drag_start_scroll = scroll_area.horizontalScrollBar().value(), scroll_area.verticalScrollBar().value()
            self.setCursor(Qt.ClosedHandCursor)
            
    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton and self.drag_start_pos and self.drag_start_scroll:
            delta = event.globalPos() - self.drag_start_pos
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            if scroll_area:
                scroll_area.horizontalScrollBar().setValue(self.drag_start_scroll[0] - delta.x())
                scroll_area.verticalScrollBar().setValue(self.drag_start_scroll[1] - delta.y())
                
    def mouseReleaseEvent(self, event):
        self.drag_start_pos = None
        self.drag_start_scroll = None
        self.setCursor(Qt.ArrowCursor)
        
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            super().wheelEvent(event)
        else:
            scroll_area = self.parent()
            while scroll_area and not isinstance(scroll_area, QScrollArea):
                scroll_area = scroll_area.parent()
            if scroll_area:
                QApplication.sendEvent(scroll_area.viewport(), event)


class PDFPreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_pdf_path = None
        self.current_page = 0
        self.total_pages = 0
        self.zoom_factor = 1.0
        self.fit_mode = "none"
        self.original_pixmap = None
        self.saved_page = 0
        self.init_ui()
        self.last_scroll_pos = None
        
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        toolbar_widget = QWidget()
        toolbar_widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border-radius: 8px;
                margin: 2px;
            }
        """)
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(10, 5, 10, 5)
        toolbar_layout.setSpacing(8)
        
        icon_button_style = """
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
            QPushButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
        """
        
        small_button_style = """
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 40px;
                max-width: 40px;
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
        """
        
        self.zoom_value = QLabel("100%")
        self.zoom_value.setFixedWidth(55)
        self.zoom_value.setAlignment(Qt.AlignCenter)
        self.zoom_value.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #555;
            border-radius: 6px;
            padding: 5px;
        """)
        
        self.zoom_out_btn = QPushButton("🔍−")
        self.zoom_out_btn.setToolTip("Zoom Out (Ctrl+Scroll Down)")
        self.zoom_out_btn.setStyleSheet(small_button_style)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        
        self.zoom_in_btn = QPushButton("🔍+")
        self.zoom_in_btn.setToolTip("Zoom In (Ctrl+Scroll Up)")
        self.zoom_in_btn.setStyleSheet(small_button_style)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        
        self.reset_zoom_btn = QPushButton("↺")
        self.reset_zoom_btn.setToolTip("Reset to 100%")
        self.reset_zoom_btn.setStyleSheet("""
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
        """)
        self.reset_zoom_btn.clicked.connect(self.reset_zoom)
        
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.VLine)
        separator1.setFrameShadow(QFrame.Sunken)
        separator1.setFixedSize(2, 30)
        separator1.setStyleSheet("background-color: #555;")
        
        self.fit_width_btn = QPushButton("⬌")
        self.fit_width_btn.setToolTip("Fit to Width")
        self.fit_width_btn.setStyleSheet(icon_button_style)
        self.fit_width_btn.clicked.connect(self.fit_to_width)
        
        self.fit_height_btn = QPushButton("⬍")
        self.fit_height_btn.setToolTip("Fit to Height")
        self.fit_height_btn.setStyleSheet(icon_button_style)
        self.fit_height_btn.clicked.connect(self.fit_to_height)
        
        self.fit_page_btn = QPushButton("⊞")
        self.fit_page_btn.setToolTip("Fit to Page")
        self.fit_page_btn.setStyleSheet(icon_button_style)
        self.fit_page_btn.clicked.connect(self.fit_to_page)
        
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.VLine)
        separator2.setFrameShadow(QFrame.Sunken)
        separator2.setFixedSize(2, 30)
        separator2.setStyleSheet("background-color: #555;")
        
        self.prev_btn = QPushButton("◀")
        self.prev_btn.setToolTip("Previous Page (←)")
        self.prev_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 50px;
                max-width: 50px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
            QPushButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
        """)
        self.prev_btn.clicked.connect(self.prev_page)
        
        self.page_label = QLabel("1 / 1")
        self.page_label.setFixedWidth(70)
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet("""
            font-size: 13px;
            font-weight: bold;
            background-color: #1e1e1e;
            color: #ffffff;
            border: 1px solid #555;
            border-radius: 6px;
            padding: 5px;
        """)
        
        self.next_btn = QPushButton("▶")
        self.next_btn.setToolTip("Next Page (→)")
        self.next_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #3c3c3c;
                border: 1px solid #555;
                border-radius: 6px;
                padding: 4px;
                min-width: 50px;
                max-width: 50px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #4a4a4a;
                border: 1px solid #007acc;
            }
            QPushButton:disabled {
                color: #666;
                background-color: #2a2a2a;
            }
        """)
        self.next_btn.clicked.connect(self.next_page)
                
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setToolTip("Refresh Preview")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                font-size: 18px;
                font-weight: bold;
                background-color: #007acc;
                border: 1px solid #005a9e;
                border-radius: 6px;
                padding: 4px;
                min-width: 44px;
                max-width: 44px;
                min-height: 36px;
                max-height: 36px;
                color: #ffffff;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        self.refresh_btn.clicked.connect(self.refresh_preview)
        
        toolbar_layout.addWidget(self.zoom_out_btn)
        toolbar_layout.addWidget(self.zoom_value)
        toolbar_layout.addWidget(self.zoom_in_btn)
        toolbar_layout.addWidget(self.reset_zoom_btn)
        toolbar_layout.addWidget(separator1)
        toolbar_layout.addWidget(self.fit_width_btn)
        toolbar_layout.addWidget(self.fit_height_btn)
        toolbar_layout.addWidget(self.fit_page_btn)
        toolbar_layout.addWidget(separator2)
        toolbar_layout.addWidget(self.prev_btn)
        toolbar_layout.addWidget(self.page_label)
        toolbar_layout.addWidget(self.next_btn)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.refresh_btn)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
        """)
        
        self.preview_label = PDFPreviewLabelEnhanced(self)
        self.preview_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
        """)
        self.scroll_area.setWidget(self.preview_label)
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #cccccc; padding: 5px; font-size: 11px; background-color: #1e1e1e; border-radius: 4px;")
        
        layout.addWidget(toolbar_widget)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        self.update_navigation_buttons()
        self.preview_label.setMouseTracking(True)

    def refresh_preview(self):
        if hasattr(self.parent(), 'generate_live_preview'):
            self.parent().generate_live_preview() 
    
    def zoom_in(self):
        current = int(self.zoom_value.text().rstrip('%'))
        new_value = min(300, current + 10)
        self.zoom_value.setText(f"{new_value}%")
        self.zoom_factor = new_value / 100.0
        self.fit_mode = "none"
        self.update_preview()
        
    def zoom_out(self):
        current = int(self.zoom_value.text().rstrip('%'))
        new_value = max(30, current - 10)
        self.zoom_value.setText(f"{new_value}%")
        self.zoom_factor = new_value / 100.0
        self.fit_mode = "none"
        self.update_preview()
        
    def reset_zoom(self):
        self.zoom_value.setText("100%")
        self.zoom_factor = 1.0
        self.fit_mode = "none"
        self.update_preview()
        
    def fit_to_width(self):
        if not self.original_pixmap:
            return
        self.fit_mode = "width"
        available_width = self.scroll_area.viewport().width() - 20
        if available_width > 0:
            target_width = available_width
            zoom_percent = int((target_width / self.original_pixmap.width()) * 100)
            zoom_percent = min(300, max(30, zoom_percent))
            self.zoom_value.setText(f"{zoom_percent}%")
            self.zoom_factor = zoom_percent / 100.0
            self.update_preview()
            
    def fit_to_height(self):
        if not self.original_pixmap:
            return
        self.fit_mode = "height"
        available_height = self.scroll_area.viewport().height() - 20
        if available_height > 0:
            target_height = available_height
            zoom_percent = int((target_height / self.original_pixmap.height()) * 100)
            zoom_percent = min(300, max(30, zoom_percent))
            self.zoom_value.setText(f"{zoom_percent}%")
            self.zoom_factor = zoom_percent / 100.0
            self.update_preview()
            
    def fit_to_page(self):
        if not self.original_pixmap:
            return
        self.fit_mode = "page"
        available_width = self.scroll_area.viewport().width() - 20
        available_height = self.scroll_area.viewport().height() - 20
        
        if available_width > 0 and available_height > 0:
            width_ratio = available_width / self.original_pixmap.width()
            height_ratio = available_height / self.original_pixmap.height()
            zoom_ratio = min(width_ratio, height_ratio)
            zoom_percent = int(zoom_ratio * 100)
            zoom_percent = min(300, max(30, zoom_percent))
            self.zoom_value.setText(f"{zoom_percent}%")
            self.zoom_factor = zoom_percent / 100.0
            self.update_preview()
            
    def set_preview_image(self, pixmap):
        if pixmap and not pixmap.isNull():
            self.original_pixmap = pixmap
            zoom = self.zoom_factor
            original_width = pixmap.width()
            original_height = pixmap.height()
            
            scaled_pixmap = pixmap.scaled(
                int(original_width * zoom),
                int(original_height * zoom),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            
            self.preview_label.setPixmap(scaled_pixmap)
            self.preview_label.setFixedSize(scaled_pixmap.size())
            
            zoom_percent = int(zoom * 100)
            self.status_label.setText(f"✅ Page {self.current_page + 1} | Zoom: {zoom_percent}% | Size: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
        else:
            self.original_pixmap = None
            self.preview_label.setText("📄 No preview available\n\nClick 'Refresh' to generate PDF preview")
            self.preview_label.setFixedSize(400, 300)
            self.status_label.setText("No preview available")
                    
    def update_navigation_buttons(self):
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
        self.page_label.setText(f"{self.current_page + 1} / {max(1, self.total_pages)}")
        
    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_preview()
            
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self.update_preview()
            
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            QApplication.sendEvent(self.scroll_area.viewport(), event)
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Left:
            self.prev_page()
        elif event.key() == Qt.Key_Right:
            self.next_page()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key_Home:
            self.current_page = 0
            self.update_preview()
        elif event.key() == Qt.Key_End:
            self.current_page = self.total_pages - 1
            self.update_preview()
        elif event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_W:
                self.fit_to_width()
            elif event.key() == Qt.Key_H:
                self.fit_to_height()
            elif event.key() == Qt.Key_F:
                self.fit_to_page()
            elif event.key() == Qt.Key_R:
                self.refresh_btn.click()
        else:
            super().keyPressEvent(event)
            
    def update_preview(self):
        if not self.current_pdf_path or not os.path.exists(self.current_pdf_path):
            self.preview_label.setText("📄 No PDF generated yet.\n\nAdd questions and click 'Refresh' to see preview.")
            self.status_label.setText("No PDF file available")
            self.current_page = 0
            self.total_pages = 0
            self.update_navigation_buttons()
            return
            
        if not PYMUPDF_AVAILABLE:
            file_size = os.path.getsize(self.current_pdf_path) / 1024
            self.preview_label.setText(
                f"📄 PDF File: {os.path.basename(self.current_pdf_path)}\n"
                f"📊 Size: {file_size:.1f} KB\n"
                f"📑 Pages: {self.total_pages}\n\n"
                f"⚠️ Install PyMuPDF for actual preview:\n"
                f"💻 pip install PyMuPDF"
            )
            self.status_label.setText("PyMuPDF not installed")
            return
            
        try:
            doc = fitz.open(self.current_pdf_path)
            self.total_pages = len(doc)
            
            if self.current_page >= self.total_pages:
                self.current_page = 0
                
            self.update_navigation_buttons()
            
            if self.total_pages > 0:
                current_scroll = self.scroll_area.verticalScrollBar().value()

                page = doc[self.current_page]
                zoom_matrix = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=zoom_matrix, alpha=False)
                
                img_data = pix.tobytes("png")
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                
                self.set_preview_image(pixmap)
                
                if current_scroll > 0:
                    QTimer.singleShot(50, lambda: self.scroll_area.verticalScrollBar().setValue(current_scroll))
            else:
                self.preview_label.setText("PDF has no pages")
                
            doc.close()
            
        except Exception as e:
            self.status_label.setText(f"Preview error: {str(e)}")
            self.preview_label.setText(f"Failed to render PDF preview.\n\nError: {str(e)}")
            self.current_page = 0
            self.total_pages = 0
            self.update_navigation_buttons()
            
    def load_pdf(self, pdf_path):
        self.current_pdf_path = pdf_path
        self.current_page = self.saved_page if hasattr(self, 'saved_page') else 0
        self.total_pages = 0
        self.update_preview()

    def save_current_page(self):
        self.saved_page = self.current_page