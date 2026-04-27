# grading.py
from difflib import SequenceMatcher

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def grade_multiple_choice(student, correct):
    return 1 if student == correct else 0

def grade_short_answer(student, correct):
    return similarity(student.lower(), correct.lower())

def grade_essay(student, reference):
    sim = similarity(student, reference)
    keyword_score = 1 if "AI" in student else 0
    length_score = min(len(student) / 50, 1)

    return 0.5 * sim + 0.3 * keyword_score + 0.2 * length_score
