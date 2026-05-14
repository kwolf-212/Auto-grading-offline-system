# exam_grader/graders/short_answer.py
from .base import QuestionGrader


class ShortAnswerGrader(QuestionGrader):
    """단답형 채점 (키워드 기반)"""

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
        keywords = [k.strip().upper() for k in correct.split(",")]

        matched = 0
        for keyword in keywords:
            if keyword and keyword in student.upper():
                matched += 1

        if matched == len(keywords) and len(keywords) > 0:
            return float(max_score), "All keywords matched"
        if matched > 0:
            percentage = matched / len(keywords)
            earned = max_score * percentage
            return earned, f"Partially correct ({matched}/{len(keywords)} keywords matched)"

        return 0.0, f"Incorrect. Expected keywords: {correct}"
