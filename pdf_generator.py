"""
NoticeShield - Official PDF Notice Generator Module
Generates high-fidelity, printable academic notices with official university headers,
structured notice details, digital security seals, diagonal watermarks, official
signature stamps, and embedded verification QR codes.
Also converts generated notices into PNG images for screenshot and forwarded image testing.
"""

import os
import math
import fitz  # PyMuPDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, HRFlowable
)
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import Color

from qr_generator import generate_notice_qr

NOTICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'generated_notices')
IMAGES_DIR = os.path.join(NOTICES_DIR, 'images')


# ---------------------------------------------------------------------------
# Watermark & Signature stamp helpers
# ---------------------------------------------------------------------------

def _add_watermark_and_stamp(pdf_path: str, notice_dict: dict):
    """
    Uses PyMuPDF (fitz) to overlay:
      1. A diagonal semi-transparent WATERMARK text across every page.
      2. An official round SIGNATURE STAMP in the bottom-right corner.
    Writes the result back to the same pdf_path.
    """
    try:
        doc = fitz.open(pdf_path)
        page_w, page_h = letter  # 612 x 792 pts

        for page in doc:
            # ── 1. DIAGONAL WATERMARK ──────────────────────────────────────
            wm_text = "GM UNIVERSITY  •  OFFICIAL NOTICE"
            # Font size chosen so text spans ~70% of page width diagonally
            font_size = 36
            # Rotate 45° anti-clockwise; centre of page
            cx, cy = page_w / 2, page_h / 2

            # Insert watermark text twice (top-left and bottom-right quadrant)
            for offset_x, offset_y in [(-130, 130), (130, -130)]:
                page.insert_text(
                    fitz.Point(cx + offset_x - 180, cy + offset_y),
                    wm_text,
                    fontsize=font_size,
                    fontname="helv",
                    color=(0.80, 0.86, 0.95),   # very light blue
                    rotate=45,
                    overlay=False               # draw behind content
                )

            # ── 2. OFFICIAL ROUND SIGNATURE STAMP ────────────────────────
            # Position: bottom-right corner, 10 pt margin from edge
            stamp_r = 52          # radius in points
            stamp_cx = page_w - stamp_r - 14
            stamp_cy = stamp_r + 14 + 20   # from bottom; fitz y=0 is top-left

            # Outer circle (navy border)
            page.draw_circle(
                fitz.Point(stamp_cx, page_h - stamp_cy),
                stamp_r,
                color=(0.06, 0.09, 0.17),   # #0F172A navy
                width=2.0
            )
            # Inner circle (thinner)
            page.draw_circle(
                fitz.Point(stamp_cx, page_h - stamp_cy),
                stamp_r - 6,
                color=(0.06, 0.09, 0.17),
                width=0.8
            )

            # Star in centre
            page.insert_text(
                fitz.Point(stamp_cx - 5, page_h - stamp_cy + 5),
                "★",
                fontsize=12,
                fontname="helv",
                color=(0.06, 0.09, 0.17),
            )

            # Text arced around the stamp (approximated with two straight lines)
            issuer_short = notice_dict.get('issuer', 'GMU')[:22].upper()
            page.insert_text(
                fitz.Point(stamp_cx - 46, page_h - stamp_cy - stamp_r + 14),
                "GM UNIVERSITY",
                fontsize=6.5,
                fontname="helv",
                color=(0.06, 0.09, 0.17),
            )
            page.insert_text(
                fitz.Point(stamp_cx - 44, page_h - stamp_cy + stamp_r - 7),
                "OFFICIAL SEAL",
                fontsize=6.5,
                fontname="helv",
                color=(0.06, 0.09, 0.17),
            )
            # Issuer name centred in stamp
            page.insert_text(
                fitz.Point(stamp_cx - min(len(issuer_short) * 2.4, 44),
                           page_h - stamp_cy + 3),
                issuer_short[:16],
                fontsize=5.8,
                fontname="helv",
                color=(0.02, 0.47, 0.44),   # teal
            )

        doc.save(pdf_path, incremental=False, encryption=fitz.PDF_ENCRYPT_NONE)
        doc.close()
    except Exception as e:
        print(f"Warning: could not overlay watermark/stamp: {e}")

def generate_official_notice_pdf(notice_dict: dict, host_base_url: str = "http://127.0.0.1:5000") -> dict:
    """
    Generates a professional academic notice PDF with embedded QR code.
    Also produces a companion PNG image of the document for screenshot/forwarding testing.
    
    Returns:
    {
        "pdf_path": str,
        "image_path": str,
        "qr_path": str
    }
    """
    os.makedirs(NOTICES_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    notice_id = notice_dict['notice_id']
    pdf_filename = f"{notice_id}.pdf"
    pdf_path = os.path.join(NOTICES_DIR, pdf_filename)
    
    # 1. Generate QR Code
    qr_path = generate_notice_qr(notice_id, host_base_url)

    # 2. Setup PDF document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_univ_style = ParagraphStyle(
        'UnivTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=1, # Center
        textColor=colors.HexColor('#0F172A')
    )
    
    sub_univ_style = ParagraphStyle(
        'UnivSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=1, # Center
        textColor=colors.HexColor('#475569')
    )

    ref_style = ParagraphStyle(
        'RefStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1E293B')
    )

    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=2, # Right
        textColor=colors.HexColor('#1E293B')
    )

    notice_heading_style = ParagraphStyle(
        'NoticeHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        alignment=1, # Center
        textColor=colors.HexColor('#0284C7')
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=15,
        alignment=4, # Justify
        textColor=colors.HexColor('#1E293B')
    )

    security_notice_style = ParagraphStyle(
        'SecNotice',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#0F766E')
    )

    sec_desc_style = ParagraphStyle(
        'SecDesc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9.5,
        textColor=colors.HexColor('#334155')
    )

    story = []

    # University Header
    story.append(Paragraph("GM UNIVERSITY", title_univ_style))
    story.append(Paragraph("ESTABLISHED UNDER GM UNIVERSITY ACT, 2021 | NAAC ACCREDITED", sub_univ_style))
    story.append(Paragraph("Post Box No. 4, P.B. Road, Davanagere, Karnataka - 577006", sub_univ_style))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0284C7'), spaceBefore=2, spaceAfter=8))

    # Meta Bar: Ref No & Date
    meta_table_data = [
        [
            Paragraph(f"<b>Ref No:</b> GMU/{notice_dict.get('department', 'ADMIN')[:4].upper()}/2026/NOT-{notice_id[-4:]}", ref_style),
            Paragraph(f"<b>Notice Date:</b> {notice_dict.get('notice_date', '')}", date_style)
        ]
    ]
    meta_table = Table(meta_table_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Official Circular Title
    story.append(Paragraph(f"CIRCULAR: {notice_dict.get('title', 'OFFICIAL NOTIFICATION').upper()}", notice_heading_style))
    story.append(Spacer(1, 10))

    # Structured Event Summary Table
    detail_data = [
        [Paragraph("<b>Issuing Department:</b>", ref_style), Paragraph(notice_dict.get('department', ''), body_style)],
        [Paragraph("<b>Event Date:</b>", ref_style), Paragraph(f"<b>{notice_dict.get('event_date', '')}</b>", body_style)],
        [Paragraph("<b>Official Venue:</b>", ref_style), Paragraph(f"<b>{notice_dict.get('venue', '')}</b>", body_style)],
        [Paragraph("<b>Authorized Issuer:</b>", ref_style), Paragraph(notice_dict.get('issuer', ''), body_style)]
    ]
    detail_table = Table(detail_data, colWidths=[140, 400])
    detail_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 14))

    # Notice Body / Description
    desc_text = notice_dict.get('description', '')
    story.append(Paragraph(f"<b>Notification Details:</b>", ref_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(desc_text.replace('\n', '<br/>'), body_style))
    story.append(Spacer(1, 14))

    # Instructions box
    instructions_text = (
        "<b>Important Instructions for Students and Participants:</b><br/>"
        "1. All attendees must carry their valid University Identity Card.<br/>"
        "2. Any alteration, tampering, or misrepresentation of this circular is strictly prohibited and punishable.<br/>"
        "3. Please verify the authenticity of this circular on the official NoticeShield portal before sharing."
    )
    inst_table = Table([[Paragraph(instructions_text, body_style)]], colWidths=[540])
    inst_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6FF')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#93C5FD')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(inst_table)
    story.append(Spacer(1, 18))

    # Security Seal & QR Code Block with Signatures
    qr_img = RLImage(qr_path, width=1.1*inch, height=1.1*inch)
    
    sec_info = (
        f"<b>NOTICESHIELD DIGITAL AUTHENTICITY SEAL</b><br/>"
        f"Notice ID: <b>{notice_id}</b><br/>"
        f"Signed with Ed25519 Cryptographic Key.<br/>"
        f"Scan QR code with NoticeShield or camera to verify authenticity against the tamper-proof ledger.<br/>"
        f"<i>Status: Digitally Signed & Officially Registered.</i>"
    )

    sign_info = (
        "<br/><br/>"
        "<b>________________________</b><br/>"
        f"<b>{notice_dict.get('issuer', 'Authorized Signatory')}</b><br/>"
        "GM University, Davanagere"
    )

    bottom_table_data = [
        [
            qr_img,
            Paragraph(sec_info, sec_desc_style),
            Paragraph(sign_info, ParagraphStyle('SignRight', parent=styles['Normal'], alignment=2, fontSize=8, leading=12))
        ]
    ]
    bottom_table = Table(bottom_table_data, colWidths=[90, 290, 160])
    bottom_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (1, 0), 1, colors.HexColor('#0D9488')), # Teal border around seal & QR
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#F0FDFA')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(bottom_table)

    # Build the PDF
    doc.build(story)

    # Overlay diagonal watermark + official round signature stamp
    _add_watermark_and_stamp(pdf_path, notice_dict)

    # Convert the PDF page to a PNG image for direct image viewing/screenshot testing
    image_filename = f"{notice_id}.png"
    image_path = os.path.join(IMAGES_DIR, image_filename)
    try:
        pdf_doc = fitz.open(pdf_path)
        first_page = pdf_doc[0]
        pix = first_page.get_pixmap(dpi=150)
        pix.save(image_path)
        pdf_doc.close()
    except Exception as e:
        print(f"Warning: could not render PNG from PDF: {e}")
        image_path = ""

    return {
        "pdf_path": pdf_path,
        "image_path": image_path,
        "qr_path": qr_path
    }
