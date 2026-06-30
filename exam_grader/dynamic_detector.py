# exam_grader/answer_parser.py
import os
import re
import json
from typing import Any, Dict, Optional, Tuple, List
from collections import defaultdict
import fitz
import cv2
import numpy as np

try:
    import pytesseract
    import easyocr
    from PIL import Image
    import io
    TESSERACT_AVAILABLE = True
    EASYOCR_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    EASYOCR_AVAILABLE = False

from .omr import omr_read_mc_tf_selection, pdf_region_to_bgr


class DynamicQuestionDetector:
    """PDF에서 문제 위치를 동적으로 찾는 검출기
    - tmp.py의 로직 기반: EasyOCR + JSON 앵커 + 보간법 + 레이아웃 점수
    - 이미지 좌표계 기반 처리
    - 순차적 영역 생성 (다음 문제 위치 기준)
    """
    
    def __init__(self, use_ocr: bool = True, dpi: int = 200):
        self.use_ocr = use_ocr and TESSERACT_AVAILABLE
        self.dpi = dpi
        self.question_regions = {}
        
        # 문제 패턴 (Q1, 1., Q1. 등)
        self.question_pattern = r'[QO0][\s]*([0-9]{1,2})[\.\,:]?'
        
        # EasyOCR 초기화
        self.reader = None
        if EASYOCR_AVAILABLE and use_ocr:
            try:
                self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                print("✅ EasyOCR initialized")
            except Exception as e:
                print(f"⚠️ EasyOCR init failed: {e}")
        
        # Tesseract 경로 (Windows)
        if TESSERACT_AVAILABLE:
            import sys
            if sys.platform == 'win32':
                tesseract_paths = [
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                ]
                for path in tesseract_paths:
                    if os.path.exists(path):
                        pytesseract.pytesseract.tesseract_cmd = path
                        break
        
        # 이미지 관련 변수
        self.width = None
        self.height = None
        self.img_np = None
        self.binary = None
    
    def _build_qinfo_map(self, exam_data: Dict) -> Dict:
        """JSON에서 문제 정보 매핑"""
        qinfo_map = {}
        for q in exam_data.get('answers', []):
            qid = q.get('question_id')
            if qid:
                qinfo_map[qid] = {
                    'type': q.get('question_type', 'unknown'),
                    'expected_answer': q.get('expected_answer', q.get('answer', '')),
                    'score': q.get('score', 0),
                    'position': q.get('position', {})
                }
        return qinfo_map
    
    def _prepare_image(self, page):
        """PDF 페이지를 이미지로 변환 및 전처리 (tmp.py 방식)"""
        self.scale = self.dpi / 72
        zoom = self.dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.img_np = np.array(img)
        self.height, self.width = self.img_np.shape[:2]
        
        # 이미지 전처리 (tmp.py 방식)
        gray = cv2.cvtColor(self.img_np, cv2.COLOR_RGB2GRAY)
        self.binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 31, 15
        )
        self.binary = cv2.medianBlur(self.binary, 3)
        
        return self.img_np, self.binary
    
    def _detect_with_easyocr(self, page_num: int, total_questions: int) -> Dict[int, List[Dict]]:
        """EasyOCR로 문제 번호 검출 (tmp.py 방식)"""
        candidates_by_id = defaultdict(list)
        
        if not self.reader:
            return candidates_by_id
        
        try:
            ocr_results = self.reader.readtext(self.binary)
            
            for result in ocr_results:
                box, text, conf = result
                text = text.strip()
                
                match = re.search(self.question_pattern, text)
                if not match:
                    continue
                
                try:
                    qid = int(match.group(1))
                    if not (1 <= qid <= total_questions):
                        continue
                    
                    xs = [p[0] for p in box]
                    ys = [p[1] for p in box]
                    
                    x1 = int(min(xs))
                    y1 = int(min(ys))
                    x2 = int(max(xs))
                    y2 = int(max(ys))
                    
                    candidate = {
                        "question_id": qid,
                        "bbox": [x1, y1, x2, y2],
                        "center_x": (x1 + x2) / 2,
                        "center_y": (y1 + y2) / 2,
                        "source": "easyocr",
                        "ocr_confidence": float(conf)
                    }
                    candidates_by_id[qid].append(candidate)
                except:
                    pass
        except Exception as e:
            print(f"    EasyOCR error: {e}")
        
        return candidates_by_id
    
    def _detect_with_json_anchor(self, total_questions: int, qinfo_map: Dict) -> Dict[int, List[Dict]]:
        """JSON 좌표를 앵커로 사용한 검출 (tmp.py 방식)"""
        candidates_by_id = defaultdict(list)
        
        if not TESSERACT_AVAILABLE:
            return candidates_by_id
        
        try:
            # 스케일 계산 (PDF 기본 크기 595x842 기준)
            scale_x = self.width / 595
            scale_y = self.height / 842
            
            for qid, info in qinfo_map.items():
                position = info.get('position', {})
                if not position:
                    continue
                
                json_x = position.get('x', 0)
                json_y = position.get('y', 0)
                
                expected_x = int(json_x * scale_x)
                expected_y = int(json_y * scale_y)
                
                x1 = max(0, expected_x - 120)
                y1 = max(0, expected_y - 70)
                x2 = min(self.width, expected_x + 320)
                y2 = min(self.height, expected_y + 90)
                
                crop = self.binary[y1:y2, x1:x2]
                
                text = pytesseract.image_to_string(crop, config='--psm 7')
                match = re.search(self.question_pattern, text)
                
                if not match:
                    continue
                
                try:
                    detected_qid = int(match.group(1))
                    if detected_qid != qid:
                        continue
                    
                    candidate = {
                        "question_id": qid,
                        "bbox": [x1, y1, x2, y2],
                        "center_x": (x1 + x2) / 2,
                        "center_y": (y1 + y2) / 2,
                        "source": "json_anchor",
                        "ocr_confidence": 0.7
                    }
                    candidates_by_id[qid].append(candidate)
                    print(f"    [RECOVERED] Q{qid}")
                except:
                    pass
        except Exception as e:
            print(f"    JSON anchor error: {e}")
        
        return candidates_by_id
    
    def _add_interpolation_candidates(self, candidates_by_id: Dict, id_list: List[int]) -> Dict:
        """보간법으로 누락된 문제 위치 추정 (tmp.py 방식)"""
        existing = []
        
        for qid in id_list:
            if qid in candidates_by_id and candidates_by_id[qid]:
                cand = candidates_by_id[qid][0]
                existing.append((qid, cand))
        
        existing = sorted(existing, key=lambda x: x[0])
        
        for i in range(len(existing) - 1):
            current_id, current_q = existing[i]
            next_id, next_q = existing[i + 1]
            
            gap = next_id - current_id
            if gap <= 1:
                continue
            
            for missing_id in range(current_id + 1, next_id):
                ratio = (missing_id - current_id) / gap
                
                interp_y = int(
                    current_q["center_y"]
                    + ratio * (next_q["center_y"] - current_q["center_y"])
                )
                interp_x = int(current_q["center_x"])
                
                candidate = {
                    "question_id": missing_id,
                    "bbox": [
                        interp_x - 100,
                        interp_y - 40,
                        interp_x + 300,
                        interp_y + 40
                    ],
                    "center_x": interp_x,
                    "center_y": interp_y,
                    "source": "interpolated",
                    "ocr_confidence": 0.3
                }
                candidates_by_id[missing_id].append(candidate)
                print(f"    [INTERPOLATED] Q{missing_id}")
        
        return candidates_by_id
    
    def _compute_layout_score(self, candidate, prev_q, next_q) -> float:
        """레이아웃 점수 계산 (tmp.py 방식)"""
        score = 0
        y = candidate["center_y"]
        
        # OCR confidence
        score += candidate["ocr_confidence"] * 50
        
        # monotonic order (Y 좌표 순서)
        if prev_q is not None:
            if y > prev_q["center_y"]:
                score += 80
            else:
                score -= 200
        
        if next_q is not None:
            if y < next_q["center_y"]:
                score += 80
            else:
                score -= 200
        
        # spacing consistency
        if prev_q is not None and next_q is not None:
            prev_gap = y - prev_q["center_y"]
            next_gap = next_q["center_y"] - y
            spacing_diff = abs(prev_gap - next_gap)
            score -= spacing_diff * 0.05
        
        # source prior
        source_bonus = {
            "easyocr": 20,
            "json_anchor": 15,
            "interpolated": 10
        }
        score += source_bonus.get(candidate["source"], 0)
        
        return score
    
    def _select_best_candidates(self, candidates_by_id: Dict, total_questions: int) -> List[Dict]:
        """최적의 문제 후보 선택 (tmp.py 방식)"""
        final_questions = []
        
        for qid in range(1, total_questions + 1):
            candidates = candidates_by_id.get(qid, [])
            if len(candidates) == 0:
                continue
            
            prev_q = None
            next_q = None
            
            # previous
            for prev_id in range(qid - 1, 0, -1):
                if prev_id in candidates_by_id and candidates_by_id[prev_id]:
                    prev_q = candidates_by_id[prev_id][0]
                    break
            
            # next
            for next_id in range(qid + 1, total_questions + 1):
                if next_id in candidates_by_id and candidates_by_id[next_id]:
                    next_q = candidates_by_id[next_id][0]
                    break
            
            best_score = -999999
            best_candidate = None
            
            for candidate in candidates:
                score = self._compute_layout_score(candidate, prev_q, next_q)
                candidate["layout_score"] = score
                
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
            
            final_questions.append(best_candidate)
            print(f"    Q{qid} -> {best_candidate['source']}, score={round(best_score, 2)}")
        
        return final_questions
    
    def _build_regions(self, question_list: List[Dict], qinfo_map: Dict) -> Dict:
        """검출된 문제 위치로 영역 생성 (tmp.py 방식 - 순차적)"""
        regions = {}
                
        for i, q in enumerate(question_list):
            qid = q["question_id"]
            x1, y1, x2, y2 = q["bbox"]
            
            top = max(0, y1 - 20)
            
            # 다음 문제의 Y 좌표를 기준으로 영역 하단 결정 (중요!)
            if i < len(question_list) - 1:
                bottom = question_list[i + 1]["bbox"][1] - 10
            else:
                bottom = self.height - 20
            
            # 컬럼별 X 범위 (X 좌표 기준)
            if q["center_x"] < self.width / 2:
                left = 0
                right = self.width // 2 - 20
                column = 'left'
            else:
                left = self.width // 2 + 20
                right = self.width - 1
                column = 'right'
            
            pdf_left = left / self.scale
            pdf_top = top / self.scale
            pdf_right = right / self.scale
            pdf_bottom = bottom / self.scale

            regions[qid] = {
                'page': 0,
                'page_display': 1,
                'region': fitz.Rect(pdf_left, pdf_top, pdf_right, pdf_bottom),
                'question_bbox': (x1, y1, x2, y2),
                'question_type': qinfo_map[qid]['type'],
                'expected_answer': qinfo_map[qid]['expected_answer'],
                'score': qinfo_map[qid]['score'],
                'detection_source': q["source"],
                'layout_score': q.get("layout_score", 0)
            }
        
        return regions
    
    def _split_columns_by_position(self, candidates_by_id: Dict, total_questions: int):
        """tmp.py와 동일한 고정 컬럼 분할"""

        LEFT_IDS = []
        RIGHT_IDS = []

        for qid in range(1, total_questions + 1):

            if qid <= 16:
                LEFT_IDS.append(qid)
            else:
                RIGHT_IDS.append(qid)

        return LEFT_IDS, RIGHT_IDS

    def detect_all_questions(self, pdf_path: str, exam_data: Dict) -> Dict:
        """PDF에서 모든 문제 위치를 동적으로 검출 (tmp.py 로직 기반)"""
        if not fitz:
            raise ImportError("PyMuPDF (fitz) is required")
        
        doc = fitz.open(pdf_path)
        self.question_regions = {}
        qinfo_map = self._build_qinfo_map(exam_data)
        total_questions = exam_data.get(
            'total_questions',
            max(qinfo_map.keys()) if qinfo_map else 0
        )
        
        print("\n🔍 Dynamic question detection with tmp.py logic...")
        
        # 첫 페이지만 처리 (tmp.py와 동일)
        page_num = 0
        page = doc[page_num]
        
        print(f"  Page {page_num + 1}:")
        
        # 1. 이미지 준비
        self._prepare_image(page)
        
        # 2. EasyOCR 검출
        candidates_by_id = self._detect_with_easyocr(page_num, total_questions)
        
        # 3. JSON 앵커 검출
        json_candidates = self._detect_with_json_anchor(total_questions, qinfo_map)
        for qid, cand_list in json_candidates.items():
            candidates_by_id[qid].extend(cand_list)
        
        # 4. 컬럼 분할 - X 좌표 기반 (tmp.py 방식)
        LEFT_IDS, RIGHT_IDS = self._split_columns_by_position(candidates_by_id, total_questions)
        
        print(f"    Left column: {LEFT_IDS}")
        print(f"    Right column: {RIGHT_IDS}")
        
        # 5. 보간법 적용 (왼쪽/오른쪽 컬럼별)
        candidates_by_id = self._add_interpolation_candidates(candidates_by_id, LEFT_IDS)
        candidates_by_id = self._add_interpolation_candidates(candidates_by_id, RIGHT_IDS)
        
        # 6. 최적 후보 선택
        final_questions = self._select_best_candidates(candidates_by_id, total_questions)
        
        # 7. 영역 생성
        left_questions = []
        right_questions = []

        for q in final_questions:
            if q['center_x'] < self.width / 2:
                left_questions.append(q)
            else:
                right_questions.append(q)

        left_questions = sorted(left_questions, key=lambda x: x['center_y'])
        right_questions = sorted(right_questions, key=lambda x: x['center_y'])

        left_regions = self._build_regions(left_questions, qinfo_map)
        right_regions = self._build_regions(right_questions, qinfo_map)

        self.question_regions = {}
        self.question_regions.update(left_regions)
        self.question_regions.update(right_regions)
        
        doc.close()
        print(f"\n✅ Detected {len(self.question_regions)} questions")
        return self.question_regions