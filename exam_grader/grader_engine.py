# exam_grader/grader_engine.py
import os
import json
import re
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from PIL import Image
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False


class AnswerParser:
    """답안 파싱 클래스 - 텍스트 및 시각적 정보 모두 활용"""
    
    def __init__(self, exam_data: Dict[str, Any]):
        self.exam_data = exam_data
        self.question_ids = [q.get('question_id') for q in exam_data.get('answers', []) if q.get('question_id')]
    
    def parse_from_pdf(self, pdf_path: str) -> Dict[int, str]:
        """PDF에서 답안 추출 (텍스트 + 시각적 정보)"""
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF is required for PDF parsing. Install with: pip install PyMuPDF")
        
        try:
            doc = fitz.open(pdf_path)
            answers = {}
            
            # 각 페이지별로 처리
            for page_num, page in enumerate(doc):
                # 텍스트 추출
                text = page.get_text()
                text_answers = self._parse_answers_from_text(text)
                
                # 시각적 정보 추출 (칠해진 항목)
                visual_answers = self._parse_answers_from_visual(page)
                
                # 병합 (시각적 정보 우선)
                for qid, answer in visual_answers.items():
                    answers[qid] = answer
                for qid, answer in text_answers.items():
                    if qid not in answers:
                        answers[qid] = answer
            
            doc.close()
            return answers
            
        except Exception as e:
            raise Exception(f"Failed to parse PDF: {str(e)}")
    
    def _parse_answers_from_visual(self, page) -> Dict[int, str]:
        """PDF 페이지에서 시각적 정보(칠해진 항목) 분석"""
        answers = {}
        
        # 페이지 확대 (더 정밀한 분석을 위해)
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        
        # PIL Image로 변환
        img_data = pix.tobytes("png")
        from PIL import Image
        import io
        
        img = Image.open(io.BytesIO(img_data))
        
        # 그레이스케일 변환
        gray = img.convert('L')
        
        # 이미지 크기
        width, height = gray.size
        
        # 문제 위치 정보 (JSON에서 제공)
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            position = q.get('position')
            
            if not position or not qid:
                continue
            
            # 페이지 확인 (1-based vs 0-based)
            page_no = position.get('page', 1)
            if page_no != page.number + 1:
                continue
            
            # 좌표 변환 (PDF 좌표 -> 이미지 좌표)
            x = position.get('x', 0) * zoom
            y = position.get('y', 0) * zoom
            
            # 문제 유형에 따라 답안 영역 탐색
            qtype = q.get('question_type', '')
            
            if qtype in ['Multiple Choice', 'True/False']:
                answer = self._detect_filled_option(gray, x, y, width, height, qtype)
                if answer:
                    answers[qid] = answer
        
        return answers
    
    def _detect_filled_option(self, img, x: float, y: float, img_width: int, img_height: int, qtype: str) -> Optional[str]:
        """칠해진 옵션 감지"""
        import numpy as np
        
        # 탐색 영역 설정 (문제 위치 주변)
        search_radius = 200  # 픽셀
        x_start = max(0, int(x - search_radius))
        x_end = min(img_width, int(x + search_radius * 3))
        y_start = max(0, int(y - 50))
        y_end = min(img_height, int(y + 200))
        
        # 관심 영역 추출
        roi = img.crop((x_start, y_start, x_end, y_end))
        
        # 이진화
        import numpy as np
        roi_array = np.array(roi)
        _, binary = cv2.threshold(roi_array, 200, 255, cv2.THRESH_BINARY_INV)
        
        # 윤곽선 찾기
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 옵션 위치 정의 (상대적)
        options = ['a', 'b', 'c', 'd', 'e'] if qtype == 'Multiple Choice' else ['a', 'b']
        
        # 각 옵션 영역의 채움 정도 계산
        option_fill_ratios = {}
        
        for idx, opt in enumerate(options):
            # 옵션의 예상 위치 (ROI 내 상대적)
            opt_x = 50 + idx * 80  # 옵션 간격 약 80픽셀
            opt_y = 50
            
            # 옵션 영역 (30x30 픽셀)
            opt_roi = binary[opt_y:opt_y+40, opt_x:opt_x+40]
            
            if opt_roi.size > 0:
                # 검은 픽셀 비율 (칠해진 정도)
                black_pixels = np.sum(opt_roi > 0)
                total_pixels = opt_roi.size
                fill_ratio = black_pixels / total_pixels if total_pixels > 0 else 0
                option_fill_ratios[opt] = fill_ratio
        
        # 가장 많이 칠해진 옵션 찾기
        if option_fill_ratios:
            best_option = max(option_fill_ratios, key=lambda k: option_fill_ratios[k])
            best_ratio = option_fill_ratios[best_option]
            
            # 15% 이상 칠해진 경우에만 답으로 인정
            if best_ratio > 0.15:
                return best_option.upper()
        
        return None
    
    def _parse_answers_from_text(self, text: str) -> Dict[int, str]:
        """텍스트에서 답안 파싱"""
        answers = {}
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Qn. [a] 패턴 (칠해진 항목은 대괄호 안에 표시될 수 있음)
            bracket_match = re.search(r'Q(\d+)\.\s*\[([a-z])\]', line, re.IGNORECASE)
            if bracket_match:
                qid = int(bracket_match.group(1))
                answers[qid] = bracket_match.group(2).upper()
                continue
            
            # Qn. a 패턴
            q_match = re.search(r'Q(\d+)\.\s*([A-Za-z]+)', line, re.IGNORECASE)
            if q_match:
                qid = int(q_match.group(1))
                answer = q_match.group(2).upper()
                if answer in ['TRUE', 'T']:
                    answers[qid] = 'T'
                elif answer in ['FALSE', 'F']:
                    answers[qid] = 'F'
                else:
                    answers[qid] = answer
                continue
            
            # n. a 패턴
            num_match = re.match(r'^(\d+)[\.\):]\s*([A-Za-z]+)', line)
            if num_match:
                qid = int(num_match.group(1))
                answer = num_match.group(2).upper()
                if answer in ['TRUE', 'T']:
                    answers[qid] = 'T'
                elif answer in ['FALSE', 'F']:
                    answers[qid] = 'F'
                else:
                    answers[qid] = answer
                continue
            
            # Correct order 패턴
            order_match = re.search(r'Correct order:\s*([\d,\s]+)', line, re.IGNORECASE)
            if order_match:
                order_str = order_match.group(1)
                order_items = re.findall(r'\d+', order_str)
                if order_items:
                    for qid in self.question_ids:
                        if qid not in answers and qid >= 20:
                            answers[qid] = ','.join(order_items)
                            break
                continue
            
            # Matching 패턴
            matching_pairs = re.findall(r'(\d+)[→-]([a-z])', line, re.IGNORECASE)
            if matching_pairs:
                matching_str = ';'.join([f"{p[0]}-{p[1].upper()}" for p in matching_pairs])
                for qid in self.question_ids:
                    if qid not in answers and 18 <= qid <= 19:
                        answers[qid] = matching_str
                        break
                continue
            
            # Answer: X 패턴
            ans_match = re.search(r'Answer:\s*([A-Za-z0-9\.\-]+)', line, re.IGNORECASE)
            if ans_match:
                answer = ans_match.group(1).upper()
                for qid in self.question_ids:
                    if qid not in answers:
                        answers[qid] = answer
                        break
        
        # 코드 문제 특수 처리
        code_match = re.search(r'def\s+(\w+)', text, re.IGNORECASE)
        if code_match and 22 not in answers:
            answers[22] = code_match.group(1)
        
        # 계산 문제 특수 처리
        calc_match = re.search(r'Answer:\s*(\d+(?:\.\d+)?)\s*$', text, re.MULTILINE)
        if calc_match and 23 not in answers:
            answers[23] = calc_match.group(1)
        
        return answers


class ScoringEngine:
    """점수 계산 엔진"""
    
    def __init__(self, exam_data: Dict[str, Any]):
        self.exam_data = exam_data
        self.answers_key = self.exam_data.get('answers', [])
        
        # 정답 정보 구축
        self.correct_answers = {}
        self.max_scores = {}
        self.question_types = {}
        
        for q in self.answers_key:
            qid = q.get('question_id')
            if qid:
                expected = q.get('expected_answer', q.get('answer', ''))
                self.correct_answers[qid] = self._normalize_answer(expected)
                self.max_scores[qid] = q.get('score', 0)
                self.question_types[qid] = q.get('question_type', 'unknown')
    
    def _normalize_answer(self, answer: str) -> str:
        """답안 정규화"""
        if not answer:
            return ""
        answer = str(answer).strip().upper()
        
        # 여러 답이 있는 경우 (예: "C, D" 또는 "C;D" 또는 "C,D")
        if ',' in answer or ';' in answer:
            parts = re.split('[,;]', answer)
            return ','.join([p.strip() for p in parts])
        
        # 단일 문자 추출 (예: "C. Python" -> "C")
        if len(answer) > 1 and answer[1] == '.':
            return answer[0]
        
        return answer
    
    def calculate_scores(self, student_answers: Dict[int, str]) -> Dict[int, float]:
        """점수 계산"""
        scores = {}
        
        for qid, correct_answer in self.correct_answers.items():
            student_answer = student_answers.get(qid, '')
            student_answer = self._normalize_answer(student_answer)
            max_score = self.max_scores.get(qid, 0)
            qtype = self.question_types.get(qid, 'unknown')
            
            if not student_answer:
                scores[qid] = 0.0
            else:
                scores[qid] = self._grade_question(qid, student_answer, correct_answer, max_score, qtype)
        
        return scores
    
    def _grade_question(self, qid: int, student: str, correct: str, max_score: int, qtype: str) -> float:
        """개별 문제 채점"""
        
        # Multiple Choice
        if qtype == 'Multiple Choice':
            # 단일 문자 비교
            if len(student) == 1 and len(correct) == 1:
                if student == correct:
                    return float(max_score)
            # 여러 선택 (C,D 형태)
            elif ',' in student:
                student_parts = set(student.split(','))
                correct_parts = set(correct.split(','))
                if student_parts == correct_parts:
                    return float(max_score)
                elif student_parts.intersection(correct_parts):
                    return float(max_score) * 0.5
            # 잘못된 답
            return 0.0
        
        # True/False
        elif qtype == 'True/False':
            t_values = {'T', 'TRUE', 'O', '○', '1'}
            f_values = {'F', 'FALSE', 'X', '×', '0'}
            
            student_bool = student in t_values
            correct_bool = correct in t_values
            
            if student_bool == correct_bool:
                return float(max_score)
            return 0.0
        
        # Fill in the Blank
        elif qtype == 'Fill in the Blank':
            if student == correct:
                return float(max_score)
            if correct in student or student in correct:
                return float(max_score) * 0.7
            return 0.0
        
        # Short Answer
        elif qtype == 'Short Answer':
            if student == correct:
                return float(max_score)
            if correct.lower() in student.lower() or student.lower() in correct.lower():
                return float(max_score) * 0.8
            return 0.0
        
        # Matching
        elif qtype == 'Matching':
            student_pairs = {}
            correct_pairs = {}
            
            for pair in student.split(';'):
                if '-' in pair:
                    k, v = pair.split('-')
                    student_pairs[k.strip()] = v.strip()
            
            for pair in correct.split(';'):
                if '-' in pair:
                    k, v = pair.split('-')
                    correct_pairs[k.strip()] = v.strip()
            
            if not student_pairs:
                return 0.0
            
            matches = sum(1 for k, v in student_pairs.items() 
                         if k in correct_pairs and correct_pairs[k] == v)
            total_pairs = len(correct_pairs)
            
            if total_pairs > 0:
                return float(max_score) * (matches / total_pairs)
            return 0.0
        
        # Ordering
        elif qtype == 'Ordering/Ranking':
            student_order = [x.strip() for x in student.split(',')]
            correct_order = [x.strip() for x in correct.split(',')]
            
            if not student_order:
                return 0.0
            
            if student_order == correct_order:
                return float(max_score)
            
            correct_positions = sum(1 for i, item in enumerate(student_order) 
                                   if i < len(correct_order) and item == correct_order[i])
            if correct_positions > 0:
                return float(max_score) * (correct_positions / len(correct_order))
            return 0.0
        
        # Code Writing
        elif qtype == 'Code Writing':
            keywords = ['def', 'if', 'for', 'while', 'return', 'prime']
            score = 0
            for kw in keywords:
                if kw in student.lower():
                    score += 1
            if score >= 4:
                return float(max_score)
            elif score >= 2:
                return float(max_score) * 0.5
            elif score > 0:
                return float(max_score) * 0.2
            return 0.0
        
        # Calculation
        elif qtype == 'Calculation':
            student_num = re.search(r'(\d+(?:\.\d+)?)', student)
            correct_num = re.search(r'(\d+(?:\.\d+)?)', correct)
            
            if student_num and correct_num:
                if float(student_num.group(1)) == float(correct_num.group(1)):
                    return float(max_score)
            return 0.0
        
        # Essay (수동 채점)
        elif qtype == 'Essay':
            return 0.0
        
        # Default
        else:
            if student == correct:
                return float(max_score)
            return 0.0
    
    def get_max_total_score(self) -> int:
        """최대 총점 반환"""
        return sum(self.max_scores.values())


class ExamGrader:
    """시험 채점 메인 클래스"""
    
    def __init__(self, exam_data: Dict[str, Any]):
        self.exam_data = exam_data
        self.answer_parser = AnswerParser(exam_data)
        self.scoring_engine = ScoringEngine(exam_data)
    
    def grade_exam(self, file_path: str) -> Dict[int, float]:
        """시험 채점 (PDF 또는 이미지)"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            student_answers = self.answer_parser.parse_from_pdf(file_path)
        elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
            student_answers = self.answer_parser.parse_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        scores = self.scoring_engine.calculate_scores(student_answers)
        return scores
    
    def get_total_score(self, scores: Dict[int, float]) -> float:
        return sum(scores.values())
    
    def get_max_score(self) -> int:
        return self.scoring_engine.get_max_total_score()
    
    def get_detailed_report(self, file_path: str) -> Dict[str, Any]:
        """상세 채점 보고서 반환"""
        scores = self.grade_exam(file_path)
        
        report = {
            'file': os.path.basename(file_path),
            'total_score': self.get_total_score(scores),
            'max_score': self.get_max_score(),
            'percentage': (self.get_total_score(scores) / self.get_max_score() * 100) if self.get_max_score() > 0 else 0,
            'question_scores': {},
            'question_details': []
        }
        
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            if qid:
                score = scores.get(qid, 0)
                max_score = q.get('score', 0)
                report['question_scores'][qid] = score
                report['question_details'].append({
                    'id': qid,
                    'type': q.get('question_type'),
                    'score': score,
                    'max_score': max_score,
                    'percentage': (score / max_score * 100) if max_score > 0 else 0
                })
        
        return report


class ResultExporter:
    """결과 내보내기 엔진"""
    
    def __init__(self):
        pass
    
    def export_to_json(self, results: Dict[str, Any], file_path: str) -> None:
        export_data = {
            'exported_at': datetime.now().isoformat(),
            'total_items': len(results.get('results', [])),
            'exam_title': results.get('exam_title', 'Unknown'),
            'results': results.get('results', [])
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def export_to_csv(self, results: Dict[str, Any], file_path: str) -> None:
        import csv
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Filename', 'Total Score', 'Max Score', 'Percentage'])
            for result in results.get('results', []):
                writer.writerow([
                    result.get('filename', 'Unknown'),
                    f"{result.get('total_score', 0):.1f}",
                    result.get('max_score', 0),
                    f"{result.get('percentage', 0):.1f}%"
                ])
    
    def export_results(self, results: Dict[str, Any], file_path: str) -> None:
        if file_path.endswith('.csv'):
            self.export_to_csv(results, file_path)
        else:
            self.export_to_json(results, file_path)


# OpenCV import (이미지 처리를 위해)
try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("Warning: OpenCV not installed. Visual answer detection will be limited.")