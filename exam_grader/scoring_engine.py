# exam_grader/scoring_engine.py
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class ScoringMethod(Enum):
    """채점 방식"""
    EXACT_MATCH = "exact_match"      # 정확히 일치
    PARTIAL_CREDIT = "partial_credit"  # 부분 점수
    KEYWORD_BASED = "keyword_based"    # 키워드 기반
    RANGE_BASED = "range_based"        # 범위 기반 (숫자 답안)


@dataclass
class QuestionScore:
    """문제 점수 정보"""
    question_id: int
    earned_score: float
    max_score: float
    percentage: float
    is_correct: bool
    feedback: str = ""
    scoring_method: str = "exact_match"


@dataclass
class GradingResult:
    """채점 결과"""
    total_score: float
    max_score: float
    percentage: float
    question_scores: Dict[int, QuestionScore]
    passed: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


class ScoringEngine:
    """점수 계산 엔진"""
    
    def __init__(self, exam_data: Dict[str, Any], settings: Optional[Dict] = None):
        """
        Args:
            exam_data: 시험 데이터 (정답, 점수 등)
            settings: 채점 설정 (부분점수, 대소문자 구분 등)
        """
        self.exam_data = exam_data
        self.settings = settings or {
            'partial_credit': True,
            'case_sensitive': False,
            'ignore_whitespace': True,
            'exact_match_only': False,
        }
        
        # 정답 정보 구축
        self.answers_key = exam_data.get('answers', [])
        self.correct_answers = {}
        self.max_scores = {}
        self.question_types = {}
        
        for q in self.answers_key:
            qid = q.get('question_id')
            if qid:
                self.correct_answers[qid] = q.get('expected_answer', q.get('answer', '')).strip()
                self.max_scores[qid] = q.get('score', q.get('points', 0))
                self.question_types[qid] = q.get('question_type', 'unknown')
        
        # 문제 유형별 채점기
        self._graders = {
            'multiple_choice': self._grade_multiple_choice,
            'true_false': self._grade_true_false,
            'fill_blank': self._grade_fill_blank,
            'short_answer': self._grade_short_answer,
            'matching': self._grade_matching,
            'ordering': self._grade_ordering,
            'calculation': self._grade_calculation,
            'code': self._grade_code,
            'essay': self._grade_essay,
        }
    
    def calculate_scores(self, student_answers: Dict[int, str]) -> GradingResult:
        """
        학생 답안 채점
        
        Args:
            student_answers: 문제 ID -> 학생 답안 매핑
        
        Returns:
            GradingResult 객체
        """
        question_scores = {}
        total_score = 0.0
        total_max = 0.0
        
        for qid, max_score in self.max_scores.items():
            student_answer = student_answers.get(qid, '')
            correct_answer = self.correct_answers.get(qid, '')
            qtype = self.question_types.get(qid, 'unknown')
            
            # 점수 계산
            earned_score, feedback = self._grade_question(
                qid, student_answer, correct_answer, max_score, qtype
            )
            
            percentage = (earned_score / max_score * 100) if max_score > 0 else 0
            is_correct = earned_score >= max_score * 0.9 if max_score > 0 else False
            
            question_scores[qid] = QuestionScore(
                question_id=qid,
                earned_score=earned_score,
                max_score=float(max_score),
                percentage=percentage,
                is_correct=is_correct,
                feedback=feedback,
                scoring_method=self._get_scoring_method(qtype)
            )
            
            total_score += earned_score
            total_max += max_score
        
        percentage = (total_score / total_max * 100) if total_max > 0 else 0
        passed = percentage >= 60  # 60점 이상 합격
        
        return GradingResult(
            total_score=total_score,
            max_score=total_max,
            percentage=percentage,
            question_scores=question_scores,
            passed=passed,
            details={
                'total_questions': len(question_scores),
                'correct_count': sum(1 for qs in question_scores.values() if qs.is_correct),
                'settings': self.settings
            }
        )
    
    def _grade_question(self, qid: int, student: str, correct: str, 
                        max_score: int, qtype: str) -> Tuple[float, str]:
        """
        개별 문제 채점
        
        Returns:
            (획득 점수, 피드백)
        """
        # 빈 답안 처리
        if not student or not student.strip():
            return 0.0, "No answer provided"
        
        # 정답이 없는 경우
        if not correct:
            return 0.0, "No correct answer defined"
        
        # 정규화
        student_norm = self._normalize_answer(student)
        correct_norm = self._normalize_answer(correct)
        
        # 문제 유형별 채점
        grader = self._graders.get(qtype, self._grade_default)
        return grader(student_norm, correct_norm, max_score, qid)
    
    def _normalize_answer(self, answer: str) -> str:
        """답안 정규화"""
        if not answer:
            return ""
        
        result = answer.strip()
        
        if not self.settings.get('case_sensitive', False):
            result = result.upper()
        
        if self.settings.get('ignore_whitespace', True):
            result = ' '.join(result.split())
        
        return result
    
    def _get_scoring_method(self, qtype: str) -> str:
        """채점 방식 반환"""
        method_map = {
            'multiple_choice': 'exact_match',
            'true_false': 'exact_match',
            'fill_blank': 'partial_credit',
            'short_answer': 'keyword_based',
            'matching': 'exact_match',
            'ordering': 'exact_match',
            'calculation': 'range_based',
            'code': 'manual',
            'essay': 'manual',
        }
        return method_map.get(qtype, 'exact_match')
    
    # ===== 개별 문제 유형별 채점기 =====
    
    def _grade_multiple_choice(self, student: str, correct: str, 
                                max_score: int, qid: int) -> Tuple[float, str]:
        """객관식 채점"""
        if student == correct:
            return float(max_score), "Correct"
        
        # 알파벳만 추출하여 비교
        import re
        student_alpha = re.sub(r'[^A-Z]', '', student)
        correct_alpha = re.sub(r'[^A-Z]', '', correct)
        
        if student_alpha and correct_alpha and student_alpha[0] == correct_alpha[0]:
            return float(max_score), "Correct"
        
        return 0.0, f"Incorrect. Correct answer: {correct}"
    
    def _grade_true_false(self, student: str, correct: str, 
                      max_score: int, qid: int) -> Tuple[float, str]:
        """참/거짓 채점 - a(True), b(False) 비교"""
        # student와 correct 모두 'a' 또는 'b' 형태여야 함
        if student == correct:
            return float(max_score), "Correct"
        
        # 'a'와 'b'는 각각 True/False 의미
        # 혹시 모를 다른 형식 처리
        student_norm = self._normalize_tf(student)
        correct_norm = self._normalize_tf(correct)
        
        if student_norm == correct_norm:
            return float(max_score), "Correct"
        
        return 0.0, f"Incorrect. Correct answer: {correct}"
    
    def _normalize_tf(self, answer: str) -> str:
        """True/False 답안 정규화 (a/b 반환)"""
        answer = answer.strip().upper()
        if answer in ['A', 'TRUE', 'T', 'O', '○', '1']:
            return 'A'
        if answer in ['B', 'FALSE', 'F', 'X', '×', '0']:
            return 'B'
        return answer
    
    def _grade_fill_blank(self, student: str, correct: str, 
                          max_score: int, qid: int) -> Tuple[float, str]:
        """빈칸 채우기 채점 (부분 점수 가능)"""
        if not self.settings.get('partial_credit', True):
            return self._grade_multiple_choice(student, correct, max_score, qid)
        
        # 정확히 일치
        if student == correct:
            return float(max_score), "Correct"
        
        # 대소문자 무시 비교
        if student.upper() == correct.upper():
            return float(max_score) * 0.9, "Correct (case mismatch)"
        
        # 포함 관계 확인
        if correct in student or student in correct:
            return float(max_score) * 0.6, "Partially correct"
        
        return 0.0, f"Incorrect. Expected: {correct}"
    
    def _grade_short_answer(self, student: str, correct: str, 
                            max_score: int, qid: int) -> Tuple[float, str]:
        """단답형 채점 (키워드 기반)"""
        # 키워드 추출 (쉼표로 구분된 경우)
        keywords = [k.strip().upper() for k in correct.split(',')]
        
        matched = 0
        for keyword in keywords:
            if keyword and keyword in student.upper():
                matched += 1
        
        if matched == len(keywords) and len(keywords) > 0:
            return float(max_score), "All keywords matched"
        elif matched > 0:
            percentage = matched / len(keywords)
            earned = max_score * percentage
            return earned, f"Partially correct ({matched}/{len(keywords)} keywords matched)"
        
        return 0.0, f"Incorrect. Expected keywords: {correct}"
    
    def _grade_matching(self, student: str, correct: str, 
                        max_score: int, qid: int) -> Tuple[float, str]:
        """매칭 문제 채점"""
        # 형식: "1-A,2-B,3-C" 또는 "1→A,2→B"
        import re
        
        # 정답 파싱
        correct_pairs = self._parse_matching_pairs(correct)
        student_pairs = self._parse_matching_pairs(student)
        
        if not correct_pairs:
            return 0.0, "Invalid correct answer format"
        
        matched = 0
        for q_num, ans in student_pairs.items():
            if q_num in correct_pairs and correct_pairs[q_num] == ans:
                matched += 1
        
        if matched == len(correct_pairs):
            return float(max_score), "All matches correct"
        elif matched > 0:
            earned = max_score * (matched / len(correct_pairs))
            return earned, f"Partially correct ({matched}/{len(correct_pairs)} matches)"
        
        return 0.0, f"Incorrect matching"
    
    def _parse_matching_pairs(self, text: str) -> Dict[int, str]:
        """매칭 쌍 파싱"""
        pairs = {}
        # 패턴: 1-A, 2-B 또는 1→A
        pattern = re.compile(r'(\d+)[\-→](\w)')
        matches = pattern.findall(text)
        
        for q_num, ans in matches:
            pairs[int(q_num)] = ans.upper()
        
        return pairs
    
    def _grade_ordering(self, student: str, correct: str, 
                        max_score: int, qid: int) -> Tuple[float, str]:
        """순서 배열 채점"""
        correct_order = [x.strip() for x in correct.split(',')]
        student_order = [x.strip() for x in student.split(',')]
        
        if not correct_order:
            return 0.0, "Invalid correct order format"
        
        # 완전 일치
        if student_order == correct_order:
            return float(max_score), "Correct order"
        
        # 부분 일치 (위치 정확도)
        correct_positions = 0
        for i, item in enumerate(student_order):
            if i < len(correct_order) and item == correct_order[i]:
                correct_positions += 1
        
        if correct_positions > 0:
            percentage = correct_positions / len(correct_order)
            earned = max_score * percentage
            return earned, f"Partially correct ({correct_positions}/{len(correct_order)} positions correct)"
        
        return 0.0, f"Incorrect order"
    
    def _grade_calculation(self, student: str, correct: str, 
                           max_score: int, qid: int) -> Tuple[float, str]:
        """계산 문제 채점 (숫자 비교)"""
        try:
            # 숫자 추출
            import re
            student_num = float(re.findall(r'-?\d+\.?\d*', student)[0]) if re.findall(r'-?\d+\.?\d*', student) else None
            correct_num = float(re.findall(r'-?\d+\.?\d*', correct)[0]) if re.findall(r'-?\d+\.?\d*', correct) else None
            
            if student_num is None or correct_num is None:
                return self._grade_short_answer(student, correct, max_score, qid)
            
            # 정확히 일치
            if student_num == correct_num:
                return float(max_score), "Correct"
            
            # 오차 범위 내 (1% 이내)
            tolerance = abs(correct_num) * 0.01 if correct_num != 0 else 0.01
            if abs(student_num - correct_num) <= tolerance:
                return float(max_score) * 0.95, "Correct (within tolerance)"
            
            return 0.0, f"Incorrect. Expected: {correct_num}"
            
        except (ValueError, IndexError):
            return self._grade_short_answer(student, correct, max_score, qid)
    
    def _grade_code(self, student: str, correct: str, 
                    max_score: int, qid: int) -> Tuple[float, str]:
        """코드 문제 채점 (수동 채점 권장)"""
        # 간단한 키워드 매칭만 수행
        if not self.settings.get('exact_match_only', True):
            return 0.0, "Code questions require manual grading"
        
        # 키워드 기반 자동 채점
        keywords = [k.strip().upper() for k in correct.split(',')]
        matched = sum(1 for kw in keywords if kw and kw in student.upper())
        
        if matched == len(keywords) and len(keywords) > 0:
            return float(max_score), "All required keywords found"
        elif matched > 0:
            earned = max_score * (matched / len(keywords))
            return earned, f"Partially correct ({matched}/{len(keywords)} keywords found)"
        
        return 0.0, "Manual grading required"
    
    def _grade_essay(self, student: str, correct: str, 
                     max_score: int, qid: int) -> Tuple[float, str]:
        """에세이 채점 (수동 채점만 가능)"""
        return 0.0, "Essay questions require manual grading"
    
    def _grade_default(self, student: str, correct: str, 
                       max_score: int, qid: int) -> Tuple[float, str]:
        """기본 채점 (정확히 일치)"""
        if student == correct:
            return float(max_score), "Correct"
        return 0.0, f"Incorrect. Expected: {correct}"
    
    def get_question_summary(self, results: GradingResult) -> Dict[str, Any]:
        """문제별 통계 요약"""
        summary = {
            'total_questions': len(results.question_scores),
            'correct_count': 0,
            'partial_count': 0,
            'incorrect_count': 0,
            'average_score': 0.0,
            'question_details': []
        }
        
        for qs in results.question_scores.values():
            if qs.percentage >= 90:
                summary['correct_count'] += 1
            elif qs.percentage > 0:
                summary['partial_count'] += 1
            else:
                summary['incorrect_count'] += 1
            
            summary['question_details'].append({
                'id': qs.question_id,
                'score': qs.earned_score,
                'max': qs.max_score,
                'percentage': qs.percentage,
                'feedback': qs.feedback
            })
        
        summary['average_score'] = results.percentage
        return summary