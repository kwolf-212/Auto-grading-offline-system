# multiple_choice.py

from __future__ import annotations

from typing import List

from .base import QuestionGrader

from ..omr import (
    BubbleBox,
    omr_analyze_bubbles,
    omr_select_answers,
)


class MultipleChoiceGrader(QuestionGrader):

    def grade(
        self,
        bgr,
        bubble_boxes: List[BubbleBox],
        correct_answers: List[str],
        max_score: float = 1.0,
    ):
        """
        객관식 채점
        """

        bubble_results = omr_analyze_bubbles(
            bgr,
            bubble_boxes
        )

        selected, confidence = omr_select_answers(
            bubble_results
        )

        is_correct = (
            set(selected)
            == set(correct_answers)
        )

        score = max_score if is_correct else 0.0

        return {
            "selected": selected,
            "correct": is_correct,
            "score": score,
            "confidence": confidence,
            "details": bubble_results,
        }