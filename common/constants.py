# common/constants.py
from reportlab.lib.pagesizes import A4, letter, A5, B5, legal, landscape

PAGE_SIZES = {
    "A4": A4,
    "Letter": letter,
    "A5": A5,
    "B5": B5,
    "Legal": legal,
    "A4 Landscape": landscape(A4),
    "Letter Landscape": landscape(letter),
}

QUESTION_TYPES = {
    0: {"name": "Multiple Choice", "icon": "🔘", "has_options": True, "has_answer": True, "auto_gradable": True},
    1: {"name": "True/False", "icon": "✓✗", "has_options": False, "has_answer": True, "auto_gradable": True},
    2: {"name": "Fill in the Blank", "icon": "___", "has_options": False, "has_answer": True, "has_blanks": True, "auto_gradable": True},
    3: {"name": "Short Answer", "icon": "📝", "has_options": False, "has_answer": True, "auto_gradable": False},
    4: {"name": "Essay", "icon": "📄", "has_options": False, "has_answer": True, "has_lines": True, "auto_gradable": False},
    5: {"name": "Matching", "icon": "🔗", "has_options": True, "has_answer": True, "has_pairs": True, "auto_gradable": True},
    6: {"name": "Ordering/Ranking", "icon": "🔢", "has_options": True, "has_answer": True, "has_items": True, "auto_gradable": True},
    7: {"name": "Code Writing", "icon": "💻", "has_options": False, "has_answer": True, "has_code": True, "auto_gradable": False},
    8: {"name": "Calculation", "icon": "🧮", "has_options": False, "has_answer": True, "has_formula": True, "auto_gradable": True},
    9: {"name": "Diagram/Labeling", "icon": "📊", "has_options": False, "has_answer": True, "has_diagram": True, "auto_gradable": False},
}

# 자동 채점 가능한 문제 유형
AUTO_GRADABLE_TYPES = [0, 1, 2, 5, 6, 8]

DEFAULT_EXAM_SETTINGS = {
    'exam_title': 'Midterm Examination',
    'exam_date': None,
    'exam_instruction': '',
    'page_size': 'A4',
    'layout_style': 'Two Column',
    'margin': 50,
    'line_spacing': 1.5,
    'font_size': 11,
    'title_font_size': 18,
    'show_qr': True,
    'essay_lines': 4,
    'include_student_info': True,
    'student_name': '',
    'student_id': '',
    'department': '',
    'instructor': '',
    'show_points': True,
    'numbering_style': '1, 2, 3...'
}

DEFAULT_GRADER_SETTINGS = {
    'partial_credit': True,
    'case_sensitive': False,
    'ignore_whitespace': True,
    'exact_match_only': False,
    'points_per_question': {},
    'grading_method': 'auto',  # auto, manual, hybrid
}