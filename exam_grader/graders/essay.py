# exam_grader/graders/essay.py
from .base import QuestionGrader


class EssayGrader(QuestionGrader):
    """에세이 채점 (수동 채점만 가능)"""

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
        return 0.0, "Essay questions require manual grading"
