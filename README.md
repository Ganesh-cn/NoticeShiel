# NoticeShield 🛡️
### AI-Assisted College Notice Authentication System
**NEUROFORGE 2026 AI Hackathon | GM University, Davanagere**  
*Problem Statement: THE FORWARDED SEAL – Verifying the authenticity of official notices after forwarding, compression, cropping, and screenshots.*

---

## 🌟 Tagline
> **"Trust Every Notice. Verify Before You Believe."**

---

## 📖 1. Project Overview & Problem Statement

College students receive hundreds of circulars, exam notifications, holiday declarations, and hackathon schedules forwarded through **WhatsApp, Telegram, and social media**. 

### The Threat Model:
1. **Malicious Tampering**: Attackers easily edit dates, venues, or payment QR codes on genuine posters using Canva or Photoshop.
2. **The "Copied QR" Trap**: Attackers crop a genuine QR code from an official circular and paste it onto a fake or altered circular. Scanning the QR code alone shows a genuine link, misleading students into trusting the tampered poster!
3. **Image Compression Defeating Byte-Level Hashing**: Standard SHA-256 image hashes break the moment an image is sent on WhatsApp, screenshotted, or cropped, because recompression modifies pixel bytes even if the text is 100% genuine.

### How NoticeShield Solves It:
NoticeShield introduces a **Dual-Layer Authentication Architecture**:
1. **Cryptographic Layer (Ed25519 Asymmetric Signatures)**: College administrators register notice fields into canonical structured JSON (`title`, `notice_date`, `event_date`, `venue`, `issuer`, `description`). The backend signs this data using a private Ed25519 key and embeds a high-error-correction QR code onto the official downloadable PDF.
2. **AI Optical Character Recognition (OCR) Layer (EasyOCR & PyMuPDF)**: When a student uploads a forwarded screenshot or photo, NoticeShield scans the QR code, loads the official record, verifies the Ed25519 signature with the university's public key, and **uses OCR to inspect the visible text on the image**. If a scammer altered the date or venue, NoticeShield detects the discrepancy and flags the notice as **MODIFIED / TAMPERED**.

---

## 🏗️ 2. System Architecture

```
[ College Administrator ]
           │
           ▼
[ Notice Registration Form ] ──► [ Canonical JSON Serializer ]
                                             │
                                             ▼
                               [ Ed25519 Private Key Signer ]
                                             │
                      ┌──────────────────────┴──────────────────────┐
                      ▼                                             ▼
             [ SQLite Database ]                            [ PDF Generator ]
        (notices, admins, audit logs)                  (ReportLab + QR Code Seal)
                                                                    │
                                                                    ▼
                                                       [ Official College Circular ]
                                                                    │
                                     (Forwarded, screenshotted, compressed on WhatsApp)
                                                                    │
                                                                    ▼
[ Student Verification Portal ] ◄───────────────────────────────────┘
           │
           ├─► STEP 1: OpenCV QR Code Scanner (Multi-pass CLAHE / Thresholding)
           ├─► STEP 2: Notice ID Lookup in SQLite Registry
           ├─► STEP 3: Check Notice Status (Active vs Revoked)
           ├─► STEP 4: Ed25519 Digital Signature Verification (Public Key)
           ├─► STEP 5: AI OCR Text Extraction (EasyOCR & PyMuPDF)
           ├─► STEP 6: Semantic Field Comparison (Title, Dates, Venue, Instructions)
           │
           ▼
[ Verification Verdict Banner & Transparency Report ]
   ├── A. VERIFIED (Green)   - Authentic notice, valid signature & 100% content match
   ├── B. MODIFIED (Red)     - Signature matches, but visible date/venue was tampered!
   ├── C. UNVERIFIED (Amber) - Unknown ID, missing QR code, or unreadable OCR
   ├── D. REVOKED (Dark Red) - Officially cancelled circular
   └── E. INVALID SIGNATURE  - Forged cryptographic signature
```

---

## 🛠️ 3. Technology Stack

- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5.3, Bootstrap Icons, Chart.js.
- **Backend**: Python 3.10+ / 3.14, Flask.
- **Database**: SQLite3 (`notices.db`) with parameterized queries.
- **Cryptography**: Python `cryptography` library, Ed25519 asymmetric key pairs, SHA-256.
- **QR Code Engine**: `qrcode[pil]`, OpenCV (`cv2.QRCodeDetector`) with multi-pass preprocessors.
- **OCR Engine**: `easyocr` (offline PyTorch models) and `pymupdf` (PDF raster & text parser).
- **PDF Engine**: `reportlab` for official printable academic circulars.
- **100% Local**: No paid APIs, no third-party cloud subscriptions. Runs completely offline on a laptop.

---

## 🚀 4. Beginner-Friendly Setup Guide (Windows / Mac / Linux)

### Step 1: Open the Project Folder
Open VS Code and open the `Notice shield` directory:
```powershell
cd "c:\Users\Yashwanth G\OneDrive\Desktop\Notice shield"
```

### Step 2: (Optional) Create a Virtual Environment
```powershell
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Generate Demo Test Notices & Seed Database
Run the test generator script to seed GM University's demo circulars:
```powershell
python generate_test_samples.py
```

### Step 5: Start the NoticeShield Web Application
```powershell
python app.py
```

### Step 6: Open in Your Browser
Open your browser and navigate to:
👉 **`http://127.0.0.1:5000`**

---

## 🔐 5. Default Credentials

- **Admin Login URL**: `http://127.0.0.1:5000/admin/login`
- **Username**: `admin`
- **Password**: `admin123`

---

## 🧪 6. Hackathon Demonstration Scenarios

| Test Case | Uploaded File | Description | Expected Verdict |
|:---|:---|:---|:---|
| **TEST 1: Genuine Notice** | `test_samples/test1_genuine_notice.png` or `generated_notices/NS-2026-NEURO01.pdf` | Official circular issued by AIML & Robotics Club with authentic QR & signature. | **VERIFIED (Green)** |
| **TEST 2: Modified Notice** | `test_samples/test2_modified_notice.png` | Scammer changed Event Date to `15 December 2026` and Venue to `Convention Hall B, Bangalore`, but retained the original QR code! | **MODIFIED (Red)** - Flags exact tampered fields! |
| **TEST 3: Unknown Notice** | `test_samples/test3_unknown_notice.png` | Unregistered notice or counterfeit circular not in university ledger. | **UNVERIFIED (Amber)** |
| **TEST 4: Screenshot Notice** | `test_samples/test4_screenshot_notice.png` | WhatsApp mobile screenshot with lossy compression, status bar, and downscaling. | **VERIFIED (Green)** |
| **TEST 5: Revoked Notice** | `generated_notices/NS-2026-REVOKED01.pdf` | Official circular that was cancelled/revoked by the college administration. | **REVOKED (Red)** |

---

## 📊 7. Automated Test Execution

You can run our automated test runner at any time:
```powershell
python run_verification_tests.py
```

---

## 🎤 8. Hackathon 2-Minute Presentation Pitch

> *"Good morning, esteemed judges and fellow innovators. Today, our team presents **NoticeShield** for the NEUROFORGE 2026 AI Hackathon.*
> 
> *The problem we are addressing is **THE FORWARDED SEAL**. Every day in college group chats, circulars get forwarded, screenshotted, and recompressed. Malicious actors take real circulars, alter the date or venue in Canva, and share them. If you only check a QR code, you get tricked because the scammer left the original QR code on the poster! If you try using a file hash, standard WhatsApp compression breaks the hash completely.*
> 
> *NoticeShield solves this with a **Dual Cryptographic and AI Vision Pipeline**:*
> *1. When our college issues a notice, we canonicalize the structured fields and digitally sign them using **Ed25519**.*
> *2. When a student uploads a screenshot, NoticeShield uses **OpenCV** to locate the seal, verifies the signature with the university's public key, and unleashes **deep learning OCR** to inspect the visible text.*
> *3. If a scammer changed '6 November' to '15 December', NoticeShield immediately catches the discrepancy and screams **NOTICE CONTENT MISMATCH**.*
> 
> *With NoticeShield, we give universities a tamper-proof seal and students total peace of mind. **Trust Every Notice. Verify Before You Believe.** Thank you!"*
