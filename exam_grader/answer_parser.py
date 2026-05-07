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
            
            # ===== 패턴 1: Qn. [a] (가장 중요! 객관식/TrueFalse 모두 이 패턴 사용) =====
            bracket_match = re.search(r'Q(\d+)\.\s*\[([a-z])\]', line, re.IGNORECASE)
            if bracket_match:
                qid = int(bracket_match.group(1))
                answers[qid] = bracket_match.group(2).lower()  # 'a', 'b', 'c'...
                continue
            
            # ===== 패턴 2: Qn. a =====
            q_match = re.search(r'Q(\d+)\.\s*([A-Za-z]+)', line, re.IGNORECASE)
            if q_match:
                qid = int(q_match.group(1))
                answer = q_match.group(2).lower()
                # True/False 문제인 경우 a/b로 변환
                if answer in ['true', 't', 'o', '○']:
                    answers[qid] = 'a'
                elif answer in ['false', 'f', 'x', '×']:
                    answers[qid] = 'b'
                else:
                    answers[qid] = answer.upper()
                continue
            
            # ===== 패턴 3: n. a (숫자. 알파벳) =====
            num_match = re.match(r'^(\d+)[\.\):]\s*([A-Za-z]+)', line)
            if num_match:
                qid = int(num_match.group(1))
                answer = num_match.group(2).lower()
                if answer in ['true', 't', 'o', '○']:
                    answers[qid] = 'a'
                elif answer in ['false', 'f', 'x', '×']:
                    answers[qid] = 'b'
                else:
                    answers[qid] = answer.upper()
                continue
            
            # ===== 패턴 4: Correct order (순서 문제) =====
            order_match = re.search(r'Correct order:\s*([\d,\s]+)', line, re.IGNORECASE)
            if order_match:
                order_str = order_match.group(1)
                order_items = re.findall(r'\d+', order_str)
                if order_items:
                    # 문제 ID를 찾아서 할당 (보통 20, 21번)
                    for qid in self.question_ids:
                        if qid not in answers and qid >= 20:
                            answers[qid] = ','.join(order_items)
                            break
                continue
            
            # ===== 패턴 5: Matching (짝짓기 문제) =====
            matching_pairs = re.findall(r'(\d+)[→-]([a-z])', line, re.IGNORECASE)
            if matching_pairs:
                matching_str = ';'.join([f"{p[0]}-{p[1].upper()}" for p in matching_pairs])
                for qid in self.question_ids:
                    if qid not in answers and 18 <= qid <= 19:
                        answers[qid] = matching_str
                        break
                continue
            
            # ===== 패턴 6: Answer: X (계산 문제 답) =====
            ans_match = re.search(r'Answer:\s*([A-Za-z0-9\.\-]+)', line, re.IGNORECASE)
            if ans_match:
                answer = ans_match.group(1).upper()
                for qid in self.question_ids:
                    if qid not in answers:
                        answers[qid] = answer
                        break
                continue
        
        # ===== 코드 문제 특수 처리 (def 함수명 찾기) =====
        code_match = re.search(r'def\s+(\w+)', text, re.IGNORECASE)
        if code_match and 22 not in answers:
            answers[22] = code_match.group(1)
        
        # ===== 계산 문제 특수 처리 (Answer: 숫자) =====
        calc_match = re.search(r'Answer:\s*(\d+(?:\.\d+)?)\s*$', text, re.MULTILINE)
        if calc_match and 23 not in answers:
            answers[23] = calc_match.group(1)
        
        # ===== 빈 칸 형태의 답안 찾기 (예: "1. ___") =====
        blank_pattern = re.compile(r'(\d+)[\.\):]\s*[\[(]?\s*[\)\]]?\s*$')
        for line in lines:
            match = blank_pattern.match(line.strip())
            if match:
                qid = int(match.group(1))
                if qid not in answers:
                    answers[qid] = ""  # 빈 답안
        
        return answers
    
    def _normalize_answer(self, answer: str) -> str:
        answer = answer.strip().upper()
        
        # 한글/특수문자 매핑
        if answer in self.korean_mapping:
            return self.korean_mapping[answer]
        
        # 길이가 1인 알파벳
        if len(answer) == 1 and answer.isalpha():
            return answer
        
        # True/False -> a/b 변환 (중요!)
        if answer in ['TRUE', 'T', 'O', '○', '1']:
            return 'A'   # a로 매핑
        if answer in ['FALSE', 'F', 'X', '×', '0']:
            return 'B'   # b로 매핑
        
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
        correct = self.correct_answers.get(qid, '')
        qtype = self.answer_types.get(qid, 'unknown')
        
        # True/False는 a/b로 변환하여 비교
        if qtype == 'True/False':
            student_norm = self._normalize_tf(student_answer)
            correct_norm = self._normalize_tf(correct)
        else:
            student_norm = self._normalize(student_answer)
            correct_norm = self._normalize(correct)
        
        if student_norm == correct_norm:
            return True, 1.0
        return False, 0.0

    def _normalize_tf(self, answer: str) -> str:
        """True/False 전용 정규화 (a/b 반환)"""
        if not answer:
            return ""
        answer = answer.strip().upper()
        if answer in ['T', 'TRUE', 'O', '○', '1']:
            return 'A'
        if answer in ['F', 'FALSE', 'X', '×', '0']:
            return 'B'
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