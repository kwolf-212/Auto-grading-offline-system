# exam_grader/graders/true_false.py
from .base import QuestionGrader


class TrueFalseGrader(QuestionGrader):
    """참/거짓 채점 - a(True), b(False) 비교"""

    @staticmethod
    def _normalize_tf(answer: str) -> str:
        answer = answer.strip().upper()
        if answer in ["A", "TRUE", "T", "O", "○", "1"]:
            return "A"
        if answer in ["B", "FALSE", "F", "X", "×", "0"]:
            return "B"
        return answer

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
        if student == correct:
            return float(max_score), "Correct"

        student_norm = self._normalize_tf(student)
        correct_norm = self._normalize_tf(correct)

        if student_norm == correct_norm:
            return float(max_score), "Correct"

        return 0.0, f"Incorrect. Correct answer: {correct}"
