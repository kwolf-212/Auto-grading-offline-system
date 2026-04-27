# teacher_review.py

def review_scores(results):
    for qid, score in results.items():
        print(f"Q{qid}: {score}")
        new_score = input("수정 점수 입력 (Enter=유지): ")

        if new_score.strip() != "":
            results[qid] = float(new_score)

    return results
