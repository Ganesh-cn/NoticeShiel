"""
NoticeShield - Flask Application End-to-End Route Validation
Verifies all public, student, and admin routes, sessions, file downloads, and upload verification.
"""

import os
import io
from app import app
import database as db

def test_all_routes():
    print("Testing NoticeShield Flask Endpoints...")
    app.config['TESTING'] = True
    client = app.test_client()

    # 1. Home page
    res = client.get('/')
    assert res.status_code == 200, f"Home page failed: {res.status_code}"
    assert b"NoticeShield" in res.data
    print(" [x] GET / -> 200 OK")

    # 2. Student verification page
    res = client.get('/verify')
    assert res.status_code == 200, f"Verify page failed: {res.status_code}"
    assert b"Verify Official Notice" in res.data
    print(" [x] GET /verify -> 200 OK")

    # 3. Admin login page
    res = client.get('/admin/login')
    assert res.status_code == 200
    assert b"Administrator Portal" in res.data
    print(" [x] GET /admin/login -> 200 OK")

    # 4. Admin login action
    res = client.post('/admin/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Security Operations Dashboard" in res.data
    print(" [x] POST /admin/login (Auth Success) -> 200 OK")

    # 5. Admin Dashboard
    res = client.get('/admin/dashboard')
    assert res.status_code == 200
    assert b"Registered Official Notices" in res.data
    print(" [x] GET /admin/dashboard -> 200 OK")

    # 6. Admin Create Notice page
    res = client.get('/admin/create-notice')
    assert res.status_code == 200
    assert b"Issue & Digitally Sign Official Notice" in res.data
    print(" [x] GET /admin/create-notice -> 200 OK")

    # 7. File downloads
    res = client.get('/download/pdf/NS-2026-NEURO01')
    assert res.status_code == 200
    assert res.mimetype == 'application/pdf'
    print(" [x] GET /download/pdf/NS-2026-NEURO01 -> 200 OK (PDF)")

    res = client.get('/download/qr/NS-2026-NEURO01')
    assert res.status_code == 200
    assert res.mimetype == 'image/png'
    print(" [x] GET /download/qr/NS-2026-NEURO01 -> 200 OK (QR PNG)")

    # 8. Verification POST - Genuine PDF
    pdf_path = os.path.join(os.path.dirname(__file__), 'generated_notices', 'NS-2026-NEURO01.pdf')
    with open(pdf_path, 'rb') as f:
        res = client.post('/verify', data={'notice_file': (f, 'NS-2026-NEURO01.pdf')}, content_type='multipart/form-data')
    assert res.status_code == 200
    assert b"OFFICIAL NOTICE VERIFIED" in res.data
    print(" [x] POST /verify (Genuine Notice) -> 200 OK (OFFICIAL NOTICE VERIFIED)")

    # 9. Verification POST - Modified Notice
    mod_path = os.path.join(os.path.dirname(__file__), 'test_samples', 'test2_modified_notice.png')
    with open(mod_path, 'rb') as f:
        res = client.post('/verify', data={'notice_file': (f, 'test2_modified_notice.png')}, content_type='multipart/form-data')
    assert res.status_code == 200
    assert b"NOTICE CONTENT MISMATCH" in res.data
    print(" [x] POST /verify (Modified Notice) -> 200 OK (NOTICE CONTENT MISMATCH)")

    # 10. Verification POST - Unknown Notice
    unk_path = os.path.join(os.path.dirname(__file__), 'test_samples', 'test3_unknown_notice.png')
    with open(unk_path, 'rb') as f:
        res = client.post('/verify', data={'notice_file': (f, 'test3_unknown_notice.png')}, content_type='multipart/form-data')
    assert res.status_code == 200
    assert b"UNKNOWN NOTICE IDENTIFIER" in res.data or b"AUTHENTICITY COULD NOT BE ESTABLISHED" in res.data
    print(" [x] POST /verify (Unknown Notice) -> 200 OK (UNKNOWN IDENTIFIER / UNVERIFIED)")

    # 11. Admin Logout
    res = client.get('/admin/logout', follow_redirects=True)
    assert res.status_code == 200
    assert b"Administrator Portal" in res.data
    print(" [x] GET /admin/logout -> 200 OK")

    print("\nALL FLASK APPLICATION ROUTES & WORKFLOWS VALIDATED 100% SUCCESSFULLY!")

if __name__ == '__main__':
    test_all_routes()
