"""
NoticeShield - QR Code Scanner Module
Robust QR code detection from forwarded images, screenshots, cropped photos, and PDF files.
Uses OpenCV QRCodeDetector with multi-pass image preprocessing (upscaling, contrast enhancement,
adaptive thresholding) to reliably detect QR codes even after lossy compression or resizing.
"""

import os
import re
import urllib.parse
import json
import cv2
import numpy as np
import fitz  # PyMuPDF
from PIL import Image

def extract_notice_id_from_payload(payload: str) -> str:
    """
    Extracts the unique notice_id from decoded QR text payload.
    Supports full verification URL, JSON payload, or plain Notice ID string.
    """
    if not payload:
        return ""
    
    payload = payload.strip()

    # Case 1: URL format (e.g., http://127.0.0.1:5000/verify?notice_id=NS-2026-A1B2C3D4)
    if "notice_id=" in payload:
        try:
            parsed = urllib.parse.urlparse(payload)
            qs = urllib.parse.parse_qs(parsed.query)
            if 'notice_id' in qs and qs['notice_id']:
                return qs['notice_id'][0].strip()
        except Exception:
            pass

    # Case 2: JSON format (e.g., {"notice_id": "NS-2026-..."})
    if payload.startswith('{') and payload.endswith('}'):
        try:
            data = json.loads(payload)
            if 'notice_id' in data:
                return data['notice_id'].strip()
        except Exception:
            pass

    # Case 3: Regex pattern matching standard NoticeShield ID format (NS-YYYY-HEX8)
    match = re.search(r'NS-\d{4}-[A-Z0-9]{8}', payload, re.IGNORECASE)
    if match:
        return match.group(0).upper()

    # Case 4: Plain string if it looks like an ID
    if payload.startswith("NS-"):
        return payload

    return payload

def detect_qr_in_cv_image(cv_img):
    """
    Runs multi-pass QR code detection using OpenCV.
    Applies several preprocessing variations to handle compression and blur.
    """
    detector = cv2.QRCodeDetector()

    # Pass 1: Original image
    data, points, _ = detector.detectAndDecode(cv_img)
    if data:
        return data

    # Convert to grayscale if not already
    if len(cv_img.shape) == 3:
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = cv_img

    # Pass 2: Grayscale
    data, points, _ = detector.detectAndDecode(gray)
    if data:
        return data

    # Pass 3: Contrast enhancement / Histogram Equalization
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    data, points, _ = detector.detectAndDecode(enhanced)
    if data:
        return data

    # Pass 4: Upscaling (helpful for small / screenshot QR codes)
    h, w = gray.shape[:2]
    if h < 1200 or w < 1200:
        scaled = cv2.resize(gray, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
        data, points, _ = detector.detectAndDecode(scaled)
        if data:
            return data

    # Pass 5: Otsu's Binarization
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    data, points, _ = detector.detectAndDecode(thresh)
    if data:
        return data

    # Pass 6: Adaptive Thresholding
    adapt_thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 19, 5
    )
    data, points, _ = detector.detectAndDecode(adapt_thresh)
    if data:
        return data

    # Pass 7: Multi-detect in case OpenCV finds multiple or partial markers
    try:
        retval, decoded_info, points, _ = detector.detectAndDecodeMulti(cv_img)
        if retval and decoded_info:
            for info in decoded_info:
                if info:
                    return info
    except Exception:
        pass

    return ""

def scan_qr_from_file(file_path: str) -> dict:
    """
    Scans an image or PDF file for an official NoticeShield QR code.
    Returns:
    {
        "success": bool,
        "notice_id": str,
        "raw_payload": str,
        "message": str
    }
    """
    if not os.path.exists(file_path):
        return {
            "success": False,
            "notice_id": "",
            "raw_payload": "",
            "message": f"File not found: {file_path}"
        }

    ext = os.path.splitext(file_path)[1].lower()

    # Case A: PDF Document
    if ext == '.pdf':
        try:
            doc = fitz.open(file_path)
            # Scan each page (usually page 1 has the notice and QR)
            for page_idx in range(min(3, len(doc))):
                page = doc[page_idx]
                
                # Check embedded raster images first
                image_list = page.get_images(full=True)
                for img_info in image_list:
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if cv_img is not None:
                        qr_data = detect_qr_in_cv_image(cv_img)
                        if qr_data:
                            notice_id = extract_notice_id_from_payload(qr_data)
                            return {
                                "success": True,
                                "notice_id": notice_id,
                                "raw_payload": qr_data,
                                "message": "QR Code extracted successfully from PDF embedded image."
                            }

                # If not found in embedded images, render page to high-res image and scan
                pix = page.get_pixmap(dpi=200)
                img_data = pix.tobytes("png")
                nparr = np.frombuffer(img_data, np.uint8)
                cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if cv_img is not None:
                    qr_data = detect_qr_in_cv_image(cv_img)
                    if qr_data:
                        notice_id = extract_notice_id_from_payload(qr_data)
                        return {
                            "success": True,
                            "notice_id": notice_id,
                            "raw_payload": qr_data,
                            "message": "QR Code extracted successfully from rendered PDF page."
                        }

            return {
                "success": False,
                "notice_id": "",
                "raw_payload": "",
                "message": "No valid QR code detected in the uploaded PDF."
            }
        except Exception as e:
            return {
                "success": False,
                "notice_id": "",
                "raw_payload": "",
                "message": f"Error scanning PDF: {str(e)}"
            }

    # Case B: Image (PNG, JPG, JPEG, WEBP, etc.)
    try:
        # Read with OpenCV (supports utf-8 paths on Windows using imdecode)
        with open(file_path, 'rb') as f:
            bytes_data = bytearray(f.read())
            nparr = np.asarray(bytes_data, dtype=np.uint8)
            cv_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if cv_img is None:
            return {
                "success": False,
                "notice_id": "",
                "raw_payload": "",
                "message": "Could not decode uploaded image format."
            }

        qr_data = detect_qr_in_cv_image(cv_img)
        if qr_data:
            notice_id = extract_notice_id_from_payload(qr_data)
            return {
                "success": True,
                "notice_id": notice_id,
                "raw_payload": qr_data,
                "message": "QR Code detected and decoded successfully."
            }

        return {
            "success": False,
            "notice_id": "",
            "raw_payload": "",
            "message": "No QR code could be found in the image. It may be missing, too heavily blurred, or cropped out."
        }
    except Exception as e:
        return {
            "success": False,
            "notice_id": "",
            "raw_payload": "",
            "message": f"Error processing image: {str(e)}"
        }
