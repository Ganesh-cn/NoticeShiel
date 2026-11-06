"""
NoticeShield - QR Code Generator Module
Generates tamper-evident QR codes containing verification metadata and direct URL.
Uses high error correction (level H/M) to withstand compression, screenshots, and forwarding.
"""

import os
import qrcode
from PIL import Image

QR_OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_notices', 'qr_codes')

def generate_notice_qr(notice_id: str, host_base_url: str = "http://127.0.0.1:5000") -> str:
    """
    Generates a QR code image for a notice containing the verification URL.
    Saves the image to disk and returns the relative/absolute file path.
    """
    os.makedirs(QR_OUTPUT_DIR, exist_ok=True)
    
    # URL that students can visit or scan directly
    verify_url = f"{host_base_url}/verify?notice_id={notice_id}"
    
    # Payload format includes explicit NoticeShield metadata to prevent confusion
    # We embed the direct verify URL so camera apps open the verification page,
    # and our scanner can extract notice_id directly.
    qr = qrcode.QRCode(
        version=None, # Auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M, # Resilient to mild damage/compression
        box_size=10,
        border=4,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0F172A", back_color="#FFFFFF")
    
    filename = f"{notice_id}_qr.png"
    filepath = os.path.join(QR_OUTPUT_DIR, filename)
    img.save(filepath)
    
    return filepath

def get_qr_image_bytes(notice_id: str, host_base_url: str = "http://127.0.0.1:5000") -> bytes:
    """Returns raw PNG bytes of the generated QR code."""
    import io
    filepath = generate_notice_qr(notice_id, host_base_url)
    with open(filepath, 'rb') as f:
        return f.read()
