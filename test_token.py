# 사용 예시
import cv2
from exam_grader.omr import *

# 이미지 로드
img = cv2.imread("Q01_region_original.png")

# 방법 1: 시각화 이미지 저장
debug_info = visualize_token_segmentation_v2(
    img, 
    expected_letters=['a', 'b', 'c', 'd'],
    save_path="token_segmentation_output.png",
    show_debug=True
)

# 방법 2: 디버그 정보와 함께 감지 실행
# coords, debug = debug_detect_bracket_choices_v2(
#     img,
#     expected_letters=['a', 'b', 'c', 'd'],
#     save_path="debug_output.png",
#     show_plot=True
# )

# # 방법 3: 상세 디버그 정보만 출력
# coords, debug = detect_bracket_choices_v2_debug(
#     img,
#     expected_letters=['a', 'b', 'c', 'd'],
#     verbose=True
# )

# # 방법 4: 원본 감지 함수 (변경 없음)
# coords = detect_bracket_choices_v2(img)