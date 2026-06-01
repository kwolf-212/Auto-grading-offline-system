# test_grader_engine.py - ArUco 기준점 기반 선택지 영역 표시

import sys
import os
import json
import re
import cv2
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtGui import QFont, QColor, QPixmap, QImage, QPainter, QPen, QBrush
from PyQt5.QtCore import Qt, QSize, QRect, QThread, pyqtSignal, QTimer

from exam_grader.grader_engine import ExamGrader
from exam_grader.omr import ArUcoDetector  # convert_normalized_coordinates_from_json 제거
from exam_grader.image_preprocessor import ImagePreprocessor, preprocess_for_display


def _format_grading_debug_block(
    qtype: str,
    grading_debug: dict,
    region_text: str,
    *,
    result_text: str = "",
    student: str = "",
    correct: str = "",
    score: float = 0.0,
    max_score: float = 0.0,
) -> str:
    """채점 과정·결과를 한 블록으로 (디버그 패널 전용)."""
    lines = []

    if not grading_debug:
        hint = (result_text or "").strip()
        lines.append(f"[결과] {hint}" if hint else "[결과] 채점 전 · Grade 실행")
        return "\n".join(lines)

    sd = str(student or "").strip() or "—"
    cd = str(correct or "").strip() or "—"
    res = (result_text or "").strip() or "—"
    if max_score:
        pct = 100.0 * float(score) / float(max_score) if max_score else 0.0
        pts = f"{float(score):g}/{float(max_score):g} pts ({pct:.0f}%)"
    else:
        pts = f"{float(score):g} pts"
    lines.append(f"[결과] {res} · {pts} · 학생:{sd} · 정답:{cd}")

    ch = grading_debug.get("answer_channel", "")
    line1 = ""

    if ch == "image_primary":
        oa = grading_debug.get("omr_letter") or "—"
        oc = float(grading_debug.get("omr_confidence", 0))
        ta = grading_debug.get("ocr_parsed_letter") or "—"
        ms = grading_debug.get("merge_source", "?")
        od = grading_debug.get("omr_detail") or {}
        path = od.get("path", "?")
        ink = od.get("per_option_ink") or {}
        ink_s = ""
        if ink:
            ink_s = " " + " ".join(f"{k}:{float(v):.2f}" for k, v in sorted(ink.items()))
        rt = (region_text or "").strip()
        tail = f" · PDF텍스트 {len(rt)}자(참고)" if rt else ""
        line1 = f"[인식] OMR {oa} conf={oc:.2f} · OCR글자 {ta} · 병합:{ms} · 경로:{path}{ink_s}{tail}"
    elif ch == "text":
        n = grading_debug.get("region_text_len", len(region_text or ""))
        line1 = f"[인식] 텍스트/OCR 파싱 · 추출 {n}자"
    else:
        line1 = f"[인식] 채널:{ch or '?'}"

    sm = grading_debug.get("scoring_method_key") or "—"
    fb = (grading_debug.get("score_engine_feedback") or "").strip()
    ok = grading_debug.get("is_correct")
    mark = "○" if ok is True else ("×" if ok is False else "—")
    line2 = f"[엔진] 방식:{sm} 판정:{mark}" + (f" · {fb}" if fb else "")

    lines.extend([line1, line2])
    return "\n".join(lines)


try:
    import fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    import io
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class GradingWorker(QThread):
    progress = pyqtSignal(int, str)
    question_progress = pyqtSignal(int, int, str, str, str, float, str, str, object)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, exam_data, pdf_path, use_ocr=True, debug_mode=True):
        super().__init__()
        self.exam_data = exam_data
        self.pdf_path = pdf_path
        self.use_ocr = use_ocr
        self.debug_mode = debug_mode
    
    def run(self):
        try:
            self.progress.emit(10, "Loading PDF and preparing ArUco...")
            
            from exam_grader.grader_engine import ExamGrader
            # use_detection 파라미터 제거
            grader = ExamGrader(self.exam_data, debug_mode=self.debug_mode)
            
            result = grader.grade_from_pdf(self.pdf_path)
            
            total_questions = len(result['max_scores'])
            
            self.progress.emit(30, f"Grading {total_questions} questions...")
            
            for idx, qid in enumerate(sorted(result['max_scores'].keys())):
                student = result['student_answers'].get(qid, '')
                correct = result['correct_answers'].get(qid, '')
                score = result['scores'].get(qid, 0)
                max_score = result['max_scores'].get(qid, 0)
                qtype = result['question_types'].get(qid, "")
                
                if student and correct:
                    is_correct = (str(student).upper() == str(correct).upper())
                    result_text = "✓ 정답" if is_correct else "✗ 오답"
                elif student:
                    result_text = "⚠️ 답변 있음"
                else:
                    result_text = "❌ 미응답"
                
                gd = result.get("grading_debug", {}).get(qid, {})
                
                self.question_progress.emit(
                    qid, total_questions,
                    str(student) if student else "(없음)",
                    str(correct) if correct else "(없음)",
                    result_text, score, "", qtype,
                    gd,
                )
                
                progress_pct = 30 + int((idx + 1) / total_questions * 65)
                self.progress.emit(progress_pct, f"Grading Q{qid}...")
                self.msleep(20)
            
            self.progress.emit(100, "Complete!")
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))
            import traceback
            traceback.print_exc()
    

class PDFImageViewer(QLabel):
    """PDF 페이지 이미지 뷰어 - ArUco 기준 선택지 영역 표시"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.setMinimumSize(600, 800)
        self.setStyleSheet("""
            background-color: #1e1e1e;
            border: 1px solid #3d3d3d;
            border-radius: 8px;
        """)
        self.current_pixmap = None
        self.choice_rects = []
        self.aruco_detector = None
    
    
    def update_display(self):
        if self.current_pixmap:
            scaled = self.current_pixmap.scaled(
                self.width() - 20, self.height() - 20,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(scaled)
    
    def resizeEvent(self, event):
        if self.current_pixmap:
            scaled = self.current_pixmap.scaled(
                self.width() - 20, self.height() - 20,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.setPixmap(scaled)
        super().resizeEvent(event)


class QuestionDetailWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # ========== 헤더 (문제 번호 + 유형 + 점수) ==========
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        
        self.qid_label = QLabel("Q?")
        self.qid_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #007acc;")
        self.qid_label.setFixedWidth(70)
        header_layout.addWidget(self.qid_label)
        
        self.type_label = QLabel("-")
        self.type_label.setStyleSheet("font-size: 12px; color: #b0bec5;")
        header_layout.addWidget(self.type_label)
        
        header_layout.addStretch()
        
        self.score_label = QLabel("0 / 0 pts")
        self.score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #81c784;")
        self.score_label.setFixedWidth(100)
        header_layout.addWidget(self.score_label)
        
        layout.addWidget(header_frame)
        
        # ========== 답안 비교 영역 (학생 답 vs 정답) ==========
        answer_frame = QFrame()
        answer_frame.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        answer_layout = QHBoxLayout(answer_frame)
        answer_layout.setSpacing(20)
        
        # 학생 답 영역
        student_frame = QFrame()
        student_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        student_layout = QVBoxLayout(student_frame)
        
        student_title = QLabel("📝 학생 답")
        student_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #64b5f6;")
        student_layout.addWidget(student_title)
        
        self.student_answer_label = QLabel("-")
        self.student_answer_label.setStyleSheet("""
            font-size: 24px;
            font-family: monospace;
            font-weight: bold;
            color: #ffffff;
            background-color: #0d0d1a;
            border-radius: 4px;
            padding: 12px;
            min-height: 60px;
        """)
        self.student_answer_label.setAlignment(Qt.AlignCenter)
        student_layout.addWidget(self.student_answer_label)
        
        answer_layout.addWidget(student_frame, 1)
        
        # VS 아이콘
        vs_label = QLabel("VS")
        vs_label.setStyleSheet("""
            font-size: 16px;
            font-weight: bold;
            color: #ff9800;
            background: transparent;
            padding: 0px 10px;
        """)
        vs_label.setAlignment(Qt.AlignCenter)
        answer_layout.addWidget(vs_label)
        
        # 정답 영역
        correct_frame = QFrame()
        correct_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        correct_layout = QVBoxLayout(correct_frame)
        
        correct_title = QLabel("✅ 정답")
        correct_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #81c784;")
        correct_layout.addWidget(correct_title)
        
        self.correct_answer_label = QLabel("-")
        self.correct_answer_label.setStyleSheet("""
            font-size: 24px;
            font-family: monospace;
            font-weight: bold;
            color: #81c784;
            background-color: #0d0d1a;
            border-radius: 4px;
            padding: 12px;
            min-height: 60px;
        """)
        self.correct_answer_label.setAlignment(Qt.AlignCenter)
        correct_layout.addWidget(self.correct_answer_label)
        
        answer_layout.addWidget(correct_frame, 1)
        
        layout.addWidget(answer_frame)
        
        # ========== 결과 메시지 ==========
        self.result_frame = QFrame()
        self.result_frame.setStyleSheet("""
            QFrame {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        result_layout = QHBoxLayout(self.result_frame)
        
        self.result_icon = QLabel("")
        self.result_icon.setFixedSize(32, 32)
        result_layout.addWidget(self.result_icon)
        
        self.result_message = QLabel("채점 결과가 여기에 표시됩니다")
        self.result_message.setStyleSheet("font-size: 13px; color: #b0bec5;")
        result_layout.addWidget(self.result_message)
        
        result_layout.addStretch()
        
        layout.addWidget(self.result_frame)
        
        # ========== 간단 정보 (선택지 수 등) ==========
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("font-size: 10px; color: #78909c;")
        info_layout.addWidget(self.info_label)
        info_layout.addStretch()
        
        layout.addWidget(info_frame)
        
        layout.addStretch()
        self.setLayout(layout)
    
    def update_question(
        self,
        qid,
        qtype,
        student,
        correct,
        score,
        max_score,
        result_text,
        region_text,
        grading_debug=None,
    ):
        # 문제 번호 및 유형
        self.qid_label.setText(f"Q{qid}" if qid else "Q?")
        self.type_label.setText(f"[{qtype}]" if qtype else "[-]")
        
        # 답안 표시
        student_display = student if student else "(미응답)"
        correct_display = correct if correct else "(없음)"
        
        self.student_answer_label.setText(
            str(student_display).upper()
        )
        self.correct_answer_label.setText(
            str(correct_display).upper()
        )
        
        # 점수 표시
        score_display = f"{score:.1f}" if score % 1 else f"{int(score)}"
        max_display = f"{max_score:.1f}" if max_score % 1 else f"{int(max_score)}"
        self.score_label.setText(f"{score_display} / {max_display} pts")
        
        # 결과 메시지 및 아이콘 설정
        if "정답" in result_text:
            self.result_message.setText(f"✓ {result_text}")
            self.result_message.setStyleSheet("font-size: 13px; font-weight: bold; color: #81c784;")
            self.result_icon.setText("✅")
            self.score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #81c784;")
            self.result_frame.setStyleSheet("""
                QFrame {
                    background-color: #1b3a2a;
                    border-radius: 8px;
                    padding: 10px;
                    border: 1px solid #81c784;
                }
            """)
        elif "오답" in result_text:
            self.result_message.setText(f"✗ {result_text}")
            self.result_message.setStyleSheet("font-size: 13px; font-weight: bold; color: #e57373;")
            self.result_icon.setText("❌")
            self.score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e57373;")
            self.result_frame.setStyleSheet("""
                QFrame {
                    background-color: #3a1b1b;
                    border-radius: 8px;
                    padding: 10px;
                    border: 1px solid #e57373;
                }
            """)
        elif "답변" in result_text:
            self.result_message.setText(f"⚠️ {result_text}")
            self.result_message.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffb74d;")
            self.result_icon.setText("⚠️")
            self.score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffb74d;")
            self.result_frame.setStyleSheet("""
                QFrame {
                    background-color: #3a2e1b;
                    border-radius: 8px;
                    padding: 10px;
                    border: 1px solid #ffb74d;
                }
            """)
        else:
            self.result_message.setText("📋 아직 채점되지 않음")
            self.result_message.setStyleSheet("font-size: 13px; color: #b0bec5;")
            self.result_icon.setText("📋")
            self.score_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #b0bec5;")
            self.result_frame.setStyleSheet("""
                QFrame {
                    background-color: #2d2d2d;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
        
        # 간단 정보 표시 (선택지 수 등)
        if grading_debug and isinstance(grading_debug, dict):
            bubble_count = len(grading_debug.get('bubble_scores', []))
            if bubble_count > 0:
                self.info_label.setText(f"선택지 {bubble_count}개 · 신뢰도: {grading_debug.get('confidence', 0):.2f}")
            else:
                self.info_label.setText("")
        else:
            self.info_label.setText("")
    
    def update_question_from_progress(
        self,
        qid,
        qtype,
        student,
        correct,
        score,
        result_text,
        region_text,
        grading_debug,
    ):
        """진행 중 리스트 갱신 시 사용"""
        max_score = 0
        if isinstance(grading_debug, dict):
            max_score = grading_debug.get("max_score", 0)
            if not max_score:
                max_score = grading_debug.get("max_points", 0)
            if not max_score:
                omr_detail = grading_debug.get("omr_detail", {})
                max_score = omr_detail.get("max_score", 0)
        
        self.update_question(
            qid, qtype, student, correct, score, max_score, 
            result_text, region_text, grading_debug
        )


class GraderTester(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🔬 채점 엔진 테스터 - ArUco 기반 선택지 영역 표시")
        self.setGeometry(100, 100, 1600, 950)
        
        self.exam_data = None
        self.pdf_path = None
        self.grading_result = None
        self.worker = None
        self.all_questions_list = []
        self.current_page = 0
        self.total_pages = 0
        
        # ========== debug_mode 속성 추가 ==========
        self.debug_mode = True  # 디버그 모드 활성화
        
        self.init_ui()
        self.apply_style()
        self.showMaximized()
        
        if sys.platform == 'win32':
            tesseract_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            ]
            for path in tesseract_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
    
    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
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
            QTableWidget {
                background-color: #252526;
                alternate-background-color: #2d2d2d;
                gridline-color: #3d3d3d;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #007acc;
                padding: 8px;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #252526;
                color: #e0e0e0;
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                font-family: monospace;
            }
            QTextEdit:read-only {
                color: #e0e0e0;
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 6px;
                text-align: center;
            }
            QProgressBar::chunk { background-color: #007acc; border-radius: 6px; }
            QListWidget {
                background-color: #252526;
                border: 1px solid #3d3d3d;
                border-radius: 8px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background-color: #0d7377;
            }
            QListWidget::item:hover:!selected {
                background-color: #3d3d3d;
            }
            QLabel { color: #e0e0e0; }
            QScrollArea { border: none; }
        """)
    
    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(10)
        
        left_panel = self._create_image_panel()
        main_layout.addWidget(left_panel, 4)
        
        middle_panel = self._create_question_list_panel()
        main_layout.addWidget(middle_panel, 2)
        
        right_panel = self._create_detail_panel()
        main_layout.addWidget(right_panel, 4)
        
        self.statusBar().showMessage("Ready - Load exam JSON and PDF")
    
    def _create_image_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        title = QLabel("📄 PDF 이미지 (ArUco 기반 선택지 영역)")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #007acc; padding: 5px;")
        layout.addWidget(title)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignCenter)
        scroll.setStyleSheet("border: 1px solid #3d3d3d; border-radius: 8px;")
        
        self.image_viewer = PDFImageViewer()
        scroll.setWidget(self.image_viewer)
        layout.addWidget(scroll, 1)
        
        page_layout = QHBoxLayout()
        page_layout.addStretch()
        self.prev_btn = QPushButton("◀ Previous Page")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setEnabled(False)
        page_layout.addWidget(self.prev_btn)
        
        self.page_label = QLabel("Page 1")
        self.page_label.setFixedWidth(80)
        self.page_label.setAlignment(Qt.AlignCenter)
        page_layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Next Page ▶")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setEnabled(False)
        page_layout.addWidget(self.next_btn)
        page_layout.addStretch()
        layout.addLayout(page_layout)
        
        self.calibration_status = QLabel("")
        self.calibration_status.setAlignment(Qt.AlignCenter)
        self.calibration_status.setStyleSheet("font-size: 10px; color: #ffb74d;")
        layout.addWidget(self.calibration_status)
        
        return panel
    
    def _create_question_list_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        title = QLabel("📋 문제 목록 (클릭하여 분석)")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #007acc; padding: 5px;")
        layout.addWidget(title)
        
        self.question_list = QListWidget()
        self.question_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1d23;
                color: #f0f4fc;
                border: 1px solid #4a5568;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                color: #f5f7fb;
                padding: 8px 6px;
                border-bottom: 1px solid #2d333b;
            }
            QListWidget::item:selected {
                background-color: #1565c0;
                color: #ffffff;
                border-bottom: 1px solid #1565c0;
            }
            QListWidget::item:hover:!selected {
                background-color: #2d3d52;
                color: #ffffff;
            }
        """)
        self.question_list.itemClicked.connect(self.on_question_selected)
        layout.addWidget(self.question_list)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.grade_status = QLabel("Ready")
        self.grade_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.grade_status)

        self.list_summary_label = QLabel("요약 · —")
        self.list_summary_label.setWordWrap(True)
        self.list_summary_label.setAlignment(Qt.AlignCenter)
        self.list_summary_label.setStyleSheet(
            "font-size: 11px; color: #cfd8dc; padding: 4px 2px; background: transparent;"
        )
        layout.addWidget(self.list_summary_label)

        return panel

    def _create_detail_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel("📊 채점 결과")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #64b5f6; 
            padding: 8px;
            background-color: #1e1e1e;
            border-radius: 6px;
        """)
        layout.addWidget(title)

        # 컨트롤 버튼 영역
        ctrl_frame = QFrame()
        ctrl_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        ctrl_layout = QHBoxLayout(ctrl_frame)
        ctrl_layout.setSpacing(6)

        def _mini_btn(btn: QPushButton, tip: str):
            btn.setToolTip(tip)
            btn.setMaximumHeight(32)
            btn.setMinimumWidth(60)

        self.load_exam_btn = QPushButton("📁 JSON")
        self.load_exam_btn.clicked.connect(self.load_exam)
        _mini_btn(self.load_exam_btn, "시험 JSON 불러오기")

        self.load_pdf_btn = QPushButton("📄 PDF")
        self.load_pdf_btn.clicked.connect(self.load_pdf)
        _mini_btn(self.load_pdf_btn, "답안 PDF 불러오기")

        self.grade_btn = QPushButton("🎯 채점")
        self.grade_btn.setObjectName("primary")
        self.grade_btn.clicked.connect(self.start_grading)
        self.grade_btn.setEnabled(False)
        _mini_btn(self.grade_btn, "채점 실행")

        self.clear_btn = QPushButton("🗑 초기화")
        self.clear_btn.clicked.connect(self.clear_results)
        _mini_btn(self.clear_btn, "채점 결과 초기화")

        for btn in (self.load_exam_btn, self.load_pdf_btn, self.grade_btn, self.clear_btn):
            ctrl_layout.addWidget(btn)
        ctrl_layout.addStretch()
        
        layout.addWidget(ctrl_frame)

        # 문제 상세 위젯 (간소화된 버전)
        self.question_detail = QuestionDetailWidget()
        layout.addWidget(self.question_detail, 1)

        # 간단 로그 영역
        log_frame = QFrame()
        log_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        log_layout = QVBoxLayout(log_frame)
        log_layout.setContentsMargins(4, 4, 4, 4)
        
        log_header = QHBoxLayout()
        log_lbl = QLabel("📋 로그")
        log_lbl.setStyleSheet("font-size: 10px; font-weight: bold; color: #90a4ae;")
        log_header.addWidget(log_lbl)
        log_header.addStretch()
        
        clr = QPushButton("지우기")
        clr.setMaximumHeight(24)
        clr.setMaximumWidth(60)
        clr.clicked.connect(lambda: self.log_text.clear())
        log_header.addWidget(clr)
        log_layout.addLayout(log_header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setFont(QFont("Consolas", 8))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #0d0d1a;
                color: #b0bec5;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_frame)

        return panel
    
    def load_exam(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load Exam JSON", "", "JSON (*.json)")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.exam_data = json.load(f)
                
                exam_title = self.exam_data.get('exam_title', 'Unknown')
                total_q = len(self.exam_data.get('answers', []))
                total_pts = self.exam_data.get('total_points', 0)

                self.statusBar().showMessage(
                    f"{exam_title} · {total_q}문항 · {total_pts}점 · {os.path.basename(file_path)}"
                )
                self._add_log(f"✅ Loaded exam: {os.path.basename(file_path)}")
                
                self.all_questions_list = []
                self.question_list.clear()
                for q in self.exam_data.get('answers', []):
                    qid = q.get('question_id')
                    qtype = q.get('question_type', 'unknown')
                    score = q.get('score', 0)
                    item_text = f"Q{qid} [{qtype}] ({score} pts)"
                    self.question_list.addItem(item_text)
                    self.all_questions_list.append(qid)
                
                self._check_ready()
                
                # PDF가 이미 로드되어 있으면 현재 페이지 다시 표시
                if self.pdf_path:
                    self._display_current_page()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load exam:\n{str(e)}")
                self._add_log(f"❌ Failed: {str(e)}")
    
    # PDF 버튼 클릭 시 전처리 실행 (수정)
    def load_pdf(self):
        """수정: PDF 로드 시 전처리 수행"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Load PDF", "", "PDF (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self._add_log(f"✅ Loaded PDF: {os.path.basename(file_path)}")
            
            # PDF 페이지 수 확인
            doc = fitz.open(file_path)
            self.total_pages = len(doc)
            doc.close()
            self.page_label.setText(f"Page 1/{self.total_pages}")
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(self.total_pages > 1)
            self.current_page = 0
            
            # 🔑 PDF 로드 시 전처리 수행 (debug_mode 전달)
            if self.exam_data:
                self._add_log("🔄 Preprocessing PDF with ArUco...")
                self.preprocessor = ImagePreprocessor(zoom=1.5, debug_mode=True)  # debug_mode=True로 설정
                success = self.preprocessor.preprocess_pdf(self.pdf_path, self.exam_data)
                
                if success:
                    summary = self.preprocessor.get_preprocess_summary()
                    self._add_log(f"✅ Preprocessing complete: {summary}")
                    
                    # 요약 출력
                    self.preprocessor.print_summary()
                    
                    self.statusBar().showMessage(
                        f"Preprocessed: {summary['calibrated_pages']}/{summary['total_pages']} pages calibrated, "
                        f"{summary['total_choice_regions']} choice regions"
                    )
                else:
                    self._add_log("❌ Preprocessing failed")
                    self.preprocessor = None
            else:
                self._add_log("⚠️ Load exam JSON first before preprocessing PDF")
            
            # 현재 페이지 표시
            self._display_current_page()
            self._check_ready()
    
    def _display_current_page(self):
        """수정: 전처리된 결과를 사용하여 표시 (상세 디버깅 포함)"""
        if not self.pdf_path or not self.exam_data:
            print("❌ _display_current_page: No PDF or exam data")
            return
        
        print(f"\n{'='*60}")
        print(f"📄 _display_current_page: Page {self.current_page + 1}/{self.total_pages}")
        print(f"{'='*60}")
        
        # 전처리된 결과가 있으면 사용
        if self.preprocessor:
            print("✅ Using preprocessed data for display")
            
            # 1. 페이지 이미지 가져오기
            page_image = self.preprocessor.get_page_image(self.current_page)
            if page_image is None:
                print(f"❌ No page image for page {self.current_page}")
                return
            
            print(f"   📸 Page image shape: {page_image.shape}")
            
            # 2. ArUco detector 가져오기
            detector = self.preprocessor.get_detector(self.current_page)
            if detector:
                print(f"   🔍 Detector calibrated: {detector.is_calibrated}")
                print(f"   🔍 Transform type: {getattr(detector, 'transform_type', 'unknown')}")
                print(f"   🔍 Detected markers: {list(detector.detected_markers.keys()) if detector.detected_markers else []}")
            else:
                print(f"   ⚠️ No detector for page {self.current_page}")
            
            # 3. 페이지의 선택지 영역 가져오기 (전처리된 데이터)
            page_num_1based = self.current_page + 1
            page_regions = self.preprocessor.question_regions.get(page_num_1based, {})
            
            print(f"   📍 Questions on page {page_num_1based}: {len(page_regions)}")
            
            # 4. 모든 선택지 영역 수집 및 디버깅
            choice_regions = {}
            for qid, region in page_regions.items():
                print(f"\n   📌 Q{qid} [{region.question_type}]:")
                print(f"      Expected: {region.expected_answer}, Score: {region.score}")
                print(f"      Choice regions: {len(region.choice_regions)}")
                
                choice_regions[qid] = {}

                for choice, rect in region.choice_regions.items():
                    choice_regions[qid][choice] = rect
                    print(f"         {choice}: x={rect['x']:4d}, y={rect['y']:4d}, "
                          f"w={rect['w']:3d}, h={rect['h']:3d}")
                    
                    # 좌표 유효성 검사
                    if page_image is not None:
                        img_h, img_w = page_image.shape[:2]
                        is_valid = (0 <= rect['x'] < img_w and 
                                   0 <= rect['y'] < img_h and
                                   rect['w'] > 0 and rect['h'] > 0)
                        if not is_valid:
                            print(f"         ⚠️ WARNING: Invalid coordinates! Image size: {img_w}x{img_h}")
            
            # 5. OpenCV 이미지를 QPixmap으로 변환
            try:
                rgb = cv2.cvtColor(page_image, cv2.COLOR_BGR2RGB)
                h, w, ch = rgb.shape
                bytes_per_line = ch * w
                qimage = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
                base_pixmap = QPixmap.fromImage(qimage)
                print(f"   🖼️ QPixmap created: {w}x{h}")
            except Exception as e:
                print(f"❌ Failed to convert image: {e}")
                return
            
            # 6. 선택지 영역 그리기 (디버그 모드)
            final_pixmap = self._draw_choice_regions_with_debug(base_pixmap, choice_regions, page_num_1based)
            
            # 7. ArUco 마커 그리기
            if detector and detector.detected_markers:
                final_pixmap = self._draw_aruco_markers_with_debug(final_pixmap, detector.detected_markers)
            
            # 8. 결과 이미지 표시
            self.image_viewer.current_pixmap = final_pixmap
            scaled = final_pixmap.scaled(
                self.image_viewer.width() - 20, self.image_viewer.height() - 20,
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self.image_viewer.setPixmap(scaled)
            
            # 9. 상태 표시줄 업데이트
            if detector and detector.is_calibrated:
                transform_type = getattr(detector, 'transform_type', 'unknown')
                self.calibration_status.setText(f"✅ {transform_type} calibrated - {len(choice_regions)} regions")
                self.calibration_status.setStyleSheet("font-size: 10px; color: #81c784;")
            else:
                self.calibration_status.setText(f"⚠️ Not calibrated - {len(choice_regions)} regions")
                self.calibration_status.setStyleSheet("font-size: 10px; color: #ffb74d;")
            
            print(f"\n✅ Display complete: {len(choice_regions)} choice regions drawn")
            
        else:
            print("⚠️ No preprocessor data, using fallback method")
            self._display_current_page_fallback()
        
        print(f"{'='*60}\n")
    
    def _draw_choice_regions_with_debug(self, pixmap, choice_regions, page_num):
        """선택지 영역 그리기 (디버그 정보 포함)"""
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        colors = {
            1: QColor(255, 100, 100),   # 빨강
            2: QColor(100, 255, 100),   # 초록
            3: QColor(100, 100, 255),   # 파랑
            4: QColor(255, 255, 100),   # 노랑
            5: QColor(255, 100, 255),   # 마젠타
        }
        
        drawn_count = 0
        for qid, choices in choice_regions.items():
            for choice, rect in choices.items():
                color = colors.get(choice, QColor(200, 200, 200))
                
                # 사각형 테두리 (두껍게)
                pen = QPen(color, 3)
                painter.setPen(pen)                
                painter.drawRect(rect['x'], rect['y'], rect['w'], rect['h'])
                
                drawn_count += 1
                
                # ========== 수정: debug_mode 속성 확인 ==========
                if hasattr(self, 'debug_mode') and self.debug_mode:
                    coord_text = f"{rect['x']},{rect['y']}"
                    painter.setFont(QFont("Consolas", 7))
                    painter.setPen(QPen(QColor(255, 255, 255, 200), 1))
                    painter.drawText(rect['x'] + 2, rect['y'] + rect['h'] - 2, coord_text)
        
        painter.end()
        
        if hasattr(self, 'debug_mode') and self.debug_mode:
            print(f"   🎨 Drawn {drawn_count} choice regions on page {page_num}")
        return pixmap
    
    def _draw_aruco_markers_with_debug(self, pixmap, detected_markers):
        """ArUco 마커 그리기 (디버그 정보 포함)"""
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for marker_id, info in detected_markers.items():
            center = info['center']
            x, y = int(center[0]), int(center[1])
            
            # 마커 중심 원
            painter.setBrush(QColor(0, 255, 0, 200))
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.drawEllipse(x - 8, y - 8, 16, 16)
            
            # 마커 ID 배경
            painter.setBrush(QColor(0, 0, 0, 180))
            painter.setPen(Qt.NoPen)
            painter.drawRect(x + 10, y - 12, 40, 20)
            
            # 마커 ID 텍스트
            painter.setPen(QPen(Qt.white, 1))
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            painter.drawText(x + 12, y + 2, f"M{marker_id}")
            
            # ========== 수정: debug_mode 속성 확인 ==========
            if hasattr(self, 'debug_mode') and self.debug_mode:
                painter.setFont(QFont("Consolas", 8))
                painter.setPen(QPen(QColor(255, 255, 0), 1))
                painter.drawText(x + 10, y + 15, f"({x},{y})")
        
        painter.end()
        
        if hasattr(self, 'debug_mode') and self.debug_mode:
            print(f"   🎯 Drawn {len(detected_markers)} ArUco markers")
        return pixmap


    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._display_current_page()
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled(True)

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._display_current_page()
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(self.current_page < self.total_pages - 1)
    
    def _check_ready(self):
        ready = self.exam_data is not None and self.pdf_path is not None
        self.grade_btn.setEnabled(ready)
        self.grade_status.setText("✅ 준비됨" if ready else "⚠️ JSON·PDF 필요")

    def on_question_selected(self, item):
        row = self.question_list.row(item)
        if row < len(self.all_questions_list):
            qid = self.all_questions_list[row]
            self._display_question_detail(qid)
    
    def _display_question_detail(self, qid):
        if not self.exam_data:
            return
        
        q_info = None
        for q in self.exam_data.get('answers', []):
            if q.get('question_id') == qid:
                q_info = q
                break
        
        if not q_info:
            return
        
        qtype = q_info.get('question_type', 'unknown')
        max_score = q_info.get('score', 0)
        
        student = ""
        correct = q_info.get('expected_answer', q_info.get('answer', ''))
        score = 0
        result_text = "Not graded yet"
        region_text = ""
        
        grading_debug = None
        if self.grading_result:
            student = self.grading_result.get('student_answers', {}).get(qid, '')
            score = self.grading_result.get('scores', {}).get(qid, 0)
            region_text = self.grading_result.get('region_texts', {}).get(qid, '')
            grading_debug = self.grading_result.get('grading_debug', {}).get(qid)

            if student and correct:
                is_correct = str(student) == str(correct)
                result_text = "✓ 정답" if is_correct else f"✗ 오답 (정답: {correct})"
            elif student:
                result_text = "⚠️ 답변 있음"
            else:
                result_text = "❌ 미응답"

        self.question_detail.update_question(
            qid, qtype, student, correct, score, max_score, result_text, region_text, grading_debug
        )
    
    def start_grading(self):
        """수정: 전처리된 결과를 사용하여 채점"""
        if not self.exam_data or not self.pdf_path:
            QMessageBox.warning(self, "Warning", "Please load both exam JSON and PDF file.")
            return
        
        # 이미 전처리되어 있으면 바로 채점
        if self.preprocessor:
            self._add_log("🚀 Using preprocessed data for grading...")
            self._grade_with_preprocessor()
        else:
            # Fallback: 전처리 없이 채점 (기존 방식)
            self._add_log("⚠️ No preprocessed data, using on-demand grading...")
            self._start_grading_worker()
    
    def _grade_with_preprocessor(self):
        """전처리된 데이터로 채점"""
        from exam_grader.grader_engine import ExamGrader
        
        self.grade_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        grader = ExamGrader(self.exam_data, debug_mode=True)
        grader.set_preprocessor(self.preprocessor)  # 전처리 결과 주입
        result = grader.grade_from_preprocessed()
        
        self.on_grading_finished(result)
    
    def _start_grading_worker(self):
        """기존 방식 (GradingWorker 사용)"""
        self.worker = GradingWorker(
            self.exam_data, self.pdf_path, use_ocr=True, debug_mode=True
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.question_progress.connect(self.update_question_progress)
        self.worker.finished.connect(self.on_grading_finished)
        self.worker.error.connect(self.on_grading_error)
        self.worker.start()
        
    def update_progress(self, value, message):
        self.progress_bar.setValue(value)
        self.grade_status.setText(message)
        self._add_log(f"  {message}")
    
    def update_question_progress(self, qid, total, student, correct, result, score, region_text, qtype, grading_debug):
        for i in range(self.question_list.count()):
            item = self.question_list.item(i)
            if item.text().startswith(f"Q{qid}"):
                if "정답" in result:
                    item.setForeground(QColor(129, 199, 132))
                    item.setText(f"✓ {item.text()} → {score:.0f} pts")
                elif "오답" in result:
                    item.setForeground(QColor(239, 154, 154))
                    item.setText(f"✗ {item.text()} → {score:.0f} pts")
                elif "답변" in result:
                    item.setForeground(QColor(255, 204, 128))
                    item.setText(f"⚠️ {item.text()} → {score:.0f} pts")
                else:
                    item.setForeground(QColor(224, 224, 224))
                    item.setText(f"❌ {item.text()} → {score:.0f} pts")
                break

        self._add_log(f"  Q{qid}: {result} (Student: '{student}', Correct: '{correct}', Score: {score})")
        
        self.question_detail.update_question_from_progress(
            qid, qtype, student, correct, score, result, region_text, grading_debug
        )
        QApplication.processEvents()
    
    def on_grading_finished(self, result):
        self.grading_result = result
        self.progress_bar.setVisible(False)
        self.grade_btn.setEnabled(True)
        
        total = result['total']
        max_score = result['max_score']
        percentage = result['percentage']
        
        student_answers = result.get('student_answers', {})
        correct_answers = result.get('correct_answers', {})

        correct_count = 0
        incorrect_count = 0
        empty_count = 0

        for qid in result['max_scores']:
            student = student_answers.get(qid, '')
            correct = correct_answers.get(qid, '')
            if not student:
                empty_count += 1
            elif student == correct:
                correct_count += 1
            else:
                incorrect_count += 1

        self.list_summary_label.setText(
            f"요약 · {total:.1f}/{max_score}점 ({percentage:.1f}%) · "
            f"정답 {correct_count} · 오답 {incorrect_count} · 미응답 {empty_count}"
        )

        self.grade_status.setText(f"완료 {total:.1f}/{max_score}점")
        self._add_log(f"✅ Grading completed! Correct={correct_count}, Incorrect={incorrect_count}, Empty={empty_count}")
        
        if self.all_questions_list:
            self._display_question_detail(self.all_questions_list[0])
    
    def on_grading_error(self, error_msg):
        self.progress_bar.setVisible(False)
        self.grade_btn.setEnabled(True)
        self.grade_status.setText("❌ Grading failed")
        self._add_log(f"❌ Error: {error_msg}")
        QMessageBox.critical(self, "Error", f"Grading failed:\n{error_msg}")
    
    def clear_results(self):
        self.grading_result = None
        self._add_log("🗑 Cleared all results")
        
        self.question_list.clear()
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            qtype = q.get('question_type', 'unknown')
            score = q.get('score', 0)
            item_text = f"Q{qid} [{qtype}] ({score} pts)"
            self.question_list.addItem(item_text)
        
        self.question_detail.update_question(0, "", "", "", 0, 0, "No grading yet", "", None)
    
    def _add_log(self, message):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = GraderTester()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()