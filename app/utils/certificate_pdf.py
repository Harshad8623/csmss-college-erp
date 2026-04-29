"""
certificate_pdf.py — Generates official, professional A4 certificate PDFs.

Features:
  • Times-Roman professional serif font throughout
  • Student name, academic year, branch in BOLD in the body text
  • QR code for tamper-evident verification (scan → verify on the ERP)
  • Principal: Dr. G. B. Dongre (correct signatory)
  • Serial number, date, college letterhead with logo
  • Valid only when physically signed & stamped
"""

import os
import io
import hashlib
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether,
)

import qrcode
from qrcode.image.pil import PilImage

# ── College constants ────────────────────────────────────────────────────────
COLLEGE_NAME     = "CSMSS Chh. Shahu College of Engineering"
COLLEGE_SUBTITLE = "Kanchanwadi, Aurangabad – 431 002 (M.S.)"
COLLEGE_AFFIL    = ("Affiliated to Dr. Babasaheb Ambedkar Marathwada University, "
                    "Chhatrapati Sambhajinagar")
COLLEGE_PHONE    = "Tel: 0240-2376111  |  Email: principal@csmss.ac.in"
PRINCIPAL_NAME   = "Dr. G. B. Dongre"
PRINCIPAL_TITLE  = "Principal"

YEAR_LABELS = {
    1: "First Year (F.E.)",
    2: "Second Year (S.E.)",
    3: "Third Year (T.E.)",
    4: "Fourth Year (B.E.)",
}

CERT_TITLES = {
    "bonafide":  "BONAFIDE CERTIFICATE",
    "character": "CHARACTER CERTIFICATE",
    "leaving":   "LEAVING CERTIFICATE",
    "transfer":  "TRANSFER CERTIFICATE",
}

# Body text: {name}, {year_label}, {department} will be injected as bold inline
CERTIFICATE_BODY = {
    "bonafide": (
        "This is to certify that <b>{name}</b>, PRN No. {prn}, "
        "is a bonafide student of this institution and is currently studying in "
        "<b>{year_label}</b>, Department of <b>{department}</b>, "
        "for the academic year <b>{academic_year}</b>.\n\n"
        "He / She bears a good moral character and his / her conduct is satisfactory."
    ),
    "character": (
        "This is to certify that <b>{name}</b>, PRN No. {prn}, "
        "was a bonafide student of this institution and was studying in "
        "<b>{year_label}</b>, Department of <b>{department}</b>.\n\n"
        "During his / her tenure at this institution, his / her character and conduct "
        "were found to be satisfactory. He / She has no pending dues or disciplinary "
        "action against his / her name."
    ),
    "leaving": (
        "This is to certify that <b>{name}</b>, PRN No. {prn}, "
        "was enrolled as a student in <b>{year_label}</b>, "
        "Department of <b>{department}</b>.\n\n"
        "He / She has left this institution on {date}. "
        "His / Her conduct and character during his / her stay at this institution were "
        "satisfactory. He / She has cleared all dues of the institution."
    ),
    "transfer": (
        "This is to certify that <b>{name}</b>, PRN No. {prn}, "
        "was a bonafide student of this institution in "
        "<b>{year_label}</b>, Department of <b>{department}</b>.\n\n"
        "He / She is hereby granted this Transfer Certificate as he / she is leaving "
        "this institution. His / Her conduct was good during his / her stay here. "
        "He / She has no pending dues or disciplinary record."
    ),
}


# ── Colour palette ───────────────────────────────────────────────────────────
NAVY   = colors.HexColor("#0d2366")
DARK   = colors.HexColor("#111111")
MUTED  = colors.HexColor("#555555")
RULE   = colors.HexColor("#0d2366")
LIGHT  = colors.HexColor("#888888")


def _make_verification_token(cert_id: int, secret: str) -> str:
    """Generate a short, URL-safe HMAC token for QR verification."""
    raw = f"cert-{cert_id}-{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _make_qr_image(url: str) -> io.BytesIO:
    """Generate a QR code PNG image and return as BytesIO."""
    qr = qrcode.QRCode(
        version=2,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=6,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0d2366", back_color="white", image_factory=PilImage)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_certificate_pdf(cert, app) -> bytes:
    """
    Generate a professional A4 certificate PDF with QR verification code.

    :param cert:  Certificate model instance (must be approved)
    :param app:   Flask application instance
    :return:      PDF as bytes
    """
    secret     = app.config.get("SECRET_KEY", "csmss")
    base_url   = app.config.get("SERVER_NAME") or "https://csmss-college-erp.onrender.com"
    token      = _make_verification_token(cert.id, secret)
    verify_url = f"{base_url}/certificate/verify/{cert.id}/{token}"

    buf = io.BytesIO()
    W, H = A4
    MARGIN = 2.4 * cm
    content_w = W - 2 * MARGIN

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=MARGIN, leftMargin=MARGIN,
        topMargin=1.8 * cm, bottomMargin=2.2 * cm,
    )

    # ── Style helpers ────────────────────────────────────────────────────────
    def S(name, **kw):
        defaults = dict(fontName="Times-Roman", fontSize=11,
                        textColor=DARK, leading=16)
        defaults.update(kw)
        return ParagraphStyle(name, **defaults)

    sCollegeName  = S("CN",  fontName="Times-Bold",   fontSize=17, textColor=NAVY,
                       alignment=TA_CENTER, spaceAfter=2, leading=20)
    sCollegeSub   = S("CS",  fontSize=9,  alignment=TA_CENTER, textColor=MUTED,
                       spaceAfter=1, leading=12)
    sCertTitle    = S("CT",  fontName="Times-Bold",   fontSize=15, textColor=NAVY,
                       alignment=TA_CENTER, spaceBefore=10, spaceAfter=2, leading=18)
    sMeta         = S("MT",  fontSize=9.5, textColor=MUTED, leading=13)
    sSubject      = S("SB",  fontName="Times-Bold",   fontSize=11, textColor=DARK,
                       spaceBefore=10, spaceAfter=4, leading=14)
    sBody         = S("BD",  fontSize=11.5, alignment=TA_JUSTIFY,
                       spaceAfter=8, leading=20)
    sLabelBold    = S("LB",  fontName="Times-Bold",   fontSize=10.5, textColor=DARK)
    sLabelVal     = S("LV",  fontSize=10.5, textColor=DARK)
    sSignCenter   = S("SC",  alignment=TA_CENTER, fontSize=10.5, leading=16)
    sSignBold     = S("SB2", fontName="Times-Bold",   fontSize=10.5,
                       alignment=TA_CENTER, textColor=DARK, leading=14)
    sFooter       = S("FT",  fontSize=7.5, alignment=TA_CENTER,
                       textColor=LIGHT, leading=10, spaceBefore=4)
    sQRLabel      = S("QL",  fontSize=7.5, alignment=TA_CENTER,
                       textColor=MUTED, leading=10)

    # ── Gather data ──────────────────────────────────────────────────────────
    student     = cert.student
    user        = student.user
    cls         = student.class_
    dept        = cls.department if cls else None
    year_num    = cls.year if cls else 3

    name         = user.name.upper()
    prn          = student.prn or "—"
    roll_no      = student.roll_no or "—"
    class_name   = cls.name if cls else "—"
    department   = dept.name if dept else "—"
    year_label   = YEAR_LABELS.get(year_num, "—")
    academic_yr  = f"{datetime.now().year - 1}–{datetime.now().year}"
    date_str     = datetime.now().strftime("%d %B %Y")
    cert_type    = cert.type.lower()
    serial_no    = f"CSMSS/{datetime.now().year}/{cert.id:04d}"

    body_template = CERTIFICATE_BODY.get(cert_type, CERTIFICATE_BODY["bonafide"])
    body_text = body_template.format(
        name=name, prn=prn, class_name=class_name,
        department=department, year_label=year_label,
        academic_year=academic_yr, date=date_str,
    )

    # ── Story ────────────────────────────────────────────────────────────────
    story = []

    # ── 1. Header: Logo + College name ──────────────────────────────────────
    logo_path = os.path.join(app.static_folder, "img", "college_logo.png")
    college_block = [
        Paragraph(COLLEGE_NAME,     sCollegeName),
        Paragraph(COLLEGE_SUBTITLE, sCollegeSub),
        Paragraph(COLLEGE_AFFIL,    sCollegeSub),
        Paragraph(COLLEGE_PHONE,    sCollegeSub),
    ]

    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.3 * cm, height=2.3 * cm)
        logo_col_w = 2.8 * cm
        hdr = Table(
            [[logo, college_block]],
            colWidths=[logo_col_w, content_w - logo_col_w],
        )
        hdr.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ]))
        story.append(hdr)
    else:
        for p in college_block:
            story.append(p)

    # ── 2. Decorative rule ───────────────────────────────────────────────────
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2.5, color=RULE, spaceAfter=1.5))
    story.append(HRFlowable(width="100%", thickness=0.8, color=RULE, spaceAfter=0))

    # ── 3. Certificate title ─────────────────────────────────────────────────
    title_text = CERT_TITLES.get(cert_type, "CERTIFICATE")
    story.append(Paragraph(title_text, sCertTitle))
    story.append(HRFlowable(width="40%", thickness=1.5, color=NAVY,
                             hAlign="CENTER", spaceAfter=10))

    # ── 4. Serial / date row ─────────────────────────────────────────────────
    meta_row = Table(
        [[Paragraph(f"Cert. No.: {serial_no}", sMeta),
          Paragraph(f"Date: {date_str}",       sMeta)]],
        colWidths=[content_w * 0.5, content_w * 0.5],
    )
    meta_row.setStyle(TableStyle([
        ("ALIGN",         (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_row)
    story.append(Spacer(1, 10))

    # ── 5. Salutation ────────────────────────────────────────────────────────
    story.append(Paragraph("TO WHOM IT MAY CONCERN", sSubject))

    # ── 6. Body paragraphs ───────────────────────────────────────────────────
    for para in body_text.split("\n\n"):
        story.append(Paragraph(para.strip(), sBody))

    story.append(Spacer(1, 12))

    # ── 7. Student detail table ──────────────────────────────────────────────
    detail_rows = [
        ["Student Name", ":", Paragraph(f"<b>{name}</b>",       sLabelVal)],
        ["PRN No.",       ":", Paragraph(prn,                    sLabelVal)],
        ["Roll No.",      ":", Paragraph(roll_no,                sLabelVal)],
        ["Class / Year",  ":", Paragraph(
            f"<b>{class_name} ({year_label})</b>",              sLabelVal)],
        ["Department",    ":", Paragraph(f"<b>{department}</b>", sLabelVal)],
    ]
    detail_table = Table(
        detail_rows,
        colWidths=[3.2 * cm, 0.5 * cm, content_w - 3.7 * cm],
    )
    detail_table.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Times-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10.5),
        ("TEXTCOLOR",     (0, 0), (-1, -1), DARK),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 2),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 22))

    # ── 8. Signature + QR code side by side ──────────────────────────────────
    # QR code
    qr_buf  = _make_qr_image(verify_url)
    qr_img  = Image(qr_buf, width=2.8 * cm, height=2.8 * cm)
    qr_label = Paragraph(
        "Scan to verify authenticity",
        sQRLabel,
    )

    qr_cell = Table([[qr_img], [qr_label]],
                    colWidths=[3.2 * cm])
    qr_cell.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
    ]))

    # Signature block
    sig_lines = [
        Paragraph("<br/><br/><br/>", sSignCenter),
        Paragraph("____________________________", sSignCenter),
        Paragraph(f"<b>{PRINCIPAL_NAME}</b>", sSignBold),
        Paragraph(PRINCIPAL_TITLE, sSignCenter),
        Paragraph(COLLEGE_NAME,    sSignCenter),
    ]
    sig_cell = Table([[p] for p in sig_lines], colWidths=[content_w - 3.8 * cm])
    sig_cell.setStyle(TableStyle([
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
    ]))

    bottom_row = Table(
        [[qr_cell, sig_cell]],
        colWidths=[3.4 * cm, content_w - 3.4 * cm],
    )
    bottom_row.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(bottom_row))

    # ── 9. Footer ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5,
                             color=colors.HexColor("#cccccc"), spaceAfter=4))
    story.append(Paragraph(
        "This certificate is computer-generated. It is valid only when signed and "
        "stamped by the Principal of CSMSS Chh. Shahu College of Engineering. "
        f"Verify at: {verify_url}",
        sFooter,
    ))

    doc.build(story)
    return buf.getvalue()
