# exam_generator/answer_sheet_engine.py
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import black

from common.constants import PAGE_SIZES


class AnswerSheetEngine:
    """답안지 PDF 생성 엔진 - 위치 저장 기능 포함"""
    
    def __init__(self, questions, settings):
        self.questions = questions
        self.settings = settings
    
    def generate_answer_sheet(self, file_path, position_callback=None):
        """
        답안지 PDF 생성
        
        Args:
            file_path: 저장할 파일 경로
            position_callback: 위치 정보를 저장할 콜백 함수 (question_id, x, y, page)
        """
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
        
        # Student info - 중앙에 한 줄로
        if self.settings.get('include_student_info', True):
            c.setFont("Helvetica", 10)
            name = self.settings.get('student_name', '') or "_________________________"
            student_id = self.settings.get('student_id', '') or "_________________________"
            dept = self.settings.get('department', '') or "_________________________"
            
            total_width = width - (margin * 2)
            col_width_student = total_width // 3
            
            x1 = margin
            x2 = margin + col_width_student
            x3 = margin + (col_width_student * 2)
            
            c.drawString(x1, y, f"Name: {name}")
            c.drawString(x2, y, f"ID: {student_id}")
            c.drawString(x3, y, f"Dept: {dept}")
            
            y -= 25
        else:
            y -= 15

        y -= 15

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Write your answers below:")
        y -= line_height

        c.setFont("Helvetica", base_font_size)
        
        # Two Column 배치 - 위치 저장 포함
        left_x = margin
        right_x = margin + col_width + col_gap
        
        # 각 질문의 필요 높이 계산
        question_heights = []
        for q in self.questions:
            height_needed = self._calculate_answer_sheet_height(q, col_width, line_height, small_line_height)
            question_heights.append(height_needed)
        
        # 왼쪽 컬럼에 배치할 질문 결정
        left_indices = []
        right_indices = []
        current_height = 0
        page_height = height - margin - 100
        
        for idx, q_height in enumerate(question_heights):
            if current_height + q_height <= page_height:
                left_indices.append(idx)
                current_height += q_height + small_line_height
            else:
                right_indices.append(idx)
        
        # 나머지 질문들을 오른쪽 컬럼에 순차적으로 배치
        all_pages = []
        current_page_indices = []
        current_page_height = 0
        
        for idx in right_indices:
            q_height = question_heights[idx]
            if current_page_height + q_height <= page_height:
                current_page_indices.append(idx)
                current_page_height += q_height + small_line_height
            else:
                if current_page_indices:
                    all_pages.append(current_page_indices)
                current_page_indices = [idx]
                current_page_height = q_height + small_line_height
        
        if current_page_indices:
            all_pages.append(current_page_indices)
        
        current_page = 1
        
        # 첫 페이지: 왼쪽 컬럼 그리기 (위치 저장)
        current_y_left = y
        for idx in left_indices:
            if current_y_left < margin + 50:
                c.showPage()
                current_page += 1
                current_y_left = height - margin
                c.setFont("Helvetica", base_font_size)
            
            # 위치 정보 저장 (왼쪽 컬럼)
            if position_callback:
                q = self.questions[idx]
                y_from_top = height - current_y_left
                position_callback(q['id'], left_x, y_from_top, current_page)
            
            current_y_left = self._draw_answer_sheet_question(
                c, self.questions[idx], left_x, current_y_left, col_width,
                line_height, small_line_height, width, margin, base_font_size
            )
            current_y_left -= small_line_height
        
        # 오른쪽 컬럼: 여러 페이지에 걸쳐 그리기 (위치 저장)
        for page_idx, page_indices in enumerate(all_pages):
            if page_idx > 0:
                c.showPage()
                current_page += 1
            
            current_y_right = y
            for idx in page_indices:
                if current_y_right < margin + 50:
                    c.showPage()
                    current_page += 1
                    current_y_right = height - margin
                    c.setFont("Helvetica", base_font_size)
                
                # 위치 정보 저장 (오른쪽 컬럼)
                if position_callback:
                    q = self.questions[idx]
                    y_from_top = height - current_y_right
                    position_callback(q['id'], right_x, y_from_top, current_page)
                
                current_y_right = self._draw_answer_sheet_question(
                    c, self.questions[idx], right_x, current_y_right, col_width,
                    line_height, small_line_height, width, margin, base_font_size
                )
                current_y_right -= small_line_height

        c.save()
        return current_page
    
    def _calculate_answer_sheet_height(self, q, col_width, line_height, small_line_height):
        """질문이 차지하는 높이 계산"""
        qtype = q["type"]
        total_height = line_height  # 기본 질문 한 줄 높이 (질문 번호 라인)
        
        if qtype == 0:  # Multiple Choice
            total_height += small_line_height  # 체크박스 라인
            total_height += 5  # 여백
        
        elif qtype == 1:  # True/False
            total_height += 0  # 한 줄로 충분
        
        elif qtype == 2:  # Fill in the Blank
            total_height += 0  # 한 줄로 충분
        
        elif qtype == 3:  # Short Answer
            total_height += 0  # 한 줄로 충분
        
        elif qtype == 4:  # Essay
            essay_lines = min(self.settings.get('essay_lines', 6), 6)
            total_height += int(line_height * 0.7)  # 제목과의 간격
            total_height += essay_lines * line_height  # 에세이 라인
            total_height += 5  # 여백
        
        elif qtype == 5:  # Matching
            pairs = q.get("matching_pairs", [])
            total_height += line_height  # "Matching (Example...)" 라인
            lines_needed = (len(pairs) + 3) // 4
            total_height += lines_needed * small_line_height
        
        elif qtype == 6:  # Ordering
            total_height += 0  # 한 줄로 충분
        
        elif qtype == 7:  # Code
            total_height += line_height  # "Q{n}. Write your code below:" 라인
            answer_key = q.get('answer', '')
            if answer_key:
                answer_lines = len(answer_key.split('\n'))
                code_lines = max(3, answer_lines + 2)
            else:
                code_lines = 5
            code_height = min(code_lines * 15, 250)
            total_height += code_height + 10
        
        elif qtype == 8:  # Calculation
            total_height += line_height  # "Q{n}. Work:" 라인
            total_height += line_height * 3  # 작업 공간 3줄
            total_height += small_line_height  # Answer 라인 간격
        
        else:
            total_height += 0
        
        return total_height
    
    def _draw_answer_sheet_question(self, c, q, x, y, col_width, line_height, small_line_height, width, margin, base_font_size):
        """단일 답안지 질문 그리기"""
        
        qtype = q["type"]
        
        c.setFont("Helvetica", base_font_size)
        
        if qtype == 0:  # Multiple Choice
            choices = q.get("choices", [])
            c.drawString(x, y, f"Q{q['id']}.")
            line_text = "       " + "".join(f"  [{chr(97+i)}]" for i in range(len(choices)))
            c.drawString(x, y, line_text)
            y -= line_height
            y -= 5
        
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
            for i in range(essay_lines):
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
            if answer_key:
                answer_lines = len(answer_key.split('\n'))
                code_lines = max(3, answer_lines + 2)
            else:
                code_lines = 5
            
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
            for i in range(3):
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