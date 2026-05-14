# exam_generator/answer_sheet_engine.py

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import black
from reportlab.pdfbase import pdfmetrics

from common.constants import PAGE_SIZES

class AnswerSheetEngine:
    """답안지 PDF 생성 엔진 - 영역 정보 저장 기능 포함"""
    
    def __init__(self, questions, settings):
        self.questions = questions
        self.settings = settings


    def _generate_aruco_image(self, marker_id, size=120):
        """
        ArUco 마커 이미지를 생성합니다.
        
        Args:
            marker_id: 마커 ID (0-49)
            size: 생성할 이미지 크기 (픽셀)
        
        Returns:
            ImageReader: ReportLab에서 사용 가능한 이미지 객체
        """
        import cv2
        import numpy as np
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        import io
        
        dictionary = cv2.aruco.getPredefinedDictionary(
            cv2.aruco.DICT_4X4_50
        )
        
        marker = cv2.aruco.generateImageMarker(
            dictionary,
            marker_id,
            size
        )
        
        # ArUco 마커는 흑백 이미지이므로, 필요시 컬러로 변환
        if len(marker.shape) == 2:
            marker = cv2.cvtColor(marker, cv2.COLOR_GRAY2RGB)
        
        pil = Image.fromarray(marker)
        
        buf = io.BytesIO()
        pil.save(buf, format='PNG')
        buf.seek(0)
        
        return ImageReader(buf)


    def _draw_aruco_markers(self, c, width, height):
        """
        PDF 페이지 네 모서리에 ArUco 마커를 삽입합니다.
        
        Args:
            c: ReportLab canvas 객체
            width: 페이지 너비
            height: 페이지 높이
        """
        try:
            # 마커 크기 (포인트/픽셀 단위)
            marker_size = 28
            
            # 각 모서리의 마커 ID와 위치 (왼쪽 하단이 원점)
            # ID 0: 좌측 상단 모서리 (또는 필요에 따라 조정)
            # ID 1: 우측 상단 모서리
            # ID 2: 좌측 하단 모서리
            # ID 3: 우측 하단 모서리
            positions = [
                (0, 10, height - marker_size - 10),      # 좌측 상단
                (1, width - marker_size - 10, height - marker_size - 10),  # 우측 상단
                (2, 10, 10),                             # 좌측 하단
                (3, width - marker_size - 10, 10),       # 우측 하단
            ]
            
            for marker_id, mx, my in positions:
                img = self._generate_aruco_image(marker_id, size=120)
                
                c.drawImage(
                    img,
                    mx,
                    my,
                    marker_size,
                    marker_size,
                    preserveAspectRatio=True
                )
                
        except Exception as e:
            # ArUco 마커 생성 실패 시 자동으로 건너뛰기 (에러 무시)
            # 로깅이 필요하다면 여기에 추가 가능
            pass

    def _draw_metadata_qr(
        self,
        c,
        width,
        height,
        page_num
    ):
        """
        페이지에 QR 코드 메타데이터를 삽입합니다.
        
        Args:
            c: ReportLab canvas 객체
            width: 페이지 너비
            height: 페이지 높이
            page_num: 현재 페이지 번호
        """
        try:
            import qrcode
            import json
            from reportlab.lib.utils import ImageReader
            import io
            
            # 메타데이터 구성
            metadata = {
                "exam_id": self.settings.get("exam_id", "unknown"),
                "version": self.settings.get("version", "A"),
                "page": page_num,
                "questions": len(self.questions),
                "timestamp": self.settings.get("timestamp", ""),  # 생성 시간
                "layout_hash": self.settings.get("layout_hash", "")  # 레이아웃 해시 (선택사항)
            }
            
            # QR 코드 생성
            qr = qrcode.QRCode(
                version=1,  # QR 코드 버전 (1-40, 작을수록 간단)
                error_correction=qrcode.constants.ERROR_CORRECT_M,  # 오류 정정 수준
                box_size=4,  # 각 박스의 픽셀 수
                border=2,    # 테두리 두께
            )
            qr.add_data(json.dumps(metadata, ensure_ascii=False))
            qr.make(fit=True)
            
            # PIL Image로 변환
            qr_image = qr.make_image(fill_color="black", back_color="white")
            
            # BytesIO에 저장
            buf = io.BytesIO()
            qr_image.save(buf, format='PNG')
            buf.seek(0)
            
            # QR 코드 크기 및 위치 (오른쪽 하단에 배치)
            qr_size = 55
            margin_bottom = 15  # 하단 여백
            
            # 하단 중앙에 배치 (ArUco 마커와 겹치지 않음)
            center_x = (width - qr_size) / 2
            
            c.drawImage(
                ImageReader(buf),
                center_x,
                margin_bottom,
                qr_size,
                qr_size
            )
            
        except Exception as e:
            # QR 코드 생성 실패 시 무시 (로깅 필요시 추가)
            # print(f"QR generation failed for page {page_num}: {e}")
            pass

    def generate_answer_sheet(self, file_path, position_callback=None, choice_region_callback=None):
        """
        답안지 PDF 생성
        
        Args:
            file_path: 저장할 파일 경로
            position_callback: 문제 위치 정보를 저장할 콜백 함수 (question_id, x, y, page)
            choice_region_callback: 선택지 영역 정보를 저장할 콜백 함수 
                (question_id, choice_letter, x, y, w, h, page, choice_type)
        """
        if not self.questions:
            return

        page_size = PAGE_SIZES.get(self.settings.get('page_size', 'A4'), A4)
        margin = 35
        col_gap = 20
        col_width = (page_size[0] - (margin * 2) - col_gap) // 2
        
        base_font_size = 12
        line_height = int(self.settings.get('line_spacing', 1.5) * base_font_size)
        small_line_height = line_height - 3
        
        c = canvas.Canvas(file_path, pagesize=page_size)
        width, height = page_size

        # 타이틀
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(width/2, height - 35, "ANSWER SHEET")
        c.setFont("Helvetica", 10)
        c.drawCentredString(width/2, height - 55, f"{self.settings.get('exam_title', 'Exam')}")

        y = height - 85
        
        # Student info
        if self.settings.get('include_student_info', True):
            c.setFont("Helvetica", 10)
            name = self.settings.get('student_name', '') or "_________________________"
            student_id = self.settings.get('student_id', '') or "_________________________"
            dept = self.settings.get('department', '') or "_________________________"
            
            total_width = width - (margin * 2)
            col_width_student = total_width // 3
            
            x1 = margin
            x2 = margin + col_width_student
            x3 = margin + (col_width_student * 2)
            
            c.drawString(x1, y, f"Name: {name}")
            c.drawString(x2, y, f"ID: {student_id}")
            c.drawString(x3, y, f"Dept: {dept}")
            
            y -= 25
        else:
            y -= 15

        y -= 15

        c.setFont("Helvetica-Bold", 11)
        c.drawString(margin, y, "Write your answers below:")
        y -= line_height

        c.setFont("Helvetica", base_font_size)
        
        # current_page 변수를 여기서 정의 (1페이지부터 시작)
        current_page = 1
        
        # 페이지에 ArUco 마커 추가
        self._draw_aruco_markers(c, width, height)

        # QR 메타데이터 추가 (current_page가 정의된 후)
        self._draw_metadata_qr(c, width, height, current_page)

        # Two Column 배치
        left_x = margin
        right_x = margin + col_width + col_gap
        
        # 각 질문의 필요 높이 계산
        question_heights = []
        for q in self.questions:
            height_needed = self._calculate_answer_sheet_height(q, col_width, line_height, small_line_height)
            question_heights.append(height_needed)
        
        # 왼쪽 컬럼에 배치할 질문 결정
        left_indices = []
        right_indices = []
        current_height = 0
        page_height = height - margin - 100
        
        for idx, q_height in enumerate(question_heights):
            if current_height + q_height <= page_height:
                left_indices.append(idx)
                current_height += q_height + small_line_height
            else:
                right_indices.append(idx)
        
        # 나머지 질문들을 오른쪽 컬럼에 순차적으로 배치
        all_pages = []
        current_page_indices = []
        current_page_height = 0
        
        for idx in right_indices:
            q_height = question_heights[idx]
            if current_page_height + q_height <= page_height:
                current_page_indices.append(idx)
                current_page_height += q_height + small_line_height
            else:
                if current_page_indices:
                    all_pages.append(current_page_indices)
                current_page_indices = [idx]
                current_page_height = q_height + small_line_height
        
        if current_page_indices:
            all_pages.append(current_page_indices)
        
        # 첫 페이지: 왼쪽 컬럼 그리기
        current_y_left = y
        for idx in left_indices:
            if current_y_left < margin + 50:
                c.showPage()
                current_page += 1
                self._draw_aruco_markers(c, width, height)  # 새 페이지에 마커 추가
                self._draw_metadata_qr(c, width, height, current_page)
                current_y_left = height - margin
                c.setFont("Helvetica", base_font_size)
            
            # 문제 위치 정보 저장
            if position_callback:
                q = self.questions[idx]
                                
                # 정규화 좌표로 변환 (너비/높이는 0으로 설정)
                nx, ny, _, _ = self._get_aruco_normalized_coordinates(c, left_x, current_y_left, 0, 0)
                
                position_callback(q['id'], nx, ny, current_page)
            
            # 선택지 영역 정보 저장
            current_y_left = self._draw_answer_sheet_question_with_choice_regions(
                c, self.questions[idx], left_x, current_y_left, col_width,
                line_height, small_line_height, width, margin, base_font_size,
                current_page, choice_region_callback
            )
            current_y_left -= small_line_height
        
        # 오른쪽 컬럼: 여러 페이지에 걸쳐 그리기
        for page_idx, page_indices in enumerate(all_pages):
            if page_idx > 0:
                c.showPage()
                current_page += 1
                self._draw_aruco_markers(c, width, height)  # 새 페이지에 마커 추가
                self._draw_metadata_qr(c, width, height, current_page)
            
            current_y_right = y
            for idx in page_indices:
                if current_y_right < margin + 50:
                    c.showPage()
                    current_page += 1
                    self._draw_aruco_markers(c, width, height)  # 새 페이지에 마커 추가
                    self._draw_metadata_qr(c, width, height, current_page)
                    current_y_right = height - margin
                    c.setFont("Helvetica", base_font_size)
                
                # 문제 위치 정보 저장
                if position_callback:
                    q = self.questions[idx]
                    y_from_top = height - current_y_right
                    position_callback(q['id'], right_x, y_from_top, current_page)
                
                # 선택지 영역 정보 저장
                current_y_right = self._draw_answer_sheet_question_with_choice_regions(
                    c, self.questions[idx], right_x, current_y_right, col_width,
                    line_height, small_line_height, width, margin, base_font_size,
                    current_page, choice_region_callback
                )
                current_y_right -= small_line_height

        c.save()
        return current_page
    
    def _get_aruco_normalized_coordinates(self, c, x_abs, y_abs, w_abs, h_abs):
        """
        ArUco 마커를 기준으로 한 정규화 좌표계로 변환합니다.
        
        [Aruco 0] (좌측 상단) -> (0, 0)
        [Aruco 3] (우측 하단) -> (1, 1)
        
        Args:
            c: ReportLab canvas 객체
            x_abs: 절대 X 좌표 (px) - 페이지 좌측 기준
            y_abs: 절대 Y 좌표 (px) - 페이지 하단 기준
            w_abs: 절대 너비 (px)
            h_abs: 절대 높이 (px)
        
        Returns:
            tuple: (nx, ny, nw, nh) 정규화된 좌표 (0~1 범위)
        """
        page_w, page_h = c._pagesize
        
        # ArUco 마커의 절대 좌표 (px)
        marker_size = 28
        margin = 10
        
        # [Aruco 0] 좌측 상단 (원점)
        aruco0_x = margin
        aruco0_y = page_h - margin - marker_size  # 상단 기준 Y
        
        # [Aruco 3] 우측 하단 (1, 1)
        aruco3_x = page_w - margin - marker_size
        aruco3_y = margin  # 하단 기준 Y
        
        # ArUco 마커 중심 좌표 계산
        center_offset = marker_size / 2
        aruco0_center_x = aruco0_x + center_offset
        aruco0_center_y = aruco0_y + center_offset
        aruco3_center_x = aruco3_x + center_offset
        aruco3_center_y = aruco3_y + center_offset
        
        # 실제 사용 가능한 영역의 너비와 높이 (ArUco 마커 중심 간 거리)
        usable_width = aruco3_center_x - aruco0_center_x
        usable_height = aruco0_center_y - aruco3_center_y
        
        # 정규화 좌표 계산 (0~1)
        # x 좌표: 좌측 상단 마커를 기준으로
        nx = (x_abs - aruco0_center_x) / usable_width
        
        # y 좌표: y_abs는 하단 기준이므로 상단 기준으로 변환 후 계산
        ny = (aruco0_center_y - y_abs) / usable_height
        
        # 너비와 높이도 정규화
        nw = w_abs / usable_width
        nh = h_abs / usable_height
        
        return nx, ny, nw, nh

    # =========================================================
    # callback emit
    # =========================================================
    def _emit_region_callback(
        self,
        c,
        callback,
        question_id,
        region_id,
        region_type,  # 이 매개변수는 유지하지만 콜백에 전달하지 않음
        x,
        y_bottom,
        w,
        h
    ):
        if callback is None:
            return

        # ArUco 기준 정규화 좌표로 변환
        nx, ny, nw, nh = self._get_aruco_normalized_coordinates(c, x, y_bottom, w, h)
        
        # region_type과 absolute_info 없이 6개 인자만 전달
        callback(
            question_id,
            region_id,
            nx,      # 정규화 X (0~1, ArUco 기준)
            ny,      # 정규화 Y (0~1, ArUco 기준)
            nw,      # 정규화 너비
            nh       # 정규화 높이
        )


    # =========================================================
    # token layout tracker
    # =========================================================

    # def _track_text_token(
    #     self,
    #     c,
    #     token_text,
    #     current_x,
    #     baseline_y,
    #     font_name,
    #     font_size
    # ):
    #     """
    #     현재 token bbox 계산 후
    #     다음 x 위치 반환
    #     """

    #     bbox = self._measure_text_bbox(
    #         c,
    #         token_text,
    #         current_x,
    #         baseline_y,
    #         font_name,
    #         font_size
    #     )

    #     token_w = c.stringWidth(
    #         token_text,
    #         font_name,
    #         font_size
    #     )

    #     next_x = current_x + token_w

    #     return bbox, next_x

    def _draw_answer_sheet_question_with_choice_regions(
        self, c, q, x, y, col_width, line_height, small_line_height, 
        width, margin, base_font_size, current_page, choice_region_callback
    ):
        """단일 답안지 질문을 그리고 선택지 영역 정보 저장 (OMR 사각 버블 스타일)"""
        
        qtype = q["type"]
        font_name = "Helvetica"
        c.setFont(font_name, base_font_size)
        
        # 텍스트 높이 계산 (폰트의 실제 높이)
        from reportlab.pdfbase import pdfmetrics
        ascent, descent = pdfmetrics.getAscentDescent(font_name)
        font_height = (ascent - descent) / 1000.0 * base_font_size
        text_center_y = y + (font_height / 2) - 2  # 텍스트의 중앙 Y 좌표
        
        # 버블 그리기 함수
        def draw_bubble(x, y_center, size=12, line_width=1.5):
            """사각 버블 그리기 (y_center는 버블의 중앙 Y 좌표)"""
            c.setLineWidth(line_width)
            bubble_y = y_center - size/2
            c.rect(x, bubble_y, size, size)
            c.setLineWidth(1.0)
        
        # 밑줄 그리기 함수
        def draw_underline(x, y_baseline, width, line_width=1.0):
            """밑줄 그리기"""
            c.setLineWidth(line_width)
            underline_y = y_baseline - 3  # 텍스트 기준선 아래 3pt
            c.line(x, underline_y, x + width, underline_y)
            c.setLineWidth(1.0)

        if qtype == 0:  # Multiple Choice - OMR 스타일 사각 버블
            c.setFont(font_name, base_font_size)
            q_text = f"Q{q['id']}."
            choices = q.get("choices", [])
            
            # 질문 번호 출력
            c.drawString(x, y, q_text)
            
            # 버블 크기 및 간격 설정
            bubble_size = 12
            bubble_spacing = 45
            text_spacing = 5
            
            start_x = x + c.stringWidth(q_text, font_name, base_font_size) + 15
            
            current_x = start_x
            for i in range(len(choices)):
                letter = chr(97 + i)
                
                # 버블 그리기 (텍스트 중앙에 맞춤)
                draw_bubble(current_x, text_center_y, bubble_size, 1.5)
                
                # 선택지 문자 출력 (버블 오른쪽, 텍스트 기준선 y 사용)
                c.drawString(current_x + bubble_size + text_spacing, y, letter.upper())
                
                # 영역 정보 저장
                if choice_region_callback:
                    bubble_y = text_center_y - bubble_size/2
                    nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                        c, current_x, bubble_y, bubble_size, bubble_size
                    )
                    choice_region_callback(q['id'], letter, nx, ny, nw, nh)
                
                current_x += bubble_spacing
            
            y -= line_height
            y -= 5
        
        elif qtype == 1:  # True/False
            q_text = f"Q{q['id']}."
            c.drawString(x, y, q_text)
            
            bubble_size = 12
            bubble_spacing = 45
            text_spacing = 5
            
            start_x = x + c.stringWidth(q_text, font_name, base_font_size) + 15
            
            letters = ['T', 'F']
            current_x = start_x
            for letter in letters:
                draw_bubble(current_x, text_center_y, bubble_size, 1.5)
                c.drawString(current_x + bubble_size + text_spacing, y, letter)
                
                if choice_region_callback:
                    bubble_y = text_center_y - bubble_size/2
                    nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                        c, current_x, bubble_y, bubble_size, bubble_size
                    )
                    choice_region_callback(q['id'], letter.lower(), nx, ny, nw, nh)
                
                current_x += bubble_spacing
            
            y -= line_height
        
        elif qtype == 2 or qtype == 3:  # Fill in the Blank, Short Answer - 밑줄만 그리기
            q_text = f"Q{q['id']}."
            c.drawString(x, y, q_text)
            
            # 밑줄 길이 계산
            blank_width = col_width - 30  # 컬럼 너비의 대부분 사용
            underline_x = x + c.stringWidth(q_text, font_name, base_font_size) + 10
            
            # 밑줄 그리기
            draw_underline(underline_x, y, blank_width, 1.5)
            
            # 영역 정보 저장
            if choice_region_callback:
                underline_height = 3
                underline_y = y - 3 - underline_height
                nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                    c, underline_x, underline_y, blank_width, underline_height
                )
                choice_region_callback(q['id'], "blank", nx, ny, nw, nh)
            
            y -= line_height
        
        elif qtype == 4:  # Essay
            c.setFont("Helvetica", base_font_size)
            c.drawString(x, y, f"Q{q['id']}.")
            y -= int(line_height * 0.7)
            essay_lines = min(self.settings.get('essay_lines', 6), 6)
            
            # 에세이 영역 정보 저장
            if choice_region_callback:
                essay_w = col_width - 10
                essay_h = essay_lines * line_height
                essay_x = x
                essay_y = y - essay_h
                nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                    c, essay_x, essay_y, essay_w, essay_h
                )
                choice_region_callback(q['id'], 'essay', nx, ny, nw, nh)
            
            for i in range(essay_lines):
                c.line(x, y, x + col_width - 10, y)
                y -= line_height
            y -= 5
        
        elif qtype == 5:  # Matching - 단순히 1→□, 2→□, ... 형식
            pairs = q.get("matching_pairs", [])
            
            # 질문 텍스트 표시
            q_text = f"Q{q['id']}."
            c.drawString(x, y, q_text)
            start_x = x + c.stringWidth(q_text, font_name, base_font_size) + 15
            current_match_x = start_x
            items_per_row = 5  # 한 줄에 5개씩 표시
            bubble_size = 12
            text_spacing = 3
            
            for i in range(len(pairs)):
                match_text = f"{i+1}→"
                text_width = c.stringWidth(match_text, font_name, base_font_size)
                
                # 텍스트 출력
                c.drawString(current_match_x, y, match_text)
                
                # 버블 위치 (텍스트 오른쪽)
                bubble_x = current_match_x + text_width + text_spacing
                draw_bubble(bubble_x, text_center_y, bubble_size, 1.5)
                
                # 영역 정보 저장
                if choice_region_callback:
                    bubble_y = text_center_y - bubble_size/2
                    nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                        c, bubble_x, bubble_y, bubble_size, bubble_size
                    )
                    choice_region_callback(q['id'], str(i+1), nx, ny, nw, nh)
                
                # 다음 항목 위치 계산
                item_width = text_width + bubble_size + text_spacing + 12
                current_match_x += item_width
                
                # 줄바꿈 처리
                if (i + 1) % items_per_row == 0 and (i + 1) < len(pairs):
                    y -= small_line_height
                    current_match_x = start_x
            
            y -= small_line_height
        
        elif qtype == 6:  # Ordering - 간단히 □, □, □ 형태
            items = q.get("ordering_items", [])
            
            # 질문 텍스트 표시
            q_text = f"Q{q['id']}."
            c.drawString(x, y, q_text)
            
            # 버블 크기 및 간격
            bubble_size = 12
            bubble_spacing = 32
            text_spacing = 3
            
            # 질문 텍스트 너비 계산
            current_x = x + c.stringWidth(q_text, font_name, base_font_size) + 15
            
            # 항목 개수만큼 버블 표시 (기본 3개, 최대 8개)
            num_bubbles = len(items) if items else 3
            if num_bubbles > 8:
                num_bubbles = 8
            
            for i in range(num_bubbles):
                # 버블 그리기
                draw_bubble(current_x, text_center_y, bubble_size, 1.5)
                
                # 영역 정보 저장
                if choice_region_callback:
                    bubble_y = text_center_y - bubble_size/2
                    nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                        c, current_x, bubble_y, bubble_size, bubble_size
                    )
                    choice_region_callback(q['id'], str(i+1), nx, ny, nw, nh)
                
                current_x += bubble_spacing
                
                # 쉼표 표시 (마지막 항목 제외)
                if i < num_bubbles - 1:
                    comma_x = current_x - bubble_spacing + bubble_size + text_spacing
                    c.drawString(comma_x, y, ",")
            
            y -= line_height
        
        elif qtype == 7:  # Code
            c.setFont("Helvetica", base_font_size)
            c.drawString(x, y, f"Q{q['id']}. Write your code below:")
            y -= line_height
            
            answer_key = q.get('answer', '')
            if answer_key:
                answer_lines = len(answer_key.split('\n'))
                code_lines = max(3, answer_lines + 2)
            else:
                code_lines = 5
            
            line_spacing = 14
            code_height = min(code_lines * line_spacing + 10, 250)
            
            rect_x = x
            rect_y = y - code_height
            rect_width = col_width - 10
            rect_height = code_height
            
            # 사각형 테두리 굵게
            c.setLineWidth(1.5)
            c.rect(rect_x, rect_y, rect_width, rect_height)
            c.setLineWidth(1.0)
            
            # 코드 영역 정보 저장
            if choice_region_callback:
                nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                    c, rect_x, rect_y, rect_width, rect_height
                )
                choice_region_callback(q['id'], 'code', nx, ny, nw, nh)
            
            c.setFont("Helvetica", 7)
            top_y = rect_y + rect_height
            for i in range(1, min(code_lines + 1, 16)):
                line_y = top_y - (i * line_spacing) + 5
                if line_y > rect_y + 5:
                    c.drawString(rect_x + 5, line_y, f"{i}.")
            
            y = rect_y - 10
            c.setFont("Helvetica", base_font_size)
        
        elif qtype == 8:  # Calculation
            c.drawString(x, y, f"Q{q['id']}. Work:")
            y -= line_height
            for i in range(3):
                c.line(x, y, x + col_width - 10, y)
                y -= line_height
            y -= small_line_height
            
            # Answer with bubble
            c.drawString(x, y, "Answer: ")
            answer_line_x = x + 45
            text_y = y
            
            # 사각 버블 그리기
            bubble_size = 12
            bubble_x = answer_line_x
            bubble_y = text_y - base_font_size + 2
            
            c.setLineWidth(1.5)
            c.rect(bubble_x, bubble_y, bubble_size, bubble_size)
            c.setLineWidth(1.0)
            
            # 답안 영역 정보 저장
            if choice_region_callback:
                nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                    c, bubble_x, bubble_y, bubble_size, bubble_size
                )
                choice_region_callback(q['id'], 'answer', nx, ny, nw, nh)
            
            y -= small_line_height
        
        else:
            c.drawString(x, y, f"Q{q['id']}.   ____________________")
            
            if choice_region_callback:
                base_width = c.stringWidth(f"Q{q['id']}.   ", font_name, base_font_size)
                line_width = c.stringWidth("____________________", font_name, base_font_size)
                nx, ny, nw, nh = self._get_aruco_normalized_coordinates(
                    c, x + base_width, y - base_font_size + 2, line_width, base_font_size
                )
                choice_region_callback(q['id'], 'answer', nx, ny, nw, nh)
            
            y -= line_height
        
        return y
    
    def _calculate_answer_sheet_height(self, q, col_width, line_height, small_line_height):
        """질문이 차지하는 높이 계산"""
        qtype = q["type"]
        total_height = line_height
        
        if qtype == 0:
            total_height += small_line_height + 5
        elif qtype == 1:
            total_height += 0
        elif qtype == 2:
            total_height += 0
        elif qtype == 3:
            total_height += 0
        elif qtype == 4:
            essay_lines = min(self.settings.get('essay_lines', 6), 6)
            total_height += int(line_height * 0.7)
            total_height += essay_lines * line_height
            total_height += 5
        elif qtype == 5:
            pairs = q.get("matching_pairs", [])
            total_height += line_height
            lines_needed = (len(pairs) + 3) // 4
            total_height += lines_needed * small_line_height
        elif qtype == 6:
            total_height += 0
        elif qtype == 7:
            total_height += line_height
            answer_key = q.get('answer', '')
            if answer_key:
                answer_lines = len(answer_key.split('\n'))
                code_lines = max(3, answer_lines + 2)
            else:
                code_lines = 5
            code_height = min(code_lines * 15, 250)
            total_height += code_height + 10
        elif qtype == 8:
            total_height += line_height
            total_height += line_height * 3
            total_height += small_line_height
        
        return total_height