# ocr_module.py
import pytesseract

def recognize_text(image):
    text = pytesseract.image_to_string(image, lang='eng')
    return text.strip()

def recognize_choice(image):
    # 간단한 마킹 검출 (픽셀 밀도 기반)
    import numpy as np
    return "A" if np.mean(image) < 127 else "B"
