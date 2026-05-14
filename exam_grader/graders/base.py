# exam_grader/graders/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Tuple


class QuestionGrader(ABC):
    """개별 문제 유형 채점기 베이스 (정규화된 student/correct 문자열을 받음)"""

    @abstractmethod
    def grade(self, student: str, correct: str, max_score: int, qid: int) -> Tuple[float, str]:
        """획득 점수와 피드백 메시지를 반환한다."""
