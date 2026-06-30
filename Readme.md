# Auto-grading Offline System

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> A standalone offline system for automated exam paper generation and grading, featuring QR code/Aruco marker verification and an intuitive GUI.

## 🎯 Overview

The **Auto-grading Offline System** is a comprehensive Python-based solution designed to streamline the entire examination workflow—from generating customizable question papers to automatically grading scanned answer sheets—all without requiring an internet connection. This system is ideal for educational institutions, training centers, and organizations that need a secure, self-contained assessment tool.

## ✨ Key Features

- **Offline Operation** – Fully functional without internet connectivity, ensuring data privacy and security.
- **Exam Paper Generator** – Create structured question papers with embedded QR/Aruco markers for easy identification.
- **Automated Grading** – Grade scanned answer sheets with precision, supporting multiple question types.
- **GUI-Based Interaction** – User-friendly graphical interfaces for both paper generation and grading.
- **Database Management** – Built-in SQLite database for storing questions, answers, and results.
- **PDF Calibration** – Tools to calibrate scanned documents for accurate grading.
- **Debug & Testing** – Dedicated modules for system testing and debugging.

## 🚀 Getting Started

### Prerequisites

- **Python** 3.8 or higher
- Required Python packages (see installation)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/kwolf-212/Auto-grading-offline-system.git
   cd Auto-grading-offline-system
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running the Application

- **Generate exam papers:**
  ```bash
  python main.py
  ```
- **Grade answer sheets:**
  ```bash
  python main.py --grader
  ```

## 📁 Project Structure

```
├── common/                 # Shared utilities and helpers
├── exam_generator/         # Exam paper generation engine
├── exam_grader/            # Answer sheet grading engine
├── sample_data/            # Sample exams and templates
├── ui/                     # GUI components (toolbars, windows)
├── database_manager.py     # SQLite database interface
├── exam_generator_app.py   # Generator GUI launcher
├── exam_grader_app.py      # Grader GUI launcher
├── main.py                 # Main entry point
├── test_grader_engine.py   # Unit tests for grading
├── exam_questions.db       # SQLite database file
```

## 🛠️ How It Works

### 1. Exam Paper Generation
   - **Design** – Create custom question papers with multiple-choice, true/false, or short-answer questions.
   - **Markers** – Embed QR codes or Aruco markers on each paper for automated identification during grading.
   - **Output** – Generate high-quality PDFs ready for printing.

### 2. Grading Process
   - **Scan** – Digitize completed answer sheets (PDF or image).
   - **Calibrate** – Use `pdf_calibration.py` to align scanned documents.
   - **Grade** – The `exam_grader` engine processes each sheet, matching student answers against the answer key.
   - **Results** – Scores are stored in the database and can be exported.

### 3. Database
   - SQLite database (`exam_questions.db`) manages questions, answer keys, student responses, and grades.
   - `database_manager.py` provides a simple CRUD interface.

## 🧪 Testing

Run the grading engine tests to ensure everything is working:
```bash
python test_grader_engine.py
```
Debug modules under `debug/digits/` can be used for isolated testing of image recognition components.

## 📄 Sample Data

The `sample_data/` folder includes:
- `Midterm_Examination_answer_sheet.json` – Sample answer key in JSON.
- `Midterm_Examination_answer_sheet.pdf` – Corresponding printable answer sheet.
- `20260514174014927_0001.pdf` – Example scanned response.

## 🤝 Contributing

Contributions are welcome! Please follow these steps:
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -m 'Add YourFeature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📧 Contact

**Project Maintainer:** [kwolf-212](https://github.com/kwolf-212)  
For any queries or support, please open an issue on GitHub.

---

**Happy Grading!** 📚✨