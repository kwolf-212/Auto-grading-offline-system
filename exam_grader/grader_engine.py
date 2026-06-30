# exam_grader/grader_engine.py (수정된 버전)
"""
채점 엔진 - PDF 처리, 채점 흐름, 결과 집계
"""
import os
from typing import Dict, List, Tuple
import cv2
import numpy as np

from .omr import (
    ArUcoDetector, BubbleBox, BubbleMarkResult,
    omr_analyze_bubbles, omr_select_answers
)
from .graders import get_grader  # 추가


def _answer_to_number(answer):
    # ... (기존 코드 유지) ...
    if answer is None:
        return 0
    if isinstance(answer, int):
        return answer
    a = str(answer).strip().lower()
    if a.isdigit():
        return int(a)
    if a in ('t', 'true'):
        return 1
    if a in ('f', 'false'):
        return 2
    if len(a) == 1 and a.isalpha():
        return ord(a) - ord('a') + 1
    return 0


def _format_ordering_result(result: Dict) -> str:
    """ordering 유형 결과를 표시용 문자열로 변환"""
    student_order = result.get('student_order', [])
    correct_order = result.get('correct_order', [])
    
    if student_order and correct_order:
        student_str = ">".join(str(x) for x in student_order if x > 0)
        correct_str = ">".join(str(x) for x in correct_order)
        
        # 미인식된 항목 표시
        unknown_count = sum(1 for x in student_order if x == 0)
        if unknown_count > 0:
            student_str += f" (인식실패:{unknown_count})"
        
        return f"{student_str} (정답:{correct_str})"
    
    return str(result.get('selected_label', ''))


class ExamGrader:
    """통합 채점 엔진"""
    
    def __init__(self, exam_data: Dict, debug_mode: bool = False):
        # ... (기존 코드 유지) ...
        self.exam_data = exam_data
        self.debug_mode = debug_mode
        self.page_calibrations: Dict[int, ArUcoDetector] = {}
        self.question_boxes: Dict[int, Dict] = {}
        self.preprocessor = None
        self.is_preprocessed = False
    
    def set_preprocessor(self, preprocessor):
        """전처리 결과 설정"""
        self.preprocessor = preprocessor
        self.is_preprocessed = True
        self._build_question_boxes_from_preprocessor()
    
    def grade_from_preprocessed(self) -> Dict:
        """전처리된 데이터로 채점 실행"""
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
                    # 정답 처리 (ordering 유형은 문자열/리스트 그대로 보존)
                    expected_answer = region.expected_answer
                    if region.question_type == 'ordering':
                        # ordering: 문자열/리스트 형태 유지
                        expected_answer_value = expected_answer
                    else:
                        # 객관식: 숫자로 변환
                        expected_answer_value = _answer_to_number(expected_answer)
                    
                    self.question_boxes[qid] = {
                        'question_id': qid,
                        'page': page_num - 1,
                        'question_type': region.question_type,
                        'expected_answer_number': expected_answer_value,
                        'score': region.score,
                        'bubble_boxes': bubble_boxes
                    }
                    
                    detector = self.preprocessor.get_detector(page_num - 1)
                    if detector:
                        self.page_calibrations[page_num - 1] = detector
                    
                    if self.debug_mode:
                        print(f"  Q{qid}: {len(bubble_boxes)} choices, type={region.question_type} (from preprocessor)")
    
    def _grade_from_preprocessed(self) -> Dict:
        """전처리된 데이터로 채점 실행 (수정된 부분)"""
        if not self.preprocessor:
            raise ValueError("No preprocessor data available")
        
        answers = {}
        scores = {}
        debug_info = {}
        ordering_details = {}  # ordering 유형 상세 정보 저장
        
        print("\n📝 Grading from preprocessed data...")
        
        for qid, qinfo in self.question_boxes.items():
            page_num = qinfo['page']
            qtype = qinfo['question_type']
            
            page_image = self.preprocessor.get_page_image(page_num)
            
            if page_image is None:
                print(f"  ⚠️ Q{qid}: No image for page {page_num + 1}")
                answers[qid] = ""
                scores[qid] = 0
                debug_info[qid] = {'error': 'No page image'}
                continue
            
            # ========== 유형별 채점기 사용 ==========
            grader = get_grader(qtype, qinfo)
            result = grader.grade(page_image, self.debug_mode)

            # 유형별 결과 처리
            if qtype == 'Ordering/Ranking':
                student_order = result.get('student_order', [])
                ocr_texts = result.get('ocr_texts', [])  # OCR 텍스트 가져오기
                
                answers[qid] = ">".join(str(x) for x in student_order if x > 0) if student_order else ""
                scores[qid] = result['score']
                debug_info[qid] = result['debug']
                ordering_details[qid] = {
                    'student_order': result.get('student_order', []),
                    'correct_order': result.get('correct_order', []),
                    'ocr_texts': result.get('ocr_texts', []),  # OCR 텍스트 저장
                    'is_correct': result.get('correct', False)
                }
                
                status = "✓" if result['correct'] else "✗"
                student_str = ">".join(str(x) for x in result.get('student_order', []) if x > 0)
                correct_str = ">".join(str(x) for x in result.get('correct_order', []))
                
                # 디버그 모드에서 OCR 텍스트 출력
                if self.debug_mode and ocr_texts:
                    print(f"  Q{qid}: {status} ordering: {student_str} (expected: {correct_str}) → {result['score']:.1f}/{qinfo['score']}")
                    for idx, text in enumerate(ocr_texts):
                        print(f"      OCR[{idx+1}]: '{text}'")
                else:
                    print(f"  Q{qid}: {status} ordering: {student_str} (expected: {correct_str}) → {result['score']:.1f}/{qinfo['score']}")
                
            else:  # multiple_choice 등
                answers[qid] = result['selected_label']
                scores[qid] = result['score']
                debug_info[qid] = result['debug']
                
                status = "✓" if result['correct'] else "✗"
                print(f"  Q{qid}: {status} choice #{result['selected_number']} (expected: #{qinfo['expected_answer_number']}) → {result['score']:.1f}/{qinfo['score']}")
        
        # 결과 집계
        result_dict = self._build_result(answers, scores, debug_info)
        
        # ordering 상세 정보 추가
        if ordering_details:
            result_dict['ordering_details'] = ordering_details
        
        return result_dict
    
    def _build_result(self, answers: Dict, scores: Dict, debug_info: Dict) -> Dict:
        """결과 집계 (ordering 유형 지원 확장)"""
        total = sum(scores.values())
        max_score = sum(self.question_boxes[qid]['score'] for qid in self.question_boxes)
        
        # 정답 개수 계산 (유형별로 다른 방식)
        correct_count = 0
        for qid in self.question_boxes:
            qtype = self.question_boxes[qid]['question_type']
            expected = self.question_boxes[qid]['expected_answer_number']
            student = answers.get(qid)
            
            if qtype == 'ordering':
                # ordering: student_order 리스트 비교 필요 (debug_info 활용)
                debug = debug_info.get(qid, {})
                if debug.get('is_correct', False):
                    correct_count += 1
            else:
                # 객관식: 레이블 비교
                if student == expected:
                    correct_count += 1
        
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
    
    def get_ordering_summary(self) -> Dict:
        """ordering 유형 문제만 요약"""
        if not hasattr(self, 'question_boxes'):
            return {}
        
        summary = {}
        for qid, qinfo in self.question_boxes.items():
            if qinfo['question_type'] == 'ordering':
                summary[qid] = {
                    'question_id': qid,
                    'score': qinfo['score'],
                    'expected': qinfo['expected_answer_number']
                }
        return summary
    
    def print_ordering_results(self):
        """ordering 유형 결과 출력"""
        if not hasattr(self, 'preprocessor') or not self.preprocessor:
            print("No preprocessor data available")
            return
        
        print("\n" + "="*50)
        print("📋 Ordering Questions Results")
        print("="*50)
        
        for qid, qinfo in self.question_boxes.items():
            if qinfo['question_type'] != 'ordering':
                continue
            
            # 최종 결과에서 정보 가져오기 (grade_from_preprocessed 호출 필요)
            # 또는 별도로 저장된 정보 사용
            print(f"\nQ{qid}: (Score: {qinfo['score']} points)")
            print(f"  Expected order: {qinfo['expected_answer_number']}")
    
    def export_results(self, output_path: str, format: str = 'json'):
        """결과 내보내기 (ordering 지원)"""
        import json
        
        # grade_from_preprocessed() 실행 필요
        results = self.grade_from_preprocessed() if not hasattr(self, '_graded') else self._graded_results
        
        if format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"✅ Results exported to {output_path}")
        
        elif format == 'csv':
            import csv
            with open(output_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Question ID', 'Type', 'Student Answer', 'Correct Answer', 'Score', 'Max Score'])
                for qid in self.question_boxes:
                    qtype = self.question_boxes[qid]['question_type']
                    expected = self.question_boxes[qid]['expected_answer_number']
                    student = results['student_answers'].get(qid, '')
                    score = results['scores'].get(qid, 0)
                    max_score = results['max_scores'].get(qid, 0)
                    
                    if qtype == 'ordering':
                        # ordering은 이미 문자열로 변환됨
                        writer.writerow([qid, qtype, student, expected, score, max_score])
                    else:
                        writer.writerow([qid, qtype, student, expected, score, max_score])
            
            print(f"✅ Results exported to {output_path}")