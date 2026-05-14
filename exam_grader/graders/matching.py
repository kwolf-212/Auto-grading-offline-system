# exam_grader/graders/matching.py
import re
from typing import Dict

from .base import QuestionGrader


class MatchingGrader(QuestionGrader):
    """매칭 문제 채점"""

    _PAIR_PATTERN = re.compile(r"(\d+)[\-→](\w)")

    @classmethod
    def _parse_matching_pairs(cls, text: str) -> Dict[int, str]:
        pairs: Dict[int, str] = {}
        for q_num, ans in cls._PAIR_PATTERN.findall(text):
            pairs[int(q_num)] = ans.upper()
        return pairs

    def grade(self, student: str, correct: str, max_score: int, qid: int) -> tuple[float, str]:
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
        if matched > 0:
            earned = max_score * (matched / len(correct_pairs))
            return earned, f"Partially correct ({matched}/{len(correct_pairs)} matches)"

        return 0.0, "Incorrect matching"
