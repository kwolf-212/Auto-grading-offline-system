# exam_grader/omr.py
"""
OMR 공용 모듈 — PDF 영역 렌더, ROI 마킹 농도, 객관식/참거짓 선택 읽기.
다른 문제 유형(매칭 옆 체크, 설문지 등)에서도 `pdf_region_to_bgr`, `omr_roi_mark_score` 등을 재사용할 수 있다.
"""
from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING, Dict, List, Optional, Tuple

from dataclasses import dataclass
import cv2
import numpy as np

if TYPE_CHECKING:
    import fitz

try:
    import easyocr

    _EASYOCR_OK = True
except ImportError:
    _EASYOCR_OK = False

_easy_reader: Optional["easyocr.Reader"] = None


def omr_get_easyocr_reader():
    """프로세스당 한 번 초기화되는 EasyOCR Reader (없으면 None)."""
    global _easy_reader
    if not _EASYOCR_OK:
        return None
    if _easy_reader is None:
        _easy_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    return _easy_reader


def pdf_region_to_bgr(page: "fitz.Page", region: "fitz.Rect", zoom: float = 3.4) -> np.ndarray:
    """PDF 페이지의 한 직사각형을 고해상도 BGR 이미지로 렌더한다."""
    import fitz as _fitz

    if not isinstance(page, _fitz.Page):
        raise TypeError("page must be a fitz.Page")
    mat = _fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, clip=region, alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def omr_to_gray(img: np.ndarray) -> np.ndarray:
    if img is None or img.size == 0:
        return img
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def omr_clahe(gray: np.ndarray, clip_limit: float = 2.0, tile: int = 8) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    return clahe.apply(gray)


def omr_roi_mark_score(gray_roi: np.ndarray) -> float:
    """
    단일 그레이스케일 ROI에서 필기/마킹에 해당하는 잉크 비율(0~1 근사).
    괄호·얇은 인쇄선은 morphology로 억제한다.
    """
    if gray_roi is None or gray_roi.size < 16:
        return 0.0
    h, w = gray_roi.shape[:2]
    blur = cv2.GaussianBlur(gray_roi, (3, 3), 0)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    k = max(2, min(h, w) // 12)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    return float(np.mean(opened > 200))


def _parse_letter_from_ocr_text(text: str) -> Optional[str]:
    t = text.strip().lower().replace(" ", "")
    t = t.replace("(", "[").replace(")", "]")
    m = re.search(r"\[?\s*([a-j])\s*\]?", t)
    if m:
        return m.group(1)
    if len(t) == 1 and "a" <= t <= "j":
        return t
    return None


def _ocr_option_boxes(bgr: np.ndarray, reader) -> List[Tuple[str, int, int, int, int, float]]:
    found: Dict[str, Tuple[int, int, int, int, float]] = {}
    try:
        results = reader.readtext(bgr, detail=1, paragraph=False)
    except Exception:
        return []

    for box, text, conf in results:
        letter = _parse_letter_from_ocr_text(text)
        if letter is None or conf < 0.15:
            continue
        xs = [int(p[0]) for p in box]
        ys = [int(p[1]) for p in box]
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        if letter in found and conf <= found[letter][4]:
            continue
        found[letter] = (x1, y1, x2, y2, float(conf))

    out: List[Tuple[str, int, int, int, int, float]] = []
    for letter, (x1, y1, x2, y2, cf) in found.items():
        out.append((letter, x1, y1, x2, y2, cf))
    out.sort(key=lambda r: ((r[2] + r[4]) * 0.5, r[0]))
    return out


def _expand_roi(
    x1: int, y1: int, x2: int, y2: int, w: int, h: int, pad_x: float = 0.2, pad_y: float = 0.35
) -> Tuple[int, int, int, int]:
    pw = int((x2 - x1) * pad_x)
    ph = int((y2 - y1) * pad_y)
    nx1 = max(0, x1 - pw)
    ny1 = max(0, y1 - ph)
    nx2 = min(w, x2 + pw)
    ny2 = min(h, y2 + ph)
    if nx2 <= nx1 or ny2 <= ny1:
        return x1, y1, x2, y2
    return nx1, ny1, nx2, ny2


def _score_options_from_rois(gray: np.ndarray, rois: List[Tuple[str, int, int, int, int]]) -> Dict[str, float]:
    h, w = gray.shape[:2]
    scores: Dict[str, float] = {}
    for letter, x1, y1, x2, y2 in rois:
        ex1, ey1, ex2, ey2 = _expand_roi(x1, y1, x2, y2, w, h)
        roi = gray[ey1:ey2, ex1:ex2]
        scores[letter] = omr_roi_mark_score(roi)
    return scores


def _pick_best_relative(scores: Dict[str, float]) -> Tuple[str, float]:
    if not scores:
        return "", 0.0
    med = float(np.median(list(scores.values())))
    rel = {k: float(v - med) for k, v in scores.items()}
    best_letter = max(rel, key=rel.get)
    best_rel = rel[best_letter]
    best_abs = scores[best_letter]
    others_rel = [rel[k] for k in rel if k != best_letter]
    second_rel = max(others_rel) if others_rel else 0.0
    margin = best_rel - second_rel

    conf = min(1.0, best_abs * 2.0 + margin * 8.0)
    if best_abs < 0.055 and margin < 0.022:
        return "", 0.0
    if margin < 0.016:
        return "", conf * 0.25
    return best_letter, conf


def omr_equal_column_scores(gray: np.ndarray, num_slots: int) -> Dict[str, float]:
    """동일 폭 슬롯별 잉크 점수만 계산 (디버그·폴백 공용)."""
    h, w = gray.shape[:2]
    if h < 8 or w < 40 or num_slots < 2:
        return {}
    x0 = min(int(0.12 * w), w - 20)
    strip = gray[int(0.22 * h) :, x0:]
    sh, sw = strip.shape[:2]
    if sh < 4 or sw < num_slots * 8:
        return {}
    g = omr_clahe(strip)
    scores: Dict[str, float] = {}
    slot_w = sw // num_slots
    letters = [chr(ord("a") + i) for i in range(num_slots)]
    for i, L in enumerate(letters):
        x1 = i * slot_w + slot_w // 10
        x2 = (i + 1) * slot_w - slot_w // 10
        roi = g[:, x1:x2]
        scores[L] = omr_roi_mark_score(roi)
    return scores


def omr_equal_column_fallback(gray: np.ndarray, num_slots: int) -> Tuple[str, float]:
    """[a][b]… OCR 실패 시 동일 폭 슬롯 폴백."""
    scores = omr_equal_column_scores(gray, num_slots)
    if not scores:
        return "", 0.0
    return _pick_best_relative(scores)


def omr_read_mc_tf_selection_debug(
    bgr: np.ndarray,
    question_type: str,
    easyocr_reader=None,
) -> Tuple[str, float, Dict[str, Any]]:
    """
    `omr_read_mc_tf_selection`과 동일한 추정 + UI/로그용 디버그 dict.

    debug 키 예: ``path``, ``per_option_ink``, ``easyocr_label_count``,
    ``equal_column_scores``, ``image_shape``.
    """
    debug: Dict[str, Any] = {
        "path": "none",
        "per_option_ink": {},
        "easyocr_label_count": 0,
        "equal_column_scores": {},
        "image_shape": None,
    }
    if bgr is None or bgr.size == 0:
        return "", 0.0, debug

    gray = omr_to_gray(bgr)
    gray = omr_clahe(gray)
    debug["image_shape"] = tuple(int(x) for x in gray.shape[:2])

    is_tf = question_type in ("True/False", "true_false")
    max_letters = 2 if is_tf else 6
    min_letters = 2 if is_tf else 2
    num_slots = 2 if is_tf else 4

    reader = easyocr_reader if easyocr_reader is not None else omr_get_easyocr_reader()
    scores: Dict[str, float] = {}

    if reader is not None:
        boxes = _ocr_option_boxes(bgr, reader)
        debug["easyocr_label_count"] = len(boxes)
        allowed = {chr(ord("a") + i) for i in range(max_letters)}
        rois = [(L, x1, y1, x2, y2) for L, x1, y1, x2, y2, _ in boxes if L in allowed]
        if len(rois) >= min_letters:
            scores = _score_options_from_rois(gray, rois)

    eq_scores = omr_equal_column_scores(gray, num_slots)
    debug["equal_column_scores"] = dict(eq_scores)

    if len(scores) >= min_letters:
        letter, conf = _pick_best_relative(scores)
        debug["path"] = "easyocr_rois"
        debug["per_option_ink"] = dict(scores)
        if letter:
            return letter, conf, debug

    letter2, c2 = omr_equal_column_fallback(gray, num_slots)
    if letter2 and c2 >= 0.26:
        debug["path"] = "equal_columns_fallback"
        debug["per_option_ink"] = dict(eq_scores)
        return letter2, c2, debug

    if len(scores) >= min_letters:
        letter, conf = _pick_best_relative(scores)
        debug["path"] = "easyocr_rois_low_confidence"
        debug["per_option_ink"] = dict(scores)
        return letter, conf, debug

    return "", 0.0, debug


def omr_read_mc_tf_selection(
    bgr: np.ndarray,
    question_type: str,
    easyocr_reader=None,
) -> Tuple[str, float]:
    """
    객관식 / 참거짓 답안지 한 블록(BGR)에서 마킹된 한 글자(a,b,…)를 추정한다.

    Args:
        bgr: OpenCV BGR 이미지 (문제 영역 크롭).
        question_type: ``Multiple Choice`` / ``True/False`` 등 (참거짓은 2지선다로 처리).
        easyocr_reader: 재사용 Reader; None이면 `omr_get_easyocr_reader()`.

    Returns:
        (소문자 한 글자 또는 '', 신뢰도 0~1)
    """
    a, b, _ = omr_read_mc_tf_selection_debug(bgr, question_type, easyocr_reader=easyocr_reader)
    return a, b


def detect_marked_choice_bubble(
    bgr: np.ndarray,
    qtype: str,
    easyocr_reader=None,
) -> Tuple[str, float]:
    """하위 호환 별칭 — `omr_read_mc_tf_selection`과 동일."""
    return omr_read_mc_tf_selection(bgr, qtype, easyocr_reader=easyocr_reader)

def omr_debug_visualize_detection(bgr: np.ndarray, output_path: str = None) -> Dict[str, Any]:
    """
    OMR 감지 과정을 시각화하여 디버깅 정보 반환
    """
    debug_info = {}
    
    # 원본 이미지 저장
    debug_info['original_shape'] = bgr.shape
    
    # 그레이스케일 변환
    gray = omr_to_gray(bgr)
    debug_info['gray_shape'] = gray.shape
    
    # CLAHE 적용 결과
    clahe_applied = omr_clahe(gray)
    debug_info['clahe_mean'] = float(np.mean(clahe_applied))
    debug_info['clahe_std'] = float(np.std(clahe_applied))
    
    # EasyOCR 감지 결과
    reader = omr_get_easyocr_reader()
    if reader:
        results = reader.readtext(bgr, detail=1, paragraph=False)
        debug_info['ocr_detections'] = []
        for box, text, conf in results:
            debug_info['ocr_detections'].append({
                'text': text,
                'confidence': conf,
                'bbox': [[int(p[0]), int(p[1])] for p in box]
            })
    
    # 균등 분할 점수
    h, w = gray.shape
    num_slots = 4
    eq_scores = omr_equal_column_scores(gray, num_slots)
    debug_info['equal_column_scores'] = eq_scores
    
    # 최종 선택
    letter, conf = omr_read_mc_tf_selection(bgr, "Multiple Choice")
    debug_info['final_letter'] = letter
    debug_info['final_confidence'] = conf
    
    # 시각화 이미지 생성 (선택적)
    if output_path:
        vis_img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        h, w = gray.shape
        
        # 균등 분할 영역 표시
        x0 = int(0.12 * w)
        strip = gray[int(0.22 * h):, x0:]
        sh, sw = strip.shape
        slot_w = sw // num_slots
        
        for i in range(num_slots):
            x1 = i * slot_w + slot_w // 10 + x0
            x2 = (i + 1) * slot_w - slot_w // 10 + x0
            cv2.rectangle(vis_img, (x1, int(0.22 * h)), (x2, h), (0, 255, 0), 2)
            cv2.putText(vis_img, chr(ord('a') + i), (x1 + 5, int(0.22 * h) + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # 선택된 항목 표시
        if letter:
            idx = ord(letter) - ord('a')
            if 0 <= idx < num_slots:
                x1 = idx * slot_w + slot_w // 10 + x0
                x2 = (idx + 1) * slot_w - slot_w // 10 + x0
                cv2.rectangle(vis_img, (x1, int(0.22 * h)), (x2, h), (0, 0, 255), 3)
        
        cv2.imwrite(output_path, vis_img)
    
    return debug_info


def omr_debug_analyze_bracket_region(bgr: np.ndarray, expected_letters: List[str] = None) -> Dict[str, Any]:
    """
    괄호 형태 선택지([a], [b], [c], [d]) 영역 분석 디버깅
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    debug_info = {
        'bracket_regions': {},
        'intensity_scores': {},
        'binary_ratios': {},
        'detected_letters': {}
    }
    
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # 수평선 감지로 영역 분할
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, 
                            minLineLength=100, maxLineGap=20)
    
    # 각 예상 글자 영역 분석
    for i, letter in enumerate(expected_letters):
        # 영역을 균등 분할 (실제로는 더 정교한 방법 필요)
        region_width = w // len(expected_letters)
        x1 = i * region_width
        x2 = (i + 1) * region_width
        
        # 괄호 찾기 시도
        roi = gray[:, x1:x2]
        
        # 괄호 [] 패턴 찾기
        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # 수직선 패턴 찾기 (괄호의 세로선)
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, roi.shape[0]//3))
        vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
        
        # 밝기 분석
        mean_intensity = np.mean(roi)
        dark_ratio = np.sum(roi < 100) / roi.size
        
        debug_info['bracket_regions'][letter] = {
            'x_range': (x1, x2),
            'vertical_lines_detected': np.sum(vertical_lines > 0) > 100,
            'mean_intensity': float(mean_intensity),
            'dark_ratio': float(dark_ratio)
        }
        
        # 마킹 점수 (어두울수록 높음)
        debug_info['intensity_scores'][letter] = 1.0 - (mean_intensity / 255.0)
        debug_info['binary_ratios'][letter] = float(dark_ratio)
    
    # 최종 선택
    best_letter = max(debug_info['intensity_scores'], key=debug_info['intensity_scores'].get)
    best_score = debug_info['intensity_scores'][best_letter]
    
    debug_info['selected_letter'] = best_letter if best_score > 0.35 else ''
    debug_info['selection_confidence'] = best_score
    
    return debug_info

def detect_bracket_choices(bgr: np.ndarray, expected_letters: List[str] = None) -> Dict[str, Tuple[int, int, int, int]]:
    """
    [a], [b], [c], [d] 형태의 괄호 선택지 영역을 자동 감지
    tmp.py의 토큰 분할 알고리즘 활용
    
    Args:
        bgr: 입력 이미지 (BGR)
        expected_letters: 예상 글자 목록 (기본: ['a','b','c','d'])
    
    Returns:
        { 'a': (x1, y1, x2, y2), 'b': (x1, y1, x2, y2), ... }
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    h, w = bgr.shape[:2]
    
    # =========================
    # 1. 그레이스케일 변환
    # =========================
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    
    # =========================
    # 2. Adaptive Threshold (tmp.py 방식)
    # =========================
    th = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11,  # blockSize
        2    # C
    )
    
    # =========================
    # 3. Morphology (노이즈 제거)
    # =========================
    kernel = np.ones((2, 2), np.uint8)
    clean = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    
    # =========================
    # 4. 수평 투영으로 선택지 행 찾기
    # =========================
    horizontal_projection = np.sum(clean > 0, axis=1)
    
    # 투영값 스무딩
    horizontal_projection = np.convolve(
        horizontal_projection,
        np.ones(5)/5,
        mode='same'
    )
    
    # 동적 임계값 설정 (최대값의 15%)
    h_threshold = np.max(horizontal_projection) * 0.15
    
    # 선택지가 있는 행 찾기
    choice_rows = []
    in_row = False
    start_row = 0
    
    for i, proj in enumerate(horizontal_projection):
        if proj > h_threshold and not in_row:
            in_row = True
            start_row = i
        elif proj <= h_threshold and in_row:
            in_row = False
            if i - start_row > 15:  # 최소 높이
                choice_rows.append((start_row, i))
    
    if not choice_rows:
        return {}
    
    # 가장 큰 행을 선택지 행으로 선택
    main_row = max(choice_rows, key=lambda r: r[1] - r[0])
    row_y1, row_y2 = main_row
    
    # =========================
    # 5. 수직 투영으로 개별 토큰 분리 (tmp.py 방식)
    # =========================
    row_roi = clean[row_y1:row_y2, :]
    vertical_projection = np.sum(row_roi > 0, axis=0)
    
    # 투영값 스무딩
    vertical_projection = np.convolve(
        vertical_projection,
        np.ones(5)/5,
        mode='same'
    )
    
    # 수직 투영 임계값
    v_threshold = 1
    
    # 연속된 영역 찾기 (세그먼트)
    segments = []
    in_token = False
    start_x = 0
    
    for x in range(len(vertical_projection)):
        if vertical_projection[x] > v_threshold and not in_token:
            start_x = x
            in_token = True
        elif vertical_projection[x] <= v_threshold and in_token:
            end_x = x
            if end_x - start_x > 5:  # 최소 너비
                segments.append((start_x, end_x))
            in_token = False
    
    # =========================
    # 6. 가까운 세그먼트 병합 (tmp.py 방식)
    # =========================
    merged = []
    if len(segments) > 0:
        current = list(segments[0])
        for seg in segments[1:]:
            gap = seg[0] - current[1]
            # 토큰 내부 문자 간격이 8px 미만이면 병합
            if gap < 8:
                current[1] = seg[1]
            else:
                merged.append(tuple(current))
                current = list(seg)
        merged.append(tuple(current))
    
    # =========================
    # 7. 각 토큰의 바운딩 박스 계산 (tmp.py 방식)
    # =========================
    token_boxes = []
    for x1, x2 in merged:
        col = clean[row_y1:row_y2, x1:x2]
        ys, xs = np.where(col > 0)
        if len(ys) == 0:
            continue
        y1 = np.min(ys) + row_y1
        y2 = np.max(ys) + row_y1
        token_boxes.append((x1, y1, x2 - x1, y2 - y1))
    
    # =========================
    # 8. 좌표 정렬 및 글자 인식
    # =========================
    # x 좌표 기준 정렬
    token_boxes.sort(key=lambda b: b[0])
    
    # 필요한 개수만큼만 사용
    num_choices = len(expected_letters)
    token_boxes = token_boxes[:num_choices]
    
    bracket_coords = {}
    
    for i, (x, y, w, h) in enumerate(token_boxes):
        if i >= num_choices:
            break
        
        # 약간 여유를 두고 확장 (마킹 영역 포함)
        pad_x = 8
        pad_y = 8
        final_x1 = max(0, x - pad_x)
        final_x2 = min(w, x + w + pad_x)
        final_y1 = max(0, y - pad_y)
        final_y2 = min(h, y + h + pad_y)
        
        # 해당 영역에서 글자 인식 시도
        bracket_img = bgr[final_y1:final_y2, final_x1:final_x2]
        detected_letter = _recognize_bracket_letter_enhanced(bracket_img)
        
        expected = expected_letters[i] if i < len(expected_letters) else None
        
        # 감지된 글자와 예상 글자 매칭
        if detected_letter and expected and detected_letter == expected:
            bracket_coords[expected] = (final_x1, final_y1, final_x2, final_y2)
        else:
            # 위치 기반 할당 (a, b, c, d 순서)
            bracket_coords[expected_letters[i]] = (final_x1, final_y1, final_x2, final_y2)
    
    return bracket_coords


def _recognize_bracket_letter_enhanced(bracket_img: np.ndarray) -> Optional[str]:
    """
    향상된 괄호 내 글자 인식 (tmp.py의 토큰 분할 방식 활용)
    """
    if bracket_img is None or bracket_img.size == 0:
        return None
    
    gray = cv2.cvtColor(bracket_img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    # Adaptive Threshold
    th = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )
    
    # Morphology로 노이즈 제거
    kernel = np.ones((2, 2), np.uint8)
    clean = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    
    # 괄호 안쪽 영역 추출 (좌우 20%, 상하 20% 제외)
    inner_x1 = int(w * 0.25)
    inner_x2 = int(w * 0.75)
    inner_y1 = int(h * 0.25)
    inner_y2 = int(h * 0.75)
    
    if inner_x2 <= inner_x1 or inner_y2 <= inner_y1:
        inner = clean
    else:
        inner = clean[inner_y1:inner_y2, inner_x1:inner_x2]
    
    # 수직 투영으로 문자 영역 찾기
    vertical_proj = np.sum(inner > 0, axis=0)
    vertical_proj = np.convolve(vertical_proj, np.ones(3)/3, mode='same')
    
    # 문자 영역 찾기
    char_segments = []
    in_char = False
    start = 0
    
    for x in range(len(vertical_proj)):
        if vertical_proj[x] > 2 and not in_char:
            start = x
            in_char = True
        elif vertical_proj[x] <= 2 and in_char:
            end = x
            if end - start > 3:
                char_segments.append((start, end))
            in_char = False
    
    if not char_segments:
        return None
    
    # 가장 큰 문자 영역 선택
    char_segments.sort(key=lambda s: s[1] - s[0], reverse=True)
    cx1, cx2 = char_segments[0]
    
    # y 좌표 찾기
    char_roi = inner[:, cx1:cx2]
    ys, xs = np.where(char_roi > 0)
    if len(ys) == 0:
        return None
    
    cy1 = np.min(ys)
    cy2 = np.max(ys)
    
    # 문자 이미지 추출
    char_img = inner[cy1:cy2, cx1:cx2]
    
    if char_img.size == 0:
        return None
    
    # =========================
    # EasyOCR 인식 시도
    # =========================
    try:
        import easyocr
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        # 원본 이미지에서 인식 시도
        results = reader.readtext(bracket_img, detail=0, paragraph=False)
        for text in results:
            cleaned = re.sub(r'[\[\]\(\)\s]', '', text.lower())
            if len(cleaned) == 1 and 'a' <= cleaned <= 'z':
                return cleaned
    except Exception:
        pass
    
    # =========================
    # Tesseract 인식 시도
    # =========================
    try:
        import pytesseract
        # 문자 이미지 확대
        char_img_large = cv2.resize(char_img, (char_img.shape[1] * 3, char_img.shape[0] * 3))
        text = pytesseract.image_to_string(
            char_img_large, 
            config='--psm 8 -c tessedit_char_whitelist=abcdefghijklmnopqrstuvwxyz'
        )
        cleaned = re.sub(r'[\[\]\(\)\s]', '', text.lower())
        if len(cleaned) == 1 and 'a' <= cleaned <= 'z':
            return cleaned
    except Exception:
        pass
    
    # =========================
    # 템플릿 매칭 폴백 (간단한 형태 분석)
    # =========================
    # 문자의 종횡비로 추정
    aspect_ratio = char_img.shape[1] / char_img.shape[0] if char_img.shape[0] > 0 else 1
    
    if 0.5 < aspect_ratio < 1.5:
        # 밀도 기반 간단한 분류 (실제로는 더 정교한 방법 필요)
        density = np.sum(char_img > 0) / char_img.size
        
        # a와 e는 밀도가 낮음, b/d/p/q는 밀도가 중간, c/o는 밀도가 높음
        if density < 0.3:
            return 'a'  # 또는 'e'
        elif density > 0.6:
            return 'o'  # 또는 'c'
        else:
            return 'b'  # 또는 'd'
    
    return None


def omr_read_bracket_selection(
    bgr: np.ndarray,
    num_choices: int = 4,
    expected_letters: List[str] = None,
) -> Tuple[str, float, Dict[str, Any]]:
    """
    괄호 형태 [a], [b], [c], [d] 선택지에서 마킹된 항목 감지
    
    Args:
        bgr: 문제 영역 이미지
        num_choices: 선택지 개수 (기본 4)
        expected_letters: 예상 글자 목록
    
    Returns:
        (선택된 글자, 신뢰도, 디버그 정보)
    """
    if expected_letters is None:
        expected_letters = [chr(ord('a') + i) for i in range(num_choices)]
    
    debug = {
        'method': 'bracket_detection',
        'detected_regions': {},
        'marking_scores': {},
        'binary_ratios': {}
    }
    
    # 1. 괄호 영역 감지
    bracket_coords = detect_bracket_choices(bgr, expected_letters)
    
    if not bracket_coords:
        # 폴백: 균등 분할
        return omr_read_mc_tf_selection(bgr, "Multiple Choice"), debug
    
    debug['detected_regions'] = bracket_coords
    
    # 2. 각 영역의 마킹 정도 측정
    gray = omr_to_gray(bgr)
    gray = omr_clahe(gray)
    
    scores = {}
    binary_ratios = {}
    
    for letter, (x1, y1, x2, y2) in bracket_coords.items():
        roi = gray[y1:y2, x1:x2]
        
        if roi.size == 0:
            scores[letter] = 0.0
            continue
        
        # 마킹 점수 계산
        marking_score = _calculate_bracket_marking_score(roi)
        scores[letter] = marking_score
        
        # 이진화 비율 계산
        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        binary_ratios[letter] = float(np.sum(binary > 0) / binary.size)
    
    debug['marking_scores'] = scores
    debug['binary_ratios'] = binary_ratios
    
    # 3. 최적 선택 결정
    best_letter, confidence = _pick_best_bracket_marking(scores, binary_ratios)
    
    debug['best_letter'] = best_letter
    debug['confidence'] = confidence
    
    return best_letter, confidence, debug


def _calculate_bracket_marking_score(roi: np.ndarray) -> float:
    """
    괄호 영역 내 마킹 정도 계산 (네모 괄호 특화)
    """
    h, w = roi.shape
    
    # 중앙 영역에 가중치 부여 (괄호 안쪽이 중요)
    center_y1 = h // 3
    center_y2 = 2 * h // 3
    center_x1 = w // 3
    center_x2 = 2 * w // 3
    
    center_roi = roi[center_y1:center_y2, center_x1:center_x2]
    
    if center_roi.size == 0:
        # 전체 영역 사용
        _, binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        marked_ratio = np.sum(binary > 0) / binary.size
        return marked_ratio
    
    # 중앙 영역 가중치 70%, 전체 영역 30%
    _, center_binary = cv2.threshold(center_roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    center_marked_ratio = np.sum(center_binary > 0) / center_binary.size
    
    _, full_binary = cv2.threshold(roi, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    full_marked_ratio = np.sum(full_binary > 0) / full_binary.size
    
    # 중심부에 더 높은 가중치 (학생이 칠하는 부분은 괄호 안쪽)
    score = 0.7 * center_marked_ratio + 0.3 * full_marked_ratio
    
    return min(1.0, score)


def _pick_best_bracket_marking(
    scores: Dict[str, float], 
    binary_ratios: Dict[str, float]
) -> Tuple[str, float]:
    """
    괄호 마킹 점수에서 최적 선택 결정
    """
    if not scores:
        return "", 0.0
    
    # 유효 마킹 임계값
    MARKING_THRESHOLD = 0.25
    
    # 임계값 이상인 후보만 고려
    candidates = {k: v for k, v in scores.items() if v >= MARKING_THRESHOLD}
    
    if not candidates:
        # 가장 높은 점수라도 임계값 미만이면 미응답
        best_letter = max(scores, key=scores.get)
        best_score = scores[best_letter]
        if best_score < 0.15:
            return "", 0.0
        return best_letter, best_score * 0.5
    
    # 점수순 정렬
    sorted_items = sorted(candidates.items(), key=lambda x: x[1], reverse=True)
    best_letter, best_score = sorted_items[0]
    
    if len(candidates) == 1:
        # 단일 마킹: 높은 신뢰도
        confidence = min(1.0, best_score * 1.2)
        return best_letter, confidence
    
    # 중복 마킹 처리
    second_score = sorted_items[1][1]
    margin = best_score - second_score
    
    if margin > 0.15:
        confidence = min(1.0, 0.7 + margin)
    elif margin > 0.08:
        confidence = 0.5 + margin
    else:
        confidence = 0.3
    
    return best_letter, confidence

# exam_grader/omr.py (하단에 추가)

def visualize_token_segmentation(
    bgr: np.ndarray, 
    expected_letters: List[str] = None,
    save_path: str = None
) -> Dict[str, Any]:
    """
    tmp.py 스타일의 토큰 분할 결과를 시각화하는 디버그 함수
    
    Args:
        bgr: 입력 이미지 (BGR)
        expected_letters: 예상 글자 목록
        save_path: 결과 이미지 저장 경로 (선택)
    
    Returns:
        디버그 정보 딕셔너리
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    debug_info = {
        'num_tokens': 0,
        'token_boxes': [],
        'detected_letters': [],
        'step_images': {}
    }
    
    h, w = bgr.shape[:2]
    
    # =========================
    # 1. 그레이스케일 변환
    # =========================
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    debug_info['step_images']['gray'] = gray.copy()
    
    # =========================
    # 2. Adaptive Threshold
    # =========================
    th = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )
    debug_info['step_images']['threshold'] = th.copy()
    
    # =========================
    # 3. Morphology (노이즈 제거)
    # =========================
    kernel = np.ones((2, 2), np.uint8)
    clean = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    debug_info['step_images']['clean'] = clean.copy()
    
    # =========================
    # 4. 수평 투영
    # =========================
    horizontal_projection = np.sum(clean > 0, axis=1)
    horizontal_projection_smooth = np.convolve(
        horizontal_projection,
        np.ones(5)/5,
        mode='same'
    )
    
    debug_info['horizontal_projection'] = {
        'raw': horizontal_projection.tolist(),
        'smooth': horizontal_projection_smooth.tolist()
    }
    
    # 선택지 행 찾기
    h_threshold = np.max(horizontal_projection_smooth) * 0.15
    choice_rows = []
    in_row = False
    start_row = 0
    
    for i, proj in enumerate(horizontal_projection_smooth):
        if proj > h_threshold and not in_row:
            start_row = i
            in_row = True
        elif proj <= h_threshold and in_row:
            if i - start_row > 15:
                choice_rows.append((start_row, i))
            in_row = False
    
    if not choice_rows:
        debug_info['error'] = 'No choice rows found'
        return debug_info
    
    main_row = max(choice_rows, key=lambda r: r[1] - r[0])
    row_y1, row_y2 = main_row
    debug_info['choice_row'] = {'y1': row_y1, 'y2': row_y2}
    
    # =========================
    # 5. 수직 투영
    # =========================
    row_roi = clean[row_y1:row_y2, :]
    vertical_projection = np.sum(row_roi > 0, axis=0)
    vertical_projection_smooth = np.convolve(
        vertical_projection,
        np.ones(5)/5,
        mode='same'
    )
    
    debug_info['vertical_projection'] = {
        'raw': vertical_projection.tolist(),
        'smooth': vertical_projection_smooth.tolist()
    }
    
    # 세그먼트 찾기
    v_threshold = 1
    segments = []
    in_token = False
    start_x = 0
    
    for x in range(len(vertical_projection_smooth)):
        if vertical_projection_smooth[x] > v_threshold and not in_token:
            start_x = x
            in_token = True
        elif vertical_projection_smooth[x] <= v_threshold and in_token:
            end_x = x
            if end_x - start_x > 5:
                segments.append((start_x, end_x))
            in_token = False
    
    debug_info['segments'] = segments
    
    # =========================
    # 6. 세그먼트 병합
    # =========================
    merged = []
    if len(segments) > 0:
        current = list(segments[0])
        for seg in segments[1:]:
            gap = seg[0] - current[1]
            if gap < 8:
                current[1] = seg[1]
            else:
                merged.append(tuple(current))
                current = list(seg)
        merged.append(tuple(current))
    
    debug_info['merged_segments'] = merged
    
    # =========================
    # 7. 토큰 바운딩 박스 계산
    # =========================
    token_boxes = []
    for x1, x2 in merged:
        col = clean[row_y1:row_y2, x1:x2]
        ys, xs = np.where(col > 0)
        if len(ys) == 0:
            continue
        y1 = np.min(ys) + row_y1
        y2 = np.max(ys) + row_y1
        token_boxes.append((x1, y1, x2 - x1, y2 - y1))
    
    debug_info['token_boxes'] = token_boxes
    debug_info['num_tokens'] = len(token_boxes)
    
    # =========================
    # 8. 글자 인식
    # =========================
    token_boxes.sort(key=lambda b: b[0])
    
    for i, (x, y, w, h) in enumerate(token_boxes[:len(expected_letters)]):
        # 확장된 영역
        pad = 5
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(bgr.shape[1], x + w + pad)
        y2 = min(bgr.shape[0], y + h + pad)
        
        token_img = bgr[y1:y2, x1:x2]
        detected = _recognize_bracket_letter_enhanced(token_img)
        
        debug_info['detected_letters'].append({
            'index': i,
            'expected': expected_letters[i] if i < len(expected_letters) else None,
            'detected': detected,
            'bbox': (x1, y1, x2, y2)
        })
    
    # =========================
    # 9. 시각화 이미지 생성
    # =========================
    vis_img = bgr.copy()
    
    # 선택지 행 표시 (노란색)
    cv2.rectangle(vis_img, (0, row_y1), (w, row_y2), (0, 255, 255), 2)
    cv2.putText(vis_img, "Choice Row", (10, row_y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    
    # 토큰 박스 표시 (초록색)
    for idx, (x, y, tw, th) in enumerate(token_boxes):
        cv2.rectangle(vis_img, (x, y), (x + tw, y + th), (0, 255, 0), 2)
        cv2.putText(vis_img, f"T{idx}", (x, y - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    
    # 최종 선택지 영역 표시 (빨간색)
    bracket_coords = detect_bracket_choices(bgr, expected_letters)
    for letter, (x1, y1, x2, y2) in bracket_coords.items():
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 0, 255), 2)
        cv2.putText(vis_img, f"[{letter}]", (x1, y1 - 3),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    
    debug_info['visualization'] = vis_img
    
    if save_path:
        cv2.imwrite(save_path, vis_img)
    
    return debug_info


def debug_detect_bracket_choices(
    bgr: np.ndarray,
    expected_letters: List[str] = None,
    show_plots: bool = True
) -> Tuple[Dict[str, Tuple[int, int, int, int]], Dict[str, Any]]:
    """
    디버깅 정보를 포함한 괄호 선택지 감지
    
    Returns:
        (bracket_coords, debug_info)
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    # 토큰 분할 시각화
    debug_info = visualize_token_segmentation(bgr, expected_letters)
    
    # 실제 감지 실행
    bracket_coords = detect_bracket_choices(bgr, expected_letters)
    
    if show_plots and debug_info.get('visualization') is not None:
        # matplotlib으로 표시
        import matplotlib.pyplot as plt
        
        vis_rgb = cv2.cvtColor(debug_info['visualization'], cv2.COLOR_BGR2RGB)
        
        plt.figure(figsize=(14, 8))
        plt.imshow(vis_rgb)
        plt.title("Token Segmentation & Bracket Detection")
        plt.axis("off")
        
        # 투영 그래프 오버레이
        ax_inset = plt.axes([0.65, 0.02, 0.3, 0.15])
        h_proj = debug_info.get('horizontal_projection', {}).get('smooth', [])
        if h_proj:
            ax_inset.plot(h_proj, color='blue')
            ax_inset.axhline(y=np.max(h_proj) * 0.15, color='red', linestyle='--')
            ax_inset.set_title('Horizontal Projection')
            ax_inset.set_xlabel('Row')
            ax_inset.set_ylabel('Dark Pixels')
        
        plt.show()
    
    return bracket_coords, debug_info


def save_token_segmentation_image(
    bgr: np.ndarray,
    output_path: str,
    expected_letters: List[str] = None
) -> None:
    """
    토큰 분할 결과를 이미지 파일로 저장
    """
    debug_info = visualize_token_segmentation(bgr, expected_letters, save_path=output_path)
    print(f"Token segmentation saved to: {output_path}")
    print(f"Detected {debug_info['num_tokens']} tokens")
    for token in debug_info.get('detected_letters', []):
        print(f"  Token {token['index']}: expected={token['expected']}, detected={token['detected']}")

def detect_bracket_choices_v2(bgr: np.ndarray, expected_letters: List[str] = None) -> Dict[str, Tuple[int, int, int, int]]:
    """
    tmp.py의 토큰 분할 알고리즘을 정확히 구현한 괄호 선택지 감지 (개선 버전)
    
    Args:
        bgr: 입력 이미지 (BGR)
        expected_letters: 예상 글자 목록 (기본: ['a','b','c','d'])
    
    Returns:
        { 'a': (x1, y1, x2, y2), 'b': (x1, y1, x2, y2), ... }
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    h, w = bgr.shape[:2]
    
    # =========================
    # 1. 그레이스케일 변환
    # =========================
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    
    # =========================
    # 2. Adaptive Threshold (tmp.py 정확히 동일)
    # =========================
    th = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )
    
    # =========================
    # 3. Morphology (tmp.py 정확히 동일)
    # =========================
    kernel = np.ones((2, 2), np.uint8)
    clean = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    
    # =========================
    # 4. 수직 투영 (tmp.py 방식 - 전체 이미지 기준)
    # =========================
    projection = np.sum(clean > 0, axis=0)
    projection = np.convolve(projection, np.ones(5)/5, mode='same')
    
    # 세그먼트 찾기
    segments = []
    in_token = False
    start_x = 0
    
    for x in range(len(projection)):
        if projection[x] > 1 and not in_token:
            start_x = x
            in_token = True
        elif projection[x] <= 1 and in_token:
            end_x = x
            if end_x - start_x > 5:
                segments.append((start_x, end_x))
            in_token = False
    
    # =========================
    # 5. 가까운 세그먼트 병합 (tmp.py 방식)
    # =========================
    merged = []
    if len(segments) > 0:
        current = list(segments[0])
        for seg in segments[1:]:
            gap = seg[0] - current[1]
            if gap < 8:
                current[1] = seg[1]
            else:
                merged.append(tuple(current))
                current = list(seg)
        merged.append(tuple(current))
    
    # =========================
    # 6. 각 토큰의 바운딩 박스 계산 (tmp.py 방식)
    # =========================
    token_boxes = []
    for x1, x2 in merged:
        col = clean[:, x1:x2]
        ys, xs = np.where(col > 0)
        if len(ys) == 0:
            continue
        y1 = np.min(ys)
        y2 = np.max(ys)
        token_boxes.append((x1, y1, x2 - x1, y2 - y1))
    
    if len(token_boxes) == 0:
        return {}
    
    # =========================
    # 7. x 좌표 기준 정렬
    # =========================
    token_boxes.sort(key=lambda b: b[0])
    
    # =========================
    # 8. y 좌표 기준 정렬 (여러 줄인 경우 처리)
    # =========================
    rows = []
    current_row = []
    y_threshold = 20
    
    for box in token_boxes:
        if not current_row:
            current_row.append(box)
        else:
            if abs(box[1] - current_row[0][1]) < y_threshold:
                current_row.append(box)
            else:
                current_row.sort(key=lambda b: b[0])
                rows.extend(current_row)
                current_row = [box]
    
    if current_row:
        current_row.sort(key=lambda b: b[0])
        rows.extend(current_row)
    
    token_boxes = rows[:len(expected_letters)]
    
    # =========================
    # 9. 글자 인식 및 좌표 할당
    # =========================
    bracket_coords = {}
    
    for i, (x, y, w, h) in enumerate(token_boxes):
        if i >= len(expected_letters):
            break
        
        # 영역 확장 (마킹 영역 포함)
        pad_x = 10
        pad_y = 8
        final_x1 = max(0, x - pad_x)
        final_x2 = min(bgr.shape[1], x + w + pad_x)
        final_y1 = max(0, y - pad_y)
        final_y2 = min(bgr.shape[0], y + h + pad_y)
        
        expected = expected_letters[i]
        bracket_coords[expected] = (final_x1, final_y1, final_x2, final_y2)
    
    return bracket_coords


def detect_bracket_choices_robust(bgr: np.ndarray, expected_letters: List[str] = None) -> Dict[str, Tuple[int, int, int, int]]:
    """
    여러 방법을 조합한 강건한 괄호 선택지 감지
    
    Args:
        bgr: 입력 이미지 (BGR)
        expected_letters: 예상 글자 목록
    
    Returns:
        { 'a': (x1, y1, x2, y2), 'b': (x1, y1, x2, y2), ... }
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    # 방법 1: tmp.py 방식으로 시도
    coords = detect_bracket_choices_v2(bgr, expected_letters)
    if len(coords) >= len(expected_letters):
        return coords
    
    # 방법 2: 원본 detect_bracket_choices 시도
    coords = detect_bracket_choices(bgr, expected_letters)
    if len(coords) >= len(expected_letters):
        return coords
    
    # 방법 3: 균등 분할 폴백
    h, w = bgr.shape[:2]
    num = len(expected_letters)
    slot_w = w // num
    coords = {}
    for i, letter in enumerate(expected_letters):
        x1 = i * slot_w
        x2 = (i + 1) * slot_w
        coords[letter] = (x1, 0, x2, h)
    
    return coords

# omr.py에 추가할 함수들

def visualize_token_segmentation_v2(
    bgr: np.ndarray,
    expected_letters: List[str] = None,
    save_path: str = None,
    show_debug: bool = False
) -> Dict[str, Any]:
    """
    detect_bracket_choices_v2 함수의 토큰 분할 결과를 시각화하는 디버그 함수
    
    Args:
        bgr: 입력 이미지 (BGR)
        expected_letters: 예상 글자 목록
        save_path: 결과 이미지 저장 경로 (선택)
        show_debug: 디버그 정보 출력 여부
    
    Returns:
        디버그 정보 딕셔너리
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    debug_info = {
        'method': 'detect_bracket_choices_v2',
        'num_tokens': 0,
        'token_boxes': [],
        'detected_regions': {},
        'detected_letters': [],
        'step_images': {}
    }
    
    h, w = bgr.shape[:2]
    
    # =========================
    # 1. 그레이스케일 변환
    # =========================
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    debug_info['step_images']['gray'] = gray.copy()
    
    # =========================
    # 2. Adaptive Threshold
    # =========================
    th = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )
    debug_info['step_images']['threshold'] = th.copy()
    
    # =========================
    # 3. Morphology
    # =========================
    kernel = np.ones((2, 2), np.uint8)
    clean = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    debug_info['step_images']['clean'] = clean.copy()
    
    # =========================
    # 4. 수직 투영
    # =========================
    projection = np.sum(clean > 0, axis=0)
    projection_smooth = np.convolve(projection, np.ones(5)/5, mode='same')
    
    debug_info['projection'] = {
        'raw': projection.tolist(),
        'smooth': projection_smooth.tolist()
    }
    
    # =========================
    # 5. 세그먼트 찾기
    # =========================
    segments = []
    in_token = False
    start_x = 0
    
    for x in range(len(projection_smooth)):
        if projection_smooth[x] > 1 and not in_token:
            start_x = x
            in_token = True
        elif projection_smooth[x] <= 1 and in_token:
            end_x = x
            if end_x - start_x > 5:
                segments.append((start_x, end_x))
            in_token = False
    
    debug_info['segments'] = segments
    
    # =========================
    # 6. 세그먼트 병합
    # =========================
    merged = []
    if len(segments) > 0:
        current = list(segments[0])
        for seg in segments[1:]:
            gap = seg[0] - current[1]
            if gap < 8:
                current[1] = seg[1]
            else:
                merged.append(tuple(current))
                current = list(seg)
        merged.append(tuple(current))
    
    debug_info['merged_segments'] = merged
    
    # =========================
    # 7. 바운딩 박스 계산
    # =========================
    token_boxes = []
    for x1, x2 in merged:
        col = clean[:, x1:x2]
        ys, xs = np.where(col > 0)
        if len(ys) == 0:
            continue
        y1 = np.min(ys)
        y2 = np.max(ys)
        token_boxes.append((x1, y1, x2 - x1, y2 - y1))
    
    debug_info['token_boxes'] = token_boxes
    debug_info['num_tokens'] = len(token_boxes)
    
    # =========================
    # 8. y 좌표 기준 정렬 (여러 줄 처리)
    # =========================
    if token_boxes:
        rows = []
        current_row = []
        y_threshold = 20
        
        for box in token_boxes:
            if not current_row:
                current_row.append(box)
            else:
                if abs(box[1] - current_row[0][1]) < y_threshold:
                    current_row.append(box)
                else:
                    current_row.sort(key=lambda b: b[0])
                    rows.extend(current_row)
                    current_row = [box]
        
        if current_row:
            current_row.sort(key=lambda b: b[0])
            rows.extend(current_row)
        
        token_boxes = rows
    
    # =========================
    # 9. x 좌표 기준 정렬
    # =========================
    token_boxes.sort(key=lambda b: b[0])
    
    # =========================
    # 10. 최종 선택지 영역 계산
    # =========================
    detected_regions = {}
    
    for i, (x, y, tw, th_h) in enumerate(token_boxes[:len(expected_letters)]):
        # 영역 확장
        pad_x = 10
        pad_y = 8
        final_x1 = max(0, x - pad_x)
        final_x2 = min(bgr.shape[1], x + tw + pad_x)
        final_y1 = max(0, y - pad_y)
        final_y2 = min(bgr.shape[0], y + th_h + pad_y)
        
        expected = expected_letters[i] if i < len(expected_letters) else None
        if expected:
            detected_regions[expected] = (final_x1, final_y1, final_x2, final_y2)
            
            # 글자 인식 시도
            region_img = bgr[final_y1:final_y2, final_x1:final_x2]
            detected_letter = _recognize_bracket_letter_enhanced(region_img)
            debug_info['detected_letters'].append({
                'index': i,
                'expected': expected,
                'detected': detected_letter,
                'bbox': (final_x1, final_y1, final_x2, final_y2)
            })
    
    debug_info['detected_regions'] = detected_regions
    
    # =========================
    # 11. 시각화 이미지 생성
    # =========================
    # 투영값 오버레이를 위한 상단 영역 확보 (이미지 상단에 그래프 추가)
    graph_height = min(100, h // 3)  # 그래프 높이를 이미지 높이의 1/3 이하로 제한
    
    # 올바른 크기의 배열 생성
    vis_with_graph = np.zeros((h + graph_height, w, 3), dtype=np.uint8)
    
    # 원본 이미지 복사 (bgr 사용, vis_img 대신)
    vis_with_graph[graph_height:graph_height + h, :, :] = bgr  # 수정: vis_img -> bgr
    
    # 수직 투영 그래프 그리기
    max_proj = max(projection_smooth) if len(projection_smooth) > 0 and max(projection_smooth) > 0 else 1
    for x in range(min(w, len(projection_smooth))):
        proj_height = int((projection_smooth[x] / max_proj) * (graph_height - 10))
        if proj_height > 0:
            cv2.line(vis_with_graph, 
                     (x, graph_height - proj_height),
                     (x, graph_height - 1),
                     (100, 100, 255), 1)
    
    # 임계값 선 그리기
    threshold_val = 1
    threshold_y = graph_height - int((threshold_val / max_proj) * (graph_height - 10)) if max_proj > 0 and threshold_val <= max_proj else graph_height - 5
    threshold_y = max(0, min(graph_height, threshold_y))
    cv2.line(vis_with_graph, (0, threshold_y), (w, threshold_y), (255, 100, 100), 1)
    
    # 세그먼트 영역 표시 (파란색)
    for seg_x1, seg_x2 in segments:
        seg_x1 = max(0, min(w, seg_x1))
        seg_x2 = max(seg_x1 + 1, min(w, seg_x2))
        cv2.rectangle(vis_with_graph, 
                     (seg_x1, graph_height), 
                     (seg_x2, h + graph_height), 
                     (255, 255, 0), 1)
    
    # 병합된 토큰 영역 표시 (초록색)
    for idx, (x, y, tw, th_h) in enumerate(token_boxes):
        # 좌표 범위 확인
        x1 = max(0, min(w, x))
        y1 = max(0, min(h, y))
        x2 = max(x1 + 1, min(w, x + tw))
        y2 = max(y1 + 1, min(h, y + th_h))
        
        # 원본 이미지 영역에 표시 (그래프 아래)
        cv2.rectangle(vis_with_graph, 
                     (x1, y1 + graph_height), 
                     (x2, y2 + graph_height), 
                     (0, 255, 0), 2)
        cv2.putText(vis_with_graph, 
                   f"T{idx}", 
                   (x1, max(graph_height + 5, y1 + graph_height - 5)),
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   0.5, 
                   (0, 255, 0), 
                   1)
    
    # 최종 선택지 영역 표시 (빨간색)
    for letter, (x1, y1, x2, y2) in detected_regions.items():
        # 좌표 범위 확인
        rx1 = max(0, min(w, x1))
        ry1 = max(0, min(h, y1))
        rx2 = max(rx1 + 1, min(w, x2))
        ry2 = max(ry1 + 1, min(h, y2))
        
        cv2.rectangle(vis_with_graph, 
                     (rx1, ry1 + graph_height), 
                     (rx2, ry2 + graph_height), 
                     (0, 0, 255), 3)
        cv2.putText(vis_with_graph, 
                   f"[{letter}]", 
                   (rx1, max(graph_height + 5, ry1 + graph_height - 5)),
                   cv2.FONT_HERSHEY_SIMPLEX, 
                   0.6, 
                   (0, 0, 255), 
                   2)
    
    # 그래프 레이블 추가
    cv2.putText(vis_with_graph, "Vertical Projection", (5, graph_height - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
    
    debug_info['visualization'] = vis_with_graph
    debug_info['visualization_shape'] = vis_with_graph.shape
    
    if save_path:
        cv2.imwrite(save_path, vis_with_graph)
        print(f"Token segmentation visualization saved to: {save_path}")
    
    if show_debug:
        print(f"\n=== Token Segmentation Debug ===")
        print(f"Image shape: {bgr.shape}")
        print(f"Visualization shape: {vis_with_graph.shape}")
        print(f"Graph height: {graph_height}")
        print(f"Number of tokens detected: {len(token_boxes)}")
        print(f"Expected letters: {expected_letters}")
        print(f"Segments found: {len(segments)}")
        print(f"Merged segments: {len(merged)}")
        print(f"\nToken boxes:")
        for idx, (x, y, w, h) in enumerate(token_boxes):
            print(f"  T{idx}: x={x}, y={y}, w={w}, h={h}")
        print(f"\nDetected regions:")
        for letter, (x1, y1, x2, y2) in detected_regions.items():
            print(f"  [{letter}]: ({x1}, {y1}) -> ({x2}, {y2})")
        print(f"\nDetected letters:")
        for item in debug_info['detected_letters']:
            print(f"  Token {item['index']}: expected={item['expected']}, detected={item['detected']}")
    
    return debug_info


def debug_detect_bracket_choices_v2(
    bgr: np.ndarray,
    expected_letters: List[str] = None,
    save_path: str = None,
    show_plot: bool = True
) -> Tuple[Dict[str, Tuple[int, int, int, int]], Dict[str, Any]]:
    """
    detect_bracket_choices_v2 함수의 디버깅 버전
    
    Args:
        bgr: 입력 이미지 (BGR)
        expected_letters: 예상 글자 목록
        save_path: 시각화 이미지 저장 경로
        show_plot: matplotlib으로 표시할지 여부
    
    Returns:
        (bracket_coords, debug_info)
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    # 시각화 디버그 실행
    debug_info = visualize_token_segmentation_v2(
        bgr, expected_letters, 
        save_path=save_path, 
        show_debug=True
    )
    
    # 실제 감지 실행
    bracket_coords = detect_bracket_choices_v2(bgr, expected_letters)
    
    if show_plot and debug_info.get('visualization') is not None:
        try:
            import matplotlib.pyplot as plt
            
            vis_rgb = cv2.cvtColor(debug_info['visualization'], cv2.COLOR_BGR2RGB)
            
            plt.figure(figsize=(16, 10))
            plt.imshow(vis_rgb)
            plt.title("Token Segmentation V2 - Bracket Detection")
            plt.xlabel("X coordinate")
            plt.ylabel("Y coordinate (with projection graph on top)")
            plt.axis("off")
            plt.tight_layout()
            plt.show()
        except ImportError:
            print("matplotlib not available, skipping plot display")
    
    return bracket_coords, debug_info


def save_token_segmentation_v2(
    bgr: np.ndarray,
    output_path: str,
    expected_letters: List[str] = None
) -> Dict[str, Any]:
    """
    토큰 분할 결과를 이미지 파일로 저장하는 편의 함수
    """
    debug_info = visualize_token_segmentation_v2(
        bgr, expected_letters, 
        save_path=output_path,
        show_debug=True
    )
    return debug_info


# detect_bracket_choices_v2 함수 업데이트 (디버그 출력 추가 버전)
def detect_bracket_choices_v2_debug(
    bgr: np.ndarray, 
    expected_letters: List[str] = None,
    verbose: bool = False
) -> Tuple[Dict[str, Tuple[int, int, int, int]], Dict[str, Any]]:
    """
    디버그 정보를 함께 반환하는 detect_bracket_choices_v2
    
    Returns:
        (bracket_coords, debug_info)
    """
    if expected_letters is None:
        expected_letters = ['a', 'b', 'c', 'd']
    
    debug_info = {
        'steps': {},
        'token_boxes': [],
        'segments': [],
        'merged_segments': []
    }
    
    h, w = bgr.shape[:2]
    
    # Step 1: Grayscale
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    debug_info['steps']['gray_shape'] = gray.shape
    
    # Step 2: Adaptive Threshold
    th = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2
    )
    debug_info['steps']['threshold_mean'] = float(np.mean(th))
    
    # Step 3: Morphology
    kernel = np.ones((2, 2), np.uint8)
    clean = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
    debug_info['steps']['clean_mean'] = float(np.mean(clean))
    
    # Step 4: Vertical projection
    projection = np.sum(clean > 0, axis=0)
    projection = np.convolve(projection, np.ones(5)/5, mode='same')
    debug_info['steps']['projection_max'] = float(np.max(projection))
    debug_info['steps']['projection_min'] = float(np.min(projection))
    
    # Step 5: Find segments
    segments = []
    in_token = False
    start_x = 0
    
    for x in range(len(projection)):
        if projection[x] > 1 and not in_token:
            start_x = x
            in_token = True
        elif projection[x] <= 1 and in_token:
            end_x = x
            if end_x - start_x > 5:
                segments.append((start_x, end_x))
            in_token = False
    
    debug_info['segments'] = segments
    
    # Step 6: Merge segments
    merged = []
    if len(segments) > 0:
        current = list(segments[0])
        for seg in segments[1:]:
            gap = seg[0] - current[1]
            if gap < 8:
                current[1] = seg[1]
            else:
                merged.append(tuple(current))
                current = list(seg)
        merged.append(tuple(current))
    
    debug_info['merged_segments'] = merged
    
    # Step 7: Calculate bounding boxes
    token_boxes = []
    for x1, x2 in merged:
        col = clean[:, x1:x2]
        ys, xs = np.where(col > 0)
        if len(ys) == 0:
            continue
        y1 = np.min(ys)
        y2 = np.max(ys)
        token_boxes.append((x1, y1, x2 - x1, y2 - y1))
    
    debug_info['token_boxes'] = token_boxes
    
    # Step 8: Sort by y (handle multiple rows)
    if token_boxes:
        rows = []
        current_row = []
        y_threshold = 20
        
        for box in token_boxes:
            if not current_row:
                current_row.append(box)
            else:
                if abs(box[1] - current_row[0][1]) < y_threshold:
                    current_row.append(box)
                else:
                    current_row.sort(key=lambda b: b[0])
                    rows.extend(current_row)
                    current_row = [box]
        
        if current_row:
            current_row.sort(key=lambda b: b[0])
            rows.extend(current_row)
        
        token_boxes = rows
        debug_info['token_boxes_sorted'] = token_boxes
    
    # Step 9: Sort by x
    token_boxes.sort(key=lambda b: b[0])
    
    # Step 10: Assign to expected letters
    bracket_coords = {}
    for i, (x, y, w, h) in enumerate(token_boxes[:len(expected_letters)]):
        pad_x = 10
        pad_y = 8
        final_x1 = max(0, x - pad_x)
        final_x2 = min(bgr.shape[1], x + w + pad_x)
        final_y1 = max(0, y - pad_y)
        final_y2 = min(bgr.shape[0], y + h + pad_y)
        
        expected = expected_letters[i]
        bracket_coords[expected] = (final_x1, final_y1, final_x2, final_y2)
    
    debug_info['final_coords'] = bracket_coords
    
    if verbose:
        print(f"\n=== detect_bracket_choices_v2_debug ===")
        print(f"Segments found: {len(segments)}")
        print(f"Merged segments: {len(merged)}")
        print(f"Token boxes: {len(token_boxes)}")
        print(f"Final coordinates: {len(bracket_coords)}")
        for letter, coords in bracket_coords.items():
            print(f"  [{letter}]: {coords}")
    
    return bracket_coords, debug_info

# exam_grader/omr.py (완전한 버전 호환 ArUcoDetector)

class ArUcoDetector:
    """
    ArUco 마커 감지 및 정규화 좌표 <-> 픽셀 좌표 변환 클래스
    
    OpenCV 4.5.x, 4.6.x, 4.7.x, 4.8.x+ 모두 호환
    """
    
    # ArUco 딕셔너리 (4x4, 50개 마커)
    ARUCO_DICT = cv2.aruco.DICT_4X4_50
    
    # 기본 마커 ID 매핑 (JSON의 coordinate_system 정보와 일치)
    DEFAULT_MARKER_IDS = {
        'top_left': 0,      # 원점 마커
        'bottom_right': 3   # 단위 기준 마커
    }
    
    def __init__(self, marker_ids: Dict[str, int] = None):
        """
        Args:
            marker_ids: 마커 ID 매핑 {'top_left': id, 'bottom_right': id}
                       기본값: {0, 3}
        """
        self.marker_ids = marker_ids or self.DEFAULT_MARKER_IDS.copy()
        
        # OpenCV 버전에 맞게 초기화
        self.aruco_dict = self._get_aruco_dictionary()
        self.parameters = self._get_detector_parameters()
        
        # OpenCV 4.7.0 이상에서는 ArucoDetector 사용
        self.detector = None
        if hasattr(cv2.aruco, 'ArucoDetector'):
            self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
        
        # 감지된 마커 정보
        self.detected_markers: Dict[int, Dict[str, Any]] = {}
        
        # 변환 행렬 (정규화 좌표 -> 픽셀 좌표)
        self.transform_matrix: Optional[np.ndarray] = None
        
        # 역변환 행렬 (픽셀 좌표 -> 정규화 좌표)
        self.inverse_transform: Optional[np.ndarray] = None
        
        # 페이지 크기 (픽셀 단위)
        self.page_size: Optional[Tuple[int, int]] = None
        
        # 감지 성공 여부
        self.is_calibrated: bool = False
    
    def _get_aruco_dictionary(self):
        """OpenCV 버전에 맞는 ArUco 딕셔너리 반환"""
        # 방법 1: OpenCV 4.7.0 이상 (getPredefinedDictionary)
        if hasattr(cv2.aruco, 'getPredefinedDictionary'):
            return cv2.aruco.getPredefinedDictionary(self.ARUCO_DICT)
        
        # 방법 2: OpenCV 4.6.0 이하 (Dictionary_get)
        if hasattr(cv2.aruco, 'Dictionary_get'):
            return cv2.aruco.Dictionary_get(self.ARUCO_DICT)
        
        # 방법 3: OpenCV 4.8.0+ (ArucoDictionary_get)
        if hasattr(cv2.aruco, 'ArucoDictionary_get'):
            return cv2.aruco.ArucoDictionary_get(self.ARUCO_DICT)
        
        # 폴백: 기본 딕셔너리 생성 시도
        try:
            return cv2.aruco.Dictionary_get(self.ARUCO_DICT)
        except:
            try:
                return cv2.aruco.getPredefinedDictionary(self.ARUCO_DICT)
            except:
                raise RuntimeError("Failed to create ArUco dictionary. Check OpenCV version.")
    
    def _get_detector_parameters(self):
        """OpenCV 버전에 맞는 DetectorParameters 반환"""
        # 방법 1: OpenCV 4.7.0 이상 (DetectorParameters)
        if hasattr(cv2.aruco, 'DetectorParameters'):
            return cv2.aruco.DetectorParameters()
        
        # 방법 2: OpenCV 4.6.0 이하 (DetectorParameters_create)
        if hasattr(cv2.aruco, 'DetectorParameters_create'):
            return cv2.aruco.DetectorParameters_create()
        
        # 방법 3: create 메서드
        try:
            return cv2.aruco.DetectorParameters_create()
        except:
            try:
                return cv2.aruco.DetectorParameters()
            except:
                # 폴백: 기본 파라미터 생성
                class SimpleParams:
                    pass
                params = SimpleParams()
                params.adaptiveThreshWinSizeMin = 3
                params.adaptiveThreshWinSizeMax = 23
                params.adaptiveThreshWinSizeStep = 10
                params.adaptiveThreshConstant = 7
                params.minMarkerPerimeterRate = 0.03
                params.maxMarkerPerimeterRate = 4.0
                params.polygonalApproxAccuracyRate = 0.03
                params.minCornerDistanceRate = 0.05
                params.minDistanceToBorder = 3
                params.minMarkerDistanceRate = 0.05
                params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_NONE
                return params
    
    def _detect_markers_legacy(self, gray):
        """OpenCV 4.6.0 이하에서 마커 감지"""
        corners, ids, rejected = cv2.aruco.detectMarkers(
            gray, self.aruco_dict, parameters=self.parameters
        )
        return corners, ids
    
    def _detect_markers_new(self, gray):
        """OpenCV 4.7.0 이상에서 마커 감지"""
        corners, ids, rejected = self.detector.detectMarkers(gray)
        return corners, ids
    
    def detect_markers(self, image: np.ndarray) -> Dict[int, Dict[str, Any]]:
        """
        이미지에서 ArUco 마커 감지
        
        Args:
            image: BGR 이미지 (OpenCV 형식)
            
        Returns:
            감지된 마커 정보 딕셔너리 {marker_id: {'corners': array, 'center': (x,y)}}
        """
        if image is None or image.size == 0:
            return {}
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # OpenCV 버전에 따른 마커 감지
        corners_list = []
        ids_list = None
        
        if self.detector is not None:
            # OpenCV 4.7.0 이상 (ArucoDetector 사용)
            corners_list, ids_list, _ = self.detector.detectMarkers(gray)
        else:
            # OpenCV 4.6.0 이하 (기존 방식)
            corners_list, ids_list, _ = cv2.aruco.detectMarkers(
                gray, self.aruco_dict, parameters=self.parameters
            )
        
        self.detected_markers = {}
        
        if ids_list is not None and len(ids_list) > 0:
            for i, marker_id in enumerate(ids_list.flatten()):
                marker_corners = corners_list[i][0]  # 4개 모서리 좌표
                center = np.mean(marker_corners, axis=0)
                self.detected_markers[int(marker_id)] = {
                    'corners': marker_corners,
                    'center': center,
                    'corner_points': marker_corners.tolist()
                }
        
        return self.detected_markers
    
    def detect_markers_from_pdf_page(
        self, 
        pdf_path: str, 
        page_num: int, 
        zoom: float = 1.5
    ) -> Dict[int, Dict[str, Any]]:
        """
        PDF 페이지에서 ArUco 마커 감지
        
        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (0부터 시작)
            zoom: 확대 비율
            
        Returns:
            감지된 마커 정보
        """
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF (fitz) is required for PDF processing")
        
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            doc.close()
            raise ValueError(f"Page {page_num} not found (total {len(doc)} pages)")
        
        page = doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_data = pix.tobytes("png")
        
        # PNG 데이터를 OpenCV 이미지로 변환
        import io
        from PIL import Image
        pil_img = Image.open(io.BytesIO(img_data))
        bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        
        doc.close()
        
        # 페이지 크기 저장
        self.page_size = (pix.width, pix.height)
        
        return self.detect_markers(bgr)
    
    def compute_transform(self, page_width: int, page_height: int) -> bool:
        """
        감지된 마커를 기반으로 정규화 좌표 -> 픽셀 좌표 변환 행렬 계산
        
        정규화 좌표계:
        - (0, 0) -> top-left 마커 중심
        - (1, 0) -> top-right 마커 중심 (필요시 ID 1 사용)
        - (0, 1) -> bottom-left 마커 중심 (필요시 ID 2 사용)
        - (1, 1) -> bottom-right 마커 중심
        
        Returns:
            변환 행렬 계산 성공 여부
        """
        tl_id = self.marker_ids.get('top_left')
        br_id = self.marker_ids.get('bottom_right')
        
        if tl_id is None or br_id is None:
            print(f"❌ Marker IDs not configured: TL={tl_id}, BR={br_id}")
            return False
        
        if tl_id not in self.detected_markers:
            print(f"❌ Top-left marker (ID {tl_id}) not detected")
            print(f"   Detected markers: {list(self.detected_markers.keys())}")
            return False
        
        if br_id not in self.detected_markers:
            print(f"❌ Bottom-right marker (ID {br_id}) not detected")
            print(f"   Detected markers: {list(self.detected_markers.keys())}")
            return False
        
        tl_center = self.detected_markers[tl_id]['center']
        br_center = self.detected_markers[br_id]['center']
        
        # 추가 마커 감지 시도 (더 정확한 변환을 위해)
        # ID 1: top-right, ID 2: bottom-left
        tr_id = 1
        bl_id = 2
        
        tr_center = None
        bl_center = None
        
        if tr_id in self.detected_markers:
            tr_center = self.detected_markers[tr_id]['center']
            print(f"   TR (ID {tr_id}): center=({tr_center[0]:.1f}, {tr_center[1]:.1f})")
        
        if bl_id in self.detected_markers:
            bl_center = self.detected_markers[bl_id]['center']
            print(f"   BL (ID {bl_id}): center=({bl_center[0]:.1f}, {bl_center[1]:.1f})")
        
        print(f"✅ Detected markers:")
        print(f"   TL (ID {tl_id}): center=({tl_center[0]:.1f}, {tl_center[1]:.1f})")
        print(f"   BR (ID {br_id}): center=({br_center[0]:.1f}, {br_center[1]:.1f})")
        
        # Affine 변환을 위한 최소 3개 점 준비
        src_points = []
        dst_points = []
        
        # 점 1: 정규화 좌표 (0, 0) -> TL 마커
        src_points.append([0, 0])
        dst_points.append([tl_center[0], tl_center[1]])
        
        # 점 2: 정규화 좌표 (1, 1) -> BR 마커
        src_points.append([1, 1])
        dst_points.append([br_center[0], br_center[1]])
        
        # 점 3: TR 마커가 있으면 (1, 0) 사용, 없으면 (0, 1) 사용
        if tr_center is not None:
            src_points.append([1, 0])
            dst_points.append([tr_center[0], tr_center[1]])
        elif bl_center is not None:
            src_points.append([0, 1])
            dst_points.append([bl_center[0], bl_center[1]])
        else:
            # TR, BL 마커가 모두 없으면 투영 변환(Projective) 대신 스케일링만 사용
            print(f"⚠️ Only 2 markers detected. Using simple scaling fallback.")
            
            # 페이지 크기 기반 단순 비례 변환
            scale_x = (br_center[0] - tl_center[0])  # 1 단위당 픽셀 수
            scale_y = (br_center[1] - tl_center[1])
            
            self.transform_matrix = np.array([
                [scale_x, 0, tl_center[0]],
                [0, scale_y, tl_center[1]]
            ], dtype=np.float32)
            
            # 역변환 행렬 계산
            transform_3x3 = np.vstack([self.transform_matrix, [0, 0, 1]])
            self.inverse_transform = np.linalg.inv(transform_3x3)[:2]
            
            self.page_size = (page_width, page_height)
            self.is_calibrated = True
            
            print(f"✅ Simple scaling calibration successful!")
            print(f"   Scale X: {scale_x:.2f}, Scale Y: {scale_y:.2f}")
            print(f"   Origin: ({tl_center[0]:.1f}, {tl_center[1]:.1f})")
            
            return True
        
        # 3개 이상의 점으로 변환 행렬 계산
        src_points = np.array(src_points[:3], dtype=np.float32)
        dst_points = np.array(dst_points[:3], dtype=np.float32)
        
        print(f"   Using {len(src_points)} points for affine transform")
        
        # Affine 변환 행렬 계산 (2x3)
        self.transform_matrix = cv2.getAffineTransform(src_points, dst_points)
        
        # 역변환 행렬 계산 (픽셀 -> 정규화)
        transform_3x3 = np.vstack([self.transform_matrix, [0, 0, 1]])
        self.inverse_transform = np.linalg.inv(transform_3x3)[:2]
        
        self.page_size = (page_width, page_height)
        self.is_calibrated = True
        
        print(f"✅ Affine calibration successful!")
        print(f"   Transform matrix: {self.transform_matrix}")
        
        return True
    
    def compute_perspective_transform(self, page_width: int, page_height: int) -> bool:
        """
        4개의 마커를 사용한 원근 변환(Perspective Transform) 계산 (더 정확함)
        
        정규화 좌표계:
        - (0, 0) -> top-left 마커 (ID 0)
        - (1, 0) -> top-right 마커 (ID 1)
        - (0, 1) -> bottom-left 마커 (ID 2)
        - (1, 1) -> bottom-right 마커 (ID 3)
        
        Returns:
            변환 행렬 계산 성공 여부
        """
        required_ids = [0, 1, 2, 3]  # TL, TR, BL, BR
        
        for marker_id in required_ids:
            if marker_id not in self.detected_markers:
                print(f"❌ Required marker ID {marker_id} not detected")
                return False
        
        # 정규화 좌표계의 네 모서리
        src_points = np.array([
            [0, 0],  # top-left
            [1, 0],  # top-right
            [0, 1],  # bottom-left
            [1, 1]   # bottom-right
        ], dtype=np.float32)
        
        # 감지된 마커 중심 좌표
        dst_points = np.array([
            self.detected_markers[0]['center'],  # TL
            self.detected_markers[1]['center'],  # TR
            self.detected_markers[2]['center'],  # BL
            self.detected_markers[3]['center']   # BR
        ], dtype=np.float32)
        
        # 원근 변환 행렬 계산 (3x3)
        self.transform_matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        self.is_perspective = True
        
        # 역변환 행렬 계산
        self.inverse_transform = np.linalg.inv(self.transform_matrix)
        
        self.page_size = (page_width, page_height)
        self.is_calibrated = True
        
        print(f"✅ Perspective calibration successful!")
        print(f"   TL: {dst_points[0]}")
        print(f"   TR: {dst_points[1]}")
        print(f"   BL: {dst_points[2]}")
        print(f"   BR: {dst_points[3]}")
        
        return True
    
    def compute_transform_from_markers(
        self, 
        tl_center: Tuple[float, float], 
        br_center: Tuple[float, float],
        page_width: int,
        page_height: int
    ) -> bool:
        """
        직접 마커 중심 좌표로 변환 행렬 계산 (이미 감지된 마커 사용 시)
        
        Args:
            tl_center: top-left 마커 중심 (x, y)
            br_center: bottom-right 마커 중심 (x, y)
            page_width: 페이지 너비
            page_height: 페이지 높이
        """
        src_points = np.array([[0, 0], [1, 1]], dtype=np.float32)
        dst_points = np.array([
            [tl_center[0], tl_center[1]],
            [br_center[0], br_center[1]]
        ], dtype=np.float32)
        
        self.transform_matrix = cv2.getAffineTransform(src_points, dst_points)
        
        transform_3x3 = np.vstack([self.transform_matrix, [0, 0, 1]])
        self.inverse_transform = np.linalg.inv(transform_3x3)[:2]
        
        self.page_size = (page_width, page_height)
        self.is_calibrated = True
        
        return True
    
    def normalized_to_pixel(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """
        정규화 좌표 (0~1)를 픽셀 좌표로 변환
        
        Args:
            norm_x: 정규화 X 좌표 (0~1)
            norm_y: 정규화 Y 좌표 (0~1)
            
        Returns:
            (pixel_x, pixel_y) 픽셀 좌표
        """
        if not self.is_calibrated or self.transform_matrix is None:
            # 폴백: 페이지 크기 기반 단순 비례 변환
            if self.page_size:
                return (int(norm_x * self.page_size[0]), int(norm_y * self.page_size[1]))
            return (int(norm_x), int(norm_y))
        
        norm_point = np.array([norm_x, norm_y], dtype=np.float32)
        
        # 원근 변환인 경우 (3x3 행렬)
        if hasattr(self, 'is_perspective') and self.is_perspective:
            # 동차 좌표로 변환
            point_homogeneous = np.array([norm_x, norm_y, 1.0])
            pixel_homogeneous = self.transform_matrix @ point_homogeneous
            pixel_x = pixel_homogeneous[0] / pixel_homogeneous[2]
            pixel_y = pixel_homogeneous[1] / pixel_homogeneous[2]
            return (int(pixel_x), int(pixel_y))
        
        # Affine 변환인 경우 (2x3 행렬)
        pixel_point = cv2.transform(
            np.array([[norm_point]]), 
            self.transform_matrix
        )[0][0]
        
        return (int(pixel_point[0]), int(pixel_point[1]))
    
    def pixel_to_normalized(self, pixel_x: int, pixel_y: int) -> Tuple[float, float]:
        """
        픽셀 좌표를 정규화 좌표 (0~1)로 변환
        
        Args:
            pixel_x: 픽셀 X 좌표
            pixel_y: 픽셀 Y 좌표
            
        Returns:
            (norm_x, norm_y) 정규화 좌표
        """
        if not self.is_calibrated or self.inverse_transform is None:
            # 폴백: 페이지 크기 기반 단순 비례 변환
            if self.page_size and self.page_size[0] > 0 and self.page_size[1] > 0:
                return (pixel_x / self.page_size[0], pixel_y / self.page_size[1])
            return (pixel_x, pixel_y)
        
        pixel_point = np.array([pixel_x, pixel_y], dtype=np.float32)
        norm_point = cv2.transform(
            np.array([[pixel_point]]), 
            self.inverse_transform
        )[0][0]
        
        return (norm_point[0], norm_point[1])
    
    def normalized_rect_to_pixel(
        self, 
        norm_rect: Dict[str, float]
    ) -> Dict[str, int]:
        """
        정규화 사각형 (x, y, w, h)를 픽셀 좌표로 변환
        
        Args:
            norm_rect: {'x': float, 'y': float, 'w': float, 'h': float}
            
        Returns:
            {'x': int, 'y': int, 'w': int, 'h': int}
        """
        x1, y1 = self.normalized_to_pixel(norm_rect['x'], norm_rect['y'])
        x2, y2 = self.normalized_to_pixel(
            norm_rect['x'] + norm_rect['w'], 
            norm_rect['y'] + norm_rect['h']
        )
                
        # offset 추가
        offset = 15
        return {
            'x': x1,
            'y': y1-offset,
            'w': x2 - x1,
            'h': y2 - y1
        }
    
    def draw_markers(
        self, 
        image: np.ndarray, 
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        감지된 ArUco 마커를 이미지에 그리기
        
        Args:
            image: 원본 이미지 (BGR)
            color: 표시 색상 (B, G, R)
            thickness: 선 두께
            
        Returns:
            마커가 그려진 이미지
        """
        result = image.copy()
        
        for marker_id, info in self.detected_markers.items():
            corners = info['corners']
            center = info['center']
            
            # 마커 경계선 그리기
            corners_int = corners.astype(np.int32)
            cv2.polylines(result, [corners_int], True, color, thickness)
            
            # 마커 ID 표시
            cv2.putText(
                result, 
                str(marker_id), 
                (int(center[0]) - 10, int(center[1]) - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                thickness
            )
            
            # 마커 중심점 표시
            cv2.circle(result, (int(center[0]), int(center[1])), 4, color, -1)
        
        return result
    
    def get_calibration_info(self) -> Dict[str, Any]:
        """
        현재 캘리브레이션 정보 반환
        """
        info = {
            'is_calibrated': self.is_calibrated,
            'page_size': self.page_size,
            'detected_markers': {
                str(mid): {
                    'center': info['center'].tolist() if hasattr(info['center'], 'tolist') else info['center']
                }
                for mid, info in self.detected_markers.items()
            }
        }
        
        if self.transform_matrix is not None:
            info['transform_matrix'] = self.transform_matrix.tolist()
        
        return info


# OpenCV 버전 확인용 헬퍼 함수
def get_opencv_aruco_info():
    """현재 OpenCV의 ArUco 모듈 정보 반환"""
    info = {
        'opencv_version': cv2.__version__,
        'has_aruco': hasattr(cv2, 'aruco'),
        'has_getPredefinedDictionary': hasattr(cv2.aruco, 'getPredefinedDictionary'),
        'has_Dictionary_get': hasattr(cv2.aruco, 'Dictionary_get'),
        'has_DetectorParameters': hasattr(cv2.aruco, 'DetectorParameters'),
        'has_DetectorParameters_create': hasattr(cv2.aruco, 'DetectorParameters_create'),
        'has_ArucoDetector': hasattr(cv2.aruco, 'ArucoDetector'),
    }
    return info


def convert_normalized_coordinates_from_json(
    exam_data: Dict[str, Any],
    aruco_detector: ArUcoDetector,
    page_num: int = 1
) -> Dict[int, Dict[str, Any]]:
    """
    JSON 파일의 normalized 좌표를 픽셀 좌표로 일괄 변환
    
    Args:
        exam_data: 시험 JSON 데이터
        aruco_detector: 초기화된 ArUcoDetector (이미 캘리브레이션 완료)
        page_num: 대상 페이지 번호 (1부터 시작)
        
    Returns:
        {question_id: {'choice_regions': {choice: (x1,y1,x2,y2)}, ...}}
    """
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
            if norm:
                pixel_rect = aruco_detector.normalized_rect_to_pixel(norm)
                choice_regions[cr.get('choice', '?')] = pixel_rect
        
        # 최상위 choice_regions 처리 (중복 방지)
        for cr in exam_data.get('choice_regions', []):
            if cr.get('question_id') == qid:
                norm = cr.get('normalized', {})
                if norm:
                    pixel_rect = aruco_detector.normalized_rect_to_pixel(norm)
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


def detect_aruco_and_calibrate(
    pdf_path: str,
    page_num: int,
    marker_ids: Dict[str, int] = None,
    zoom: float = 1.5
) -> Tuple[Optional[ArUcoDetector], Optional[np.ndarray]]:
    """
    PDF 페이지에서 ArUco 마커를 감지하고 캘리브레이션 수행
    
    Args:
        pdf_path: PDF 파일 경로
        page_num: 페이지 번호 (0부터 시작)
        marker_ids: 마커 ID 매핑
        zoom: 확대 비율
        
    Returns:
        (ArUcoDetector 인스턴스, 페이지 이미지) 또는 (None, None)
    """
    if not PYMUPDF_AVAILABLE:
        print("PyMuPDF (fitz) is not available")
        return None, None
    
    detector = ArUcoDetector(marker_ids)
    
    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            doc.close()
            return None, None
        
        page = doc[page_num]
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # PyMuPDF 픽셀맵을 OpenCV 이미지로 변환
        img_data = pix.tobytes("png")
        import io
        from PIL import Image
        pil_img = Image.open(io.BytesIO(img_data))
        bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        
        doc.close()
        
        # 마커 감지
        detected = detector.detect_markers(bgr)
        
        # 캘리브레이션
        if detector.compute_transform(pix.width, pix.height):
            return detector, bgr
        else:
            print(f"Failed to calibrate: required markers {detector.marker_ids} not found")
            print(f"Detected markers: {list(detected.keys())}")
            return None, bgr
            
    except Exception as e:
        print(f"ArUco detection error: {e}")
        return None, None


def visualize_choice_regions(
    image: np.ndarray,
    choice_regions: Dict[str, Dict[str, int]],
    question_id: int = None,
    color_map: Dict[str, Tuple[int, int, int]] = None
) -> np.ndarray:
    """
    선택지 영역을 이미지에 시각화
    
    Args:
        image: 원본 이미지 (BGR)
        choice_regions: {choice: {'x': int, 'y': int, 'w': int, 'h': int}}
        question_id: 문제 ID (레이블 표시용)
        color_map: 선택지별 색상 매핑
        
    Returns:
        시각화된 이미지
    """
    if color_map is None:
        # 기본 색상 (BGR)
        default_colors = [
            (255, 100, 100),  # 빨강
            (100, 255, 100),  # 초록
            (100, 100, 255),  # 파랑
            (255, 255, 100),  # 하늘
            (255, 100, 255),  # 마젠타
            (100, 255, 255),  # 노랑
        ]
        color_map = {chr(ord('a') + i): default_colors[i % len(default_colors)] 
                    for i in range(26)}
    
    result = image.copy()
    
    for choice, rect in choice_regions.items():
        x = rect['x']
        y = rect['y']
        w = rect['w']
        h = rect['h']
        
        color = color_map.get(choice, (200, 200, 200))
        
        # 영역 사각형 그리기
        cv2.rectangle(result, (x, y), (x + w, y + h), color, 2)
        
        # 선택지 레이블
        label = f"[{choice.upper()}]"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        
        # 레이블 배경
        cv2.rectangle(
            result, 
            (x, y - label_size[1] - 4), 
            (x + label_size[0] + 4, y), 
            color, 
            -1
        )
        
        # 레이블 텍스트
        cv2.putText(
            result, 
            label, 
            (x + 2, y - 2), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.5, 
            (255, 255, 255), 
            1
        )
    
    if question_id:
        cv2.putText(
            result,
            f"Q{question_id}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 200, 200),
            2
        )
    
    return result


@dataclass
class BubbleBox:
    label: str
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class BubbleMarkResult:
    label: str
    score: float
    marked: bool


def omr_preprocess_gray(bgr: np.ndarray) -> np.ndarray:
    """
    OMR 전처리
    """

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    gray = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8)
    ).apply(gray)

    return gray


def omr_compute_bubble_score(
    roi_gray: np.ndarray
) -> float:
    """
    버블 마킹 점수 계산
    """

    if roi_gray is None or roi_gray.size == 0:
        return 0.0

    th = cv2.adaptiveThreshold(
        roi_gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        21,
        8
    )

    kernel = np.ones((3, 3), np.uint8)

    th = cv2.morphologyEx(
        th,
        cv2.MORPH_CLOSE,
        kernel
    )

    total_ratio = np.count_nonzero(th) / th.size

    h, w = th.shape

    cy1 = h // 4
    cy2 = 3 * h // 4

    cx1 = w // 4
    cx2 = 3 * w // 4

    center = th[cy1:cy2, cx1:cx2]

    center_ratio = (
        np.count_nonzero(center) / center.size
        if center.size > 0 else 0.0
    )

    score = (
        0.4 * total_ratio +
        0.6 * center_ratio
    )

    return float(np.clip(score, 0.0, 1.0))


def omr_analyze_bubbles(
    bgr: np.ndarray,
    bubble_boxes: List[BubbleBox],
    mark_threshold: float = 0.30,
) -> List[BubbleMarkResult]:
    """
    모든 버블 분석
    """

    gray = omr_preprocess_gray(bgr)

    results = []

    for box in bubble_boxes:

        roi = gray[
            box.y1:box.y2,
            box.x1:box.x2
        ]

        score = omr_compute_bubble_score(roi)

        results.append(
            BubbleMarkResult(
                label=box.label,
                score=score,
                marked=score >= mark_threshold
            )
        )

    return results


def omr_select_answers(
    results: List[BubbleMarkResult],
    mark_threshold: float = 0.30,
    multi_delta: float = 0.08,
) -> Tuple[List[str], float]:
    """
    최종 선택지 결정
    """

    if not results:
        return [], 0.0

    results = sorted(
        results,
        key=lambda x: x.score,
        reverse=True
    )

    best = results[0]

    if best.score < mark_threshold:
        return [], 0.0

    selected = [best.label]

    for r in results[1:]:

        if (
            best.score - r.score <= multi_delta
            and r.score >= mark_threshold
        ):
            selected.append(r.label)

    confidence = best.score

    return selected, confidence