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
from exam_grader.omr import ArUcoDetector, convert_normalized_coordinates_from_json


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
    
    def __init__(self, exam_data, pdf_path, use_ocr=True, use_dynamic_detection=True, 
                 debug_mode=True):
        super().__init__()
        self.exam_data = exam_data
        self.pdf_path = pdf_path
        self.use_ocr = use_ocr
        self.use_dynamic_detection = use_dynamic_detection
        self.debug_mode = debug_mode
    
    def run(self):
        try:
            self.progress.emit(10, "Processing PDF...")
            
            from exam_grader.grader_engine import ExamGrader
            grader = ExamGrader(self.exam_data, use_detection=self.use_dynamic_detection)
            
            if self.debug_mode:
                grader.debug_mode = True
            
            result = grader.grade_from_pdf(self.pdf_path)
            
            total_questions = len(result['max_scores'])
            for idx, qid in enumerate(sorted(result['max_scores'].keys())):
                student = result['student_answers'].get(qid, '')
                correct = result['correct_answers'].get(qid, '')
                score = result['scores'].get(qid, 0)
                max_score = result['max_scores'].get(qid, 0)
                region_text = result['region_texts'].get(qid, "")
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
                    result_text, score, region_text, qtype,
                    gd,
                )
                
                progress_pct = 50 + int((idx + 1) / total_questions * 45)
                self.progress.emit(progress_pct, f"Grading Q{qid}...")
                self.msleep(30)
            
            self.progress.emit(100, "Complete!")
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))
    

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
        self.choice_rects = []  # 표시할 선택지 영역 리스트
        self.aruco_markers = []  # 감지된 ArUco 마커 위치
        self.aruco_detector = None
    
    def load_pdf_page_with_aruco(self, pdf_path, page_num, exam_data, zoom=1.5):
        """
        PDF 페이지 로드, ArUco 마커 감지, 선택지 영역 표시
        """
        if not PYMUPDF_AVAILABLE:
            self.setText("PyMuPDF not installed")
            return
        
        try:
            doc = fitz.open(pdf_path)
            if page_num >= len(doc):
                self.setText(f"Page {page_num + 1} not found")
                doc.close()
                return
            
            page = doc[page_num]
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # PyMuPDF 픽셀맵을 QPixmap으로 변환
            img_data = pix.tobytes("png")
            qimage = QImage.fromData(img_data, "PNG")
            base_pixmap = QPixmap.fromImage(qimage)
            
            # OpenCV 이미지로 변환 (ArUco 감지용)
            pil_img = Image.open(io.BytesIO(img_data))
            bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            
            doc.close()
            
            # ArUco 마커 감지 및 캘리브레이션
            self.aruco_detector = ArUcoDetector()
            detected_markers = self.aruco_detector.detect_markers(bgr)
            
            # 4개 마커(ID 0,1,2,3)가 모두 있는지 확인
            required_markers = [0, 1, 2, 3]
            has_all_markers = all(mid in detected_markers for mid in required_markers)
            
            if has_all_markers:
                # 원근 변환 사용 (더 정확함)
                success = self.aruco_detector.compute_perspective_transform(pix.width, pix.height)
                transform_type = "Perspective"
            else:
                # Affine 변환 사용 (2개 이상 마커 필요)
                success = self.aruco_detector.compute_transform(pix.width, pix.height)
                transform_type = "Affine"
            
            if success:
                print(f"✅ ArUco calibration successful using {transform_type} transform")
                print(f"   Detected markers: {list(detected_markers.keys())}")
                
                # JSON 좌표 변환
                choice_data = self._convert_choice_coordinates(exam_data, page_num + 1)
                
                # 선택지 영역 그리기
                final_pixmap = self._draw_choice_regions(base_pixmap, choice_data, zoom)
                
                # ArUco 마커 그리기
                final_pixmap = self._draw_aruco_markers(final_pixmap, detected_markers, zoom)
                
                self.current_pixmap = final_pixmap
                self.choice_rects = choice_data
                
                scaled = final_pixmap.scaled(
                    self.width() - 20, self.height() - 20,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.setPixmap(scaled)
            else:
                print(f"⚠️ ArUco calibration failed. Required markers not found.")
                print(f"   Detected: {list(detected_markers.keys())}")
                
                # 캘리브레이션 실패 시 원본 이미지만 표시
                scaled = base_pixmap.scaled(
                    self.width() - 20, self.height() - 20,
                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self.setPixmap(scaled)
            
        except Exception as e:
            self.setText(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _convert_choice_coordinates(self, exam_data, page_num):
        """
        JSON의 normalized 좌표를 픽셀 좌표로 변환
        
        Args:
            exam_data: 시험 JSON 데이터
            page_num: 페이지 번호 (1부터 시작)
        
        Returns:
            {question_id: {'choice_regions': {choice: (x1,y1,x2,y2)}, ...}}
        """
        if not exam_data or not self.aruco_detector or not self.aruco_detector.is_calibrated:
            return {}
        
        result = {}
        
        for q in exam_data.get('answers', []):
            qid = q.get('question_id')
            if not qid:
                continue
            
            # 문제의 페이지 확인
            pos = q.get('position', {})
            q_page = pos.get('page', 1)
            
            if q_page != page_num:
                continue
            
            choice_regions = {}
            
            # answers 내 choice_regions 처리
            for cr in q.get('choice_regions', []):
                norm = cr.get('normalized', {})
                if norm and 'x' in norm and 'y' in norm and 'w' in norm and 'h' in norm:
                    pixel_rect = self.aruco_detector.normalized_rect_to_pixel(norm)
                    choice_regions[cr.get('choice', '?')] = pixel_rect
            
            # 최상위 choice_regions 처리
            for cr in exam_data.get('choice_regions', []):
                if cr.get('question_id') == qid:
                    norm = cr.get('normalized', {})
                    if norm and 'x' in norm and 'y' in norm and 'w' in norm and 'h' in norm:
                        pixel_rect = self.aruco_detector.normalized_rect_to_pixel(norm)
                        choice = cr.get('choice', '?')
                        if choice not in choice_regions:
                            choice_regions[choice] = pixel_rect
            
            if choice_regions:
                result[qid] = {
                    'question_type': q.get('question_type', 'unknown'),
                    'expected_answer': q.get('expected_answer', q.get('answer', '')),
                    'score': q.get('score', 0),
                    'choice_regions': choice_regions
                }
        
        return result
    
    def _draw_choice_regions(self, pixmap, choice_data, zoom=1.5):
        """선택지 영역을 pixmap에 그리기"""
        if not choice_data:
            return pixmap
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 선택지별 색상 매핑
        color_map = {
            'a': QColor(255, 100, 100),   # 빨강
            'b': QColor(100, 255, 100),   # 초록
            'c': QColor(100, 100, 255),   # 파랑
            'd': QColor(255, 255, 100),   # 하늘
            'e': QColor(255, 100, 255),   # 마젠타
            'f': QColor(100, 255, 255),   # 노랑
            't': QColor(255, 100, 100),   # True (빨강)
            'f_': QColor(100, 100, 255),  # False (파랑)
            'blank': QColor(200, 200, 100)  # 빈칸
        }
        
        for qid, info in choice_data.items():
            choice_regions = info.get('choice_regions', {})
            qtype = info.get('question_type', 'unknown')
            
            for choice, rect in choice_regions.items():
                x = rect['x']
                y = rect['y']
                w = rect['w']
                h = rect['h']
                
                # 색상 선택
                color = color_map.get(choice.lower(), QColor(200, 200, 200))
                
                # 영역 사각형 그리기
                pen = QPen(color, 2)
                painter.setPen(pen)
                painter.setBrush(QColor(color.red(), color.green(), color.blue(), 50))
                painter.drawRect(x, y, w, h)
                
                # 선택지 레이블
                label = f"[{choice.upper()}]"
                painter.setBrush(QColor(color.red(), color.green(), color.blue(), 200))
                painter.setPen(Qt.NoPen)
                
                # # 레이블 배경
                # label_x = x
                # label_y = y - 18
                # painter.drawRect(label_x, label_y, 40, 16)
                
                # # 레이블 텍스트
                # painter.setPen(QPen(Qt.white, 1))
                # painter.setFont(QFont("Arial", 8, QFont.Bold))
                # painter.drawText(label_x + 4, label_y + 12, label)
        
        painter.end()
        return pixmap
    
    def _draw_aruco_markers(self, pixmap, detected_markers, zoom=1.5):
        """ArUco 마커 위치를 pixmap에 그리기"""
        if not detected_markers:
            return pixmap
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for marker_id, info in detected_markers.items():
            center = info['center']
            x = int(center[0])
            y = int(center[1])
            
            # 마커 중심에 원 그리기
            painter.setBrush(QColor(0, 255, 0, 180))
            painter.setPen(QPen(QColor(0, 255, 0), 2))
            painter.drawEllipse(x - 6, y - 6, 12, 12)
            
            # 마커 ID 표시
            painter.setBrush(QColor(0, 255, 0, 200))
            painter.setPen(Qt.NoPen)
            painter.drawRect(x + 8, y - 12, 30, 16)
            
            painter.setPen(QPen(Qt.white, 1))
            painter.setFont(QFont("Arial", 8, QFont.Bold))
            painter.drawText(x + 10, y - 2, f"M{marker_id}")
        
        painter.end()
        return pixmap
    
    def update_display(self):
        """현재 저장된 pixmap으로 화면 갱신"""
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
        layout.setSpacing(3)
        layout.setContentsMargins(4, 4, 4, 4)
        
        # 헤더
        header_layout = QHBoxLayout()
        self.qid_label = QLabel("Q?")
        self.qid_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #007acc; background: transparent;")
        self.qid_label.setFixedWidth(60)
        header_layout.addWidget(self.qid_label)
        
        self.type_label = QLabel("-")
        self.type_label.setStyleSheet("font-size: 12px; color: #cfd8dc; background: transparent;")
        header_layout.addWidget(self.type_label)
        
        header_layout.addStretch()
        
        self.score_label = QLabel("0 / 0 pts")
        self.score_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #eceff1; background: transparent;")
        header_layout.addWidget(self.score_label)
        
        layout.addLayout(header_layout)

        # 탭 위젯
        self.debug_tabs = QTabWidget()
        self.debug_tabs.setStyleSheet("""
            QTabWidget::pane {
                background-color: #121826;
                border: 1px solid #3d5a80;
                border-radius: 6px;
            }
            QTabBar::tab {
                background-color: #1a1f2e;
                color: #b0bec5;
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background-color: #0d47a1;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #1565c0;
            }
        """)
        
        # 탭 1: 기본 디버그 정보
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        self.debug_text = QTextEdit()
        self.debug_text.setReadOnly(True)
        self.debug_text.setFont(QFont("Consolas", 9))
        self.debug_text.setMinimumHeight(150)
        self.debug_text.setStyleSheet("""
            QTextEdit {
                background-color: #0a0f18;
                color: #d6e9ff;
                border: 1px solid #2a3f5a;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        basic_layout.addWidget(self.debug_text)
        self.debug_tabs.addTab(basic_tab, "📋 기본 정보")
        
        # 탭 2: OMR 상세 분석
        omr_tab = QWidget()
        omr_layout = QVBoxLayout(omr_tab)
        self.omr_details_text = QTextEdit()
        self.omr_details_text.setReadOnly(True)
        self.omr_details_text.setFont(QFont("Consolas", 9))
        self.omr_details_text.setStyleSheet("""
            QTextEdit {
                background-color: #0a0f18;
                color: #d6e9ff;
                border: 1px solid #2a3f5a;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        omr_layout.addWidget(self.omr_details_text)
        self.debug_tabs.addTab(omr_tab, "🔍 OMR 분석")
        
        # 탭 3: 채점 단계 로그
        steps_tab = QWidget()
        steps_layout = QVBoxLayout(steps_tab)
        self.steps_text = QTextEdit()
        self.steps_text.setReadOnly(True)
        self.steps_text.setFont(QFont("Consolas", 9))
        self.steps_text.setStyleSheet("""
            QTextEdit {
                background-color: #0a0f18;
                color: #d6e9ff;
                border: 1px solid #2a3f5a;
                border-radius: 4px;
                padding: 6px;
            }
        """)
        steps_layout.addWidget(self.steps_text)
        self.debug_tabs.addTab(steps_tab, "📝 채점 단계")
        
        layout.addWidget(self.debug_tabs, 2)

        # 문제 영역 텍스트
        self.region_frame = QFrame()
        self.region_frame.setStyleSheet("""
            QFrame {
                background-color: #1a1a2e;
                border-radius: 6px;
                padding: 4px 6px;
                border: 1px solid #3d3d3d;
            }
        """)
        region_layout = QVBoxLayout(self.region_frame)
        region_layout.setContentsMargins(4, 2, 4, 2)

        self.region_title = QLabel("추출 텍스트")
        self.region_title.setStyleSheet("font-size: 10px; color: #ffb74d; font-weight: bold; background: transparent;")
        region_layout.addWidget(self.region_title)

        self.region_text_label = QLabel("-")
        self.region_text_label.setWordWrap(True)
        self.region_text_label.setMaximumHeight(88)
        self.region_text_label.setStyleSheet("""
            font-size: 9px;
            font-family: monospace;
            color: #f5f5f5;
            background-color: #0d0d1a;
            padding: 4px 6px;
            border-radius: 4px;
        """)
        region_layout.addWidget(self.region_text_label)

        layout.addWidget(self.region_frame)
        
        # 답안 비교 영역
        answer_frame = QFrame()
        answer_frame.setStyleSheet("""
            QFrame {
                background-color: #252526;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        answer_layout = QHBoxLayout(answer_frame)

        student_frame = QFrame()
        student_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 4px; padding: 4px 6px;")
        student_layout = QVBoxLayout(student_frame)

        self.student_title = QLabel("학생 답")
        self.student_title.setStyleSheet("font-size: 10px; color: #b0bec5; background: transparent;")
        student_layout.addWidget(self.student_title)
        
        self.student_answer_label = QLabel("-")
        self.student_answer_label.setStyleSheet("font-size: 12px; font-family: monospace; font-weight: bold; color: #ffffff; background: transparent;")
        self.student_answer_label.setWordWrap(True)
        self.student_answer_label.setMaximumHeight(44)
        student_layout.addWidget(self.student_answer_label)
        answer_layout.addWidget(student_frame, 1)

        vs_label = QLabel("vs")
        vs_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #ff9800; background: transparent;")
        vs_label.setAlignment(Qt.AlignCenter)
        answer_layout.addWidget(vs_label)
        
        correct_frame = QFrame()
        correct_frame.setStyleSheet("background-color: #1e1e1e; border-radius: 4px; padding: 4px 6px;")
        correct_layout = QVBoxLayout(correct_frame)

        correct_title = QLabel("정답")
        correct_title.setStyleSheet("font-size: 10px; color: #b0bec5; background: transparent;")
        correct_layout.addWidget(correct_title)
        
        self.correct_answer_label = QLabel("-")
        self.correct_answer_label.setStyleSheet("font-size: 12px; font-family: monospace; color: #81c784; font-weight: bold; background: transparent;")
        self.correct_answer_label.setWordWrap(True)
        self.correct_answer_label.setMaximumHeight(44)
        correct_layout.addWidget(self.correct_answer_label)
        answer_layout.addWidget(correct_frame, 1)
        
        layout.addWidget(answer_frame)

        self.setLayout(layout)

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
        """진행 중 리스트 갱신 시 사용 - max_score는 grading_debug에서 추출"""
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
        self.qid_label.setText(f"Q{qid}" if qid else "Q?")
        self.type_label.setText(f"[{qtype}]" if qtype else "[-]")

        is_image_mc = qtype in ("Multiple Choice", "True/False")
        if is_image_mc:
            self.student_title.setText("학생 답 · OMR+텍스트 병합")
            self.region_frame.setVisible(False)
        else:
            self.student_title.setText("학생 답 · 텍스트/OCR")
            self.region_frame.setVisible(True)
            self.region_title.setText("추출 텍스트 (파싱)")

        display_text = (region_text or "")[:220] + ("…" if len(region_text or "") > 220 else "")
        self.region_text_label.setText(display_text if display_text.strip() else "(없음)")

        self.debug_text.setPlainText(
            self._format_debug_block(
                qtype, grading_debug or {}, region_text or "",
                result_text=result_text, student=student, correct=correct,
                score=float(score or 0), max_score=float(max_score or 0)
            )
        )
        
        self.omr_details_text.setPlainText(
            self._format_omr_details(grading_debug or {})
        )
        
        self.steps_text.setPlainText(
            self._format_scoring_steps(grading_debug or {})
        )

        self.student_answer_label.setText(student if student else "(없음)")
        self.correct_answer_label.setText(correct if correct else "(없음)")

        score_display = f"{score:.1f}" if score % 1 else f"{int(score)}"
        max_display = f"{max_score:.1f}" if max_score % 1 else f"{int(max_score)}"
        self.score_label.setText(f"{score_display} / {max_display} pts")

        if "정답" in result_text:
            self.score_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #81c784;")
        elif "오답" in result_text:
            self.score_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e57373;")
        elif "답변" in result_text:
            self.score_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #ffb74d;")
        else:
            self.score_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #b0bec5;")

    def _format_debug_block(self, qtype, grading_debug, region_text, **kwargs):
        lines = []
        
        if not grading_debug:
            hint = (kwargs.get('result_text', '') or "").strip()
            lines.append(f"[결과] {hint}" if hint else "[결과] 채점 전 · Grade 실행")
            return "\n".join(lines)

        sd = str(kwargs.get('student', '') or "").strip() or "—"
        cd = str(kwargs.get('correct', '') or "").strip() or "—"
        res = (kwargs.get('result_text', '') or "").strip() or "—"
        max_score = kwargs.get('max_score', 0)
        score = kwargs.get('score', 0)
        
        if max_score:
            pct = 100.0 * float(score) / float(max_score) if max_score else 0.0
            pts = f"{float(score):g}/{float(max_score):g} pts ({pct:.0f}%)"
        else:
            pts = f"{float(score):g} pts"
        lines.append(f"[결과] {res} · {pts} · 학생:{sd} · 정답:{cd}")

        ch = grading_debug.get("answer_channel", "")
        
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
            lines.append(f"[인식] OMR {oa} conf={oc:.2f} · OCR글자 {ta} · 병합:{ms} · 경로:{path}{ink_s}{tail}")
        elif ch == "text":
            n = grading_debug.get("region_text_len", len(region_text or ""))
            lines.append(f"[인식] 텍스트/OCR 파싱 · 추출 {n}자")
        else:
            lines.append(f"[인식] 채널:{ch or '?'}")

        sm = grading_debug.get("scoring_method_key") or "—"
        fb = (grading_debug.get("score_engine_feedback") or "").strip()
        ok = grading_debug.get("is_correct")
        mark = "○" if ok is True else ("×" if ok is False else "—")
        lines.append(f"[엔진] 방식:{sm} 판정:{mark}" + (f" · {fb}" if fb else ""))
        
        if ch == "image_primary":
            lines.append(f"[신뢰도] OMR 신뢰도: {oc:.2f}" + 
                        (f" · 병합 소스: {ms}" if ms else ""))
        
        return "\n".join(lines)

    def _format_omr_details(self, grading_debug: dict) -> str:
        lines = []
        
        omr_detail = grading_debug.get("omr_detail", {})
        if not omr_detail:
            lines.append("⚠️ OMR 감지 정보 없음 (텍스트 기반 채점 사용)")
            return "\n".join(lines)
        
        lines.append("=" * 50)
        lines.append("🔍 OMR 감지 상세 분석")
        lines.append("=" * 50)
        
        path = omr_detail.get("path", "unknown")
        lines.append(f"감지 경로: {path}")
        
        img_shape = omr_detail.get("image_shape")
        if img_shape:
            lines.append(f"이미지 크기: {img_shape[0]} x {img_shape[1]} px")
        
        ocr_count = omr_detail.get("easyocr_label_count", 0)
        lines.append(f"EasyOCR 감지 글자 수: {ocr_count}")
        
        ink_scores = omr_detail.get("per_option_ink", {})
        if ink_scores:
            lines.append("\n📊 선택지별 잉크 점수:")
            for letter, score in sorted(ink_scores.items()):
                bar_len = int(score * 30)
                bar = "█" * bar_len + "░" * (30 - bar_len)
                lines.append(f"  [{letter}] {bar} {score:.3f}")
        
        eq_scores = omr_detail.get("equal_column_scores", {})
        if eq_scores:
            lines.append("\n📊 균등 분할 점수 (폴백):")
            for letter, score in sorted(eq_scores.items()):
                bar_len = int(score * 30)
                bar = "█" * bar_len + "░" * (30 - bar_len)
                lines.append(f"  [{letter}] {bar} {score:.3f}")
        
        final_letter = omr_detail.get("final_letter", "")
        final_conf = omr_detail.get("final_confidence", 0)
        if final_letter:
            lines.append(f"\n✅ 최종 선택: [{final_letter}] (신뢰도: {final_conf:.2f})")
        else:
            lines.append("\n❌ 최종 선택: 없음 (미응답 또는 감지 실패)")
        
        bracket_analysis = omr_detail.get("bracket_analysis", {})
        if bracket_analysis:
            lines.append("\n" + "=" * 50)
            lines.append("📦 괄호 형태 선택지 분석")
            lines.append("=" * 50)
            
            intensities = bracket_analysis.get("intensity_scores", {})
            if intensities:
                lines.append("밝기 기반 점수:")
                for letter, score in sorted(intensities.items()):
                    bar_len = int(score * 30)
                    bar = "█" * bar_len + "░" * (30 - bar_len)
                    lines.append(f"  [{letter}] {bar} {score:.3f}")
            
            selected = bracket_analysis.get("selected_letter", "")
            if selected:
                lines.append(f"\n👉 괄호 분석 선택: [{selected}]")
        
        return "\n".join(lines)

    def _format_scoring_steps(self, grading_debug: dict) -> str:
        lines = []
        
        lines.append("=" * 50)
        lines.append("📝 채점 단계별 상세 로그")
        lines.append("=" * 50)
        
        feedback = grading_debug.get("score_engine_feedback", "")
        if feedback:
            lines.append(f"\n[엔진 피드백]\n{feedback}")
        
        method = grading_debug.get("scoring_method_key", "")
        if method:
            lines.append(f"\n[스코어링 방식] {method}")
        
        text_len = grading_debug.get("region_text_len", 0)
        text_parsed = grading_debug.get("text_parsed_answer", "")
        if text_len > 0:
            lines.append(f"\n[텍스트 추출] 길이: {text_len}자")
            if text_parsed:
                lines.append(f"파싱 결과: '{text_parsed}'")
        
        ocr_letter = grading_debug.get("ocr_parsed_letter", "")
        if ocr_letter:
            lines.append(f"\n[OCR 인식] '{ocr_letter}'")
        
        omr_letter = grading_debug.get("omr_letter", "")
        omr_conf = grading_debug.get("omr_confidence", 0)
        if omr_letter:
            lines.append(f"\n[OMR 감지] '{omr_letter}' (신뢰도: {omr_conf:.2f})")
        
        merge_source = grading_debug.get("merge_source", "")
        if merge_source:
            lines.append(f"\n[병합 소스] {merge_source}")
        
        return "\n".join(lines)


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
        layout.setSpacing(6)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel("채점 디버그")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 13px; font-weight: bold; color: #64b5f6; padding: 2px;")
        layout.addWidget(title)

        ctrl = QHBoxLayout()
        ctrl.setSpacing(4)
        ctrl.setContentsMargins(0, 0, 0, 0)

        def _mini_btn(btn: QPushButton, tip: str):
            btn.setToolTip(tip)
            btn.setMaximumHeight(30)
            btn.setMinimumWidth(52)

        self.load_exam_btn = QPushButton("JSON")
        self.load_exam_btn.clicked.connect(self.load_exam)
        _mini_btn(self.load_exam_btn, "시험 JSON 불러오기")

        self.load_pdf_btn = QPushButton("PDF")
        self.load_pdf_btn.clicked.connect(self.load_pdf)
        _mini_btn(self.load_pdf_btn, "답안 PDF 불러오기")

        self.grade_btn = QPushButton("채점")
        self.grade_btn.setObjectName("primary")
        self.grade_btn.clicked.connect(self.start_grading)
        self.grade_btn.setEnabled(False)
        _mini_btn(self.grade_btn, "채점 실행")

        self.clear_btn = QPushButton("초기화")
        self.clear_btn.clicked.connect(self.clear_results)
        _mini_btn(self.clear_btn, "채점 결과만 목록에서 초기화")

        for b in (
            self.load_exam_btn,
            self.load_pdf_btn,
            self.grade_btn,
            self.clear_btn,
        ):
            ctrl.addWidget(b)
        ctrl.addStretch()
        layout.addLayout(ctrl)

        self.question_detail = QuestionDetailWidget()
        layout.addWidget(self.question_detail, 1)

        log_row = QHBoxLayout()
        log_lbl = QLabel("로그")
        log_lbl.setStyleSheet("font-size: 10px; color: #90a4ae;")
        log_row.addWidget(log_lbl)
        log_row.addStretch()
        clr = QPushButton("비우기")
        clr.setMaximumHeight(24)
        clr.clicked.connect(lambda: self.log_text.clear())
        log_row.addWidget(clr)
        layout.addLayout(log_row)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(88)
        self.log_text.setFont(QFont("Consolas", 8))
        layout.addWidget(self.log_text)

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
    
    def load_pdf(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Load PDF", "", "PDF (*.pdf)")
        if file_path:
            self.pdf_path = file_path
            self._add_log(f"✅ Loaded PDF: {os.path.basename(file_path)}")
            
            if PYMUPDF_AVAILABLE:
                doc = fitz.open(file_path)
                self.total_pages = len(doc)
                doc.close()
                self.page_label.setText(f"Page 1/{self.total_pages}")
                self.prev_btn.setEnabled(False)
                self.next_btn.setEnabled(self.total_pages > 1)
                self.current_page = 0
                
                self._display_current_page()
            
            if TESSERACT_AVAILABLE:
                self._add_log("📌 Tesseract OCR is available.")
            
            self._check_ready()
    
    def _display_current_page(self):
        """현재 페이지의 PDF 이미지와 선택지 영역 표시"""
        if not self.pdf_path or not self.exam_data:
            return
        
        self.image_viewer.load_pdf_page_with_aruco(
            self.pdf_path, 
            self.current_page, 
            self.exam_data,
            zoom=1.5
        )
        
        self.page_label.setText(f"Page {self.current_page + 1}/{self.total_pages}")
        
        # 캘리브레이션 상태 표시
        if self.image_viewer.aruco_detector and self.image_viewer.aruco_detector.is_calibrated:
            self.calibration_status.setText("✅ ArUco calibrated")
            self.calibration_status.setStyleSheet("font-size: 10px; color: #81c784;")
        else:
            self.calibration_status.setText("⚠️ ArUco calibration failed - markers not detected")
            self.calibration_status.setStyleSheet("font-size: 10px; color: #e57373;")

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
                is_correct = student.upper() == str(correct).upper()
                result_text = "✓ 정답" if is_correct else f"✗ 오답 (정답: {correct})"
            elif student:
                result_text = "⚠️ 답변 있음"
            else:
                result_text = "❌ 미응답"

        self.question_detail.update_question(
            qid, qtype, student, correct, score, max_score, result_text, region_text, grading_debug
        )
    
    def start_grading(self):
        if not self.exam_data or not self.pdf_path:
            QMessageBox.warning(self, "Warning", "Please load both exam JSON and PDF file.")
            return
        
        self.grade_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.grade_status.setText("⏳ Grading in progress...")
        self._add_log("🚀 Starting grading process...")
        
        self.grading_result = None
        self.question_list.clear()
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            qtype = q.get('question_type', 'unknown')
            score = q.get('score', 0)
            item_text = f"Q{qid} [{qtype}] ({score} pts)"
            self.question_list.addItem(item_text)
        
        self.worker = GradingWorker(
            self.exam_data, 
            self.pdf_path, 
            use_ocr=True
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