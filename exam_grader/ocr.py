# exam_grader/ocr.py

import pytesseract
from PIL import Image
import numpy as np
import cv2
from typing import List, Tuple

def ocr_from_region(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> str:
    """이미지의 특정 영역에서 OCR 수행"""
    
    x1, y1, x2, y2 = bbox
    cropped = image[y1:y2, x1:x2]

    gray = cv2.cvtColor(cropped, cv2.COLOR_BGR2GRAY)
    
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    pil_image = Image.fromarray(thresh)
    text = pytesseract.image_to_string(
        pil_image,
        config='--psm 10 --oem 3 -c tessedit_char_whitelist=123456789'
    )

    return text.strip()

def extract_numbers_from_ocr(text: str) -> List[int]:
    """OCR 텍스트에서 숫자만 추출"""
    import re
    numbers = re.findall(r'\d+', text)
    return [int(n) for n in numbers]