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
from sqlalchemy import extract

from flask import url_for
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
COLLEGE_NAME     = "CHH. SHAHU COLLEGE OF ENGINEERING"
PRINCIPAL_NAME   = "PRINCIPAL"
PRINCIPAL_TITLE  = ""

YEAR_LABELS = {
    1: "First Year",
    2: "Second Year",
    3: "Third Year",
    4: "Fourth Year",
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
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;This is to certify that {name} is Bonafide Student "
        "of this college. He/She is studying in B. Tech {year_label} {department} "
        "during the Academic Year-{academic_year}. His / Her Date of Birth "
        "as per college record is {dob}.\n\n"
        "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;His / Her Conduct & Progress is satisfactory to the best of my knowledge. He "
        "/ She bears a Good Moral Character."
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
    secret = app.config.get("SECRET_KEY", "csmss")
    token  = _make_verification_token(cert.id, secret)

    # Build the absolute verification URL using Flask's url_for so it always
    # matches the actual server the app is running on (local dev OR Render).
    # Falls back to the configured SITE_URL env var if outside a request context.
    try:
        verify_url = url_for(
            'certificate.verify',
            cert_id=cert.id,
            token=token,
            _external=True,
        )
    except RuntimeError:
        # Outside request context (e.g. background job) — use env var fallback
        site_url = app.config.get('SITE_URL', 'https://csmss-college-erp.onrender.com')
        verify_url = f"{site_url.rstrip('/')}/certificate/verify/{cert.id}/{token}"

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

    sSociety      = S("SOC", fontName="Times-Bold",   fontSize=10, textColor=DARK,
                       alignment=TA_CENTER, spaceAfter=2, leading=14)
    sCollegeName  = S("CN",  fontName="Times-Bold",   fontSize=17, textColor=DARK,
                       alignment=TA_CENTER, spaceAfter=4, leading=20)
    sCollegeSub   = S("CS",  fontSize=8,  alignment=TA_CENTER, textColor=DARK,
                       spaceAfter=2, leading=10)
    sCertTitle    = S("CT",  fontName="Times-Bold",   fontSize=18, textColor=DARK,
                       alignment=TA_CENTER, spaceBefore=15, spaceAfter=15, leading=22)
    sMeta         = S("MT",  fontName="Times-Bold", fontSize=10, textColor=DARK, leading=13)
    sSubject      = S("SB",  fontName="Times-Bold",   fontSize=11, textColor=DARK,
                       spaceBefore=10, spaceAfter=4, leading=14)
    sBody         = S("BD",  fontSize=14, alignment=TA_JUSTIFY,
                       spaceAfter=15, leading=24)
    sLabelBold    = S("LB",  fontName="Times-Bold",   fontSize=10.5, textColor=DARK)
    sLabelVal     = S("LV",  fontSize=10.5, textColor=DARK)
    sSignCenter   = S("SC",  alignment=TA_CENTER, fontSize=10.5, leading=16)
    sSignBold     = S("SB2", fontName="Times-Bold",   fontSize=11,
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
    academic_yr  = f"{datetime.now().year}-{str(datetime.now().year + 1)[-2:]}"
    date_str     = datetime.now().strftime("%d/%m/%Y")
    cert_type    = cert.type.lower()
    
    # Calculate sequential serial number for this year and type
    from app.models import Certificate
    cert_year = cert.created_at.year if cert.created_at else datetime.now().year
    count = Certificate.query.filter(
        extract('year', Certificate.created_at) == cert_year,
        Certificate.type == cert.type,
        Certificate.id <= cert.id
    ).count()
    serial_no    = str(count)
    
    dob          = student.dob or "—"

    if dob != "—" and "-" in dob:
        try:
            parts = dob.split("-")
            if len(parts) == 3:
                if len(parts[0]) == 4: # YYYY-MM-DD
                    d = datetime.strptime(dob, "%Y-%m-%d")
                    dob = d.strftime("%d-%b-%Y")
                else: # DD-MM-YYYY
                    d = datetime.strptime(dob, "%d-%m-%Y")
                    dob = d.strftime("%d-%b-%Y")
        except:
            pass

    body_template = CERTIFICATE_BODY.get(cert_type, CERTIFICATE_BODY["bonafide"])
    body_text = body_template.format(
        name=name, prn=prn, class_name=class_name,
        department=department, year_label=year_label,
        academic_year=academic_yr, date=date_str, dob=dob
    )

    # ── Story ────────────────────────────────────────────────────────────────
    story = []

    # ── 1. Header: Logo + College name ──────────────────────────────────────
    logo_path = os.path.join(app.static_folder, "img", "college_logo.png")
    logo_path2 = os.path.join(app.static_folder, "img", "sanstha_logo.png")
    college_block = [
        Paragraph("CSMSS", sSociety),
        Paragraph("CHHATRAPATI SHAHU MAHARAJ SHIKSHAN SANSTHA'S", sSociety,),
        Paragraph("CHH. SHAHU COLLEGE OF ENGINEERING", sCollegeName),
        Paragraph("<para>Approved by AICTE New Delhi, DTE (Govt. of Maharashtra) <br/> Affiliated to Dr. Babasaheb Ambedkar Technological University Lonere, <br/></para>", sCollegeSub),
        Paragraph("Kanchanwadi, Paithan Road, Chhatrapati Sambhajinagar 431 011 (M.S)", sCollegeSub),
        Paragraph("Ph. No. : (0240) 2646363, 2646350 Fax : (0240) 2379015", sCollegeSub),
        Paragraph("Email : shahuengg@gmail.com, principal@csmssengg.org Website : www.csmssengg.org", sCollegeSub),
    ]

    if os.path.exists(logo_path):
        logo  = Image(logo_path,  width=2.5 * cm, height=2.5 * cm)   # college logo (left)
        logo2 = Image(logo_path2, width=2.5 * cm, height=2.5 * cm)   # sanstha logo (right)
        logo_col_w = 2.8 * cm
        hdr = Table(
            [[logo, college_block, logo2]],
            colWidths=[logo_col_w, content_w - (2 * logo_col_w), logo_col_w],
        )
        hdr.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",         (0, 0), (0, 0), "LEFT"),
            ("ALIGN",         (2, 0), (2, 0), "RIGHT"),
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
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=1.5, color=DARK, spaceAfter=2))
    story.append(Spacer(1, 4))

    # ── 3. Serial / date row ─────────────────────────────────────────────────
    ref_title = CERT_TITLES.get(cert_type, "Certificate").title()
    ref_no_str = f"Ref. No.:- CSMSS CSCOE/{ref_title}/{datetime.now().year}/    <font color='red' size='10'><b>{serial_no}</b></font>"
    date_str_fmt = f"<b>   Date:-</b> {date_str}"
    
    meta_row = Table(
        [[Paragraph(ref_no_str, sMeta),
          Paragraph(date_str_fmt, sMeta)]],
        colWidths=[content_w * 0.75, content_w * 0.25],
    )
    meta_row.setStyle(TableStyle([
        ("ALIGN",         (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_row)
    story.append(Spacer(1, 10))

    # ── 4. Certificate title ─────────────────────────────────────────────────
    title_text = f"<u>{CERT_TITLES.get(cert_type, 'CERTIFICATE')}</u>"
    story.append(Paragraph(title_text, sCertTitle))

    if cert_type != "bonafide":
        story.append(Paragraph("TO WHOM IT MAY CONCERN", sSubject))

    # ── 5. Body paragraphs ───────────────────────────────────────────────────
    for para in body_text.split("\n\n"):
        story.append(Paragraph(para.strip(), sBody))

    story.append(Spacer(1, 12))

    # ── 6. Student detail table (Not for bonafide) ───────────────────────────
    if cert_type != "bonafide":
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
    else:
        story.append(Spacer(1, 30))

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
        Paragraph("<b>PRINCIPAL</b>", sSignBold),
        Paragraph("CSMSS CHH. SHAHU COLLEGE OF ENGINEERING", S("SC2", alignment=TA_CENTER, fontSize=10, textColor=colors.HexColor("#333399"), leading=12)),
        Paragraph("Kanchanwadi, Paithan Road, Chhatrapati Sambhajinagar", S("SC3", alignment=TA_CENTER, fontSize=9, textColor=MUTED, leading=12)),
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
