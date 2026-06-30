# exam_grader/graders/base.py
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any, Optional
import numpy as np

from ..omr import BubbleMarkResult


class BaseGrader(ABC):
    """문제 유형별 채점기의 기본 추상 클래스"""
    
    def __init__(self, qinfo: Dict):
        """
        Args:
            qinfo: 문제 정보 (bubble_boxes, expected_answer_number, score 등)
        """
        self.qinfo = qinfo
        self.question_id = qinfo.get('question_id', 'unknown')
        self.expected_answer = qinfo.get('expected_answer_number')
        self.score_value = qinfo.get('score', 0)
        self.bubble_boxes = qinfo.get('bubble_boxes', [])
    
    @abstractmethod
    def grade(self, page_image: np.ndarray, debug_mode: bool = False) -> Dict:
        """
        채점 실행
        
        Returns:
            Dict: {
                'selected_number': int,
                'selected_label': str,
                'correct': bool,
                'score': float,
                'debug': dict
            }
        """
        pass
    
    def _crop_bubble_regions(self, page_image: np.ndarray) -> List[Tuple[str, np.ndarray]]:
        """이미지에서 버블 영역들을 크롭"""
        valid = []
        for box in self.bubble_boxes:
            x1, y1, x2, y2 = int(box.x1), int(box.y1), int(box.x2), int(box.y2)
            
            if y2 > page_image.shape[0] or x2 > page_image.shape[1]:
                continue
            
            bgr = page_image[y1:y2, x1:x2]
            if bgr.size == 0:
                continue
            
            valid.append((box.label, bgr))
        
        return valid
    
    def _analyze_bubbles(self, bubble_images: List[Tuple[str, np.ndarray]]) -> List[BubbleMarkResult]:
        """OMR 분석 (공통 로직)"""
        from ..omr import omr_analyze_bubbles
        return omr_analyze_bubbles(bubble_images)
    
    def _select_answers(self, results: List[BubbleMarkResult]) -> Tuple[List[str], float]:
        """선택지 선택 (공통 로직)"""
        from ..omr import omr_select_answers
        return omr_select_answers(results)
    
    def _build_result(self, selected_number: int, selected_label: str, 
                      confidence: float = 0.0, extra_debug: Dict = None) -> Dict:
        """결과 딕셔너리 빌드"""
        correct = (selected_number == self.expected_answer)
        
        return {
            'selected_number': selected_number,
            'selected_label': selected_label,
            'correct': correct,
            'score': self.score_value if correct else 0.0,
            'debug': {
                'confidence': confidence,
                'expected': self.expected_answer,
                **(extra_debug or {})
            }
        }