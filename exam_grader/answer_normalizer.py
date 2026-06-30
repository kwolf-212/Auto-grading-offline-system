# exam_grader/answer_normalizer.py (신규 파일)
"""답안 정규화 유틸리티 (채점 엔진 공용)"""

class AnswerNormalizer:
    @staticmethod
    def to_number(answer) -> int:
        """A→1, True→1, False→2"""
        # grader_engine._answer_to_number 로직 이동
    
    @staticmethod
    def to_letter(answer) -> str:
        """1→A, True→T"""
    
    @staticmethod
    def normalize(answer) -> str:
        """비교용 정규화"""
    
    @staticmethod
    def compare(student, correct) -> bool:
        """답안 비교"""