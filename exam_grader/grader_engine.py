# exam_grader/grader_engine.py

import os
from typing import Any, Dict
import fitz
import cv2
import numpy as np

from .answer_parser import DynamicQuestionDetector, AnswerExtractor
from .scoring_engine import GradingResult, ScoringEngine
from .omr import pdf_region_to_bgr, omr_get_easyocr_reader
from .graders.multiple_choice import MultipleChoiceGrader


class ExamGrader:
    """통합 채점 엔진 - 개선된 동적 위치 검출 및 괄호 인식 사용"""
    
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
        self.easyocr_reader = omr_get_easyocr_reader() if use_ocr else None
        
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
        
        # 2. 답안 추출 (이미지 기반 OMR 감지 통합)
        print("\n📝 Step 2: Answer extraction with OMR/bracket detection")
        answers, region_texts, extract_debug = self._extract_answers_with_omr(
            pdf_path, question_regions
        )

        # 3. 채점
        print("\n⚖️ Step 3: Scoring")
        grading = self.scoring_engine.calculate_scores(answers)
        scores = {
            qid: grading.question_scores[qid].earned_score
            for qid in question_regions
            if qid in grading.question_scores
        }
        for qid in question_regions:
            scores.setdefault(qid, 0.0)

        # 4. 결과 생성
        result = self._build_result(
            answers, scores, region_texts, question_regions, grading, extract_debug
        )
        
        print("\n" + "=" * 60)
        print(f"📊 Grading complete: {result['total']:.1f} / {result['max_score']:.1f} points ({result['percentage']:.1f}%)")
        print("=" * 60)
        
        return result
    
    def _extract_answers_with_omr(
        self, 
        pdf_path: str, 
        question_regions: Dict
    ) -> tuple[Dict[int, str], Dict[int, str], Dict[int, Dict]]:
        """
        문제 영역에서 답안 추출 (이미지 기반 OMR/괄호 감지 포함)
        """
        doc = fitz.open(pdf_path)
        answers = {}
        region_texts = {}
        extract_debug = {}
        
        for qid, info in question_regions.items():
            page_num = info.get('page', 0)
            region = info.get('region')
            qtype = info.get('question_type', 'unknown')
            
            if page_num >= len(doc) or region is None:
                answers[qid] = ""
                region_texts[qid] = ""
                extract_debug[qid] = {"error": "invalid region"}
                continue
            
            page = doc[page_num]
            student_answer = ""
            debug_info = {"question_type": qtype}
            
            # Multiple Choice / True/False: 이미지 기반 OMR 감지
            if qtype in ("Multiple Choice", "True/False", "multiple_choice", "true_false"):
                try:
                    # 문제 영역 이미지 렌더링
                    zoom = 1.5
                    bgr = pdf_region_to_bgr(page, region, zoom=zoom)
                    
                    if bgr is not None and bgr.size > 0:
                        # 문제 영역 원본 저장
                        orig_filename = f"Q{qid:02d}_region_original.png"
                        cv2.imwrite(orig_filename, bgr)

                        # 괄호 인식 우선 사용
                        num_choices = 2 if qtype in ("True/False", "true_false") else 4
                        student_answer, confidence = MultipleChoiceGrader.detect_mark_from_region_bgr(
                            bgr, 
                            question_type=qtype,
                            easyocr_reader=self.easyocr_reader,
                            use_bracket_detection=True,
                            num_choices=num_choices
                        )
                        
                        debug_info['omr_method'] = 'bracket_priority'
                        debug_info['omr_confidence'] = confidence
                        debug_info['image_shape'] = bgr.shape
                        
                        # 디버그: 괄호 영역 감지 결과 (선택적)
                        try:
                            bracket_coords = MultipleChoiceGrader.detect_bracket_regions(bgr, num_choices)
                            debug_info['bracket_coords_detected'] = len(bracket_coords)
                        except Exception:
                            pass
                    else:
                        debug_info['error'] = 'empty_image'
                        
                except Exception as e:
                    debug_info['error'] = str(e)
                    student_answer = ""
                
                answers[qid] = student_answer if student_answer else ""
                region_texts[qid] = ""  # 이미지 기반은 텍스트 없음
                
            else:
                # 텍스트 기반 문제: 기존 AnswerExtractor 사용
                try:
                    text = self.extractor._extract_text_from_region(page, region)
                    region_texts[qid] = text
                    # 텍스트에서 답안 파싱
                    student_answer = self._parse_answer_from_text(text, qtype)
                    answers[qid] = student_answer
                    debug_info['text_length'] = len(text)
                except Exception as e:
                    debug_info['error'] = str(e)
                    answers[qid] = ""
                    region_texts[qid] = ""
            
            extract_debug[qid] = debug_info
        
        doc.close()
        return answers, region_texts, extract_debug
    
    def _parse_answer_from_text(self, text: str, qtype: str) -> str:
        """텍스트에서 답안 파싱"""
        if not text:
            return ""
        
        # Multiple Choice 텍스트 파싱 (폴백용)
        if qtype in ("Multiple Choice", "multiple_choice"):
            # 패턴: "answer: c", "답: c", "③", "[c]" 등
            patterns = [
                r'(?:answer|답|정답)[:\s]*([a-d])',
                r'\[([a-d])\]',
                r'\(([a-d])\)',
                r'([a-d])\s*(?:\.|\)|])',
            ]
            for pattern in patterns:
                match = re.search(pattern, text.lower())
                if match:
                    return match.group(1).lower()
        
        # True/False
        elif qtype in ("True/False", "true_false"):
            if 'true' in text.lower() and 'false' not in text.lower()[:20]:
                return 'a'
            elif 'false' in text.lower():
                return 'b'
        
        # 기타: 첫 번째 알파벳 반환
        match = re.search(r'[a-d]', text.lower())
        if match:
            return match.group()
        
        return text.strip()[:20] if text else ""
    
    def _build_from_json_coordinates(self, pdf_path: str) -> Dict:
        """JSON 좌표를 사용하여 영역 생성 (하위 호환용)"""
        doc = fitz.open(pdf_path)
        regions = {}
        
        height_map = {
            'Multiple Choice': 100, 'True/False': 90, 'Fill in the Blank': 100,
            'Short Answer': 110, 'Matching': 150, 'Ordering': 120,
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
            
            # 충분한 너비와 높이로 영역 확장
            width = 500 if qtype in ('Multiple Choice', 'True/False') else 350
            
            region = fitz.Rect(
                max(0, x - 20), 
                max(0, y - height), 
                min(page.rect.width, x + width), 
                y + 30
            )
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
    
    def _build_result(
        self,
        answers: Dict,
        scores: Dict,
        region_texts: Dict,
        question_regions: Dict,
        grading: GradingResult,
        extract_debug: Dict[int, Dict[str, Any]],
    ) -> Dict:
        """결과 데이터 구성"""
        total = sum(scores.values())
        max_score = sum(info['score'] for info in question_regions.values())

        correct_answers = {qid: info['expected_answer'] for qid, info in question_regions.items()}
        question_types = {qid: info['question_type'] for qid, info in question_regions.items()}
        max_scores = {qid: info['score'] for qid, info in question_regions.items()}
        detection_sources = {qid: info.get('detection_source', 'unknown') for qid, info in question_regions.items()}

        grading_debug: Dict[int, Dict[str, Any]] = {}
        for qid in question_regions:
            block: Dict[str, Any] = dict(extract_debug.get(qid, {}))
            qs = grading.question_scores.get(qid)
            if qs:
                block['earned_score'] = qs.earned_score
                block['max_score'] = qs.max_score
                block['score_engine_feedback'] = qs.feedback
                block['scoring_method_key'] = qs.scoring_method
                block['is_correct'] = qs.is_correct
                block['answer_channel'] = 'image_primary' if qs.earned_score > 0 else 'none'
                block['omr_letter'] = answers.get(qid, '')
            grading_debug[qid] = block

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
            'detection_sources': detection_sources,
            'grading_debug': grading_debug,
        }