# generator.py
import json

class ExamGenerator:
    def __init__(self):
        self.questions = []

    def add_question(self, qid, qtype, answer, score, bbox):
        self.questions.append({
            "id": qid,
            "type": qtype,
            "answer": answer,
            "score": score,
            "bbox": bbox
        })

    def create_exam(self):
        # 예시 문제 추가
        self.add_question(1, "multiple_choice", "B", 5, [100, 200, 300, 350])
        self.add_question(2, "short_answer", "Python", 5, [100, 400, 300, 450])
        self.add_question(3, "essay", "AI is important", 10, [100, 500, 500, 700])

        with open("exam.json", "w") as f:
            json.dump({"questions": self.questions}, f, indent=2)

        return {"questions": self.questions}
