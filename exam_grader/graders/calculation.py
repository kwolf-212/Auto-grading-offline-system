# exam_grader/graders/calculation.py
import re

from .base import QuestionGrader
from .short_answer import ShortAnswerGrader


class CalculationGrader(QuestionGrader):
    """계산 문제 채점 (숫자 비교)"""

    def __init__(self, short_answer: ShortAnswerGrader):
        self._short_answer = short_answer

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
        try:
            student_nums = re.findall(r"-?\d+\.?\d*", student)
            correct_nums = re.findall(r"-?\d+\.?\d*", correct)
            student_num = float(student_nums[0]) if student_nums else None
            correct_num = float(correct_nums[0]) if correct_nums else None

            if student_num is None or correct_num is None:
                return self._short_answer.grade(student, correct, max_score, qid)

            if student_num == correct_num:
                return float(max_score), "Correct"

            tolerance = abs(correct_num) * 0.01 if correct_num != 0 else 0.01
            if abs(student_num - correct_num) <= tolerance:
                return float(max_score) * 0.95, "Correct (within tolerance)"

            return 0.0, f"Incorrect. Expected: {correct_num}"

        except (ValueError, IndexError):
            return self._short_answer.grade(student, correct, max_score, qid)
