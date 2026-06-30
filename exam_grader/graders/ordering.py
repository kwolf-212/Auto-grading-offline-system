# exam_grader/graders/ordering.py
from typing import Dict, List, Tuple, Optional
import numpy as np
import re

from .base import BaseGrader
from ..recognition.digit_recognizer import DigitRecognizer

class OrderingGrader(BaseGrader):
    """
    순서 배열(ordering) 유형 문제 채점기
    
    - 각 선택지 영역에는 학생이 순서 번호(1,2,3,...)를 기입
    - 정답 형식: "1>2>3" 또는 "1,2,3" 또는 "1-2-3" 등
    - 학생이 기입한 순서가 정답 순서와 일치하는지 채점
    """
    def __init__(self, qinfo: Dict):    
        super().__init__(qinfo)

    def grade(self, page_image: np.ndarray, debug_mode: bool = False) -> Dict:
        """
        순서 배열 문제 채점 실행
        
        Returns:
            Dict: {
                'selected_number': int (첫 번째 선택지의 순번, 호환용),
                'selected_label': str (첫 번째 선택지의 레이블, 호환용),
                'student_order': List[int],  # 학생이 기입한 전체 순서
                'correct_order': List[int],  # 정답 순서
                'correct': bool,              # 전체 순서 일치 여부
                'score': float,
                'debug': dict
            }
        """
        result = {
            'selected_number': 0,
            'selected_label': '',
            'student_order': [],
            'correct_order': [],
            'correct': False,
            'score': 0.0,
            'debug': {}
        }
        
        if not self.bubble_boxes:
            return result
        
        try:
            # 각 영역에서 학생이 기입한 순서 번호 추출
            student_order, confidences = self._extract_student_order(page_image)
            
            # 정답 순서 파싱
            correct_order = self._parse_correct_order()
            
            # 채점
            is_correct = (student_order == correct_order)
            
            # 호환용: 첫 번째 선택지의 순번을 selected_number로 설정
            first_order = student_order[0] if student_order else 0
            
            # 신뢰도 계산 (OCR 기반)
            confidence = self._calculate_confidence_from_ocr(student_order)
            
            result = self._build_result(
                selected_number=first_order,
                selected_label=str(first_order) if first_order else '',
                confidence=confidence,
                extra_debug={
                    'student_order': student_order,
                    'correct_order': correct_order,
                    'bubble_boxes': [(box.label, box.x1, box.y1, box.x2, box.y2) 
                                     for box in self.bubble_boxes]
                }
            )
            
            # 결과에 ordering 특화 정보 추가
            result['student_order'] = student_order
            result["digit_confidence"] = confidences
            result['correct_order'] = correct_order
            result['correct'] = is_correct
            result['score'] = (
                self.score_value
                if is_correct
                else 0.0
            )
            print("ordering")
            if debug_mode:
                print(f"    Q{self.question_id}: Ordering result - student={student_order}, correct={correct_order}, match={is_correct}")
                
        except Exception as e:
            result['debug']['error'] = str(e)
            if debug_mode:
                import traceback
                traceback.print_exc()
        
        return result
    
    def _extract_student_order(
        self, 
        page_image: np.ndarray
    ) -> List[int]:
        """
        Keras CNN 모델로 학생 순서 추출
        """
        recognizer = DigitRecognizer()

        crop_imgs = self._crop_bubble_regions(page_image)
        student_order, confidences = recognizer.recognize_boxes(crop_imgs)

        return student_order, confidences
    
    def _calculate_confidence_from_ocr(self, student_order: List[int]) -> float:
        """
        OCR 기반 신뢰도 계산
        
        - 유효한 숫자가 있는 영역 비율
        - 모든 영역에서 숫자가 인식되었는지 여부
        """
        if not student_order:
            return 0.0
        
        # 유효한 순서 번호 비율 (0이 아닌 값)
        valid_count = sum(1 for x in student_order if x > 0)
        valid_ratio = valid_count / len(student_order)
        
        # 모든 영역이 인식되었으면 신뢰도 상승
        if valid_count == len(student_order):
            confidence = 0.95
        elif valid_count >= len(student_order) * 0.7:
            confidence = 0.7
        elif valid_count >= len(student_order) * 0.5:
            confidence = 0.5
        else:
            confidence = 0.3
        
        return min(1.0, max(0.0, confidence))
    
    def _parse_correct_order(self) -> List[int]:
        """
        정답 순서 파싱
        
        지원 형식:
        - "1>2>3"  (1순위, 2순위, 3순위)
        - "1,2,3"
        - "1-2-3"
        - "1 2 3"
        - "1→2→3"
        - [1,2,3]  (직접 리스트로 입력된 경우)
        
        expected_answer_number가 리스트 또는 문자열 형태로 제공됨
        """
        expected = self.expected_answer
        
        # 이미 리스트인 경우
        if isinstance(expected, list):
            return [int(x) for x in expected]
        
        # 문자열인 경우 파싱
        if isinstance(expected, str):
            # 숫자와 구분자 매칭
            numbers = re.findall(r'\d+', expected)
            if numbers:
                return [int(n) for n in numbers]
        
        # 숫자인 경우 (단일 값: 한 문제만 있는 순서 배열)
        if isinstance(expected, (int, float)):
            return [int(expected)]
        
        # 파싱 실패
        return []
    
    def get_partial_score(self, page_image: np.ndarray, 
                          partial_weights: List[float] = None) -> Dict:
        """
        부분 점수 계산 (순서가 완전히 일치하지 않을 때)
        
        Args:
            page_image: 페이지 이미지
            partial_weights: 각 위치의 가중치 (예: [0.3, 0.3, 0.4])
        
        Returns:
            Dict: 부분 점수 정보
        """
        result = self.grade(page_image)
        
        if result['correct']:
            result['partial_score'] = self.score_value
            result['partial_ratio'] = 1.0
            return result
        
        student_order = result.get('student_order', [])
        correct_order = result.get('correct_order', [])
        
        if not student_order or not correct_order:
            result['partial_score'] = 0.0
            result['partial_ratio'] = 0.0
            return result
        
        # 순서 일치도 계산
        match_count = 0
        total = len(correct_order)
        
        for i, (s, c) in enumerate(zip(student_order, correct_order)):
            if s == c:
                match_count += 1
        
        # 기본: 맞춘 개수 비율
        ratio = match_count / total if total > 0 else 0
        
        # 가중치가 있는 경우 적용
        if partial_weights and len(partial_weights) == total:
            weighted_score = 0.0
            for i, (s, c) in enumerate(zip(student_order, correct_order)):
                if s == c:
                    weighted_score += partial_weights[i]
            total_weight = sum(partial_weights)
            ratio = weighted_score / total_weight if total_weight > 0 else 0
        
        result['partial_score'] = self.score_value * ratio
        result['partial_ratio'] = ratio
        result['match_count'] = match_count
        result['total_count'] = total
        
        return result