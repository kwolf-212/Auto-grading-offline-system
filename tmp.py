import fitz
import cv2
import json
import re
import numpy as np
import pytesseract
import easyocr

from collections import defaultdict

from PIL import Image
import matplotlib.pyplot as plt

# =========================================================
# CONFIG
# =========================================================

PDF_PATH = "20260506112241347_0001.pdf"
JSON_PATH = "2.json"

DPI = 300

DEBUG = True

# Windows:
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# =========================================================
# LOAD JSON
# =========================================================

with open(JSON_PATH, "r", encoding="utf-8") as f:
    exam_data = json.load(f)

answers = exam_data["answers"]
TOTAL_QUESTIONS = exam_data["total_questions"]

# =========================================================
# PDF -> IMAGE
# =========================================================

doc = fitz.open(PDF_PATH)

page = doc[0]

mat = fitz.Matrix(DPI / 72, DPI / 72)

pix = page.get_pixmap(matrix=mat)

img = Image.frombytes(
    "RGB",
    [pix.width, pix.height],
    pix.samples
)

img_np = np.array(img)

HEIGHT, WIDTH = img_np.shape[:2]

# =========================================================
# PREPROCESSING
# =========================================================

gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

binary = cv2.adaptiveThreshold(
    gray,
    255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,
    31,
    15
)

binary = cv2.medianBlur(binary, 3)

# =========================================================
# OCR
# =========================================================

reader = easyocr.Reader(['en'])

ocr_results = reader.readtext(binary)

# =========================================================
# QUESTION PATTERN
# =========================================================

QUESTION_PATTERN = r'[QO0][\s]*([0-9]{1,2})[\.\,:]?'

# =========================================================
# STORE ALL CANDIDATES
# =========================================================

question_candidates_by_id = defaultdict(list)

# =========================================================
# EASYOCR DETECTION
# =========================================================

for result in ocr_results:

    box, text, conf = result

    text = text.strip()

    match = re.search(QUESTION_PATTERN, text)

    if not match:
        continue

    try:

        qid = int(match.group(1))

        if not (1 <= qid <= TOTAL_QUESTIONS):
            continue

        xs = [p[0] for p in box]
        ys = [p[1] for p in box]

        x1 = int(min(xs))
        y1 = int(min(ys))
        x2 = int(max(xs))
        y2 = int(max(ys))

        candidate = {
            "question_id": qid,
            "bbox": [x1, y1, x2, y2],
            "center_x": (x1 + x2) / 2,
            "center_y": (y1 + y2) / 2,
            "source": "easyocr",
            "ocr_confidence": float(conf)
        }

        question_candidates_by_id[qid].append(candidate)

    except:
        pass

# =========================================================
# JSON ANCHOR RECOVERY OCR
# =========================================================

SCALE_X = WIDTH / 595
SCALE_Y = HEIGHT / 842

for item in answers:

    qid = item["question_id"]

    json_x = item["position"]["x"]
    json_y = item["position"]["y"]

    expected_x = int(json_x * SCALE_X)
    expected_y = int(json_y * SCALE_Y)

    x1 = max(0, expected_x - 120)
    y1 = max(0, expected_y - 70)

    x2 = min(WIDTH, expected_x + 320)
    y2 = min(HEIGHT, expected_y + 90)

    crop = binary[y1:y2, x1:x2]

    text = pytesseract.image_to_string(
        crop,
        config='--psm 7'
    )

    match = re.search(QUESTION_PATTERN, text)

    if not match:
        continue

    try:

        detected_qid = int(match.group(1))

        if detected_qid != qid:
            continue

        candidate = {
            "question_id": qid,
            "bbox": [x1, y1, x2, y2],
            "center_x": (x1 + x2) / 2,
            "center_y": (y1 + y2) / 2,
            "source": "json_anchor",
            "ocr_confidence": 0.7
        }

        question_candidates_by_id[qid].append(candidate)

        print(f"[RECOVERED] Q{qid}")

    except:
        pass

# =========================================================
# COLUMN SPLIT
# =========================================================

LEFT_IDS = []
RIGHT_IDS = []

for qid in range(1, TOTAL_QUESTIONS + 1):

    if qid <= 16:
        LEFT_IDS.append(qid)
    else:
        RIGHT_IDS.append(qid)

# =========================================================
# INTERPOLATION CANDIDATES
# =========================================================

def add_interpolation_candidates(id_list):

    existing = []

    for qid in id_list:

        if qid in question_candidates_by_id:

            cand = question_candidates_by_id[qid][0]

            existing.append((qid, cand))

    existing = sorted(existing, key=lambda x: x[0])

    for i in range(len(existing) - 1):

        current_id, current_q = existing[i]
        next_id, next_q = existing[i + 1]

        gap = next_id - current_id

        if gap <= 1:
            continue

        for missing_id in range(current_id + 1, next_id):

            ratio = (
                (missing_id - current_id)
                / gap
            )

            interp_y = int(
                current_q["center_y"]
                +
                ratio
                *
                (
                    next_q["center_y"]
                    -
                    current_q["center_y"]
                )
            )

            interp_x = int(current_q["center_x"])

            candidate = {
                "question_id": missing_id,
                "bbox": [
                    interp_x - 100,
                    interp_y - 40,
                    interp_x + 300,
                    interp_y + 40
                ],
                "center_x": interp_x,
                "center_y": interp_y,
                "source": "interpolated",
                "ocr_confidence": 0.3
            }

            question_candidates_by_id[missing_id].append(candidate)

            print(f"[INTERPOLATED] Q{missing_id}")

add_interpolation_candidates(LEFT_IDS)
add_interpolation_candidates(RIGHT_IDS)

# =========================================================
# LAYOUT SCORE
# =========================================================

def compute_layout_score(candidate, prev_q, next_q):

    score = 0

    y = candidate["center_y"]

    # -------------------------------------------------
    # OCR confidence
    # -------------------------------------------------

    score += candidate["ocr_confidence"] * 50

    # -------------------------------------------------
    # monotonic order
    # -------------------------------------------------

    if prev_q is not None:

        if y > prev_q["center_y"]:
            score += 80
        else:
            score -= 200

    if next_q is not None:

        if y < next_q["center_y"]:
            score += 80
        else:
            score -= 200

    # -------------------------------------------------
    # spacing consistency
    # -------------------------------------------------

    if prev_q is not None and next_q is not None:

        prev_gap = y - prev_q["center_y"]
        next_gap = next_q["center_y"] - y

        spacing_diff = abs(prev_gap - next_gap)

        score -= spacing_diff * 0.05

    # -------------------------------------------------
    # source prior
    # -------------------------------------------------

    source_bonus = {
        "easyocr": 20,
        "json_anchor": 15,
        "interpolated": 10
    }

    score += source_bonus.get(candidate["source"], 0)

    return score

# =========================================================
# SELECT BEST CANDIDATES
# =========================================================

final_questions = []

for qid in range(1, TOTAL_QUESTIONS + 1):

    candidates = question_candidates_by_id[qid]

    if len(candidates) == 0:
        continue

    prev_q = None
    next_q = None

    # previous
    for prev_id in range(qid - 1, 0, -1):

        if prev_id in question_candidates_by_id:

            prev_q = question_candidates_by_id[prev_id][0]
            break

    # next
    for next_id in range(qid + 1, TOTAL_QUESTIONS + 1):

        if next_id in question_candidates_by_id:

            next_q = question_candidates_by_id[next_id][0]
            break

    best_score = -999999
    best_candidate = None

    for candidate in candidates:

        score = compute_layout_score(
            candidate,
            prev_q,
            next_q
        )

        candidate["layout_score"] = score

        if score > best_score:

            best_score = score
            best_candidate = candidate

    final_questions.append(best_candidate)

    print(
        f"Q{qid} ->",
        best_candidate["source"],
        "score=",
        round(best_score, 2)
    )

# =========================================================
# SORT
# =========================================================

final_questions = sorted(
    final_questions,
    key=lambda x: (
        x["center_x"],
        x["center_y"]
    )
)

# =========================================================
# BUILD REGIONS
# =========================================================

def build_regions(question_list):

    regions = []

    for i, q in enumerate(question_list):

        qid = q["question_id"]

        x1, y1, x2, y2 = q["bbox"]

        top = max(0, y1 - 20)

        if i < len(question_list) - 1:
            bottom = question_list[i + 1]["bbox"][1] - 10
        else:
            bottom = HEIGHT - 20

        if q["center_x"] < WIDTH / 2:

            left = 0
            right = WIDTH // 2 - 20

        else:

            left = WIDTH // 2 + 20
            right = WIDTH - 1

        regions.append({
            "question_id": qid,
            "region": {
                "x1": int(left),
                "y1": int(top),
                "x2": int(right),
                "y2": int(bottom)
            },
            "source": q["source"],
            "layout_score": round(q["layout_score"], 2)
        })

    return regions

# =========================================================
# SPLIT AGAIN
# =========================================================

left_questions = []
right_questions = []

for q in final_questions:

    if q["center_x"] < WIDTH / 2:
        left_questions.append(q)
    else:
        right_questions.append(q)

left_questions = sorted(left_questions, key=lambda x: x["center_y"])
right_questions = sorted(right_questions, key=lambda x: x["center_y"])

left_regions = build_regions(left_questions)
right_regions = build_regions(right_questions)

all_regions = left_regions + right_regions

all_regions = sorted(
    all_regions,
    key=lambda x: x["question_id"]
)

# =========================================================
# VISUALIZATION
# =========================================================

vis = img_np.copy()

for item in all_regions:

    qid = item["question_id"]

    region = item["region"]

    x1 = region["x1"]
    y1 = region["y1"]
    x2 = region["x2"]
    y2 = region["y2"]

    source = item["source"]

    if source == "easyocr":
        color = (0, 255, 0)

    elif source == "json_anchor":
        color = (255, 165, 0)

    else:
        color = (255, 0, 0)

    cv2.rectangle(
        vis,
        (x1, y1),
        (x2, y2),
        color,
        3
    )

    cv2.putText(
        vis,
        f"Q{qid}",
        (x1 + 10, y1 + 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        color,
        2
    )

# =========================================================
# SAVE JSON
# =========================================================

output = {
    "page": 1,
    "question_regions": all_regions
}

with open(
    "question_regions_final.json",
    "w",
    encoding="utf-8"
) as f:

    json.dump(output, f, indent=2)

# =========================================================
# SAVE VISUALIZATION
# =========================================================

cv2.imwrite(
    "question_regions_final.png",
    cv2.cvtColor(vis, cv2.COLOR_RGB2BGR)
)

# =========================================================
# SHOW
# =========================================================

plt.figure(figsize=(18, 24))

plt.imshow(vis)

plt.axis("off")

plt.show()

print("\n완료:")
print(" - question_regions_final.json")
print(" - question_regions_final.png")