import cv2
import numpy as np
import matplotlib.pyplot as plt

# =========================
# 이미지 로드
# =========================

img = cv2.imread("Q01_region_original.png")

if img is None:
    raise Exception("이미지 로드 실패")

orig = img.copy()

# =========================
# grayscale
# =========================

gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# =========================
# adaptive threshold
# =========================

th = cv2.adaptiveThreshold(
    gray,
    255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY_INV,
    11,
    2
)

# =========================
# morphology
# =========================

kernel = np.ones((2,2), np.uint8)

clean = cv2.morphologyEx(
    th,
    cv2.MORPH_OPEN,
    kernel
)

# =========================
# vertical projection
# =========================

projection = np.sum(clean > 0, axis=0)
projection = np.convolve(
    projection,
    np.ones(5)/5,
    mode='same'
)

# =========================
# projection threshold
# =========================

threshold = 1

segments = []

in_char = False
start = 0

for x in range(len(projection)):

    if projection[x] > threshold and not in_char:

        start = x
        in_char = True

    elif projection[x] <= threshold and in_char:

        end = x

        if end - start > 5:
            segments.append((start, end))

        in_char = False

# =========================
# 가까운 segment 병합
# =========================

merged = []

if len(segments) > 0:

    current = list(segments[0])

    for seg in segments[1:]:

        gap = seg[0] - current[1]

        # 토큰 내부 문자 간격
        if gap < 8:

            current[1] = seg[1]

        else:

            merged.append(tuple(current))
            current = list(seg)

    merged.append(tuple(current))

# =========================
# bounding box 계산
# =========================

token_boxes = []

for (x1, x2) in merged:

    col = clean[:, x1:x2]

    ys, xs = np.where(col > 0)

    if len(ys) == 0:
        continue

    y1 = np.min(ys)
    y2 = np.max(ys)

    token_boxes.append((x1, y1, x2-x1, y2-y1))

# =========================
# 결과 표시
# =========================

display = orig.copy()

for idx, (x, y, w, h) in enumerate(token_boxes):

    cv2.rectangle(
        display,
        (x, y),
        (x+w, y+h),
        (0,255,0),
        2
    )

    cv2.putText(
        display,
        f"T{idx}",
        (x, y-5),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255,0,0),
        2
    )

# =========================
# matplotlib 출력
# =========================

display_rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)

plt.figure(figsize=(12,4))
plt.imshow(display_rgb)
plt.title("Token Segmentation")
plt.axis("off")
plt.show()

# =========================
# 개별 토큰 출력
# =========================

for idx, (x, y, w, h) in enumerate(token_boxes):

    roi = orig[y:y+h, x:x+w]

    roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)

    plt.figure(figsize=(2,2))
    plt.imshow(roi_rgb)
    plt.title(f"Token {idx}")
    plt.axis("off")

plt.show()