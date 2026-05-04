# exam_generator/pdf_engine.py
import json
import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.colors import black
from reportlab.lib.pagesizes import A4

from common.constants import PAGE_SIZES
from common.utils import generate_qr, wrap_text


class PDFEngine:
    """시험지 PDF 생성 엔진"""
    
    def __init__(self, questions, settings):
        self.questions = questions
        self.settings = settings
    
    def generate_exam_pdf(self, file_path, is_preview=False):
        """시험지 PDF 생성"""
        exam_title = self.settings.get('exam_title', 'Untitled Exam') or "Untitled Exam"
        exam_date = self.settings.get('exam_date', '') or datetime.now().strftime("%B %d, %Y")
        
        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size

        margin_top = 25 * mm
        margin_left = 20 * mm
        margin_right = 20 * mm
        
        available_width = width - margin_left - margin_right
        
        line_height = int(self.settings.get('line_spacing', 1.5) * self.settings.get('font_size', 11))
        layout_style = self.settings.get('layout_style', 'Two Column')
        font_size = self.settings.get('font_size', 11)
        title_font_size = self.settings.get('title_font_size', 18)
        
        # ===== Header =====
        current_y = height - margin_top
        
        c.setFont("Helvetica-Bold", title_font_size)
        c.drawCentredString(width/2, current_y, exam_title)
        current_y -= 22
        
        c.setFont("Helvetica", 10)
        total_points = sum(q.get('score', 0) for q in self.questions)
        
        if self.settings.get('show_qr', True):
            qr_data = json.dumps({
                "exam": exam_title,
                "date": exam_date,
                "questions": len(self.questions),
                "total_score": total_points
            })
            qr_path = generate_qr(qr_data, f"qr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
            c.drawImage(qr_path, margin_left, current_y - 15, width=35, height=35)
            if os.path.exists(qr_path):
                os.remove(qr_path)
            c.drawRightString(width - margin_right, current_y, f"Total: {total_points} pts")
        else:
            c.drawRightString(width - margin_right, current_y, f"Total: {total_points} pts")
        
        current_y -= 18
        
        instruction = self.settings.get('exam_instruction', '')
        if instruction:
            c.setFont("Helvetica-Oblique", 9)
            instruction_lines = wrap_text(instruction, available_width - 20, 9)
            for line in instruction_lines:
                c.drawString(margin_left, current_y, f"※ {line}")
                current_y -= line_height - 4
            current_y -= 8
        
        c.line(margin_left, current_y, width - margin_right, current_y)
        current_y -= 15
        
        # ===== Question Area =====
        if layout_style == "Two Column":
            self._draw_questions_two_column(c, margin_left, margin_right, width, height,
                                            line_height, font_size, available_width, current_y)
        else:
            self._draw_questions_standard(c, margin_left, margin_right, width, height,
                                          line_height, font_size, available_width, current_y)
        
        c.save()
    
    def _draw_questions_standard(self, c, margin_left, margin_right, width, height,
                                 line_height, font_size, available_width, start_y):
        """단일 컬럼으로 질문 그리기"""
        current_y = start_y
        page_bottom_margin = 0
        
        for q in self.questions:
            needed_height = self._estimate_question_height(q, line_height, font_size, available_width)
            
            if current_y - needed_height < page_bottom_margin:
                c.showPage()
                current_y = height - 80
                c.setFont("Helvetica", font_size)
            
            current_y = self._draw_single_question_standard(
                c, q, margin_left, current_y, line_height, font_size, available_width
            )
            
            current_y -= line_height
            c.line(margin_left, current_y + 10, width - margin_right, current_y + 10)
            current_y -= 10
    
    def _draw_single_question_standard(self, c, q, x, y, line_height, font_size, available_width):
        """단일 질문 그리기"""
        current_y = y
        
        numbering = self.settings.get('numbering_style', '1, 2, 3...')
        if numbering == "1), 2), 3)...":
            q_prefix = f"{q['id']})"
        elif numbering == "(1), (2), (3)...":
            q_prefix = f"({q['id']})"
        elif numbering == "A, B, C...":
            q_prefix = chr(64 + min(q['id'], 26))
        else:
            q_prefix = f"Q{q['id']}"
        
        points_text = f" ({q['score']} pts)" if self.settings.get('show_points', True) else ""
        full_question_text = f"{q_prefix}. {q['text']}{points_text}"
        
        c.setFont("Helvetica-Bold", font_size)
        question_lines = wrap_text(full_question_text, available_width - 20, font_size)
        
        for line in question_lines:
            c.drawString(x, current_y, line)
            current_y -= line_height
        
        current_y -= 5
        c.setFont("Helvetica", font_size - 1)
        
        current_y = self._draw_question_content(c, q, x, current_y, line_height, font_size, available_width)
        
        return current_y
    
    def _draw_question_content(self, c, q, margin_left, current_y, line_height, font_size, available_width):
        """Display question content on exam paper (no answer spaces)"""
        
        if q["type"] == 0:  # Multiple Choice
            for i, choice in enumerate(q.get("choices", []), 1):
                choice_display = choice[:70] + "..." if len(choice) > 70 else choice
                c.drawString(margin_left + 10, current_y, f"   {chr(96+i)}. {choice_display}")
                current_y -= line_height - 4
        
        elif q["type"] == 1:  # True/False
            c.drawString(margin_left + 10, current_y, f"   a. True")
            current_y -= line_height - 4
            c.drawString(margin_left + 10, current_y, f"   b. False")
        
        elif q["type"] == 2:  # Fill in the Blank
            pass
        
        elif q["type"] == 3:  # Short Answer
            pass
        
        elif q["type"] == 4:  # Essay
            c.drawString(margin_left + 10, current_y, "[Essay question - answer on separate paper]")
            current_y -= line_height
        
        elif q["type"] == 5:  # Matching
            pairs = q.get("matching_pairs", [])[:8]
            if pairs:
                max_left_len = 0
                for left, right in pairs:
                    left_len = len(left[:30])
                    max_left_len = max(max_left_len, left_len)
                
                left_col_width = min(max_left_len * 4 + 20, available_width // 2)
                right_col_x = margin_left + left_col_width + 30
                
                c.setFont("Helvetica", font_size - 1)
                
                for i, (left, right) in enumerate(pairs):
                    left_display = left[:35] + "..." if len(left) > 35 else left
                    right_display = right[:35] + "..." if len(right) > 35 else right
                    
                    c.drawString(margin_left + 20, current_y, f"{i+1}. {left_display}")
                    c.drawString(right_col_x, current_y, f"{chr(97+i)}. {right_display}")
                    current_y -= line_height - 2
            else:
                c.drawString(margin_left + 10, current_y, "Match the following:")
        
        elif q["type"] == 6:  # Ordering
            items = q.get("ordering_items", [])
            if items:
                c.drawString(margin_left + 10, current_y, "Arrange in correct order:")
                current_y -= line_height
                for i, item in enumerate(items, 1):
                    item_display = item[:50] + "..." if len(item) > 50 else item
                    c.drawString(margin_left + 20, current_y, f"   {i}. {item_display}")
                    current_y -= line_height - 4
            else:
                c.drawString(margin_left + 10, current_y, "Arrange in correct order:")
        
        elif q["type"] == 7:  # Code
            c.drawString(margin_left + 10, current_y, "Write your code below:")
            current_y -= line_height * 2
            code_height = 50
            c.rect(margin_left + 10, current_y - code_height, available_width - 30, code_height)
        
        elif q["type"] == 8:  # Calculation
            pass
        
        return current_y
    
    def _draw_questions_two_column(self, c, margin_left, margin_right, width, height,
                                   line_height, font_size, available_width, start_y):
        """두 컬럼으로 질문 그리기"""
        col_gap = 15
        col_width = (available_width - col_gap) // 2
        
        left_col_x = margin_left
        right_col_x = margin_left + col_width + col_gap
        page_bottom_margin = 25
        
        current_y = start_y
        q_index = 0
        total_questions = len(self.questions)
        
        while q_index < total_questions:
            if q_index > 0:
                c.showPage()
                current_y = height - 35
            
            left_y = current_y
            left_q_indices = []
            temp_index = q_index
            
            while temp_index < total_questions:
                q = self.questions[temp_index]
                q_height = self._estimate_question_height_two_col(q, line_height, font_size, col_width) + 15
                if left_y - q_height > page_bottom_margin:
                    left_q_indices.append(temp_index)
                    left_y -= q_height
                    temp_index += 1
                else:
                    break
            
            right_q_indices = []
            right_y = current_y
            temp_index2 = temp_index
            
            while temp_index2 < total_questions:
                q = self.questions[temp_index2]
                q_height = self._estimate_question_height_two_col(q, line_height, font_size, col_width) + 15
                if right_y - q_height > page_bottom_margin:
                    right_q_indices.append(temp_index2)
                    right_y -= q_height
                    temp_index2 += 1
                else:
                    break
            
            if left_q_indices:
                y_pos = current_y
                for idx in left_q_indices:
                    q = self.questions[idx]
                    y_pos = self._draw_single_question_two_col(
                        c, q, left_col_x, y_pos, line_height, font_size, col_width, idx + 1
                    )
                    y_pos -= 25
                    if idx != left_q_indices[-1]:
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.setLineWidth(0.5)
                        c.line(left_col_x, y_pos + 12, left_col_x + col_width, y_pos + 12)
                        c.setStrokeColor(black)
            
            if right_q_indices:
                y_pos = current_y
                for idx in right_q_indices:
                    q = self.questions[idx]
                    y_pos = self._draw_single_question_two_col(
                        c, q, right_col_x, y_pos, line_height, font_size, col_width, idx + 1
                    )
                    y_pos -= 25
                    if idx != right_q_indices[-1]:
                        c.setStrokeColorRGB(0.8, 0.8, 0.8)
                        c.setLineWidth(0.5)
                        c.line(right_col_x, y_pos + 12, right_col_x + col_width, y_pos + 12)
                        c.setStrokeColor(black)
            
            if right_q_indices:
                q_index = right_q_indices[-1] + 1
            elif left_q_indices:
                q_index = left_q_indices[-1] + 1
            else:
                q_index = temp_index if temp_index > q_index else q_index + 1
    
    def _draw_single_question_two_col(self, c, q, x, y, line_height, font_size, col_width, q_num):
        """두 컬럼에서 단일 질문 그리기"""
        current_y = y
        
        numbering = self.settings.get('numbering_style', '1, 2, 3...')
        if numbering == "1), 2), 3)...":
            q_prefix = f"{q_num})"
        elif numbering == "(1), (2), (3)...":
            q_prefix = f"({q_num})"
        elif numbering == "A, B, C...":
            q_prefix = chr(64 + min(q_num, 26))
        else:
            q_prefix = f"{q_num}."
        
        points_text = f" [{q['score']} pts]" if self.settings.get('show_points', True) else ""
        full_text = f"{q_prefix} {q['text']}{points_text}"
        
        c.setFont("Helvetica-Bold", font_size - 1)
        text_lines = wrap_text(full_text, col_width - 10, font_size - 1)
        
        for idx, line in enumerate(text_lines):
            if idx == 0:
                c.drawString(x, current_y, line)
            else:
                indent = " " * (len(str(q_prefix)) + 1)
                c.drawString(x, current_y, f"{indent}{line}")
            current_y -= line_height
        
        current_y -= 6
        c.setFont("Helvetica", font_size - 2)
        current_y = self._draw_question_content_two_col(c, q, x, current_y, line_height, font_size, col_width)
        
        return current_y
    
    def _draw_question_content_two_col(self, c, q, x, current_y, line_height, font_size, col_width):
        """두 컬럼에서 질문 내용 그리기"""
        
        if q["type"] == 0:  # Multiple Choice
            c.setFont("Helvetica", font_size - 2)
            for i, choice in enumerate(q.get("choices", [])[:5], 1):
                choice_display = choice[:30] + "..." if len(choice) > 30 else choice
                c.drawString(x + 8, current_y, f"   {chr(96+i)}. {choice_display}")
                current_y -= line_height - 2
        
        elif q["type"] == 1:  # True/False
            c.drawString(x + 8, current_y, f"   a. True")
            current_y -= line_height - 2
            c.drawString(x + 8, current_y, f"   b. False")
            current_y -= 5
        
        elif q["type"] == 2:  # Fill in the Blank
            pass
        
        elif q["type"] == 3:  # Short Answer
            pass
        
        elif q["type"] == 4:  # Essay
            pass
        
        elif q["type"] == 5:  # Matching
            pairs = q.get("matching_pairs", [])[:5]
            if pairs:
                left_items = []
                right_items = []
                for i, (left, right) in enumerate(pairs):
                    left_display = left[:18] + ".." if len(left) > 18 else left
                    right_display = right[:18] + ".." if len(right) > 18 else right
                    left_items.append(f"{i+1}. {left_display}")
                    right_items.append(f"{chr(97+i)}. {right_display}")
                
                max_left_width = 0
                for item in left_items:
                    item_width = c.stringWidth(item, "Helvetica", font_size - 2)
                    max_left_width = max(max_left_width, item_width)
                
                c.setFont("Helvetica", font_size - 2)
                right_col_x = x + max_left_width + 25
                
                for i in range(max(len(left_items), len(right_items))):
                    if i < len(left_items):
                        c.drawString(x + 15, current_y, left_items[i])
                    if i < len(right_items):
                        c.drawString(right_col_x, current_y, right_items[i])
                    current_y -= line_height - 2
            else:
                c.drawString(x + 8, current_y, "Match:")
        
        elif q["type"] == 6:  # Ordering
            items = q.get("ordering_items", [])
            if items:
                c.drawString(x + 8, current_y, "Order:")
                current_y -= line_height
                for i, item in enumerate(items, 1):
                    item_display = item[:25] + "..." if len(item) > 25 else item
                    c.drawString(x + 14, current_y, f"{i}. {item_display}")
                    current_y -= line_height - 2
            current_y -= 5
        
        elif q["type"] == 7:  # Code
            pass
        
        elif q["type"] == 8:  # Calculation
            pass
        
        return current_y
    
    def _estimate_question_height(self, q, line_height, font_size, available_width):
        """질문 높이 추정 (단일 컬럼)"""
        total_height = 0
        
        question_text = q['text']
        approx_chars_per_line = int(available_width / (font_size * 0.6))
        question_lines = max(1, (len(question_text) // approx_chars_per_line) + 1)
        total_height += question_lines * line_height + 10
        
        if q["type"] == 0:
            choices_count = len(q.get("choices", []))
            total_height += choices_count * (line_height - 4) + 20
        elif q["type"] == 1:
            total_height += line_height
        elif q["type"] == 2:
            total_height += line_height
        elif q["type"] == 3:
            total_height += line_height
        elif q["type"] == 4:
            total_height += self.settings.get('essay_lines', 4) * line_height
        elif q["type"] == 5:
            pairs_count = len(q.get("matching_pairs", []))
            total_height += max(3, pairs_count) * (line_height - 4)
        elif q["type"] == 6:
            total_height += line_height
        elif q["type"] == 7:
            total_height += 60
        elif q["type"] == 8:
            total_height += line_height * 2
        
        return total_height + 30
    
    def _estimate_question_height_two_col(self, q, line_height, font_size, col_width):
        """질문 높이 추정 (두 컬럼)"""
        total_height = 20
        
        question_text = q['text']
        chars_per_line = max(10, int(col_width / (font_size * 0.55)))
        question_lines = max(1, (len(question_text) // chars_per_line) + 1)
        total_height += question_lines * (line_height + 2)
        
        if q["type"] == 0:
            choices_count = min(len(q.get("choices", [])), 5)
            total_height += choices_count * (line_height - 2) + 10
        elif q["type"] == 1:
            total_height += (line_height - 2) * 2
        elif q["type"] == 2:
            total_height += line_height - 2
        elif q["type"] == 3:
            total_height += 5
        elif q["type"] == 4:
            total_height += 20
        elif q["type"] == 5:
            pairs_count = min(len(q.get("matching_pairs", [])), 4)
            total_height += max(2, pairs_count) * (line_height - 2) + 20
        elif q["type"] == 6:
            items_count = min(len(q.get("ordering_items", [])), 4)
            total_height += items_count * (line_height - 2) + 15
        elif q["type"] == 7:
            total_height += 45
        elif q["type"] == 8:
            total_height += (line_height - 2) * 3 + 10
        
        return total_height