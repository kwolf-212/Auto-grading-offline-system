# common/models.py
from typing import List, Dict, Any, Optional


class Question:
    """질문 데이터 모델"""
    
    def __init__(self, qid: int, qtype: int, text: str, score: int = 5, 
                 difficulty: str = "Medium", answer: str = ""):
        self.id = qid
        self.type = qtype
        self.text = text
        self.score = score
        self.difficulty = difficulty
        self.answer = answer
        
        # Optional fields
        self.choices: List[str] = []
        self.blanks: List[str] = []
        self.matching_pairs: List[tuple] = []
        self.ordering_items: List[str] = []
        self.code_template: str = ""
        self.formula: str = ""
        self.db_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "type": self.type, "text": self.text,
            "score": self.score, "difficulty": self.difficulty, "answer": self.answer,
            "choices": self.choices, "blanks": self.blanks,
            "matching_pairs": self.matching_pairs, "ordering_items": self.ordering_items,
            "code_template": self.code_template, "formula": self.formula, "db_id": self.db_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Question':
        q = cls(data.get('id', 0), data.get('type', 0), data.get('text', ''),
                data.get('score', 5), data.get('difficulty', 'Medium'), data.get('answer', ''))
        q.choices = data.get('choices', [])
        q.blanks = data.get('blanks', [])
        q.matching_pairs = data.get('matching_pairs', [])
        q.ordering_items = data.get('ordering_items', [])
        q.code_template = data.get('code_template', '')
        q.formula = data.get('formula', '')
        q.db_id = data.get('db_id')
        return q