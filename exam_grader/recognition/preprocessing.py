
import cv2
import numpy as np

def preprocess_digit(crop_img):

    # 그레이스케일
    gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)

    # 28x28로 resize
    resized = cv2.resize(gray, (28, 28))

    # 이진화 (숫자가 흰색, 배경 검은색)
    _, thresh = cv2.threshold(resized, 128, 255, cv2.THRESH_BINARY_INV)

    # 정규화 & 모델 입력 형태로 변환
    input_img = thresh.astype(np.float32) / 255.0
    input_img = input_img.reshape(1, 28, 28, 1)

    return input_img