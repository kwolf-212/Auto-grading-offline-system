# exam_grader/scoring_engine.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from .graders import (
    CalculationGrader,
    CodeGrader,
    DefaultGrader,
    EssayGrader,
    FillBlankGrader,
    MatchingGrader,
    MultipleChoiceGrader,
    OrderingGrader,
    QuestionGrader,
    ShortAnswerGrader,
    TrueFalseGrader,
)

# 하위 호환: 기존 `from exam_grader.scoring_engine import MultipleChoiceGrader` 등
__all__ = [
    "ScoringMethod",
    "QuestionScore",
    "GradingResult",
    "QuestionGrader",
    "MultipleChoiceGrader",
    "TrueFalseGrader",
    "FillBlankGrader",
    "ShortAnswerGrader",
    "MatchingGrader",
    "OrderingGrader",
    "CalculationGrader",
    "CodeGrader",
    "EssayGrader",
    "DefaultGrader",
    "ScoringEngine",
]


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
            "partial_credit": True,
            "case_sensitive": False,
            "ignore_whitespace": True,
            "exact_match_only": False,
        }

        self.answers_key = exam_data.get("answers", [])
        self.correct_answers: Dict[int, str] = {}
        self.max_scores: Dict[int, Any] = {}
        self.question_types: Dict[int, str] = {}

        for q in self.answers_key:
            qid = q.get("question_id")
            if qid:
                self.correct_answers[qid] = q.get("expected_answer", q.get("answer", "")).strip()
                self.max_scores[qid] = q.get("score", q.get("points", 0))
                self.question_types[qid] = q.get("question_type", "unknown")

        multiple_choice = MultipleChoiceGrader()
        short_answer = ShortAnswerGrader()

        self._graders: Dict[str, QuestionGrader] = {
            "multiple_choice": multiple_choice,
            "true_false": TrueFalseGrader(),
            "fill_blank": FillBlankGrader(self.settings, multiple_choice),
            "short_answer": short_answer,
            "matching": MatchingGrader(),
            "ordering": OrderingGrader(),
            "calculation": CalculationGrader(short_answer),
            "code": CodeGrader(self.settings),
            "essay": EssayGrader(),
        }
        self._default_grader: QuestionGrader = DefaultGrader()

    def calculate_scores(self, student_answers: Dict[int, str]) -> GradingResult:
        """
        학생 답안 채점

        Args:
            student_answers: 문제 ID -> 학생 답안 매핑

        Returns:
            GradingResult 객체
        """
        question_scores: Dict[int, QuestionScore] = {}
        total_score = 0.0
        total_max = 0.0

        for qid, max_score in self.max_scores.items():
            student_answer = student_answers.get(qid, "")
            correct_answer = self.correct_answers.get(qid, "")
            qtype = self.question_types.get(qid, "unknown")

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
                scoring_method=self._get_scoring_method(qtype),
            )

            total_score += earned_score
            total_max += max_score

        percentage = (total_score / total_max * 100) if total_max > 0 else 0
        passed = percentage >= 60

        return GradingResult(
            total_score=total_score,
            max_score=total_max,
            percentage=percentage,
            question_scores=question_scores,
            passed=passed,
            details={
                "total_questions": len(question_scores),
                "correct_count": sum(1 for qs in question_scores.values() if qs.is_correct),
                "settings": self.settings,
            },
        )

    def _grade_question(
        self, qid: int, student: str, correct: str, max_score: int, qtype: str
    ) -> Tuple[float, str]:
        if not student or not student.strip():
            return 0.0, "No answer provided"

        if not correct:
            return 0.0, "No correct answer defined"

        student_norm = self._normalize_answer(student)
        correct_norm = self._normalize_answer(correct)

        grader = self._graders.get(qtype, self._default_grader)
        return grader.grade(student_norm, correct_norm, max_score, qid)

    def _normalize_answer(self, answer: str) -> str:
        if not answer:
            return ""

        result = answer.strip()

        if not self.settings.get("case_sensitive", False):
            result = result.upper()

        if self.settings.get("ignore_whitespace", True):
            result = " ".join(result.split())

        return result

    def _get_scoring_method(self, qtype: str) -> str:
        method_map = {
            "multiple_choice": "exact_match",
            "true_false": "exact_match",
            "fill_blank": "partial_credit",
            "short_answer": "keyword_based",
            "matching": "exact_match",
            "ordering": "exact_match",
            "calculation": "range_based",
            "code": "manual",
            "essay": "manual",
        }
        return method_map.get(qtype, "exact_match")

    def get_question_summary(self, results: GradingResult) -> Dict[str, Any]:
        summary: Dict[str, Any] = {
            "total_questions": len(results.question_scores),
            "correct_count": 0,
            "partial_count": 0,
            "incorrect_count": 0,
            "average_score": 0.0,
            "question_details": [],
        }

        for qs in results.question_scores.values():
            if qs.percentage >= 90:
                summary["correct_count"] += 1
            elif qs.percentage > 0:
                summary["partial_count"] += 1
            else:
                summary["incorrect_count"] += 1

            summary["question_details"].append({
                "id": qs.question_id,
                "score": qs.earned_score,
                "max": qs.max_score,
                "percentage": qs.percentage,
                "feedback": qs.feedback,
            })

        summary["average_score"] = results.percentage
        return summary
