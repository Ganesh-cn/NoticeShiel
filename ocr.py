"""
NoticeShield - OCR and Content Verification Module
Extracts visible text from forwarded notices, screenshots, and PDFs using EasyOCR and PyMuPDF.
Performs semantic field comparison against official canonical database records to detect tampering,
such as altered dates, changed venues, or forged instructions.
"""

import os
import re
import difflib
import fitz  # PyMuPDF
import cv2
import numpy as np

# EasyOCR singleton reader instance
_easyocr_reader = None
MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'easyocr_models')

def get_easyocr_reader():
    """Lazily loads and caches the EasyOCR reader using the workspace models directory."""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            os.makedirs(MODELS_DIR, exist_ok=True)
            _easyocr_reader = easyocr.Reader(
                ['en'],
                gpu=False,
                verbose=False,
                model_storage_directory=MODELS_DIR,
                user_network_directory=MODELS_DIR
            )
        except Exception as e:
            print(f"Warning: EasyOCR could not be initialized: {e}")
            _easyocr_reader = None
    return _easyocr_reader

def clean_text(text: str) -> str:
    """Normalizes whitespace and replaces unicode dashes and special characters."""
    if not text:
        return ""
    text = (text.replace('\xa0', ' ')
                .replace('’', "'")
                .replace('“', '"')
                .replace('”', '"')
                .replace('–', '-')
                .replace('—', '-')
                .replace('\u2013', '-')
                .replace('\u2014', '-'))
    return re.sub(r'\s+', ' ', text).strip()

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts all text layers directly from a PDF file using PyMuPDF."""
    text_parts = []
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            page_text = page.get_text()
            if page_text:
                text_parts.append(page_text)
        doc.close()
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
    return "\n".join(text_parts)

def extract_text_from_image(image_path: str) -> str:
    """
    Extracts visible text from an image file (PNG, JPG, screenshot).
    Optimizes resolution before OCR to ensure high speed and high accuracy.
    """
    reader = get_easyocr_reader()
    if not reader:
        return ""

    try:
        cv_img = cv2.imread(image_path)
        if cv_img is not None:
            h, w = cv_img.shape[:2]
            if w > 1400:
                scale = 1400.0 / w
                new_w = int(w * scale)
                new_h = int(h * scale)
                cv_img = cv2.resize(cv_img, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            results = reader.readtext(cv_img, detail=0)
            if results:
                return "\n".join(results)
    except Exception as e:
        print(f"EasyOCR readtext error: {e}")

    return ""

def extract_notice_content(file_path: str) -> str:
    """
    Dispatches file to the appropriate text extractor based on file extension.
    For PDF, uses PyMuPDF native text layer.
    For images, uses EasyOCR with workspace model caching.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.pdf':
        text = extract_text_from_pdf(file_path)
        if len(clean_text(text)) > 30:
            return text
        
        # Scanned PDF fallback
        try:
            doc = fitz.open(file_path)
            if len(doc) > 0:
                pix = doc[0].get_pixmap(dpi=150)
                temp_img_path = file_path + "_temp_page.png"
                pix.save(temp_img_path)
                doc.close()
                ocr_text = extract_text_from_image(temp_img_path)
                if os.path.exists(temp_img_path):
                    os.remove(temp_img_path)
                return ocr_text
        except Exception as e:
            print(f"PDF raster OCR fallback error: {e}")
            return ""

    return extract_text_from_image(file_path)

def normalize_for_comparison(val: str) -> str:
    """Simplifies string to lowercase alphanumeric words for comparison."""
    if not val:
        return ""
    val = val.lower()
    val = re.sub(r'[^a-z0-9\s]', ' ', val)
    return re.sub(r'\s+', ' ', val).strip()

def extract_labeled_field_value(field_key: str, lines: list) -> str:
    """
    Extracts the candidate value associated with a labeled row in OCR text.
    Handles labels like:
    - 'Event Date:', 'Notice Date:', 'Official Venue:', 'Issuing Department:'
    """
    patterns = {
        'event_date': [r'event\s*date', r'event\s*on', r'reporting\s*date'],
        'notice_date': [r'notice\s*date', r'date\s*of\s*issue'],
        'venue': [r'official\s*venue', r'venue', r'location'],
        'department': [r'issuing\s*department', r'department'],
        'issuer': [r'authorized\s*issuer', r'authorized\s*signatory'],
        'title': [r'circular:\s*', r'subject:\s*']
    }

    key_pats = patterns.get(field_key, [])
    if not key_pats:
        return ""
    
    for i, line in enumerate(lines):
        clean_l = clean_text(line)
        for pat in key_pats:
            m = re.search(pat, clean_l, re.IGNORECASE)
            if m:
                remainder = clean_l[m.end():].lstrip(': -')
                if remainder and len(remainder) >= 2:
                    return remainder
                if i + 1 < len(lines):
                    next_l = clean_text(lines[i + 1])
                    # Check that next line isn't another header label
                    all_patterns = [p for plist in patterns.values() for p in plist]
                    if next_l and not any(re.search(p, next_l, re.IGNORECASE) for p in all_patterns):
                        return next_l
    return ""

def find_best_field_match(field_key: str, expected_val: str, extracted_text: str) -> dict:
    """
    Searches extracted OCR text for an expected field value.
    Prioritizes labeled context extraction for event_date and venue so alterations
    are caught reliably, while matching title, department, and instructions.
    """
    if not expected_val or not expected_val.strip():
        return {"matched": True, "confidence": 1.0, "detected_snippet": "", "status": "MATCH"}

    clean_expected = clean_text(expected_val)
    norm_expected = normalize_for_comparison(clean_expected)
    lines = [clean_text(line) for line in extracted_text.split('\n') if clean_text(line)]
    norm_ocr = normalize_for_comparison(extracted_text)

    # 1. For critical tamper-target fields (event_date and venue), check labeled extraction first
    if field_key in ('event_date', 'venue'):
        candidate = extract_labeled_field_value(field_key, lines)
        if candidate:
            norm_candidate = normalize_for_comparison(candidate)
            ratio = difflib.SequenceMatcher(None, norm_expected, norm_candidate).ratio()
            # If expected date/venue is in candidate or fuzzy match is high, it's genuine
            if norm_expected in norm_candidate or ratio >= 0.75:
                return {
                    "matched": True,
                    "confidence": max(1.0, round(ratio, 2)),
                    "detected_snippet": candidate,
                    "status": "EXACT_MATCH"
                }
            else:
                # Altered date or venue detected!
                return {
                    "matched": False,
                    "confidence": round(ratio, 2),
                    "detected_snippet": candidate,
                    "status": "MISMATCH"
                }

    # 2. General containment: if normalized expected string is in normalized document text
    if norm_expected in norm_ocr:
        return {
            "matched": True,
            "confidence": 1.0,
            "detected_snippet": clean_expected,
            "status": "EXACT_MATCH"
        }

    # Check key multi-word phrases (e.g., "AIML & Robotics Club" within "Head of Department / AIML & Robotics Club")
    words = norm_expected.split()
    if len(words) >= 3:
        phrase_a = " ".join(words[:3])
        phrase_b = " ".join(words[-3:])
        if (len(phrase_a) > 8 and phrase_a in norm_ocr) or (len(phrase_b) > 8 and phrase_b in norm_ocr):
            return {
                "matched": True,
                "confidence": 0.92,
                "detected_snippet": clean_expected,
                "status": "PHRASE_MATCH"
            }

    # 3. Fuzzy search across lines
    best_ratio = 0.0
    best_snippet = ""
    for line in lines:
        norm_line = normalize_for_comparison(line)
        ratio = difflib.SequenceMatcher(None, norm_expected, norm_line).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_snippet = line

    if best_ratio >= 0.75:
        return {
            "matched": True,
            "confidence": round(best_ratio, 2),
            "detected_snippet": best_snippet,
            "status": "FUZZY_MATCH"
        }
    elif best_ratio >= 0.35:
        return {
            "matched": False,
            "confidence": round(best_ratio, 2),
            "detected_snippet": best_snippet if best_snippet else "Altered value detected",
            "status": "MISMATCH"
        }
    else:
        return {
            "matched": False,
            "confidence": round(best_ratio, 2),
            "detected_snippet": "Not detected on uploaded document",
            "status": "MISSING"
        }

def verify_watermark_and_signature(extracted_text: str, official_record: dict) -> dict:
    """
    Checks whether the uploaded notice contains the expected watermark text
    and official signature / issuer information.

    Returns a dict with:
      watermark_found     : bool
      signature_found     : bool
      issuer_found        : bool
      seal_text_found     : bool
      details             : list[str]   human-readable findings
    """
    norm = normalize_for_comparison(extracted_text)
    details = []

    # ── Watermark check ──────────────────────────────────────────────────
    # The PDF watermark contains "GM UNIVERSITY" and "OFFICIAL NOTICE"
    wm_phrases = ["gm university", "official notice", "official seal"]
    watermark_hits = [p for p in wm_phrases if p in norm]
    watermark_found = len(watermark_hits) >= 1
    if watermark_found:
        details.append(f"✅ Watermark detected: {', '.join(watermark_hits)}")
    else:
        details.append("⚠️ Watermark text not detected on the uploaded document.")

    # ── Signature / Issuer stamp check ──────────────────────────────────
    issuer_raw = official_record.get('issuer', '').strip()
    issuer_norm = normalize_for_comparison(issuer_raw)

    # Check for issuer name in OCR text (fuzzy)
    issuer_found = False
    if issuer_norm and len(issuer_norm) > 3:
        if issuer_norm in norm:
            issuer_found = True
        else:
            # Fuzzy check on each OCR line
            for line in extracted_text.split('\n'):
                ratio = difflib.SequenceMatcher(
                    None, issuer_norm, normalize_for_comparison(line)
                ).ratio()
                if ratio >= 0.70:
                    issuer_found = True
                    break
    if issuer_found:
        details.append(f"✅ Authorized issuer/signature found: '{issuer_raw}'")
    else:
        details.append(f"⚠️ Authorized issuer '{issuer_raw}' not clearly detected in uploaded notice.")

    # ── Official seal text check ─────────────────────────────────────────
    seal_phrases = ["gmu", "official seal", "digitally signed", "noticeshield"]
    seal_hits = [p for p in seal_phrases if p in norm]
    seal_text_found = len(seal_hits) >= 1
    if seal_text_found:
        details.append(f"✅ Security seal text detected: {', '.join(seal_hits)}")
    else:
        details.append("ℹ️ Seal/stamp text not extracted (may be graphical — this is non-critical).")

    # ── Signature line check ─────────────────────────────────────────────
    sig_phrases = ["authorized signatory", "signature", "________________", "gm university davanagere"]
    signature_found = any(p in norm for p in sig_phrases)
    if signature_found:
        details.append("✅ Signature line / authorized signatory text found.")
    else:
        details.append("ℹ️ Handwritten signature line not detected via OCR (expected for graphical signatures).")

    return {
        "watermark_found": watermark_found,
        "signature_found": signature_found,
        "issuer_found": issuer_found,
        "seal_text_found": seal_text_found,
        "details": details,
        "overall_ok": watermark_found or issuer_found   # at least one must be present
    }


def compare_notice_fields(official_record: dict, extracted_text: str) -> dict:
    """
    Compares critical official fields against extracted notice text.
    Evaluates:
    - Title
    - Department
    - Notice Date
    - Event Date
    - Venue
    - Issuer
    
    Returns structured comparison result.
    """
    if not extracted_text or len(clean_text(extracted_text)) < 15:
        return {
            "ocr_readable": False,
            "all_matched": False,
            "extracted_text": extracted_text,
            "field_results": {},
            "mismatched_fields": ["Unreadable OCR text - document too blurry, cropped, or text not detected"],
            "summary": "OCR could not read sufficient text from the uploaded notice."
        }

    fields_to_check = [
        ("title", "Notice Title"),
        ("department", "Department"),
        ("notice_date", "Notice Date"),
        ("event_date", "Event Date"),
        ("venue", "Venue / Location"),
        ("issuer", "Authorized Issuer")
    ]

    field_results = {}
    mismatched_fields = []
    matched_count = 0

    for key, display_name in fields_to_check:
        expected_val = str(official_record.get(key, '')).strip()
        if not expected_val:
            continue
            
        match_info = find_best_field_match(key, expected_val, extracted_text)
        match_info['field_name'] = display_name
        match_info['official_value'] = expected_val
        field_results[key] = match_info

        if match_info['matched']:
            matched_count += 1
        else:
            mismatched_fields.append({
                "field_key": key,
                "field_name": display_name,
                "official_value": expected_val,
                "detected_value": match_info['detected_snippet'],
                "confidence": match_info['confidence']
            })

    total_checked = len(field_results)
    all_matched = (len(mismatched_fields) == 0)

    return {
        "ocr_readable": True,
        "all_matched": all_matched,
        "matched_count": matched_count,
        "total_checked": total_checked,
        "field_results": field_results,
        "mismatched_fields": mismatched_fields,
        "extracted_text_preview": clean_text(extracted_text)[:600]
    }
