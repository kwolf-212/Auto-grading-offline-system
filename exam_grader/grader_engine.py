# exam_grader/grader_engine.py
import os
import json
from typing import Dict, Any, List, Optional
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
    """답안 파싱 클래스"""
    
    def __init__(self, exam_data: Dict[str, Any]):
        self.exam_data = exam_data
    
    def parse_from_image(self, image_path: str) -> Dict[int, str]:
        """이미지에서 답안 추출"""
        if not TESSERACT_AVAILABLE:
            raise ImportError("Pillow and pytesseract are required for OCR. Install with: pip install Pillow pytesseract")
        
        try:
            # Open image
            image = Image.open(image_path)
            
            # OCR processing
            # TODO: Implement proper OCR with preprocessing
            text = pytesseract.image_to_string(image, lang='eng+kor')
            
            # Parse answers from text
            answers = self._parse_answers_from_text(text)
            return answers
            
        except Exception as e:
            raise Exception(f"Failed to parse image: {str(e)}")
    
    def parse_from_pdf(self, pdf_path: str, page_num: int = 0) -> Dict[int, str]:
        """PDF에서 답안 추출"""
        if not PYMUPDF_AVAILABLE:
            raise ImportError("PyMuPDF is required for PDF parsing. Install with: pip install PyMuPDF")
        
        try:
            doc = fitz.open(pdf_path)
            if page_num >= len(doc):
                page_num = 0
            
            page = doc[page_num]
            text = page.get_text()
            doc.close()
            
            answers = self._parse_answers_from_text(text)
            return answers
            
        except Exception as e:
            raise Exception(f"Failed to parse PDF: {str(e)}")
    
    def _parse_answers_from_text(self, text: str) -> Dict[int, str]:
        """텍스트에서 답안 파싱"""
        answers = {}
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            # Look for patterns like "1. A" or "Q1: B" or "1) C"
            import re
            
            # Pattern: 1. A or 1) A or 1: A
            patterns = [
                r'^(\d+)[\.\):]\s*([A-Za-z]|True|False|[①②③④⑤])',
                r'^Q\.?(\d+)[\.\):]\s*([A-Za-z]|True|False)',
                r'^문제\s*(\d+)[\.\):]\s*([A-Za-z]|True|False)',
            ]
            
            for pattern in patterns:
                match = re.match(pattern, line, re.IGNORECASE)
                if match:
                    qid = int(match.group(1))
                    answer = match.group(2).strip().upper()
                    answers[qid] = answer
                    break
        
        return answers


class ScoringEngine:
    """점수 계산 엔진"""
    
    def __init__(self, exam_data: Dict[str, Any]):
        self.exam_data = exam_data
        self.answers_key = self.exam_data.get('answers', [])
        
        # Build answer lookup
        self.correct_answers = {}
        self.max_scores = {}
        for q in self.answers_key:
            qid = q.get('question_id')
            if qid:
                self.correct_answers[qid] = q.get('expected_answer', q.get('answer', '')).strip().upper()
                self.max_scores[qid] = q.get('score', q.get('points', 0))
    
    def calculate_scores(self, student_answers: Dict[int, str]) -> Dict[int, float]:
        """점수 계산"""
        scores = {}
        
        for qid, correct_answer in self.correct_answers.items():
            student_answer = student_answers.get(qid, '').strip().upper()
            max_score = self.max_scores.get(qid, 0)
            
            if not student_answer:
                scores[qid] = 0.0
            elif self._is_answer_correct(correct_answer, student_answer):
                scores[qid] = float(max_score)
            else:
                # Partial credit logic (simple)
                scores[qid] = 0.0
        
        return scores
    
    def _is_answer_correct(self, correct: str, student: str) -> bool:
        """정답 확인"""
        if not correct or not student:
            return False
        
        # Direct match
        if correct == student:
            return True
        
        # Multiple choice: check if student answer is in correct (e.g., "A" vs "A. Option")
        if len(correct) == 1 and correct.isalpha():
            if student.startswith(correct):
                return True
        
        # True/False variations
        if correct in ['T', 'TRUE'] and student in ['T', 'TRUE', '○', 'O']:
            return True
        if correct in ['F', 'FALSE'] and student in ['F', 'FALSE', '×', 'X']:
            return True
        
        return False
    
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
        """시험 채점 (이미지 또는 PDF)"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # Parse answers based on file type
        if file_ext in ['.pdf']:
            student_answers = self.answer_parser.parse_from_pdf(file_path)
        elif file_ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
            student_answers = self.answer_parser.parse_from_image(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
        
        # Calculate scores
        scores = self.scoring_engine.calculate_scores(student_answers)
        
        return scores
    
    def get_total_score(self, scores: Dict[int, float]) -> float:
        """총점 계산"""
        return sum(scores.values())
    
    def get_max_score(self) -> int:
        """최대 점수 반환"""
        return self.scoring_engine.get_max_total_score()


class ResultExporter:
    """결과 내보내기 엔진"""
    
    def __init__(self):
        pass
    
    def export_to_json(self, results: Dict[str, Any], file_path: str) -> None:
        """JSON으로 내보내기"""
        export_data = {
            'exported_at': datetime.now().isoformat(),
            'total_images': len(results.get('results', [])),
            'exam_title': results.get('exam_title', 'Unknown'),
            'results': results.get('results', [])
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
    
    def export_to_csv(self, results: Dict[str, Any], file_path: str) -> None:
        """CSV로 내보내기"""
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
        """파일 형식에 따라 내보내기"""
        if file_path.endswith('.csv'):
            self.export_to_csv(results, file_path)
        else:
            self.export_to_json(results, file_path)