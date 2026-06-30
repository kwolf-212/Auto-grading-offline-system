# exam_grader/omr.py
"""
OMR 감지 및 분석 모듈 - 순수 이미지 처리 기능만 포함
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

import cv2
import numpy as np


# ============================================================
# 1. 이미지 기본 처리
# ============================================================

def omr_to_gray(img: np.ndarray) -> np.ndarray:
    """BGR을 그레이스케일로 변환"""
    if img is None or img.size == 0:
        return img
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def omr_clahe(gray: np.ndarray, clip_limit: float = 2.0, tile: int = 8) -> np.ndarray:
    """CLAHE 대비 향상"""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(tile, tile))
    return clahe.apply(gray)

# ============================================================
# 2. 버블 마킹 점수 계산
# ============================================================

def omr_compute_bubble_score(roi_gray: np.ndarray) -> float:
    """
    단일 버블 ROI에서 마킹 점수 계산 (0~1)
    
    Args:
        roi_gray: 버블 영역 그레이스케일 이미지
        
    Returns:
        마킹 점수 (0=빈칸, 1=완전히 마킹됨)
    """
    if roi_gray is None or roi_gray.size < 16:
        return 0.0
    
    # 적응형 이진화
    th = cv2.adaptiveThreshold(
        roi_gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        21, 8
    )
    
    # 노이즈 제거
    kernel = np.ones((3, 3), np.uint8)
    th = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel)
    
    # 전체 영역 비율
    total_ratio = np.count_nonzero(th) / th.size
    
    # 중앙 영역 (더 높은 가중치)
    h, w = th.shape
    cy1, cy2 = h // 4, 3 * h // 4
    cx1, cx2 = w // 4, 3 * w // 4
    center = th[cy1:cy2, cx1:cx2]
    center_ratio = np.count_nonzero(center) / center.size if center.size > 0 else 0.0
    
    # 40% 전체 + 60% 중앙
    score = 0.4 * total_ratio + 0.6 * center_ratio
    
    return float(np.clip(score, 0.0, 1.0))


def omr_analyze_bubbles(
    bubble_images: List[Tuple[str, np.ndarray]],
    mark_threshold: float = 0.30,
) -> List['BubbleMarkResult']:
    """
    개별 버블 이미지들 분석

    Args:
        bubble_images:
            [(label, bubble_bgr_image), ...]

        mark_threshold:
            마킹 임계값

    Returns:
        BubbleMarkResult 리스트
    """

    results = []

    for label, bgr in bubble_images:

        if bgr is None or bgr.size == 0:
            results.append(BubbleMarkResult(
                label=label,
                score=0.0,
                marked=False
            ))
            continue

        gray = omr_to_gray(bgr)
        gray = omr_clahe(gray)

        score = omr_compute_bubble_score(gray)

        results.append(BubbleMarkResult(
            label=label,
            score=score,
            marked=score >= mark_threshold
        ))

    return results

def _label_to_choice_number(label: str) -> int:
    """
    선택지 라벨 -> 번호 변환

    A/a -> 1
    B/b -> 2
    ...
    T/t -> 1
    F/f -> 2
    """

    if isinstance(label, int):
        return label

    if label is None:
        return 0

    l = str(label).strip().lower()

    if l.isdigit():
        return int(l)

    if len(l) == 1 and 'a' <= l <= 'z':
        return ord(l) - ord('a') + 1

    return 0

def omr_select_answers(
    results: List['BubbleMarkResult'],
    mark_threshold: float = 0.30,
    multi_delta: float = 0.08,
) -> Tuple[List[int], float]:

    if not results:
        return [], 0.0

    results = sorted(results, key=lambda x: x.score, reverse=True)

    best = results[0]

    if best.score < mark_threshold:
        return [], 0.0

    if isinstance(best.label, int):
        selected = [best.label]
    else:
        selected = [_label_to_choice_number(best.label)]

    for r in results[1:]:
        if (
            best.score - r.score <= multi_delta
            and r.score >= mark_threshold
        ):
            if isinstance(r.label, int):
                selected.append(r.label)
            else:
                selected.append(
                    _label_to_choice_number(r.label)
                )

    return selected, best.score

# ============================================================
# 4. ArUco 마커 감지 및 좌표 변환
# ============================================================

@dataclass
class BubbleBox:
    """버블 영역 정보"""
    label: str
    x1: int
    y1: int
    x2: int
    y2: int
    
    @property
    def x(self): return self.x1
    @property
    def y(self): return self.y1
    @property
    def w(self): return self.x2 - self.x1
    @property
    def h(self): return self.y2 - self.y1


@dataclass
class BubbleMarkResult:
    """버블 분석 결과"""
    label: str
    score: float
    marked: bool


class ArUcoDetector:
    """
    ArUco 마커 감지 및 정규화 좌표 <-> 픽셀 좌표 변환
    """
    
    ARUCO_DICT = cv2.aruco.DICT_4X4_50
    DEFAULT_MARKER_IDS = {'top_left': 0, 'bottom_right': 3}
    
    def __init__(self, marker_ids: Dict[str, int] = None):
        self.marker_ids = marker_ids or self.DEFAULT_MARKER_IDS.copy()
        self.detected_markers: Dict[int, Dict] = {}
        self.transform_matrix: Optional[np.ndarray] = None
        self.is_calibrated: bool = False
        self.page_size: Optional[Tuple[int, int]] = None
        
        # ========== 추가: transform_type 속성 ==========
        self.transform_type: str = "none"  # "perspective", "affine", "none"
        
        # OpenCV 버전 호환성 처리
        self.aruco_dict = self._get_aruco_dict()
        self.detector = None
        if hasattr(cv2.aruco, 'ArucoDetector'):
            self.detector = cv2.aruco.ArucoDetector(
                self.aruco_dict,
                cv2.aruco.DetectorParameters()
            )
    
    def _get_aruco_dict(self):
        """OpenCV 버전에 맞는 ArUco 딕셔너리 반환"""
        if hasattr(cv2.aruco, 'getPredefinedDictionary'):
            return cv2.aruco.getPredefinedDictionary(self.ARUCO_DICT)
        if hasattr(cv2.aruco, 'Dictionary_get'):
            return cv2.aruco.Dictionary_get(self.ARUCO_DICT)
        raise RuntimeError("ArUco not available in this OpenCV version")
    
    def detect_markers(self, image: np.ndarray) -> Dict[int, Dict]:
        """이미지에서 ArUco 마커 감지"""
        if image is None or image.size == 0:
            return {}
        
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if self.detector is not None:
            corners, ids, _ = self.detector.detectMarkers(gray)
        else:
            corners, ids, _ = cv2.aruco.detectMarkers(gray, self.aruco_dict)
        
        self.detected_markers = {}
        if ids is not None:
            for i, marker_id in enumerate(ids.flatten()):
                marker_corners = corners[i][0]
                center = np.mean(marker_corners, axis=0)
                self.detected_markers[int(marker_id)] = {
                    'corners': marker_corners,
                    'center': center
                }
        
        return self.detected_markers
    
    def compute_transform(self, page_width: int, page_height: int) -> bool:
        """감지된 마커로 변환 행렬 계산 (Affine)"""
        tl_id = self.marker_ids.get('top_left')
        br_id = self.marker_ids.get('bottom_right')
        
        if tl_id not in self.detected_markers or br_id not in self.detected_markers:
            self.transform_type = "none"
            return False
        
        tl = self.detected_markers[tl_id]['center']
        br = self.detected_markers[br_id]['center']
        
        # 단순 스케일링 변환
        scale_x = br[0] - tl[0]
        scale_y = br[1] - tl[1]
        
        self.transform_matrix = np.array([
            [scale_x, 0, tl[0]],
            [0, scale_y, tl[1]]
        ], dtype=np.float32)
        
        self.page_size = (page_width, page_height)
        self.is_calibrated = True
        self.transform_type = "affine"  # ========== 수정 ==========
        return True
    
    def compute_perspective_transform(self, page_width: int, page_height: int) -> bool:
        """4개 마커로 원근 변환 계산"""
        required = [0, 1, 2, 3]
        if not all(mid in self.detected_markers for mid in required):
            self.transform_type = "none"
            return False
        
        src = np.array([[0, 0], [1, 0], [0, 1], [1, 1]], dtype=np.float32)
        dst = np.array([self.detected_markers[mid]['center'] for mid in required], dtype=np.float32)
        
        self.transform_matrix = cv2.getPerspectiveTransform(src, dst)
        self.page_size = (page_width, page_height)
        self.is_calibrated = True
        self.transform_type = "perspective"  # ========== 수정 ==========
        return True
    
    def normalized_to_pixel(self, norm_x: float, norm_y: float) -> Tuple[int, int]:
        """정규화 좌표를 픽셀 좌표로 변환"""
        if not self.is_calibrated or self.transform_matrix is None:
            if self.page_size:
                return (int(norm_x * self.page_size[0]), int(norm_y * self.page_size[1]))
            return (int(norm_x), int(norm_y))
        
        point = np.array([norm_x, norm_y], dtype=np.float32)
        if self.transform_matrix.shape == (3, 3):  # Perspective
            h = np.append(point, 1.0)
            result = self.transform_matrix @ h
            return (int(result[0] / result[2]), int(result[1] / result[2]))
        else:  # Affine (2x3 matrix)
            result = cv2.transform(np.array([[point]]), self.transform_matrix)[0][0]
            return (int(result[0]), int(result[1]))
    
    def normalized_rect_to_pixel(self, norm_rect: Dict[str, float]) -> Dict[str, int]:
        """정규화 사각형을 픽셀 사각형으로 변환"""
        x1, y1 = self.normalized_to_pixel(norm_rect['x'], norm_rect['y'])
        x2, y2 = self.normalized_to_pixel(
            norm_rect['x'] + norm_rect['w'],
            norm_rect['y'] + norm_rect['h']
        )
        # offset
        offset = 15
        return {'x': x1, 'y': y1-offset, 'w': x2 - x1, 'h': y2 - y1}
    
    def get_center(self, marker_id: int) -> Optional[Tuple[float, float]]:
        """마커 중심 좌표 반환"""
        marker = self.detected_markers.get(marker_id)
        return tuple(marker['center']) if marker else None
    
    # ========== 추가: 마커 정보 반환 메서드 ==========
    def get_detected_markers(self) -> Dict[int, Dict]:
        """감지된 마커 정보 반환"""
        return self.detected_markers
    
    def is_calibrated_with_markers(self) -> bool:
        """캘리브레이션 성공 여부와 마커 정보 반환"""
        return self.is_calibrated