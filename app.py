"""
NoticeShield - AI-Assisted College Notice Authentication System
Flask Application Controller and Verification Engine for NEUROFORGE 2026
"""

import os
import json
import time
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, send_file, jsonify, abort
)
from werkzeug.utils import secure_filename

import database as db
import security
import qr_generator
import qr_scanner
import ocr
import pdf_generator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
GENERATED_DIR = os.path.join(BASE_DIR, 'generated_notices')
KEYS_DIR = os.path.join(BASE_DIR, 'keys')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(KEYS_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get('NOTICESHIELD_SECRET_KEY', 'neuroforge_noticeshield_dev_secret_2026')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
app.config['UPLOAD_FOLDER'] = UPLOADS_DIR

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename: str) -> bool:
    """Validates file extension for safety."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    """Decorator to protect admin routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            flash('Please log in to access the administrator panel.', 'warning')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Context processor for templates
@app.context_processor
def inject_global_data():
    return {
        'current_year': 2026,
        'app_name': 'NoticeShield',
        'app_tagline': 'Trust Every Notice. Verify Before You Believe.'
    }

# ----------------- Seed Hackathon Demo Notice -----------------
def seed_demo_notice():
    """Seeds the official NEUROFORGE 2026 Hackathon notice if database is empty."""
    db.init_db()
    security.ensure_keys_exist()
    
    existing = db.get_notice_by_id("NS-2026-NEURO01")
    if not existing:
        demo_notice = {
            'notice_id': 'NS-2026-NEURO01',
            'title': 'NEUROFORGE 2026 – AI Hackathon',
            'department': 'AIML & Robotics Club',
            'notice_date': '06 November 2026',
            'event_date': '06 November 2026',
            'venue': 'GM University Campus, Davanagere',
            'description': (
                'Six-hour AI hackathon organized by AIML & Robotics Club. '
                'Participants must report to the Central Computing Facility at 09:00 AM. '
                'Teams will solve challenges in Computer Vision, Cryptography, and LLMs. '
                'All college students with valid university ID cards are eligible.'
            ),
            'issuer': 'Head of Department / AIML & Robotics Club',
            'status': 'active'
        }
        canonical_json = security.canonicalize_notice_data(demo_notice)
        signature = security.sign_canonical_data(canonical_json)
        demo_notice['canonical_data'] = canonical_json
        demo_notice['digital_signature'] = signature

        # Generate official PDF and QR code
        paths = pdf_generator.generate_official_notice_pdf(demo_notice)
        demo_notice['pdf_path'] = paths['pdf_path']
        demo_notice['qr_path'] = paths['qr_path']

        db.save_notice(demo_notice)
        print("Default NEUROFORGE 2026 demo notice seeded successfully!")

# ----------------- Public Routes -----------------

@app.route('/')
def index():
    """Home landing page with system overview and features."""
    stats = db.get_dashboard_stats()
    return render_template('index.html', stats=stats)

@app.route('/verify', methods=['GET', 'POST'])
def verify_notice():
    """
    Student verification endpoint.
    Handles file upload, QR scanning, Ed25519 signature verification,
    OCR text extraction, and semantic field mismatch detection.
    """
    # If GET with query parameter notice_id, prefill or lookup
    prefill_id = request.args.get('notice_id', '').strip()
    
    if request.method == 'GET':
        return render_template('verify.html', prefill_id=prefill_id)

    # Process POST upload
    if 'notice_file' not in request.files:
        flash('No notice document was selected for upload.', 'danger')
        return redirect(request.url)

    file = request.files['notice_file']
    if file.filename == '':
        flash('No file was selected.', 'danger')
        return redirect(request.url)

    if not allowed_file(file.filename):
        flash('Unsupported file type. Please upload a PNG, JPG, JPEG or PDF document.', 'danger')
        return redirect(request.url)

    # Save uploaded file safely
    original_name = secure_filename(file.filename)
    timestamp = int(time.time())
    saved_filename = f"upload_{timestamp}_{original_name}"
    uploaded_filepath = os.path.join(app.config['UPLOAD_FOLDER'], saved_filename)
    file.save(uploaded_filepath)

    # Determine whether file is PDF or image for display
    is_pdf = saved_filename.lower().endswith('.pdf')

    # ---------------- VERIFICATION PIPELINE ----------------
    audit_steps = []
    
    # STEP 1: Scan QR Code
    audit_steps.append({"step": "STEP 1: QR Code Extraction", "desc": "Scanning uploaded document for embedded digital seal..."})
    qr_result = qr_scanner.scan_qr_from_file(uploaded_filepath)
    
    extracted_notice_id = qr_result.get('notice_id', '').strip()
    # If user manually typed a notice ID as fallback
    manual_notice_id = request.form.get('manual_notice_id', '').strip()
    if not extracted_notice_id and manual_notice_id:
        extracted_notice_id = manual_notice_id
        audit_steps.append({"step": "STEP 1b: Manual Notice ID Provided", "desc": f"Used manual fallback Notice ID: {manual_notice_id}"})

    if not extracted_notice_id:
        # Result State: UNVERIFIED (No QR code)
        verdict = {
            'status': 'UNVERIFIED',
            'badge_class': 'warning',
            'title': 'AUTHENTICITY COULD NOT BE ESTABLISHED',
            'reason': 'No official NoticeShield QR code was detected in the document. The QR code may be missing, cropped, or blurred beyond recognition.',
            'notice_id': 'UNKNOWN',
            'qr_extracted': False,
            'official_record': None,
            'signature_valid': False,
            'field_results': {},
            'mismatches': [],
            'uploaded_file': saved_filename,
            'is_pdf': is_pdf,
            'audit_steps': audit_steps
        }
        db.log_verification("UNKNOWN", "UNVERIFIED", {"reason": "Missing QR code", "file": saved_filename})
        return render_template('result.html', result=verdict)

    audit_steps.append({
        "step": "STEP 2: Notice ID Retrieved",
        "desc": f"Found Notice ID: {extracted_notice_id} (Payload: {qr_result.get('raw_payload', '')[:60]}...)"
    })

    # STEP 3: Retrieve official record from database
    official_record = db.get_notice_by_id(extracted_notice_id)
    if not official_record:
        # Result State: UNVERIFIED (Unknown ID)
        verdict = {
            'status': 'UNVERIFIED',
            'badge_class': 'warning',
            'title': 'UNKNOWN NOTICE IDENTIFIER',
            'reason': f"Notice ID '{extracted_notice_id}' is not registered in the official university records ledger.",
            'notice_id': extracted_notice_id,
            'qr_extracted': True,
            'official_record': None,
            'signature_valid': False,
            'field_results': {},
            'mismatches': [],
            'uploaded_file': saved_filename,
            'is_pdf': is_pdf,
            'audit_steps': audit_steps
        }
        db.log_verification(extracted_notice_id, "UNVERIFIED", {"reason": "Unknown Notice ID", "file": saved_filename})
        return render_template('result.html', result=verdict)

    audit_steps.append({
        "step": "STEP 3: Official Ledger Record Found",
        "desc": f"Found record issued by: {official_record.get('issuer')} (Department: {official_record.get('department')})"
    })

    # STEP 4: Check if Notice is Revoked
    if official_record.get('status') == 'revoked':
        verdict = {
            'status': 'REVOKED',
            'badge_class': 'danger',
            'title': 'OFFICIAL NOTICE HAS BEEN REVOKED',
            'reason': 'This notice was officially invalidated or cancelled by the university administration. It must NOT be treated as genuine.',
            'notice_id': extracted_notice_id,
            'qr_extracted': True,
            'official_record': official_record,
            'signature_valid': True,
            'field_results': {},
            'mismatches': [],
            'uploaded_file': saved_filename,
            'is_pdf': is_pdf,
            'audit_steps': audit_steps
        }
        db.log_verification(extracted_notice_id, "REVOKED", {"reason": "Revoked notice", "file": saved_filename})
        return render_template('result.html', result=verdict)

    # STEP 5: Verify Ed25519 Digital Signature on Canonical Data
    canonical_data = official_record.get('canonical_data', '')
    digital_signature = official_record.get('digital_signature', '')
    
    is_signature_valid = security.verify_ed25519_signature(canonical_data, digital_signature)
    audit_steps.append({
        "step": "STEP 4: Ed25519 Digital Signature Verification",
        "desc": f"Public key signature verification result: {'VALID' if is_signature_valid else 'INVALID'}"
    })

    if not is_signature_valid:
        # Result State: INVALID SIGNATURE
        verdict = {
            'status': 'INVALID_SIGNATURE',
            'badge_class': 'danger',
            'title': 'DIGITAL SIGNATURE FORGERY DETECTED',
            'reason': 'The cryptographic signature does not match the official public signing key of GM University.',
            'notice_id': extracted_notice_id,
            'qr_extracted': True,
            'official_record': official_record,
            'signature_valid': False,
            'field_results': {},
            'mismatches': [],
            'uploaded_file': saved_filename,
            'is_pdf': is_pdf,
            'audit_steps': audit_steps
        }
        db.log_verification(extracted_notice_id, "INVALID_SIGNATURE", {"reason": "Signature forgery", "file": saved_filename})
        return render_template('result.html', result=verdict)

    # STEP 6: OCR Extraction
    audit_steps.append({
        "step": "STEP 5: Optical Character Recognition (OCR)",
        "desc": "Extracting visible textual content from uploaded notice image/document..."
    })
    extracted_text = ocr.extract_notice_content(uploaded_filepath)

    # STEP 6b: Watermark & Signature Stamp Verification
    ws_check = ocr.verify_watermark_and_signature(extracted_text, official_record)
    audit_steps.append({
        "step": "STEP 5b: Watermark & Signature Verification",
        "desc": " | ".join(ws_check.get("details", []))
    })

    # STEP 7: Field Comparison
    comparison = ocr.compare_notice_fields(official_record, extracted_text)
    audit_steps.append({
        "step": "STEP 6: Semantic Field Comparison",
        "desc": f"Checked {comparison.get('total_checked', 0)} fields: {comparison.get('matched_count', 0)} matched, {len(comparison.get('mismatched_fields', []))} altered."
    })

    # STEP 8: Evaluate Final Verdict
    if not comparison.get('ocr_readable'):
        # OCR could not extract sufficient text
        verdict = {
            'status': 'UNVERIFIED',
            'badge_class': 'warning',
            'title': 'DOCUMENT CONTENT UNREADABLE',
            'reason': 'The QR code was read and verified, but the visible notice text could not be clearly extracted by OCR. We cannot certify that the document has not been altered without reading its visible text.',
            'notice_id': extracted_notice_id,
            'qr_extracted': True,
            'official_record': official_record,
            'signature_valid': True,
            'field_results': {},
            'mismatches': ['Visible text resolution insufficient for OCR verification'],
            'uploaded_file': saved_filename,
            'is_pdf': is_pdf,
            'audit_steps': audit_steps,
            'ws_check': ws_check
        }
        db.log_verification(extracted_notice_id, "UNVERIFIED", {"reason": "Unreadable OCR", "file": saved_filename})
        return render_template('result.html', result=verdict)

    # Check for mismatches (e.g. altered event date or venue)
    if not comparison.get('all_matched'):
        # Result State: MODIFIED (Tampered Notice)
        mismatched_list = comparison.get('mismatched_fields', [])
        verdict = {
            'status': 'MODIFIED',
            'badge_class': 'danger',
            'title': 'NOTICE CONTENT MISMATCH – TAMPERING DETECTED',
            'reason': (
                'WARNING: The digital seal and QR code belong to an official registered notice, '
                'but the visible content on this document has been MODIFIED or altered (e.g. forged date, fake venue, or changed instructions)!'
            ),
            'notice_id': extracted_notice_id,
            'qr_extracted': True,
            'official_record': official_record,
            'signature_valid': True,
            'field_results': comparison.get('field_results', {}),
            'mismatches': mismatched_list,
            'uploaded_file': saved_filename,
            'is_pdf': is_pdf,
            'ocr_preview': comparison.get('extracted_text_preview', ''),
            'audit_steps': audit_steps,
            'ws_check': ws_check
        }
        db.log_verification(extracted_notice_id, "MODIFIED", {
            "mismatches": mismatched_list,
            "file": saved_filename
        })
        return render_template('result.html', result=verdict)

    # Result State: VERIFIED (Genuine Official Notice)
    verdict = {
        'status': 'VERIFIED',
        'badge_class': 'success',
        'title': 'OFFICIAL NOTICE VERIFIED',
        'reason': 'Authentic document. Cryptographic signature is valid and 100% of visible notice fields match the tamper-proof university ledger.',
        'notice_id': extracted_notice_id,
        'qr_extracted': True,
        'official_record': official_record,
        'signature_valid': True,
        'field_results': comparison.get('field_results', {}),
        'mismatches': [],
        'uploaded_file': saved_filename,
        'is_pdf': is_pdf,
        'ocr_preview': comparison.get('extracted_text_preview', ''),
        'audit_steps': audit_steps,
        'ws_check': ws_check
    }
    db.log_verification(extracted_notice_id, "VERIFIED", {
        "matched_fields": list(comparison.get('field_results', {}).keys()),
        "file": saved_filename
    })
    return render_template('result.html', result=verdict)

# ----------------- Admin Authentication Routes -----------------

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin login page."""
    if session.get('admin_logged_in'):
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if db.verify_admin(username, password):
            session['admin_logged_in'] = True
            session['admin_user'] = username
            flash(f'Welcome back, Administrator ({username}).', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials. Please try again.', 'danger')

    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    """Logs out admin user."""
    session.clear()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('admin_login'))

# ----------------- Admin Dashboard & Operations -----------------

@app.route('/admin')
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """Admin overview dashboard with statistics, notice table, and audit trail."""
    stats = db.get_dashboard_stats()
    notices = db.get_all_notices()
    recent_logs = db.get_verification_logs(limit=20)
    public_key_pem = security.get_public_key_pem_str()

    return render_template(
        'admin_dashboard.html',
        stats=stats,
        notices=notices,
        logs=recent_logs,
        public_key_pem=public_key_pem
    )

@app.route('/admin/create-notice', methods=['GET', 'POST'])
@login_required
def create_notice():
    """Creates, digitally signs, and registers a new official notice."""
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        department = request.form.get('department', '').strip()
        notice_date = request.form.get('notice_date', '').strip()
        event_date = request.form.get('event_date', '').strip()
        venue = request.form.get('venue', '').strip()
        description = request.form.get('description', '').strip()
        issuer = request.form.get('issuer', '').strip()

        if not all([title, department, notice_date, event_date, venue, description, issuer]):
            flash('All notice fields are required to establish canonical integrity.', 'danger')
            return render_template('create_notice.html')

        notice_id = security.generate_notice_id()

        notice_dict = {
            'notice_id': notice_id,
            'title': title,
            'department': department,
            'notice_date': notice_date,
            'event_date': event_date,
            'venue': venue,
            'description': description,
            'issuer': issuer,
            'status': 'active'
        }

        # 1. Canonicalize notice data
        canonical_json = security.canonicalize_notice_data(notice_dict)
        # 2. Digitally sign canonical bytes using Ed25519 private key
        digital_signature = security.sign_canonical_data(canonical_json)
        
        notice_dict['canonical_data'] = canonical_json
        notice_dict['digital_signature'] = digital_signature

        # 3. Generate official PDF document and QR code
        host_base_url = request.host_url.rstrip('/')
        paths = pdf_generator.generate_official_notice_pdf(notice_dict, host_base_url)
        notice_dict['pdf_path'] = paths['pdf_path']
        notice_dict['qr_path'] = paths['qr_path']

        # 4. Save to database
        db.save_notice(notice_dict)

        flash(f'Official notice {notice_id} digitally signed and registered successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('create_notice.html')

@app.route('/admin/revoke/<notice_id>', methods=['POST'])
@login_required
def revoke_notice_action(notice_id):
    """Revokes an issued notice."""
    success = db.revoke_notice(notice_id)
    if success:
        flash(f"Notice {notice_id} has been REVOKED. It will no longer verify as genuine.", "warning")
    else:
        flash(f"Could not find notice {notice_id}.", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reactivate/<notice_id>', methods=['POST'])
@login_required
def reactivate_notice_action(notice_id):
    """Reactivates a previously revoked notice."""
    success = db.reactivate_notice(notice_id)
    if success:
        flash(f"Notice {notice_id} has been reactivated to ACTIVE.", "success")
    else:
        flash(f"Could not find notice {notice_id}.", "danger")
    return redirect(url_for('admin_dashboard'))

# ----------------- File Serving & Download Routes -----------------

@app.route('/download/pdf/<notice_id>')
def download_pdf(notice_id):
    """Downloads the official notice as a PDF."""
    notice = db.get_notice_by_id(notice_id)
    if not notice:
        abort(404)
    
    pdf_path = notice.get('pdf_path')
    if not pdf_path or not os.path.exists(pdf_path):
        # Regenerate if missing
        paths = pdf_generator.generate_official_notice_pdf(notice)
        pdf_path = paths['pdf_path']

    return send_file(
        pdf_path,
        as_attachment=True,
        download_name=f"{notice_id}_Official_Notice.pdf",
        mimetype='application/pdf'
    )

@app.route('/download/image/<notice_id>')
def download_image(notice_id):
    """Downloads or views the rendered notice PNG image."""
    img_path = os.path.join(GENERATED_DIR, 'images', f"{notice_id}.png")
    if not os.path.exists(img_path):
        # Try generating from PDF
        notice = db.get_notice_by_id(notice_id)
        if notice:
            paths = pdf_generator.generate_official_notice_pdf(notice)
            img_path = paths.get('image_path', '')
    
    if os.path.exists(img_path):
        return send_file(img_path, mimetype='image/png')
    abort(404)

@app.route('/download/qr/<notice_id>')
def download_qr(notice_id):
    """Serves the generated QR code PNG."""
    qr_path = os.path.join(GENERATED_DIR, 'qr_codes', f"{notice_id}_qr.png")
    if not os.path.exists(qr_path):
        qr_path = qr_generator.generate_notice_qr(notice_id)
    
    return send_file(qr_path, mimetype='image/png')

@app.route('/uploads/<filename>')
def serve_upload(filename):
    """Serves uploaded notice previews."""
    safe_name = secure_filename(filename)
    file_path = os.path.join(UPLOADS_DIR, safe_name)
    if os.path.exists(file_path):
        return send_file(file_path)
    abort(404)

if __name__ == '__main__':
    seed_demo_notice()
    print("\n" + "="*60)
    print(" NoticeShield - AI-Assisted College Notice Authentication System")
    print(" NEUROFORGE 2026 AI Hackathon | GM University")
    print(" Server running at: http://127.0.0.1:5000")
    print(" Default Admin: admin / admin123")
    print("="*60 + "\n")
    app.run(host='127.0.0.1', port=5000, debug=True)
