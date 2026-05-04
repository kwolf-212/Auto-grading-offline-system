# common/utils.py
import json
import tempfile
import qrcode
from typing import List
from reportlab.pdfgen import canvas


def generate_qr(data, filename="qr_code.png"):
    """QR 코드 생성"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=8,
        border=2,
    )
    qr.add_data(json.dumps(data) if not isinstance(data, str) else data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(filename)
    return filename


def wrap_text(text: str, max_width: float, font_size: int = 11, font_name: str = "Helvetica") -> List[str]:
    """텍스트 줄바꿈"""
    words = text.split()
    lines = []
    current_line = []
    
    temp_c = canvas.Canvas(tempfile.mktemp(suffix='.pdf'))
    temp_c.setFont(font_name, font_size)
    
    for word in words:
        current_line.append(word)
        test_line = ' '.join(current_line)
        text_width = temp_c.stringWidth(test_line, font_name, font_size)
        
        if text_width > max_width and len(current_line) > 1:
            current_line.pop()
            lines.append(' '.join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(' '.join(current_line))
    
    temp_c.save()
    return lines if lines else [text]


def normalize_answer(answer: str, case_sensitive: bool = False, ignore_whitespace: bool = True) -> str:
    """답안 정규화"""
    if ignore_whitespace:
        answer = ' '.join(answer.split())
    if not case_sensitive:
        answer = answer.lower()
    return answer.strip()


def calculate_score(correct_answer: str, student_answer: str, max_score: int,
                   case_sensitive: bool = False, ignore_whitespace: bool = True,
                   partial_credit: bool = True) -> float:
    """점수 계산 (단순 매칭)"""
    correct_norm = normalize_answer(correct_answer, case_sensitive, ignore_whitespace)
    student_norm = normalize_answer(student_answer, case_sensitive, ignore_whitespace)
    
    if correct_norm == student_norm:
        return float(max_score)
    elif partial_credit and student_norm:
        # 부분 점수 로직 (단순화)
        return max_score * 0.5
    return 0.0