# exam_grader/graders/code_writing.py
from typing import Any, Dict

from .base import QuestionGrader


class CodeGrader(QuestionGrader):
    """코드 문제 채점 (수동 채점 권장, 키워드 보조)"""

    def __init__(self, settings: Dict[str, Any]):
        self._settings = settings

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
        if not self._settings.get("exact_match_only", True):
            return 0.0, "Code questions require manual grading"

        keywords = [k.strip().upper() for k in correct.split(",")]
        matched = sum(1 for kw in keywords if kw and kw in student.upper())

        if matched == len(keywords) and len(keywords) > 0:
            return float(max_score), "All required keywords found"
        if matched > 0:
            earned = max_score * (matched / len(keywords))
            return earned, f"Partially correct ({matched}/{len(keywords)} keywords found)"

        return 0.0, "Manual grading required"
