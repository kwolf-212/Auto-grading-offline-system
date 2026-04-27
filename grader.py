# grader.py
import json
from image_processing import preprocess_image, extract_region
from ocr_module import recognize_text, recognize_choice
from grading import *

class ExamGrader:
    def __init__(self, exam_data):
        self.questions = exam_data["questions"]

    def grade_exam(self, image_path):
        image = preprocess_image(image_path)
        results = {}

        for q in self.questions:
            region = extract_region(image, q["bbox"])

            if q["type"] == "multiple_choice":
                student_ans = recognize_choice(region)
                score = grade_multiple_choice(student_ans, q["answer"])

            else:
                text = recognize_text(region)

                if q["type"] == "short_answer":
                    score = grade_short_answer(text, q["answer"])

                elif q["type"] == "essay":
                    score = grade_essay(text, q["answer"])

                else:
                    score = 0

            results[q["id"]] = score * q["score"]

        return results
