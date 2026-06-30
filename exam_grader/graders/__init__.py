# exam_grader/graders/__init__.py
from typing import Dict, Type

from .base import BaseGrader
from .multiple_choice import MultipleChoiceGrader
from .true_false import TrueFalseGrader
from .ordering import OrderingGrader  

# 유형별 채점기 매핑
GRADER_REGISTRY: Dict[str, Type[BaseGrader]] = {
    'multiple_choice': MultipleChoiceGrader,
    'mc': MultipleChoiceGrader,
    'true_false': TrueFalseGrader,
    'True/False': TrueFalseGrader,
    'tf': TrueFalseGrader,
    'ordering': OrderingGrader,
    'ordering/ranking': OrderingGrader,
}


def get_grader(question_type: str, qinfo: Dict) -> BaseGrader:
    """문제 유형에 맞는 채점기 반환"""
    grader_class = GRADER_REGISTRY.get(question_type.lower())
    
    if grader_class is None:
        # 기본값: Multiple Choice
        grader_class = MultipleChoiceGrader
    
    return grader_class(qinfo)


__all__ = ['BaseGrader', 'MultipleChoiceGrader', 'TrueFalseGrader', 'OrderingGrader', 'get_grader']