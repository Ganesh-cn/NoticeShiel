import sys
sys.path.insert(0, r'c:\Users\Yashwanth G\OneDrive\Desktop\Notice shield')
from app import app

with app.test_client() as c:
    r = c.get('/')
    print('Status:', r.status_code)
    body = r.data.decode('utf-8', errors='replace')
    checks = ['home-verify-form', 'home-dropzone', 'home-file-input', 'home-verify-btn', 'handleHomeDrop', 'previewHomeFile']
    all_ok = True
    for chk in checks:
        found = chk in body
        status = 'OK' if found else 'MISSING'
        print(f'  [{status}] {chk}')
        if not found:
            all_ok = False
    print()
    print('ALL CHECKS PASSED' if all_ok else 'SOME CHECKS FAILED')
