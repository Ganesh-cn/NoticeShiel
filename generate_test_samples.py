"""
NoticeShield - Demo Test Sample Generator
Creates all hackathon test notices for the 4 core evaluation scenarios:
TEST 1: Genuine Notice (Original official notice with valid signature & QR)
TEST 2: Modified Notice (Tampered date and venue with original genuine QR code)
TEST 3: Unknown Notice (Fake notice with unregistered ID or no QR code)
TEST 4: Screenshot / Forwarded Notice (Compressed and cropped mobile screenshot)
TEST 5: Revoked Notice (Officially cancelled circular)
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import database as db
import security
import pdf_generator
import qr_generator

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(BASE_DIR, 'uploads')
GENERATED_DIR = os.path.join(BASE_DIR, 'generated_notices')
TEST_DIR = os.path.join(BASE_DIR, 'test_samples')

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(TEST_DIR, exist_ok=True)

def generate_all_test_assets():
    print("Initializing Database & Cryptographic Keys...")
    db.init_db()
    security.ensure_keys_exist()

    # ---------------- 1. TEST 1: Genuine Notice ----------------
    print("\n[TEST 1] Generating Genuine Notice: NS-2026-NEURO01...")
    genuine_notice = {
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

    canon_json = security.canonicalize_notice_data(genuine_notice)
    signature = security.sign_canonical_data(canon_json)
    genuine_notice['canonical_data'] = canon_json
    genuine_notice['digital_signature'] = signature

    paths = pdf_generator.generate_official_notice_pdf(genuine_notice)
    genuine_notice['pdf_path'] = paths['pdf_path']
    genuine_notice['qr_path'] = paths['qr_path']

    existing = db.get_notice_by_id(genuine_notice['notice_id'])
    if not existing:
        db.save_notice(genuine_notice)

    genuine_img_path = paths['image_path']
    test1_target = os.path.join(TEST_DIR, 'test1_genuine_notice.png')
    test1_upload = os.path.join(UPLOADS_DIR, 'test1_genuine_notice.png')
    
    img = Image.open(genuine_img_path)
    img.save(test1_target)
    img.save(test1_upload)
    print(f" -> Genuine Notice PDF: {paths['pdf_path']}")
    print(f" -> Genuine Notice Image: {test1_target}")

    # ---------------- 2. TEST 2: Modified Notice ----------------
    # An attacker creates a modified notice with changed Event Date & Venue
    # but copies & embeds the original genuine QR code of NS-2026-NEURO01!
    print("\n[TEST 2] Generating Modified / Tampered Notice...")
    tampered_notice = {
        'notice_id': 'NS-2026-NEURO01', # Copies original QR code!
        'title': 'NEUROFORGE 2026 – AI Hackathon',
        'department': 'AIML & Robotics Club',
        'notice_date': '06 November 2026',
        'event_date': '15 December 2026 (FORGED)', # Tampered date
        'venue': 'Convention Hall B, Bangalore (FAKE)', # Tampered venue
        'description': (
            'Six-hour AI hackathon organized by AIML & Robotics Club. '
            'POSTPONED TO DECEMBER AND RELOCATED TO BANGALORE. '
            'Participants must report to Convention Hall B at 09:00 AM.'
        ),
        'issuer': 'Head of Department / AIML & Robotics Club'
    }

    # Generate a PDF with the tampered content, but using the GENUINE QR code!
    # Temporarily save under a special filename
    import fitz
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
    from reportlab.lib.units import inch

    mod_pdf_path = os.path.join(GENERATED_DIR, "test2_modified_notice.pdf")
    doc_mod = SimpleDocTemplate(mod_pdf_path, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()

    title_univ_style = ParagraphStyle('UnivTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=18, leading=22, alignment=1, textColor=colors.HexColor('#0F172A'))
    sub_univ_style = ParagraphStyle('UnivSub', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, alignment=1, textColor=colors.HexColor('#475569'))
    ref_style = ParagraphStyle('RefStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#1E293B'))
    date_style = ParagraphStyle('DateStyle', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, alignment=2, textColor=colors.HexColor('#1E293B'))
    notice_heading_style = ParagraphStyle('NoticeHeading', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=18, alignment=1, textColor=colors.HexColor('#DC2626'))
    body_style = ParagraphStyle('BodyDark', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=15, alignment=4, textColor=colors.HexColor('#1E293B'))
    sec_desc_style = ParagraphStyle('SecDesc', parent=styles['Normal'], fontName='Helvetica', fontSize=7, leading=9.5, textColor=colors.HexColor('#334155'))

    story_mod = []
    story_mod.append(Paragraph("GM UNIVERSITY", title_univ_style))
    story_mod.append(Paragraph("ESTABLISHED UNDER GM UNIVERSITY ACT, 2021 | NAAC ACCREDITED", sub_univ_style))
    story_mod.append(Spacer(1, 6))
    story_mod.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#DC2626'), spaceBefore=2, spaceAfter=8))

    meta_table_mod = Table([
        [
            Paragraph("<b>Ref No:</b> GMU/AIML/2026/NOT-RO01", ref_style),
            Paragraph("<b>Notice Date:</b> 06 November 2026", date_style)
        ]
    ], colWidths=[270, 270])
    story_mod.append(meta_table_mod)
    story_mod.append(Spacer(1, 10))

    story_mod.append(Paragraph("CIRCULAR: NEUROFORGE 2026 – AI HACKATHON", notice_heading_style))
    story_mod.append(Spacer(1, 10))

    detail_data_mod = [
        [Paragraph("<b>Issuing Department:</b>", ref_style), Paragraph(tampered_notice['department'], body_style)],
        [Paragraph("<b>Event Date:</b>", ref_style), Paragraph(f"<b><font color='#DC2626'>{tampered_notice['event_date']}</font></b>", body_style)],
        [Paragraph("<b>Official Venue:</b>", ref_style), Paragraph(f"<b><font color='#DC2626'>{tampered_notice['venue']}</font></b>", body_style)],
        [Paragraph("<b>Authorized Issuer:</b>", ref_style), Paragraph(tampered_notice['issuer'], body_style)]
    ]
    detail_table_mod = Table(detail_data_mod, colWidths=[140, 400])
    detail_table_mod.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF1F2')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#FDA4AF')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#FECDD3')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story_mod.append(detail_table_mod)
    story_mod.append(Spacer(1, 14))

    story_mod.append(Paragraph("<b>Notification Details:</b>", ref_style))
    story_mod.append(Spacer(1, 4))
    story_mod.append(Paragraph(tampered_notice['description'], body_style))
    story_mod.append(Spacer(1, 18))

    # Paste the original genuine QR code!
    qr_img = RLImage(paths['qr_path'], width=1.1*inch, height=1.1*inch)
    sec_info = (
        "<b>NOTICESHIELD DIGITAL AUTHENTICITY SEAL</b><br/>"
        "Notice ID: <b>NS-2026-NEURO01</b><br/>"
        "Signed with Ed25519 Cryptographic Key.<br/>"
        "<i>Status: Digitally Signed & Officially Registered.</i>"
    )
    sign_info = "<br/><br/><b>________________________</b><br/><b>Head of Department / AIML Club</b><br/>GM University, Davanagere"

    bottom_table = Table([[qr_img, Paragraph(sec_info, sec_desc_style), Paragraph(sign_info, ParagraphStyle('SR', parent=styles['Normal'], alignment=2, fontSize=8, leading=12))]], colWidths=[90, 290, 160])
    bottom_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (1, 0), 1, colors.HexColor('#0D9488')),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#F0FDFA')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story_mod.append(bottom_table)
    doc_mod.build(story_mod)

    # Render to PNG
    test2_target = os.path.join(TEST_DIR, 'test2_modified_notice.png')
    test2_upload = os.path.join(UPLOADS_DIR, 'test_modified_notice.png')
    pdf_doc = fitz.open(mod_pdf_path)
    pix = pdf_doc[0].get_pixmap(dpi=150)
    pix.save(test2_target)
    pix.save(test2_upload)
    pdf_doc.close()
    print(f" -> Modified Notice Image: {test2_target}")

    # ---------------- 3. TEST 3: Unknown Notice ----------------
    print("\n[TEST 3] Generating Unknown Notice with Unregistered ID...")
    unknown_img = Image.new('RGB', (1000, 1300), color='#FFFFFF')
    draw_unk = ImageDraw.Draw(unknown_img)
    
    try:
        font_large = ImageFont.truetype("arial.ttf", 26)
        font_bold = ImageFont.truetype("arialbd.ttf", 26)
    except Exception:
        font_large = ImageFont.load_default()
        font_bold = font_large

    draw_unk.rectangle([(0, 0), (1000, 120)], fill='#0F172A')
    draw_unk.text((250, 40), "XYZ INSTITUTE OF TECHNOLOGY", fill='#FFFFFF', font=font_bold)
    draw_unk.text((320, 80), "UNOFFICIAL CIRCULAR", fill='#38BDF8', font=font_large)

    draw_unk.text((80, 200), "Notice ID: NS-9999-FAKE0000 (UNREGISTERED)", fill='#0F172A', font=font_bold)
    draw_unk.text((80, 260), "Circular: Annual Tech Festival 2026", fill='#0F172A', font=font_large)
    draw_unk.text((80, 320), "Event Date: 20 December 2026", fill='#0F172A', font=font_large)
    draw_unk.text((80, 380), "Venue: Unknown Campus Ground", fill='#0F172A', font=font_large)
    draw_unk.text((80, 460), "This notice does not exist in GM University NoticeShield database.", fill='#64748B', font=font_large)

    fake_qr_path = qr_generator.generate_notice_qr("NS-9999-FAKE0000")
    fake_qr = Image.open(fake_qr_path).resize((180, 180))
    unknown_img.paste(fake_qr, (80, 550))
    draw_unk.text((280, 620), "Unregistered / Counterfeit Seal", fill='#DC2626', font=font_bold)

    test3_target = os.path.join(TEST_DIR, 'test3_unknown_notice.png')
    test3_upload = os.path.join(UPLOADS_DIR, 'test_unknown_notice.png')
    unknown_img.save(test3_target)
    unknown_img.save(test3_upload)
    print(f" -> Unknown Notice Image: {test3_target}")

    # ---------------- 4. TEST 4: Screenshot / Forwarded Notice ----------------
    print("\n[TEST 4] Generating Mobile Screenshot / Compressed Forwarded Notice...")
    screen_base = Image.open(genuine_img_path)
    sw, sh = screen_base.size
    screen_resized = screen_base.resize((int(sw * 0.75), int(sh * 0.75)), Image.Resampling.LANCZOS)
    
    rw, rh = screen_resized.size
    mobile_canvas = Image.new('RGB', (rw, rh + 60), color='#0B1120')
    draw_mob = ImageDraw.Draw(mobile_canvas)
    draw_mob.text((20, 15), "10:30 AM  •  WhatsApp Forwarded", fill='#94A3B8', font=font_large)
    draw_mob.text((rw - 120, 15), "89% [|||]", fill='#94A3B8', font=font_large)
    mobile_canvas.paste(screen_resized, (0, 60))

    test4_target = os.path.join(TEST_DIR, 'test4_screenshot_notice.png')
    test4_upload = os.path.join(UPLOADS_DIR, 'test_screenshot_notice.png')
    temp_jpg = os.path.join(UPLOADS_DIR, 'temp_compressed.jpg')
    mobile_canvas.save(temp_jpg, quality=65)
    compressed_img = Image.open(temp_jpg)
    compressed_img.save(test4_target)
    compressed_img.save(test4_upload)
    if os.path.exists(temp_jpg):
        os.remove(temp_jpg)
    print(f" -> Screenshot / Forwarded Notice Image: {test4_target}")

    # ---------------- 5. TEST 5: Revoked Notice ----------------
    print("\n[TEST 5] Registering Revoked Notice: NS-2026-REVOKED01...")
    revoked_notice = {
        'notice_id': 'NS-2026-REVOKED01',
        'title': 'Annual Inter-College Sports Fest 2026',
        'department': 'Department of Physical Education',
        'notice_date': '01 November 2026',
        'event_date': '12 November 2026',
        'venue': 'University Sports Complex, Davanagere',
        'description': 'Inter-collegiate sports tournament. CANCELLED DUE TO RAIN FORECAST.',
        'issuer': 'Director of Physical Education',
        'status': 'revoked'
    }
    c_json = security.canonicalize_notice_data(revoked_notice)
    sig = security.sign_canonical_data(c_json)
    revoked_notice['canonical_data'] = c_json
    revoked_notice['digital_signature'] = sig

    r_paths = pdf_generator.generate_official_notice_pdf(revoked_notice)
    revoked_notice['pdf_path'] = r_paths['pdf_path']
    revoked_notice['qr_path'] = r_paths['qr_path']

    if not db.get_notice_by_id("NS-2026-REVOKED01"):
        db.save_notice(revoked_notice)
        db.revoke_notice("NS-2026-REVOKED01")
    else:
        db.revoke_notice("NS-2026-REVOKED01")

    print(f" -> Revoked Notice Seeded: NS-2026-REVOKED01 (Status: REVOKED)")
    print("\nAll 5 Test Demonstration Assets Generated Successfully!")

if __name__ == '__main__':
    generate_all_test_assets()
