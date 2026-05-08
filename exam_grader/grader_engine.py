# exam_grader/grader_engine.py
import os
from typing import Dict
import fitz

from .answer_parser import DynamicQuestionDetector, AnswerExtractor
from .scoring_engine import ScoringEngine


class ExamGrader:
    """통합 채점 엔진 - 개선된 동적 위치 검출 사용"""
    
    def __init__(self, exam_data: Dict, use_detection: bool = True, use_ocr: bool = True):
        """
        Args:
            exam_data: 시험 JSON 데이터
            use_detection: True=동적 검출, False=JSON 좌표 사용
            use_ocr: OCR 사용 여부
        """
        self.exam_data = exam_data
        self.use_detection = use_detection
        self.use_ocr = use_ocr
        
        self.scoring_engine = ScoringEngine(exam_data)
        
        if use_detection:
            self.detector = DynamicQuestionDetector(use_ocr=use_ocr)
        else:
            self.detector = None
        
        self.extractor = AnswerExtractor(use_ocr=use_ocr)
    
    def grade_from_pdf(self, pdf_path: str) -> Dict:
        """PDF에서 직접 채점 수행"""
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        print("\n" + "=" * 60)
        print("📋 Exam Grader Engine")
        print("=" * 60)
        
        # 1. 문제 위치 검출
        if self.use_detection:
            print("\n🔍 Step 1: Dynamic question detection")
            question_regions = self.detector.detect_all_questions(pdf_path, self.exam_data)
        else:
            print("\n📌 Step 1: Using JSON coordinates (fallback)")
            question_regions = self._build_from_json_coordinates(pdf_path)
        
        if not question_regions:
            raise ValueError("No questions detected in PDF")
        
        print(f"\n✅ Detected {len(question_regions)} questions")
        
        # 2. 답안 추출
        print("\n📝 Step 2: Answer extraction")
        answers, region_texts = self.extractor.extract_answers(pdf_path, question_regions)
        
        # 3. 채점
        print("\n⚖️ Step 3: Scoring")
        scores = self.scoring_engine.calculate_scores(answers, region_texts)
        
        # 4. 결과 생성
        result = self._build_result(answers, scores, region_texts, question_regions)
        
        print("\n" + "=" * 60)
        print(f"📊 Grading complete: {result['total']:.1f} / {result['max_score']} points ({result['percentage']:.1f}%)")
        print("=" * 60)
        
        return result
    
    def _build_from_json_coordinates(self, pdf_path: str) -> Dict:
        """JSON 좌표를 사용하여 영역 생성 (하위 호환용)"""
        doc = fitz.open(pdf_path)
        regions = {}
        
        height_map = {
            'Multiple Choice': 80, 'True/False': 80, 'Fill in the Blank': 100,
            'Short Answer': 100, 'Matching': 150, 'Ordering': 120,
            'Ordering/Ranking': 120, 'Code Writing': 250, 'Calculation': 130, 'Essay': 250
        }
        
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            position = q.get('position')
            if not position or not qid:
                continue
            
            page_num = position.get('page', 1) - 1
            if page_num >= len(doc):
                continue
            
            page = doc[page_num]
            page_height = page.rect.height
            
            x = position.get('x', 0)
            y_from_top = position.get('y', 0)
            y = page_height - y_from_top
            
            qtype = q.get('question_type', '')
            height = height_map.get(qtype, 100)
            
            region = fitz.Rect(max(0, x - 10), max(0, y - height), min(page.rect.width, x + 300), y)
            region = region & page.rect
            
            regions[qid] = {
                'page': page_num,
                'page_display': page_num + 1,
                'region': region,
                'question_bbox': (x, y - height, x + 50, y),
                'question_type': qtype,
                'expected_answer': q.get('expected_answer', q.get('answer', '')),
                'score': q.get('score', 0),
                'detection_source': 'json_fallback'
            }
        
        doc.close()
        return regions
    
    def _build_result(self, answers: Dict, scores: Dict, region_texts: Dict, question_regions: Dict) -> Dict:
        """결과 데이터 구성"""
        total = sum(scores.values())
        max_score = sum(info['score'] for info in question_regions.values())
        
        correct_answers = {qid: info['expected_answer'] for qid, info in question_regions.items()}
        question_types = {qid: info['question_type'] for qid, info in question_regions.items()}
        max_scores = {qid: info['score'] for qid, info in question_regions.items()}
        detection_sources = {qid: info.get('detection_source', 'unknown') for qid, info in question_regions.items()}
        
        return {
            'student_answers': answers,
            'scores': scores,
            'total': total,
            'max_score': max_score,
            'percentage': (total / max_score * 100) if max_score > 0 else 0,
            'correct_answers': correct_answers,
            'question_types': question_types,
            'max_scores': max_scores,
            'region_texts': region_texts,
            'detection_sources': detection_sources
        }