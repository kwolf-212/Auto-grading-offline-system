import numpy as np
from typing import List, Tuple

from .model_manager import ModelManager
from .preprocessing import preprocess_digit
from .debug import RecognitionDebugger

class DigitRecognizer:

    def __init__(self):

        self.model = ModelManager.get_digit_model()
        self.debug = RecognitionDebugger()

    def recognize(self, crop):

        img = preprocess_digit(crop)
        pred = self.model.predict(img)
        digit = int(np.argmax(pred))
        confidence = float(np.max(pred))

        return digit, confidence
    
    def recognize_boxes(self, crops: List[Tuple[str, np.ndarray]]):

        digits = []
        confidences = []

        for _, crop in crops:
            
            #   debug
            self.debug.save_crop(crop, "crop")

            digit, confidence = self.recognize(crop)
            digits.append(digit)
            confidences.append(confidence)

        return digits, confidences