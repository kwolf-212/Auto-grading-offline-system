# exam_grader/graders/fill_blank.py
from typing import Any, Dict

from .base import QuestionGrader
from .multiple_choice import MultipleChoiceGrader


class FillBlankGrader(QuestionGrader):
    """빈칸 채우기 채점 (부분 점수 가능)"""

    def __init__(self, settings: Dict[str, Any], multiple_choice: MultipleChoiceGrader):
        self._settings = settings
        self._multiple_choice = multiple_choice

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
        if not self._settings.get("partial_credit", True):
            return self._multiple_choice.grade(student, correct, max_score, qid)

        if student == correct:
            return float(max_score), "Correct"

        if student.upper() == correct.upper():
            return float(max_score) * 0.9, "Correct (case mismatch)"

        if correct in student or student in correct:
            return float(max_score) * 0.6, "Partially correct"

        return 0.0, f"Incorrect. Expected: {correct}"
