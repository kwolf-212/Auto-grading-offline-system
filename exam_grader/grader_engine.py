# exam_grader/grader_engine.py
"""
채점 엔진 - PDF 처리, 채점 흐름, 결과 집계
"""

import os
from typing import Dict, List, Optional, Tuple
import fitz
import cv2
import numpy as np

from .omr import (
    ArUcoDetector, BubbleBox, BubbleMarkResult,
    omr_analyze_bubbles, omr_select_answers, omr_read_mc_tf_selection
)

def _answer_to_number(answer):

    if answer is None:
        return 0

    if isinstance(answer, int):
        return answer

    a = str(answer).strip().lower()

    # 숫자 문자열
    if a.isdigit():
        return int(a)

    # True / False
    if a in ('t', 'true'):
        return 1

    if a in ('f', 'false'):
        return 2

    # A,B,C,D...
    if len(a) == 1 and a.isalpha():
        return ord(a) - ord('a') + 1

    return 0

class ExamGrader:
    """통합 채점 엔진"""
    
    def __init__(self, exam_data: Dict, debug_mode: bool = False):
        """
        Args:
            exam_data: 시험 JSON 데이터
            debug_mode: 디버그 모드
        """
        self.exam_data = exam_data
        self.debug_mode = debug_mode
        self.page_calibrations: Dict[int, ArUcoDetector] = {}
        self.question_boxes: Dict[int, Dict] = {}
        
        # ========== 추가: 전처리기 연동 ==========
        self.preprocessor = None  # ImagePreprocessor 인스턴스 저장
        self.is_preprocessed = False  # 전처리 여부 플래그
    
    # ========== 추가: 전처리기 연동 메서드 ==========
    def set_preprocessor(self, preprocessor):
        """전처리 결과 설정"""
        self.preprocessor = preprocessor
        self.is_preprocessed = True
        
        # 전처리된 데이터로 question_boxes 구성
        self._build_question_boxes_from_preprocessor()
    
    def grade_from_preprocessed(self) -> Dict:
        """전처리된 데이터로 채점 실행 (추가된 메서드)"""
        if not self.preprocessor:
            raise ValueError("No preprocessor data available. Call set_preprocessor() first.")
        
        return self._grade_from_preprocessed()

    def _build_question_boxes_from_preprocessor(self):
        """전처리된 데이터로 문제 박스 구성"""
        if not self.preprocessor:
            return
        
        print("\n📦 Building question boxes from preprocessed data...")
        
        for page_num, page_regions in self.preprocessor.question_regions.items():
            for qid, region in page_regions.items():
                # BubbleBox 리스트 생성
                bubble_boxes = []
                for choice, rect in region.choice_regions.items():
                    bubble_boxes.append(BubbleBox(
                        label=choice,
                        x1=rect['x'],
                        y1=rect['y'],
                        x2=rect['x'] + rect['w'],
                        y2=rect['y'] + rect['h']
                    ))
                
                if bubble_boxes:
                    print(
                        f"Q{qid}: "
                        f"region.expected_answer={region.expected_answer!r}, "
                        f"type={type(region.expected_answer)}"
                    )
                    self.question_boxes[qid] = {
                        'question_id': qid,
                        'page': page_num - 1,  # 1-based -> 0-based
                        'question_type': region.question_type,
                        'expected_answer_number':
                            _answer_to_number(region.expected_answer),
                        'score': region.score,
                        'bubble_boxes': bubble_boxes
                    }
                    
                    # 페이지 캘리브레이션 저장
                    detector = self.preprocessor.get_detector(page_num - 1)
                    if detector:
                        self.page_calibrations[page_num - 1] = detector
                    
                    if self.debug_mode:
                        print(f"  Q{qid}: {len(bubble_boxes)} choices (from preprocessor)")
    
    # ========== 수정: grade_from_pdf (전처리 통합 버전) ==========
    def grade_from_pdf(self, pdf_path: str, use_preprocessing: bool = True) -> Dict:
        """
        PDF 채점 실행
        
        Args:
            pdf_path: PDF 파일 경로
            use_preprocessing: True=전처리 사용 (빠름), False=기존 방식
        
        Returns:
            채점 결과 딕셔너리
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        print("\n" + "=" * 60)
        print("📋 Exam Grader Engine")
        print("=" * 60)
        
        # ========== 수정: 전처리 사용 여부 확인 ==========
        if use_preprocessing and self.is_preprocessed:
            print("✅ Using preprocessed data for grading...")
            return self._grade_from_preprocessed()
        
        # 기존 방식 (전처리 없음)
        doc = fitz.open(pdf_path)
        
        # 1. ArUco 캘리브레이션
        self._calibrate_pages(doc)
        
        # 2. 문제 박스 구성
        self._build_question_boxes(doc)
        
        if not self.question_boxes:
            doc.close()
            raise ValueError("No questions found")
        
        # 3. 채점 수행
        answers, scores, debug_info = self._grade_all_questions(doc)
        
        doc.close()
        
        # 4. 결과 집계
        return self._build_result(answers, scores, debug_info)
    
    # ========== 추가: 전처리된 데이터로 채점 ==========
    def _grade_from_preprocessed(self) -> Dict:
        """전처리된 데이터로 채점 실행"""
        if not self.preprocessor:
            raise ValueError("No preprocessor data available")
        
        answers = {}
        scores = {}
        debug_info = {}
        
        print("\n📝 Grading from preprocessed data...")
        
        for qid, qinfo in self.question_boxes.items():
            page_num = qinfo['page']
            qtype = qinfo['question_type']
            
            # 전처리된 페이지 이미지 가져오기
            page_image = self.preprocessor.get_page_image(page_num)
            
            if page_image is None:
                print(f"  ⚠️ Q{qid}: No image for page {page_num + 1}")
                answers[qid] = ""
                scores[qid] = 0
                debug_info[qid] = {'error': 'No page image'}
                continue
            
            if qtype in ("Multiple Choice", "True/False", "multiple_choice", "true_false"):
                result = self._grade_multiple_choice_from_image(page_image, qinfo)
                answers[qid] = result['selected_label']
                scores[qid] = result['score']
                debug_info[qid] = result['debug']
                
                status = "✓" if result['correct'] else "✗"
                print(f"  Q{qid}: {status} choice #{result['selected_number']} (expected: #{qinfo['expected_answer_number']}) → {result['score']:.1f}/{qinfo['score']}")
            else:
                answers[qid] = ""
                scores[qid] = 0
                debug_info[qid] = {'error': f'Unsupported type: {qtype}'}
        
        return self._build_result(answers, scores, debug_info)
    
    # ========== 추가: 이미지로부터 객관식 채점 ==========
    def _grade_multiple_choice_from_image(self, page_image: np.ndarray, qinfo: Dict) -> Dict:
        """이미지 배열로부터 객관식 채점"""
        result = {'selected_number': 0, 'correct': False, 'score': 0.0, 'debug': {}}
        bubble_boxes = qinfo['bubble_boxes']
        
        if not bubble_boxes:
            return result
        
        try:
            valid = []
            qid = qinfo.get('question_id', 'unknown')
            
            # 디버그 디렉토리 생성
            debug_dir = "debug_bubbles"
            os.makedirs(debug_dir, exist_ok=True)
            
            for idx, box in enumerate(bubble_boxes):
                # 이미지에서 영역 크롭
                x1, y1, x2, y2 = int(box.x1), int(box.y1), int(box.x2), int(box.y2)
                
                # 경계 체크
                if y2 > page_image.shape[0] or x2 > page_image.shape[1]:
                    if self.debug_mode:
                        print(f"    ⚠️ Q{qid}_{box.label}: Out of bounds ({x1},{y1},{x2},{y2}) vs {page_image.shape}")
                    continue
                
                bgr = page_image[y1:y2, x1:x2]
                
                if bgr.size == 0:
                    continue
                
                # 디버그 저장
                debug_path = os.path.join(debug_dir, f"Q{qid}_{box.label}_{idx}.png")
                cv2.imwrite(debug_path, bgr)
                
                valid.append((box.label, bgr))
            
            if valid:
                results = self._analyze_bubbles(valid)
                selected, conf = self._select_answers(results)

                if selected:
                    selected_label = selected[0]
                    result['selected_label'] = selected_label
                    result['selected_number'] = _answer_to_number(selected_label)
                    result['correct'] = (
                        result['selected_number'] == qinfo['expected_answer_number']
                    )
                    result['score'] = (
                        qinfo['score'] if result['correct'] else 0.0
                    )
                    result['debug'] = {
                        'confidence': conf,
                        'bubble_scores': [
                            (r.label, r.score)
                            for r in results
                        ]
                    }
        
        except Exception as e:
            result['debug'] = {'error': str(e)}
            if self.debug_mode:
                import traceback
                traceback.print_exc()
        
        print(f"\nQ{qid}")
        print("results =", results)
        print("selected =", selected)
        print("conf =", conf)
        print("\nBubble results:")
        for r in results:
            print(
                f"label={r.label}, "
                f"score={r.score:.4f}, "
                f"marked={r.marked}"
            )

        return result
    
    # ========== 추가: OMR 분석 래퍼 ==========
    def _analyze_bubbles(
        self,
        bubble_images: List[Tuple[str, np.ndarray]]
    ) -> List['BubbleMarkResult']:
        """개별 버블 이미지 분석"""

        try:
            from .omr import omr_analyze_bubbles
            return omr_analyze_bubbles(bubble_images)
        except ImportError:
            results = []
            for label, img in bubble_images:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) \
                    if len(img.shape) == 3 else img
                _, binary = cv2.threshold(
                    gray,
                    200,
                    255,
                    cv2.THRESH_BINARY_INV
                )
                ink_ratio = (
                    np.sum(binary > 0)
                    / (binary.shape[0] * binary.shape[1])
                )
                from .omr import BubbleMarkResult
                results.append(BubbleMarkResult(
                    label=label,
                    score=ink_ratio,
                    marked=ink_ratio >= 0.3
                ))
            return results
    
    def _select_answers(self, results: List['BubbleMarkResult']) -> Tuple[List[str], float]:
        """선택지 선택"""
        try:
            from .omr import omr_select_answers
            return omr_select_answers(results)
        except ImportError:
            if not results:
                return [], 0.0
            best = max(results, key=lambda x: x.score)
            return [best.label], best.score
    
    # ========== 기존 메서드 (수정 없음) ==========
    def _calibrate_pages(self, doc):
        """각 페이지 ArUco 캘리브레이션"""
        print("\n🔍 Calibrating pages with ArUco markers...")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            zoom = 1.5
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # 이미지 변환
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR) if pix.n == 3 else cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            
            # ArUco 감지
            detector = ArUcoDetector()
            detector.detect_markers(bgr)
            
            if detector.compute_perspective_transform(pix.width, pix.height):
                self.page_calibrations[page_num] = detector
                if self.debug_mode:
                    print(f"  Page {page_num + 1}: Calibrated")
            else:
                self.page_calibrations[page_num] = None
    
    def _build_question_boxes(self, doc):
        """JSON에서 문제 박스 구성"""
        print("\n📦 Building question boxes...")
        
        for q in self.exam_data.get('answers', []):
            qid = q.get('question_id')
            if not qid:
                continue
            
            pos = q.get('position', {})
            page_num = pos.get('page', 1) - 1
            
            if page_num < 0 or page_num >= len(doc):
                continue
            
            detector = self.page_calibrations.get(page_num)
            page = doc[page_num]
            page_rect = page.rect
            
            # BubbleBox 리스트 생성
            bubble_boxes = []
            for cr in q.get('choice_regions', []):
                choice = cr.get('choice', '')
                norm = cr.get('normalized', {})
                
                if norm:
                    if detector and detector.is_calibrated:
                        pixel = detector.normalized_rect_to_pixel(norm)
                    else:
                        # 폴백: 페이지 크기 기반
                        pixel = {
                            'x': int(norm['x'] * page_rect.width),
                            'y': int(norm['y'] * page_rect.height),
                            'w': int(norm['w'] * page_rect.width),
                            'h': int(norm['h'] * page_rect.height)
                        }
                    
                    bubble_boxes.append(BubbleBox(
                        label=choice,
                        x1=pixel['x'],
                        y1=pixel['y'],
                        x2=pixel['x'] + pixel['w'],
                        y2=pixel['y'] + pixel['h']
                    ))
            
            if bubble_boxes:
                self.question_boxes[qid] = {
                    'question_id': qid,
                    'page': page_num,
                    'question_type': q.get('question_type', 'unknown'),
                    'expected_answer_number':
                        _answer_to_number(q.get('expected_answer', q.get('answer', ''))),
                    'score': q.get('score', 0),
                    'bubble_boxes': bubble_boxes
                }
                if self.debug_mode:
                    print(f"  Q{qid}: {len(bubble_boxes)} choices")
    
    def _grade_all_questions(self, doc) -> Tuple[Dict, Dict, Dict]:
        """모든 문제 채점"""
        print("\n📝 Grading...")
        
        answers = {}
        scores = {}
        debug_info = {}
        
        for qid, qinfo in self.question_boxes.items():
            page_num = qinfo['page']
            page = doc[page_num]
            qtype = qinfo['question_type']
            
            if qtype in ("Multiple Choice", "True/False", "multiple_choice", "true_false"):
                result = self._grade_multiple_choice(page, qinfo)
                answers[qid] = result['selected_label']
                scores[qid] = result['score']
                debug_info[qid] = result['debug']
                
                status = "✓" if result['correct'] else "✗"
                print(f"  Q{qid}: {status} choice #{result['selected_number']} (expected: #{qinfo['expected_answer_number']}) → {result['score']:.1f}/{qinfo['score']}")
            else:
                answers[qid] = ""
                scores[qid] = 0
                debug_info[qid] = {'error': f'Unsupported type: {qtype}'}
        
        return answers, scores, debug_info
    
    
    def _grade_multiple_choice(self, page, qinfo: Dict) -> Dict:
        """객관식 채점"""
        result = {'selected_number': 0, 'correct': False, 'score': 0.0, 'debug': {}}
        bubble_boxes = qinfo['bubble_boxes']
        
        if not bubble_boxes:
            return result
        
        try:
            zoom = 3.0
            valid = []
            
            # 디버그 디렉토리 생성
            debug_dir = "debug_bubbles"
            os.makedirs(debug_dir, exist_ok=True)
            
            for idx, box in enumerate(bubble_boxes):
                rect = fitz.Rect(box.x1, box.y1, box.x2, box.y2)
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
                
                if pix.samples is not None:
                    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                    if pix.n == 3:
                        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                    elif pix.n == 4:
                        bgr = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
                    else:
                        bgr = img
                    
                    qid = qinfo.get('question_id', 'unknown')
                    debug_path = os.path.join(debug_dir, f"Q{qid}_{box.label}_{idx}.png")
                    cv2.imwrite(debug_path, bgr)
                    
                    valid.append((box.label, bgr))
            
            if valid:
                results = self._analyze_bubbles(valid)
                selected, conf = self._select_answers(results)

                if selected:
                    selected_label = selected[0]
                    result['selected_label'] = selected_label
                    result['selected_number'] = _answer_to_number(selected_label)
                    result['correct'] = (
                        result['selected_number']
                        == qinfo['expected_answer_number']
                    )
                    result['score'] = (
                        qinfo['score'] if result['correct'] else 0.0
                    )

                    result['debug'] = {
                        'confidence': conf,
                        'bubble_scores': [
                            (r.label, r.score)
                            for r in results
                        ]
                    }
        
        except Exception as e:
            result['debug'] = {'error': str(e)}
        
        return result
    
    def _build_result(self, answers: Dict, scores: Dict, debug_info: Dict) -> Dict:
        """결과 집계"""
        total = sum(scores.values())
        max_score = sum(self.question_boxes[qid]['score'] for qid in self.question_boxes)
        
        correct_count = sum(1 for qid in self.question_boxes 
                           if answers.get(qid) == self.question_boxes[qid]['expected_answer_number'])
        
        return {
            'student_answers': answers,
            'scores': scores,
            'total': total,
            'max_score': max_score,
            'percentage': (total / max_score * 100) if max_score > 0 else 0,
            'correct_answers': {qid: qinfo['expected_answer_number'] for qid, qinfo in self.question_boxes.items()},
            'question_types': {qid: qinfo['question_type'] for qid, qinfo in self.question_boxes.items()},
            'max_scores': {qid: qinfo['score'] for qid, qinfo in self.question_boxes.items()},
            'grading_debug': debug_info,
            'statistics': {
                'correct': correct_count,
                'incorrect': len(self.question_boxes) - correct_count,
                'total': len(self.question_boxes)
            }
        }
    
    # PDF 뷰어용 메서드
    def get_choice_regions_for_page(self, page_num: int) -> Dict:
        """특정 페이지의 선택지 영역 반환 (뷰어 표시용)"""
        result = {}
        detector = self.page_calibrations.get(page_num)
        
        for qid, qinfo in self.question_boxes.items():
            if qinfo['page'] != page_num:
                continue
            
            regions = {}
            for box in qinfo['bubble_boxes']:
                regions[box.label] = {'x': box.x1, 'y': box.y1, 'w': box.w, 'h': box.h}
            
            if regions:
                result[qid] = {
                    'question_type': qinfo['question_type'],
                    'expected_answer_number': qinfo['expected_answer_number'],
                    'score': qinfo['score'],
                    'choice_regions': regions
                }
        
        return result
    
    def get_aruco_detector(self, page_num: int) -> Optional[ArUcoDetector]:
        """특정 페이지의 ArUco detector 반환"""
        return self.page_calibrations.get(page_num)
    
    # ========== 추가: 전처리된 데이터 직접 설정 ==========
    def preprocess_and_grade(self, pdf_path: str) -> Dict:
        """전처리 후 채점 (단일 호출)"""
        from .image_preprocessor import ImagePreprocessor
        
        print("\n🔧 Running preprocessor...")
        preprocessor = ImagePreprocessor(zoom=1.5)
        success = preprocessor.preprocess_pdf(pdf_path, self.exam_data)
        
        if not success:
            raise RuntimeError("Preprocessing failed")
        
        self.set_preprocessor(preprocessor)
        return self._grade_from_preprocessed()