"""
NoticeShield - Automated Verification Test Suite
Executes the full 7-step cryptographic and OCR pipeline against all 5 evaluation scenarios
and prints a detailed evaluation report.
"""

import os
import sys
import json

import database as db
import security
import qr_scanner
import ocr

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_DIR = os.path.join(BASE_DIR, 'test_samples')
GEN_DIR = os.path.join(BASE_DIR, 'generated_notices')

def run_pipeline_on_file(file_path: str) -> dict:
    """Executes the verification logic identical to app.py /verify route."""
    # Step 1: Scan QR Code
    qr_result = qr_scanner.scan_qr_from_file(file_path)
    notice_id = qr_result.get('notice_id', '').strip()

    if not notice_id:
        return {
            "status": "UNVERIFIED",
            "reason": "No NoticeShield QR code detected",
            "notice_id": "UNKNOWN"
        }

    # Step 2: Retrieve DB record
    record = db.get_notice_by_id(notice_id)
    if not record:
        return {
            "status": "UNVERIFIED",
            "reason": f"Unknown Notice ID: {notice_id}",
            "notice_id": notice_id
        }

    # Step 3: Check Revoked
    if record.get('status') == 'revoked':
        return {
            "status": "REVOKED",
            "reason": "Notice officially revoked by administration",
            "notice_id": notice_id
        }

    # Step 4: Verify Ed25519 signature
    canon_data = record.get('canonical_data', '')
    signature = record.get('digital_signature', '')
    is_valid_sig = security.verify_ed25519_signature(canon_data, signature)

    if not is_valid_sig:
        return {
            "status": "INVALID_SIGNATURE",
            "reason": "Ed25519 signature mismatch",
            "notice_id": notice_id
        }

    # Step 5: OCR text extraction
    extracted_text = ocr.extract_notice_content(file_path)
    
    # Step 6: Semantic Field Comparison
    comparison = ocr.compare_notice_fields(record, extracted_text)

    if not comparison.get('ocr_readable'):
        return {
            "status": "UNVERIFIED",
            "reason": "OCR text unreadable or resolution too low",
            "notice_id": notice_id
        }

    if not comparison.get('all_matched'):
        return {
            "status": "MODIFIED",
            "reason": "Visible text does not match official record",
            "notice_id": notice_id,
            "mismatches": comparison.get('mismatched_fields', [])
        }

    return {
        "status": "VERIFIED",
        "reason": "Cryptographic signature valid and 100% visible fields match",
        "notice_id": notice_id,
        "matched_count": comparison.get('matched_count', 0)
    }

def main():
    print("=" * 70, flush=True)
    print(" NOTICESHIELD - FULL PIPELINE AUTOMATED TEST EVALUATION", flush=True)
    print(" NEUROFORGE 2026 AI Hackathon | GM University", flush=True)
    print("=" * 70, flush=True)

    test_cases = [
        {
            "name": "TEST 1: Genuine Official PDF",
            "file": os.path.join(GEN_DIR, "NS-2026-NEURO01.pdf"),
            "expected": "VERIFIED"
        },
        {
            "name": "TEST 1b: Genuine Official PNG",
            "file": os.path.join(TEST_DIR, "test1_genuine_notice.png"),
            "expected": "VERIFIED"
        },
        {
            "name": "TEST 2: Modified / Tampered Notice (Altered Date & Venue)",
            "file": os.path.join(TEST_DIR, "test2_modified_notice.png"),
            "expected": "MODIFIED"
        },
        {
            "name": "TEST 3: Unknown / Counterfeit Notice",
            "file": os.path.join(TEST_DIR, "test3_unknown_notice.png"),
            "expected": "UNVERIFIED"
        },
        {
            "name": "TEST 4: Forwarded Mobile Screenshot (Compressed)",
            "file": os.path.join(TEST_DIR, "test4_screenshot_notice.png"),
            "expected": "VERIFIED"
        },
        {
            "name": "TEST 5: Revoked Notice (Cancelled Circular)",
            "file": os.path.join(GEN_DIR, "NS-2026-REVOKED01.pdf"),
            "expected": "REVOKED"
        }
    ]

    all_passed = True

    for i, tc in enumerate(test_cases, 1):
        print(f"\n--- Running [{tc['name']}] ---", flush=True)
        if not os.path.exists(tc['file']):
            print(f"FAILED: File not found: {tc['file']}", flush=True)
            all_passed = False
            continue

        result = run_pipeline_on_file(tc['file'])
        verdict = result.get('status')
        matched = (verdict == tc['expected'])

        print(f"  Target File : {os.path.basename(tc['file'])}", flush=True)
        print(f"  Expected    : {tc['expected']}", flush=True)
        print(f"  Actual      : {verdict}", flush=True)
        print(f"  Reason      : {result.get('reason')}", flush=True)
        if 'mismatches' in result:
            print(f"  Mismatches  : {result['mismatches']}", flush=True)

        if matched:
            print(f"  Result      : [PASSED]", flush=True)
        else:
            print(f"  Result      : [FAILED]", flush=True)
            all_passed = False

    print("\n" + "=" * 70, flush=True)
    if all_passed:
        print(" ALL VERIFICATION TESTS PASSED SUCCESSFULLY! (6/6)", flush=True)
    else:
        print(" SOME TESTS FAILED! CHECK DETAILS ABOVE.", flush=True)
    print("=" * 70, flush=True)

if __name__ == '__main__':
    main()
