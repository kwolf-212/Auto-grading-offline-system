# image_preprocessor.py
import cv2
import fitz
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

from exam_grader.omr import ArUcoDetector


@dataclass
class PagePreprocessResult:
    """페이지 전처리 결과"""
    page_num: int
    page_image: np.ndarray  # RGB 이미지
    image_width: int
    image_height: int
    aruco_detector: ArUcoDetector  # 캘리브레이션된 detector
    is_calibrated: bool
    transform_type: str  # "perspective" or "affine" or "none"
    detected_markers: Dict  # 감지된 마커 정보


@dataclass 
class QuestionRegion:
    """문제별 선택지 영역 정보"""
    question_id: int
    page_num: int
    question_type: str
    expected_answer: str
    score: int
    choice_regions: Dict[str, Dict]  # {'a': {'x':100, 'y':200, 'w':50, 'h':30}, ...}


class ImagePreprocessor:
    """PDF 이미지 전처리 및 ArUco 기반 좌표 변환"""
    
    def __init__(self, zoom: float = 1.5, debug_mode: bool = False):  # debug_mode 추가
        self.zoom = zoom
        self.debug_mode = debug_mode  # 디버그 모드 저장
        self.preprocessed_pages: Dict[int, PagePreprocessResult] = {}
        self.question_regions: Dict[int, Dict[int, QuestionRegion]] = {}  # {page_num: {qid: QuestionRegion}}
        
    def preprocess_pdf(self, pdf_path: str, exam_data: Dict) -> bool:
        """
        PDF 전체 페이지 전처리
        - PDF -> 이미지 변환
        - ArUco 마커 감지
        - 변환 행렬 계산
        - 선택지 영역 좌표 변환 및 저장
        
        Returns:
            bool: 전처리 성공 여부
        """
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                if self.debug_mode:
                    print(f"📄 Preprocessing page {page_num + 1}/{len(doc)}...")
                
                # 1. PDF 페이지 -> 이미지 변환
                page = doc[page_num]
                mat = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                
                # PyMuPDF 픽셀맵 -> OpenCV 이미지 (RGB)
                img_data = pix.tobytes("png")
                import io
                from PIL import Image
                pil_img = Image.open(io.BytesIO(img_data))
                page_image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
                
                # 2. ArUco 마커 감지 및 변환 행렬 계산
                detector = ArUcoDetector()
                detected_markers = detector.detect_markers(page_image)
                
                required_markers = [0, 1, 2, 3]
                has_all_markers = all(mid in detected_markers for mid in required_markers)
                
                is_calibrated = False
                transform_type = "none"
                
                if has_all_markers:
                    is_calibrated = detector.compute_perspective_transform(
                        pix.width, pix.height
                    )
                    transform_type = "perspective" if is_calibrated else "none"
                else:
                    is_calibrated = detector.compute_transform(pix.width, pix.height)
                    transform_type = "affine" if is_calibrated else "none"
                
                # 3. 전처리 결과 저장
                page_result = PagePreprocessResult(
                    page_num=page_num,
                    page_image=page_image,
                    image_width=pix.width,
                    image_height=pix.height,
                    aruco_detector=detector,
                    is_calibrated=is_calibrated,
                    transform_type=transform_type,
                    detected_markers=detected_markers
                )
                self.preprocessed_pages[page_num] = page_result
                
                # 4. 해당 페이지의 선택지 영역 좌표 변환
                self._convert_question_regions(exam_data, page_num + 1, detector)
                
                if self.debug_mode:
                    print(f"   ✅ Page {page_num + 1}: {transform_type} transform, "
                          f"markers: {list(detected_markers.keys())}")
            
            doc.close()
            return True
            
        except Exception as e:
            print(f"❌ Preprocessing failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _convert_question_regions(self, exam_data: Dict, page_num: int, detector: ArUcoDetector):
        """JSON의 정규화 좌표를 픽셀 좌표로 변환하여 저장"""
        
        if not detector.is_calibrated:
            if self.debug_mode:
                print(f"   ⚠️ Page {page_num}: Not calibrated, skipping region conversion")
            return
        
        page_regions = {}
        
        for q in exam_data.get('answers', []):
            qid = q.get('question_id')
            if not qid:
                continue
            
            pos = q.get('position', {})
            q_page = pos.get('page', 1)
            
            if q_page != page_num:
                continue
            
            # 선택지 영역 변환
            choice_regions_pixel = {}
            
            for cr in q.get('choice_regions', []):
                choice = cr.get('choice', '?')
                norm = cr.get('normalized', {})
                if norm and 'x' in norm and 'y' in norm and 'w' in norm and 'h' in norm:
                    try:
                        pixel_rect = detector.normalized_rect_to_pixel(norm)
                        choice_regions_pixel[cr.get('choice', '?')] = pixel_rect

                        if self.debug_mode:
                            print(f"     📍 Q{qid}[{choice}]: "
                                  f"norm({norm['x']:.3f}, {norm['y']:.3f}, {norm['w']:.3f}, {norm['h']:.3f}) "
                                  f"→ pixel({pixel_rect['x']}, {pixel_rect['y']}, {pixel_rect['w']}, {pixel_rect['h']})")
                    except Exception as e:
                        if self.debug_mode:
                            print(f"   ⚠️ Q{qid} {cr.get('choice')} conversion failed: {e}")
            
            if choice_regions_pixel:
                question_region = QuestionRegion(
                    question_id=qid,
                    page_num=page_num,
                    question_type=q.get('question_type', 'unknown'),
                    expected_answer=q.get('expected_answer', q.get('answer', '')),
                    score=q.get('score', 0),
                    choice_regions=choice_regions_pixel
                )
                page_regions[qid] = question_region
        
        if page_regions:
            self.question_regions[page_num] = page_regions
            if self.debug_mode:
                print(f"   📍 Converted {len(page_regions)} questions on page {page_num}")
    
    def get_page_image(self, page_num: int) -> Optional[np.ndarray]:
        """전처리된 페이지 이미지 반환"""
        if page_num in self.preprocessed_pages:
            return self.preprocessed_pages[page_num].page_image
        return None
    
    def get_question_region(self, page_num: int, qid: int) -> Optional[QuestionRegion]:
        """특정 문제의 선택지 영역 정보 반환"""
        # page_num은 0-based, question_regions는 1-based로 저장되어 있음
        page_num_1based = page_num + 1
        if page_num_1based in self.question_regions:
            return self.question_regions[page_num_1based].get(qid)
        return None
    
    def get_all_question_regions_on_page(self, page_num: int) -> Dict[int, QuestionRegion]:
        """특정 페이지의 모든 문제 영역 반환"""
        page_num_1based = page_num + 1
        return self.question_regions.get(page_num_1based, {})
    
    def get_detector(self, page_num: int) -> Optional[ArUcoDetector]:
        """페이지의 ArUco detector 반환"""
        if page_num in self.preprocessed_pages:
            return self.preprocessed_pages[page_num].aruco_detector
        return None
    
    def get_preprocess_summary(self) -> Dict:
        """전처리 결과 요약"""
        total_questions = sum(len(regions) for regions in self.question_regions.values())
        total_choice_regions = sum(
            sum(len(r.choice_regions) for r in regions.values())
            for regions in self.question_regions.values()
        )
        
        return {
            'total_pages': len(self.preprocessed_pages),
            'calibrated_pages': sum(1 for p in self.preprocessed_pages.values() if p.is_calibrated),
            'pages_with_regions': len(self.question_regions),
            'total_questions': total_questions,
            'total_choice_regions': total_choice_regions
        }
    
    def print_summary(self):
        """전처리 결과 요약 출력"""
        summary = self.get_preprocess_summary()
        print("\n" + "="*60)
        print("📊 PREPROCESSING SUMMARY")
        print("="*60)
        print(f"Total pages:           {summary['total_pages']}")
        print(f"Calibrated pages:      {summary['calibrated_pages']}")
        print(f"Pages with regions:    {summary['pages_with_regions']}")
        print(f"Total questions:       {summary['total_questions']}")
        print(f"Total choice regions:  {summary['total_choice_regions']}")
        print("="*60)


def preprocess_for_display(pdf_path: str, exam_data: Dict, page_num: int, zoom: float = 1.5) -> Tuple[Optional[np.ndarray], Optional[Dict], Optional[ArUcoDetector]]:
    """
    화면 표시용 단일 페이지 전처리 (기존 PDFImageViewer 호환)
    
    Returns:
        (page_image, choice_regions_pixel, detector)
    """
    preprocessor = ImagePreprocessor(zoom=zoom, debug_mode=False)
    
    # 임시로 전체 PDF 전처리 (또는 페이지 단위로 처리)
    doc = fitz.open(pdf_path)
    if page_num >= len(doc):
        doc.close()
        return None, None, None
    
    page = doc[page_num]
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    
    img_data = pix.tobytes("png")
    from PIL import Image
    import io
    pil_img = Image.open(io.BytesIO(img_data))
    page_image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    
    # ArUco 감지
    detector = ArUcoDetector()
    detector.detect_markers(page_image)
    
    required_markers = [0, 1, 2, 3]
    has_all_markers = all(mid in detector.detected_markers for mid in required_markers)
    
    if has_all_markers:
        detector.compute_perspective_transform(pix.width, pix.height)
    else:
        detector.compute_transform(pix.width, pix.height)
    
    # 선택지 영역 변환
    choice_regions = {}
    for q in exam_data.get('answers', []):
        pos = q.get('position', {})
        if pos.get('page', 1) != page_num + 1:
            continue
        
        for cr in q.get('choice_regions', []):
            norm = cr.get('normalized', {})
            if norm and detector.is_calibrated:
                try:
                    pixel_rect = detector.normalized_rect_to_pixel(norm)
                    choice_regions[cr.get('choice', '?')] = pixel_rect
                except:
                    pass
    
    doc.close()
    return page_image, choice_regions, detector