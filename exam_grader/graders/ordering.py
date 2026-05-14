# exam_grader/graders/ordering.py
from .base import QuestionGrader


class OrderingGrader(QuestionGrader):
    """순서 배열 채점"""

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
        correct_order = [x.strip() for x in correct.split(",")]
        student_order = [x.strip() for x in student.split(",")]

        if not correct_order:
            return 0.0, "Invalid correct order format"

        if student_order == correct_order:
            return float(max_score), "Correct order"

        correct_positions = 0
        for i, item in enumerate(student_order):
            if i < len(correct_order) and item == correct_order[i]:
                correct_positions += 1

        if correct_positions > 0:
            percentage = correct_positions / len(correct_order)
            earned = max_score * percentage
            return earned, f"Partially correct ({correct_positions}/{len(correct_order)} positions correct)"

        return 0.0, "Incorrect order"
