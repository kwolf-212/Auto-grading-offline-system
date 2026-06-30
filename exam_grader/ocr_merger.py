
class AnswerExtractor:
    """검출된 영역에서 답안 추출"""
    
    def __init__(self, use_ocr: bool = True, omr_zoom: float = 3.4):
        self.use_ocr = use_ocr and (TESSERACT_AVAILABLE or EASYOCR_AVAILABLE)
        self.omr_zoom = omr_zoom
    
    def extract_answers(self, pdf_path: str, question_regions: Dict) -> tuple:
        """검출된 영역에서 답안 추출.

        Returns:
            (answers, region_texts, extract_debug) — extract_debug[qid]는 UI/로그용 메타데이터.
        """
        if not fitz:
            raise ImportError("PyMuPDF (fitz) is required")
        
        doc = fitz.open(pdf_path)
        answers = {}
        region_texts = {}
        extract_debug: Dict = {}
        
        print("\n📝 Extracting answers from regions...")
        
        for qid, info in sorted(question_regions.items()):
            page_num = info['page']
            region = info['region']
            qtype = info['question_type']
            
            page = doc[page_num]
            
            # 텍스트 추출
            text = page.get_text("text", clip=region)
            
            # OCR 추가
            if self.use_ocr and (not text or len(text.strip()) < 20):
                text = self._apply_ocr(page, region, text)
            
            region_texts[qid] = text.strip() if text else ""
            
            # 답안 파싱 (객관식/참거짓은 OMR 우선)
            answer = self._parse_answer(text, qtype)
            if qtype in ("Multiple Choice", "True/False"):
                answer, merge_dbg = self._merge_mc_answer(page, region, qtype, answer, text)
                extract_debug[qid] = merge_dbg
            else:
                extract_debug[qid] = {
                    "answer_channel": "text",
                    "region_text_len": len(region_texts[qid]),
                }
            answers[qid] = answer
            
            answer_preview = answer[:50] if answer else '(empty)'
            print(f"  Q{qid:2d}: '{answer_preview}'")
        
        doc.close()
        return answers, region_texts, extract_debug
    
    def _apply_ocr(self, page, region: fitz.Rect, existing_text: str) -> str:
        """OCR 적용하여 텍스트 보완"""
        try:
            zoom = 2.0
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, clip=region, alpha=False)
            
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            ocr_text = pytesseract.image_to_string(img, lang='eng+kor')
            
            if ocr_text and ocr_text.strip():
                if existing_text:
                    return existing_text + "\n" + ocr_text
                return ocr_text
        except Exception as e:
            pass
        
        return existing_text

    def _region_to_bgr(self, page, region: fitz.Rect) -> np.ndarray:
        """PDF 영역을 고해상도 BGR numpy로 렌더 (OMR 공용 `pdf_region_to_bgr` 위임)."""
        return pdf_region_to_bgr(page, region, zoom=self.omr_zoom)

    def _merge_mc_answer(
        self, page, region: fitz.Rect, qtype: str, text_answer: str, raw_text: str
    ) -> Tuple[str, Dict[str, Any]]:
        """OMR(필기 농도)과 OCR 파싱 결과를 결합. (최종 답, 디버그 dict)."""
        omr_dbg: Dict[str, Any] = {}
        try:
            bgr = self._region_to_bgr(page, region)
            omr_ans, conf, omr_dbg = omr_read_mc_tf_selection(bgr, qtype)
        except Exception:
            omr_ans, conf = "", 0.0

        ta = (text_answer or "").strip().lower()[:1]
        oa = (omr_ans or "").strip().lower()[:1]

        merge_source = "empty"
        if oa and ta and oa != ta:
            final = oa if conf >= 0.42 else ta
            merge_source = "omr_wins" if conf >= 0.42 else "ocr_wins_conflict"
        elif conf >= 0.30 and oa:
            final = oa
            merge_source = "omr"
        elif oa and conf >= 0.18 and not ta:
            final = oa
            merge_source = "omr_low_conf"
        elif ta:
            final = ta
            merge_source = "ocr"
        else:
            final = oa or ta
            merge_source = "omr_or_empty" if oa else "empty"

        return final, {
            "answer_channel": "image_primary",
            "omr_letter": oa,
            "omr_confidence": float(conf),
            "omr_detail": omr_dbg,
            "ocr_parsed_letter": ta,
            "merge_source": merge_source,
        }

    def _parse_answer(self, text: str, qtype: str) -> str:
        """텍스트에서 답안 파싱"""
        if not text:
            return ""
        
        text = text.strip()
        
        # Multiple Choice / True/False
        if qtype in ['Multiple Choice', 'True/False']:
            brackets = re.findall(r'\[([a-z])\]', text, re.IGNORECASE)
            if brackets:
                return brackets[-1].lower()
            
            match = re.search(r'Q?\d+\.\s*([A-Za-z])', text)
            if match:
                return match.group(1).lower()
            
            match = re.search(r'\b([A-Za-z])\b', text)
            if match:
                return match.group(1).lower()
        
        # Matching
        elif qtype == 'Matching':
            pairs = re.findall(r'(\d+)[→\-=](\w)', text)
            if pairs:
                return ';'.join([f"{p[0]}-{p[1].upper()}" for p in pairs])
            
            pairs = re.findall(r'(\d+)\s+([A-Z])', text)
            if pairs:
                return ';'.join([f"{p[0]}-{p[1]}" for p in pairs])
        
        # Ordering
        elif qtype in ['Ordering', 'Ordering/Ranking']:
            numbers = re.findall(r'\d+', text)
            if len(numbers) >= 3:
                return ','.join(numbers[:5])
        
        # Fill in the Blank
        elif qtype == 'Fill in the Blank':
            blanks = re.findall(r'______\s*([^\n]+)', text)
            if blanks:
                return ', '.join([b.strip() for b in blanks[:3]])
        
        # Calculation
        elif qtype == 'Calculation':
            match = re.search(r'Answer:\s*([\d\.]+)', text, re.IGNORECASE)
            if match:
                return match.group(1)
            match = re.search(r'=\s*([\d\.]+)', text)
            if match:
                return match.group(1)
        
        # Code
        elif qtype == 'Code Writing':
            match = re.search(r'def\s+(\w+)', text)
            if match:
                return match.group(1)
            match = re.search(r'class\s+(\w+)', text)
            if match:
                return match.group(1)
        
        # Short Answer
        elif qtype == 'Short Answer':
            lines = text.split('\n')
            if lines:
                first_line = lines[0].strip()
                if first_line:
                    return first_line[:100]
        
        return text[:100]