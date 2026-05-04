# exam_generator/answer_sheet_engine.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import black

from common.constants import PAGE_SIZES


class AnswerSheetEngine:
    """답안지 PDF 생성 엔진"""
    
    def __init__(self, questions, settings):
        self.questions = questions
        self.settings = settings
    
    def generate_answer_sheet(self, file_path):
        """답안지 PDF 생성"""
        if not self.questions:
            return

        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        margin = 35
        col_gap = 20
        col_width = (page_size[0] - (margin * 2) - col_gap) // 2
        
        base_font_size = 12
        line_height = int(self.settings.get('line_spacing', 1.5) * base_font_size)
        small_line_height = line_height - 3
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size

        # 타이틀
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 35, "ANSWER SHEET")
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height - 55, f"{self.settings.get('exam_title', 'Exam')}")

        y = height - 85
        
        # Student info
        if self.settings.get('include_student_info', True):
            c.setFont("Helvetica", 10)
            name = self.settings.get('student_name', '') or "_________________________"
            student_id = self.settings.get('student_id', '') or "_________________________"
            dept = self.settings.get('department', '') or "_________________________"
            
            total_width = width - (margin * 2)
            col_width_student = total_width // 3
            
            c.drawString(margin, y, f"Name: {name}")
            c.drawString(margin + col_width_student, y, f"ID: {student_id}")
            c.drawString(margin + (col_width_student * 2), y, f"Dept: {dept}")
            y -= 40

        y -= 15
        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Write your answers below:")
        y -= line_height
        c.setFont("Helvetica", base_font_size)
        
        # Two column layout
        self._draw_questions_two_column(c, margin, col_gap, col_width, line_height,
                                        small_line_height, width, height, y, base_font_size)
        
        c.save()
    
    def _draw_questions_two_column(self, c, margin, col_gap, col_width, line_height,
                                   small_line_height, width, height, start_y, base_font_size):
        """두 컬럼으로 답안지 질문 그리기"""
        left_x = margin
        right_x = margin + col_width + col_gap
        
        # 높이 계산
        question_heights = [self._calculate_question_height(q, col_width, line_height, small_line_height) 
                           for q in self.questions]
        
        # 컬럼 분할
        left_indices, right_indices = self._split_questions(question_heights, height - margin - 100)
        
        # 왼쪽 컬럼 그리기
        current_y = start_y
        for idx in left_indices:
            if current_y < margin + 50:
                c.showPage()
                current_y = height - margin
                c.setFont("Helvetica", base_font_size)
            
            current_y = self._draw_single_question(
                c, self.questions[idx], left_x, current_y, col_width,
                line_height, small_line_height, base_font_size
            )
            current_y -= small_line_height
        
        # 오른쪽 컬럼 그리기
        current_y = start_y
        for idx in right_indices:
            if current_y < margin + 50:
                c.showPage()
                current_y = height - margin
                c.setFont("Helvetica", base_font_size)
            
            current_y = self._draw_single_question(
                c, self.questions[idx], right_x, current_y, col_width,
                line_height, small_line_height, base_font_size
            )
            current_y -= small_line_height
    
    def _split_questions(self, heights, page_height):
        """질문을 두 컬럼으로 분할"""
        left_indices = []
        right_indices = []
        current_height = 0
        
        for idx, q_height in enumerate(heights):
            if current_height + q_height <= page_height:
                left_indices.append(idx)
                current_height += q_height + 5
            else:
                right_indices.append(idx)
        
        return left_indices, right_indices
    
    def _calculate_question_height(self, q, col_width, line_height, small_line_height):
        """질문 높이 계산"""
        qtype = q["type"]
        total_height = line_height
        
        if qtype == 0:  # Multiple Choice
            total_height += small_line_height + 5
        elif qtype == 1:  # True/False
            total_height += 0
        elif qtype == 2:  # Fill in the Blank
            total_height += 0
        elif qtype == 3:  # Short Answer
            total_height += 0
        elif qtype == 4:  # Essay
            essay_lines = min(self.settings.get('essay_lines', 6), 6)
            total_height += int(line_height * 0.7) + essay_lines * line_height + 5
        elif qtype == 5:  # Matching
            pairs = q.get("matching_pairs", [])
            total_height += line_height + ((len(pairs) + 3) // 4) * small_line_height
        elif qtype == 6:  # Ordering
            total_height += 0
        elif qtype == 7:  # Code
            total_height += line_height
            answer_key = q.get('answer', '')
            code_lines = max(3, len(answer_key.split('\n')) + 2) if answer_key else 5
            code_height = min(code_lines * 15, 250)
            total_height += code_height + 10
        elif qtype == 8:  # Calculation
            total_height += line_height + line_height * 3 + small_line_height
        
        return total_height
    
    def _draw_single_question(self, c, q, x, y, col_width, line_height, small_line_height, base_font_size):
        """단일 답안지 질문 그리기"""
        c.setFont("Helvetica", base_font_size)
        qtype = q["type"]
        
        if qtype == 0:  # Multiple Choice
            choices = q.get("choices", [])
            c.drawString(x, y, f"Q{q['id']}.")
            line_text = "       " + "".join(f"  [{chr(97+i)}]" for i in range(len(choices)))
            c.drawString(x, y, line_text)
            y -= line_height + 5
        
        elif qtype == 1:  # True/False
            c.drawString(x, y, f"Q{q['id']}.   [a]    [b]")
            y -= line_height
        
        elif qtype == 2:  # Fill in the Blank
            blank_count = len(q.get("blanks", [])) or 3
            blanks = " ______ " * blank_count
            c.drawString(x, y, f"Q{q['id']}.   {blanks}")
            y -= line_height
        
        elif qtype == 3:  # Short Answer
            c.drawString(x, y, f"Q{q['id']}.   ____________________")
            y -= line_height
        
        elif qtype == 4:  # Essay
            c.setFont("Helvetica", base_font_size)
            c.drawString(x, y, f"Q{q['id']}.")
            y -= int(line_height * 0.7)
            essay_lines = min(self.settings.get('essay_lines', 6), 6)
            for _ in range(essay_lines):
                c.line(x, y, x + col_width - 10, y)
                y -= line_height
            y -= 5
        
        elif qtype == 5:  # Matching
            pairs = q.get("matching_pairs", [])
            c.drawString(x, y, f"Q{q['id']}.   Matching (Example: 1→a, 2→b):")
            y -= line_height
            match_line = ""
            for i in range(len(pairs)):
                match_line += f"{i+1}→___  "
                if (i + 1) % 4 == 0 and i + 1 < len(pairs):
                    c.drawString(x + 25, y, match_line)
                    match_line = ""
                    y -= small_line_height
            if match_line:
                c.drawString(x + 25, y, match_line)
            y -= small_line_height
        
        elif qtype == 6:  # Ordering
            items = q.get("ordering_items", [])
            if items:
                blank_placeholders = ", ".join(["___"] * len(items))
                c.drawString(x, y, f"Q{q['id']}.   Correct order: {blank_placeholders}")
            else:
                c.drawString(x, y, f"Q{q['id']}.   Order: ___ , ___ , ___")
            y -= line_height
        
        elif qtype == 7:  # Code
            c.setFont("Helvetica", base_font_size)
            c.drawString(x, y, f"Q{q['id']}. Write your code below:")
            y -= line_height
            
            answer_key = q.get('answer', '')
            code_lines = max(3, len(answer_key.split('\n')) + 2) if answer_key else 5
            line_spacing = 14
            code_height = min(code_lines * line_spacing + 10, 250)
            
            rect_x = x
            rect_y = y - code_height
            rect_width = col_width - 10
            rect_height = code_height
            
            c.rect(rect_x, rect_y, rect_width, rect_height)
            
            c.setFont("Helvetica", 7)
            top_y = rect_y + rect_height
            for i in range(1, min(code_lines + 1, 16)):
                line_y = top_y - (i * line_spacing) + 5
                if line_y > rect_y + 5:
                    c.drawString(rect_x + 5, line_y, f"{i}.")
            
            y = rect_y - 10
            c.setFont("Helvetica", base_font_size)
        
        elif qtype == 8:  # Calculation
            c.drawString(x, y, f"Q{q['id']}. Work:")
            y -= line_height
            for _ in range(3):
                c.line(x, y, x + col_width - 10, y)
                y -= line_height
            y -= small_line_height
            c.drawString(x, y, "Answer: ")
            c.line(x + 45, y, x + col_width - 10, y)
            y -= small_line_height
        
        else:
            c.drawString(x, y, f"Q{q['id']}.   ____________________")
            y -= line_height
        
        return y