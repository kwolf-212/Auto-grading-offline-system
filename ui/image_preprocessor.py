# ui/image_preprocessor.py (수정)
import cv2
import numpy as np
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage
import os
import re


# ============= 전처리 함수들 (별도 사용 가능) =============

def auto_rotate(img):
    """자동 회전 (문서 방향 감지)"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if contours:
        largest = max(contours, key=cv2.contourArea)
        rect = cv2.minAreaRect(largest)
        angle = rect[2]
        
        if abs(angle) > 45:
            angle = 90 - abs(angle)
        
        if abs(angle) > 10:
            center = (img.shape[1] // 2, img.shape[0] // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(img, matrix, (img.shape[1], img.shape[0]), 
                                 flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return img


def extract_document_area(img):
    """문서 영역 추출 (자동 크롭)"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return img, None
    
    largest = max(contours, key=cv2.contourArea)
    epsilon = 0.02 * cv2.arcLength(largest, True)
    approx = cv2.approxPolyDP(largest, epsilon, True)
    
    if len(approx) == 4:
        pts = approx.reshape(4, 2)
        rect = order_points(pts)
        x, y, w, h = cv2.boundingRect(largest)
        margin = 20
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(img.shape[1] - x, w + margin * 2)
        h = min(img.shape[0] - y, h + margin * 2)
        cropped = img[y:y+h, x:x+w]
        return cropped, rect
    else:
        x, y, w, h = cv2.boundingRect(largest)
        margin = 50
        x = max(0, x - margin)
        y = max(0, y - margin)
        w = min(img.shape[1] - x, w + margin * 2)
        h = min(img.shape[0] - y, h + margin * 2)
        cropped = img[y:y+h, x:x+w]
        return cropped, None


def order_points(pts):
    """꼭지점 정렬 (좌상, 우상, 우하, 좌하 순서)"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def perspective_correction(img, bbox):
    """원근 변환 보정"""
    if bbox is None:
        return img
    
    (tl, tr, br, bl) = bbox
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = max(int(heightA), int(heightB))
    
    if maxWidth <= 0 or maxHeight <= 0:
        return img
    
    dst = np.array([
        [0, 0],
        [maxWidth - 1, 0],
        [maxWidth - 1, maxHeight - 1],
        [0, maxHeight - 1]
    ], dtype="float32")
    
    M = cv2.getPerspectiveTransform(bbox, dst)
    warped = cv2.warpPerspective(img, M, (maxWidth, maxHeight))
    return warped


def deskew(img):
    """데스큐 (기울기 보정)"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    coords = np.column_stack(np.where(thresh > 0))
    
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        if abs(angle) > 0.5:
            (h, w) = img.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            img = cv2.warpAffine(img, M, (w, h), 
                                 flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return img


def enhance_image(img):
    """이미지 향상 (대비, 밝기, 노이즈 제거)"""
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    denoised = cv2.bilateralFilter(enhanced, 9, 75, 75)
    return cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)


def create_binary(img):
    """이진화"""
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def extract_student_info(img):
    """OCR로 학생 정보 추출"""
    info = {'name': '', 'student_id': '', 'department': ''}
    
    try:
        import pytesseract
        
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img
        
        h, w = gray.shape
        top_region = gray[0:int(h*0.3), 0:w]
        
        # 전처리
        top_region = cv2.resize(top_region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, top_region = cv2.threshold(top_region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        text = pytesseract.image_to_string(top_region, lang='eng+kor')
        
        patterns = {
            'name': r'(?:Name|이름|성명)\s*:?\s*([가-힣A-Za-z\s]+)',
            'student_id': r'(?:ID|Student ID|학번|학생번호)\s*:?\s*([A-Z0-9\-]+)',
            'department': r'(?:Dept|Department|학과|소속)\s*:?\s*([가-힣A-Za-z\s]+)'
        }
        
        for line in text.split('\n'):
            for key, pattern in patterns.items():
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value and len(value) < 50:
                        info[key] = value
        
        return info, text
        
    except ImportError:
        return info, "pytesseract not installed.\nInstall: pip install pytesseract"
    except Exception as e:
        return info, f"OCR Error: {str(e)}"


# ============= PreprocessWorker 클래스 =============

class PreprocessWorker(QThread):
    """이미지 전처리 작업자 스레드"""
    
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, image_paths, output_dir=None):
        super().__init__()
        self.image_paths = image_paths
        self.output_dir = output_dir or os.path.join(os.path.dirname(image_paths[0]), "processed")
        self.cancel = False
    
    def run(self):
        processed_files = []
        
        for idx, img_path in enumerate(self.image_paths):
            if self.cancel:
                break
            
            self.progress.emit(int((idx / len(self.image_paths)) * 100), f"Processing {os.path.basename(img_path)}")
            
            try:
                result = self.process_single_image(img_path)
                if result:
                    processed_files.append(result)
            except Exception as e:
                self.error.emit(f"Failed to process {img_path}: {str(e)}")
        
        self.finished.emit(processed_files)
    
    def process_single_image(self, img_path):
        """단일 이미지 처리"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        img = cv2.imread(img_path)
        if img is None:
            raise ValueError(f"Cannot read image: {img_path}")
        
        # 전처리 단계별 실행
        img = auto_rotate(img)
        img, bbox = extract_document_area(img)
        img = perspective_correction(img, bbox) if bbox is not None else img
        img = deskew(img)
        img = enhance_image(img)
        student_info, _ = extract_student_info(img)
        
        output_filename = f"processed_{os.path.basename(img_path)}"
        output_path = os.path.join(self.output_dir, output_filename)
        cv2.imwrite(output_path, img)
        
        return (img_path, output_path, student_info)


# ============= PreprocessDialog 클래스 =============

class PreprocessDialog(QDialog):
    """이미지 전처리 대화상자"""
    
    def __init__(self, image_paths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔧 Image Preprocessing")
        self.setGeometry(400, 300, 600, 400)
        
        self.image_paths = image_paths
        self.processed_files = []
        self.worker = None
        
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        info_label = QLabel("Preprocessing will perform:\n"
                           "• Auto rotation (문서 방향 자동 보정)\n"
                           "• Document area extraction (문서 영역 추출)\n"
                           "• Perspective correction (원근 보정)\n"
                           "• Deskew (기울기 보정)\n"
                           "• Image enhancement (이미지 품질 향상)\n"
                           "• Student info extraction (학생 정보 추출)")
        info_label.setStyleSheet("background-color: #252526; padding: 10px; border-radius: 8px;")
        layout.addWidget(info_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.result_list = QListWidget()
        self.result_list.setVisible(False)
        layout.addWidget(self.result_list)
        
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("▶ Start Preprocessing")
        self.start_btn.clicked.connect(self.start_preprocessing)
        button_layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_preprocessing)
        button_layout.addWidget(self.cancel_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setEnabled(False)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def start_preprocessing(self):
        self.start_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Processing...")
        self.result_list.clear()
        self.result_list.setVisible(True)
        
        self.worker = PreprocessWorker(self.image_paths)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
    
    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
    
    def on_finished(self, processed_files):
        self.processed_files = processed_files
        self.progress_bar.setValue(100)
        self.status_label.setText(f"✅ Completed! Processed {len(processed_files)} images.")
        
        for original, processed, info in processed_files:
            item_text = f"✓ {os.path.basename(original)} → {os.path.basename(processed)}"
            if info.get('name'):
                item_text += f" | Student: {info['name']}"
            self.result_list.addItem(item_text)
        
        self.start_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
    
    def on_error(self, error_msg):
        self.status_label.setText(f"❌ Error: {error_msg}")
        QMessageBox.warning(self, "Error", error_msg)
    
    def cancel_preprocessing(self):
        if self.worker:
            self.worker.cancel = True
            self.worker.quit()
            self.worker.wait()
        
        self.status_label.setText("Cancelled")
        self.start_btn.setEnabled(True)