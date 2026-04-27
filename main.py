# main.py

from generator import ExamGenerator
from grader import ExamGrader

def main():
    # 1. 시험 생성
    generator = ExamGenerator()
    exam_data = generator.create_exam()

    # 2. 시험 채점
    grader = ExamGrader(exam_data)
    results = grader.grade_exam("scanned_exam.jpg")

    print(results)

if __name__ == "__main__":
    main()
