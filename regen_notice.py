"""Re-generates the NEUROFORGE 2026 notice PDF with watermark + signature stamp."""
import sys
sys.path.insert(0, r'c:\Users\Yashwanth G\OneDrive\Desktop\Notice shield')

from pdf_generator import generate_official_notice_pdf
import database as db

db.init_db()
notice = db.get_notice_by_id('NS-2026-NEURO01')
if notice:
    result = generate_official_notice_pdf(dict(notice), host_base_url='http://127.0.0.1:5000')
    print(f"PDF regenerated: {result['pdf_path']}")
    print(f"PNG regenerated: {result['image_path']}")
    print("Watermark + Signature stamp applied successfully.")
else:
    print("Notice NS-2026-NEURO01 not found in database.")
