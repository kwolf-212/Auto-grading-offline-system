# exam_grader/answer_parser.py
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

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


@dataclass
class ParsedAnswer:
    """파싱된 답안 정보"""
    question_id: int
    answer: str
    confidence: float = 1.0
    raw_text: str = ""


class AnswerParser:
    """답안 파싱 엔진 - 이미지/PDF에서 답안 추출"""
    
    def __init__(self, exam_data: Dict = None):
        """
        Args:
            exam_data: 시험 데이터 (질문 수, 유형 정보 등)
        """
        self.exam_data = exam_data or {}
        self.total_questions = len(self.exam_data.get('answers', []))
        
        # 답안 패턴
        self.answer_patterns = [
            # 1. A 또는 1) A 형태
            re.compile(r'^(\d+)[\.\):]\s*([A-Za-z]|True|False|○|×|✓|✗)', re.IGNORECASE),
            # 2. Q1. A 또는 Q1: A 형태
            re.compile(r'^Q\.?(\d+)[\.\):]\s*([A-Za-z]|True|False)', re.IGNORECASE),
            # 3. 문제1. A 형태 (한글)
            re.compile(r'^문제\s*(\d+)[\.\):]\s*([A-Za-z]|True|False)', re.IGNORECASE),
            # 4. 1번: A 형태 (한글)
            re.compile(r'^(\d+)번[\.\):]\s*([A-Za-z]|True|False)', re.IGNORECASE),
            # 5. 답: 1-A 형태
            re.compile(r'^답\s*:?\s*(\d+)[-\.]?\s*([A-Za-z])', re.IGNORECASE),
            # 6. 1) (A) 형태
            re.compile(r'^(\d+)\)\s*\(?([A-Za-z])\)?', re.IGNORECASE),
        ]
        
        # 한글/특수문자 매핑
        self.korean_mapping = {
            '가': 'A', '나': 'B', '다': 'C', '라': 'D', '마': 'E',
            '①': 'A', '②': 'B', '③': 'C', '④': 'D', '⑤': 'E',
            '1': 'A', '2': 'B', '3': 'C', '4': 'D', '5': 'E',
            '○': 'O', '×': 'X', '✓': 'O', '✗': 'X',
            'True': 'T', 'False': 'F', 'true': 'T', 'false': 'F',
        }
    
    def parse_from_image(self, image_path: str, preprocess: bool = True) -> Dict[int, str]:
        """
        이미지에서 답안 추출
        
        Args:
            image_path: 이미지 파일 경로
            preprocess: 전처리 수행 여부
        
        Returns:
            question_id -> answer 매핑
        """
        if not TESSERACT_AVAILABLE:
            raise ImportError(
                "Pillow and pytesseract are required for OCR.\n"
                "Install with: pip install Pillow pytesseract\n"
                "Also install Tesseract OCR engine from: https://github.com/tesseract-ocr/tesseract"
            )
        
        try:
            # 이미지 로드
            image = Image.open(image_path)
            
            # 이미지 전처리
            if preprocess:
                image = self._preprocess_image(image)
            
            # OCR 수행
            # 여러 언어 지원 (영어 + 한국어)
            text = pytesseract.image_to_string(image, lang='eng+kor')
            
            # 답안 파싱
            answers = self._parse_answers_from_text(text)
            
            return answers
            
        except Exception as e:
            raise Exception(f"Failed to parse image: {str(e)}")
    
    def parse_from_pdf(self, pdf_path: str, page_num: int = 0) -> Dict[int, str]:
        """
        PDF에서 답안 추출
        
        Args:
            pdf_path: PDF 파일 경로
            page_num: 페이지 번호 (0부터 시작)
        
        Returns:
            question_id -> answer 매핑
        """
        if not PYMUPDF_AVAILABLE:
            raise ImportError(
                "PyMuPDF is required for PDF parsing.\n"
                "Install with: pip install PyMuPDF"
            )
        
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
    
    def parse_from_text(self, text: str) -> Dict[int, str]:
        """
        텍스트에서 답안 추출
        
        Args:
            text: 텍스트 문자열
        
        Returns:
            question_id -> answer 매핑
        """
        return self._parse_answers_from_text(text)
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        이미지 전처리 (OCR 정확도 향상)
        
        Args:
            image: PIL Image 객체
        
        Returns:
            전처리된 이미지
        """
        # Grayscale 변환
        if image.mode != 'L':
            image = image.convert('L')
        
        # 대비 향상
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        
        # 이진화 (threshold)
        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0)
        
        return image
    
    def _parse_answers_from_text(self, text: str) -> Dict[int, str]:
        """
        텍스트에서 답안 파싱
        
        Args:
            text: OCR 또는 추출된 텍스트
        
        Returns:
            question_id -> answer 매핑
        """
        answers = {}
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 각 패턴에 대해 매칭 시도
            for pattern in self.answer_patterns:
                match = pattern.match(line)
                if match:
                    qid = int(match.group(1))
                    raw_answer = match.group(2).strip()
                    answer = self._normalize_answer(raw_answer)
                    
                    if answer:
                        answers[qid] = answer
                    break
        
        # 빈 칸 형태의 답안도 찾기 (예: "1. ___" 형태)
        blank_pattern = re.compile(r'(\d+)[\.\):]\s*[\[(]?\s*[\)\]]?\s*$')
        for line in lines:
            match = blank_pattern.match(line.strip())
            if match:
                qid = int(match.group(1))
                if qid not in answers:
                    answers[qid] = ""  # 빈 답안
        
        return answers
    
    def _normalize_answer(self, answer: str) -> str:
        """
        답안 정규화
        
        Args:
            answer: 원본 답안 문자열
        
        Returns:
            정규화된 답안
        """
        answer = answer.strip().upper()
        
        # 한글/특수문자 매핑
        if answer in self.korean_mapping:
            return self.korean_mapping[answer]
        
        # 길이가 1인 알파벳
        if len(answer) == 1 and answer.isalpha():
            return answer
        
        # True/False 처리
        if answer in ['TRUE', 'T']:
            return 'T'
        if answer in ['FALSE', 'F']:
            return 'F'
        
        return answer
    
    def parse_batch(self, file_paths: List[str]) -> List[Dict[int, str]]:
        """
        여러 파일 배치 파싱
        
        Args:
            file_paths: 파일 경로 리스트
        
        Returns:
            각 파일의 답안 매핑 리스트
        """
        results = []
        for file_path in file_paths:
            ext = os.path.splitext(file_path)[1].lower()
            
            if ext == '.pdf':
                answers = self.parse_from_pdf(file_path)
            elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']:
                answers = self.parse_from_image(file_path)
            else:
                continue
            
            results.append(answers)
        
        return results


class AnswerValidator:
    """답안 검증 엔진"""
    
    def __init__(self, exam_data: Dict):
        self.exam_data = exam_data
        self.answers_key = exam_data.get('answers', [])
        
        # 정답 정보 구축
        self.correct_answers = {}
        self.answer_types = {}
        for q in self.answers_key:
            qid = q.get('question_id')
            if qid:
                self.correct_answers[qid] = q.get('expected_answer', q.get('answer', '')).strip().upper()
                self.answer_types[qid] = q.get('question_type', 'unknown')
    
    def validate_answer(self, qid: int, student_answer: str) -> Tuple[bool, float]:
        """
        단일 답안 검증
        
        Args:
            qid: 문제 ID
            student_answer: 학생 답안
        
        Returns:
            (정답 여부, 신뢰도)
        """
        correct = self.correct_answers.get(qid, '')
        if not correct:
            return False, 0.0
        
        student_norm = self._normalize(student_answer)
        correct_norm = self._normalize(correct)
        
        # 정확히 일치
        if student_norm == correct_norm:
            return True, 1.0
        
        # 부분 일치 (단답형)
        if self.answer_types.get(qid) in ['short_answer', 'fill_blank']:
            if student_norm in correct_norm or correct_norm in student_norm:
                return True, 0.7
        
        # 동의어 처리 (선택적)
        if self._is_synonym(student_norm, correct_norm):
            return True, 0.9
        
        return False, 0.0
    
    def _normalize(self, answer: str) -> str:
        """답안 정규화"""
        if not answer:
            return ""
        
        answer = answer.strip().upper()
        
        # 공백 제거
        answer = ' '.join(answer.split())
        
        # 특수문자 제거
        answer = re.sub(r'[^\w\s]', '', answer)
        
        return answer
    
    def _is_synonym(self, student: str, correct: str) -> bool:
        """동의어 확인 (확장 가능)"""
        synonyms = {
            'YES': ['Y', 'O', '○', 'TRUE'],
            'NO': ['N', 'X', '×', 'FALSE'],
            'TRUE': ['T', 'YES', 'O', '○'],
            'FALSE': ['F', 'NO', 'X', '×'],
        }
        
        for key, values in synonyms.items():
            if correct == key and student in values:
                return True
            if student == key and correct in values:
                return True
        
        return False