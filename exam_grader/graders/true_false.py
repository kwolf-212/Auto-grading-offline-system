# exam_grader/graders/true_false.py
from typing import Dict, List
import numpy as np

from .base import BaseGrader
from ..omr import BubbleMarkResult


class TrueFalseGrader(BaseGrader):
    """True/False 문제 채점기"""
    
    # True/False 매핑
    TRUE_LABELS = {'t', 'true', '1', 'a'}
    FALSE_LABELS = {'f', 'false', '0', '2', 'b'}
    
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
            
            # TF 특화 선택 로직
            selected_label, conf, details = self._select_tf_answer(results)
            
            if selected_label:
                selected_number = self._tf_label_to_number(selected_label)
                
                result = self._build_result(
                    selected_number=selected_number,
                    selected_label=selected_label,
                    confidence=conf,
                    extra_debug={
                        'bubble_scores': details,
                        'tf_analysis': self._analyze_tf_confidence(results)
                    }
                )
            
            if debug_mode:
                print(f"    Q{self.question_id}: TF result - selected={selected_label}, conf={conf:.3f}")
                
        except Exception as e:
            result['debug']['error'] = str(e)
            if debug_mode:
                import traceback
                traceback.print_exc()
        
        return result
    
    def _select_tf_answer(self, results: List[BubbleMarkResult]) -> tuple:
        """True/False 특화 선택 로직"""
        if not results:
            return None, 0.0, {}
        
        # True와 False 버블 분리
        tf_scores = {}
        for r in results:
            normalized_label = r.label.lower()
            if normalized_label in self.TRUE_LABELS:
                tf_scores['true'] = r.score
            elif normalized_label in self.FALSE_LABELS:
                tf_scores['false'] = r.score
        
        if not tf_scores:
            # 기본 fallback: 가장 높은 점수
            best = max(results, key=lambda x: x.score)
            return best.label, best.score, {'scores': {r.label: r.score for r in results}}
        
        # 더 높은 점수의 답 선택
        true_score = tf_scores.get('true', 0.0)
        false_score = tf_scores.get('false', 0.0)
        
        if true_score >= false_score:
            return 'true', true_score, {'true_score': true_score, 'false_score': false_score}
        else:
            return 'false', false_score, {'true_score': true_score, 'false_score': false_score}
    
    def _tf_label_to_number(self, label: str) -> int:
        """True/False 레이블을 숫자로 변환 (1=True, 2=False)"""
        if label is None:
            return 0
        
        label_lower = str(label).strip().lower()
        
        if label_lower in self.TRUE_LABELS:
            return 1
        elif label_lower in self.FALSE_LABELS:
            return 2
        
        return 0
    
    def _analyze_tf_confidence(self, results: List[BubbleMarkResult]) -> Dict:
        """TF 응답의 신뢰도 분석"""
        true_score = 0.0
        false_score = 0.0
        
        for r in results:
            if r.label.lower() in self.TRUE_LABELS:
                true_score = r.score
            elif r.label.lower() in self.FALSE_LABELS:
                false_score = r.score
        
        total = true_score + false_score
        if total > 0:
            return {
                'true_confidence': true_score / total,
                'false_confidence': false_score / total,
                'margin': abs(true_score - false_score)
            }
        
        return {'true_confidence': 0, 'false_confidence': 0, 'margin': 0}