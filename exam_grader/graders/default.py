# exam_grader/graders/default.py
from .base import QuestionGrader


class DefaultGrader(QuestionGrader):
    """기본 채점 (정확히 일치)"""

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
        if student == correct:
            return float(max_score), "Correct"
        return 0.0, f"Incorrect. Expected: {correct}"
