# exam_grader/graders/multiple_choice.py
from typing import Dict, List, Tuple
import numpy as np

from .base import BaseGrader
from ..omr import BubbleMarkResult


class MultipleChoiceGrader(BaseGrader):
    """객관식 문제 채점기"""
    
    def grade(self, page_image: np.ndarray, debug_mode: bool = False) -> Dict:
        result = {
            'selected_number': 0,
            'selected_label': '',
            'correct': False,
            'score': 0.0,
            'debug': {}
        }
        
        if not self.bubble_boxes:
            return result
        
        try:
            # 버블 영역 크롭
            valid = self._crop_bubble_regions(page_image)
            
            if not valid:
                return result
            
            # OMR 분석
            results = self._analyze_bubbles(valid)
            
            # 선택지 결정 (가장 높은 점수)
            selected, conf = self._select_answers(results)
            
            if selected:
                selected_label = selected[0]
                selected_number = self._label_to_number(selected_label)
                
                result = self._build_result(
                    selected_number=selected_number,
                    selected_label=selected_label,
                    confidence=conf,
                    extra_debug={
                        'bubble_scores': [(r.label, r.score) for r in results],
                        'bubble_marked': [(r.label, r.marked) for r in results]
                    }
                )
            
            if debug_mode:
                print(f"    Q{self.question_id}: MC result - selected={selected_label}, conf={conf:.3f}")
                
        except Exception as e:
            result['debug']['error'] = str(e)
            if debug_mode:
                import traceback
                traceback.print_exc()
        
        return result
    
    def _label_to_number(self, label: str) -> int:
        """선택지 레이블을 숫자로 변환"""
        if label is None:
            return 0
        
        if isinstance(label, int):
            return label
        
        a = str(label).strip().lower()
        
        if a.isdigit():
            return int(a)
        
        if a in ('t', 'true'):
            return 1
        if a in ('f', 'false'):
            return 2
        
        if len(a) == 1 and a.isalpha():
            return ord(a) - ord('a') + 1
        
        return 0