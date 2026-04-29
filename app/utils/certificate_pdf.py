"""
certificate_pdf.py — Generates official college certificate PDFs using ReportLab.
Only accessible by Class Teacher / HOD / Super Admin for download and physical printing.
"""
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── College constants ────────────────────────────────────────────────────────
COLLEGE_NAME      = "CSMSS Chh. Shahu College of Engineering"
COLLEGE_SUBTITLE  = "Kanchanwadi, Aurangabad – 431 002 (M.S.)"
COLLEGE_AFFIL     = "Affiliated to Dr. Babasaheb Ambedkar Marathwada University, Aurangabad"
COLLEGE_PHONE     = "Tel: 0240-2376111  |  Email: principal@csmss.ac.in"

# Approved certificate type → body text template
CERTIFICATE_TEXT = {
    'bonafide': (
        "TO WHOM IT MAY CONCERN\n\n"
        "This is to certify that {name}, PRN No. {prn}, son/daughter of {father_name}, "
        "is a bonafide student of this institution and is currently studying in "
        "{year_label} ({class_name}), Department of {department}, "
        "for the academic year {academic_year}.\n\n"
        "He / She bears a good moral character and his / her conduct is satisfactory."
    ),
    'character': (
        "TO WHOM IT MAY CONCERN\n\n"
        "This is to certify that {name}, PRN No. {prn}, "
        "was a bonafide student of this institution and was studying in "
        "{year_label} ({class_name}), Department of {department}.\n\n"
        "During his / her tenure at this institution, his / her character and conduct "
        "were found to be satisfactory. He / She has no pending dues or disciplinary action "
        "against his / her name."
    ),
    'leaving': (
        "TO WHOM IT MAY CONCERN\n\n"
        "This is to certify that {name}, PRN No. {prn}, "
        "was enrolled as a student in {year_label} ({class_name}), "
        "Department of {department}.\n\n"
        "He / She has left this institution on {date}. "
        "His / Her conduct and character during his / her stay at this institution were satisfactory. "
        "He / She has cleared all dues of the institution."
    ),
    'transfer': (
        "TO WHOM IT MAY CONCERN\n\n"
        "This is to certify that {name}, PRN No. {prn}, "
        "was a bonafide student of this institution in "
        "{year_label} ({class_name}), Department of {department}.\n\n"
        "He / She is hereby granted this Transfer Certificate as he / she is leaving "
        "this institution. His / Her conduct was good during his / her stay here. "
        "He / She has no pending dues or disciplinary record."
    ),
}

YEAR_LABELS = {1: 'First Year (FE)', 2: 'Second Year (SE)',
               3: 'Third Year (TE)', 4: 'Fourth Year (BE)'}

CERT_TITLES = {
    'bonafide':  'BONAFIDE CERTIFICATE',
    'character': 'CHARACTER CERTIFICATE',
    'leaving':   'LEAVING CERTIFICATE',
    'transfer':  'TRANSFER CERTIFICATE',
}


def _get_logo_path(app):
    return os.path.join(app.static_folder, 'img', 'college_logo.png')


def generate_certificate_pdf(cert, app) -> bytes:
    """
    Generate a printable A4 certificate PDF and return it as bytes.

    :param cert:  Certificate model instance (must be approved)
    :param app:   Flask application instance (for static folder path)
    :return:      PDF bytes
    """
    from io import BytesIO
    buf = BytesIO()

    # Page layout
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2 * cm,
        bottomMargin=2.5 * cm,
    )

    W, H = A4
    content_width = W - 5 * cm  # left + right margins

    styles = getSampleStyleSheet()

    # ── Custom styles ────────────────────────────────────────────────────────
    college_name_style = ParagraphStyle(
        'CollegeName',
        fontSize=16, fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceAfter=2,
        textColor=colors.HexColor('#1a237e'),
    )
    sub_style = ParagraphStyle(
        'Sub', fontSize=9, fontName='Helvetica',
        alignment=TA_CENTER, spaceAfter=1,
        textColor=colors.HexColor('#333333'),
    )
    cert_title_style = ParagraphStyle(
        'CertTitle', fontSize=14, fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceBefore=12, spaceAfter=4,
        textColor=colors.HexColor('#1a237e'),
    )
    underline_style = ParagraphStyle(
        'Underline', fontSize=8, fontName='Helvetica',
        alignment=TA_CENTER, spaceAfter=16,
        textColor=colors.HexColor('#1a237e'),
    )
    body_style = ParagraphStyle(
        'Body', fontSize=11, fontName='Helvetica',
        alignment=TA_JUSTIFY, spaceAfter=10,
        leading=18, textColor=colors.HexColor('#111111'),
    )
    label_style = ParagraphStyle(
        'Label', fontSize=10, fontName='Helvetica-Bold',
        textColor=colors.HexColor('#333333'),
    )
    sign_style = ParagraphStyle(
        'Sign', fontSize=10, fontName='Helvetica',
        alignment=TA_CENTER, textColor=colors.HexColor('#333333'),
    )
    serial_style = ParagraphStyle(
        'Serial', fontSize=9, fontName='Helvetica',
        textColor=colors.HexColor('#888888'),
    )

    # ── Gather student data ──────────────────────────────────────────────────
    student  = cert.student
    user     = student.user
    cls      = student.class_
    dept     = cls.department if cls else None
    year_num = cls.year if cls else 3

    name        = user.name
    prn         = student.prn or '—'
    father_name = getattr(student, 'father_name', 'N/A')
    class_name  = cls.name if cls else '—'
    department  = dept.name if dept else '—'
    year_label  = YEAR_LABELS.get(year_num, 'N/A')
    academic_year = f"{datetime.now().year - 1}–{datetime.now().year}"
    date_str    = datetime.now().strftime('%d %B %Y')
    cert_type   = cert.type.lower()

    # ── Body text ────────────────────────────────────────────────────────────
    template = CERTIFICATE_TEXT.get(cert_type, CERTIFICATE_TEXT['bonafide'])
    body_text = template.format(
        name=name, prn=prn, father_name=father_name,
        class_name=class_name, department=department,
        year_label=year_label, academic_year=academic_year, date=date_str,
    )

    # ── Build flowables ──────────────────────────────────────────────────────
    story = []

    # --- Header: logo + college name side by side ---
    logo_path = _get_logo_path(app)
    header_data = []
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=2.2 * cm, height=2.2 * cm)
        header_data = [[
            logo,
            [
                Paragraph(COLLEGE_NAME, college_name_style),
                Paragraph(COLLEGE_SUBTITLE, sub_style),
                Paragraph(COLLEGE_AFFIL, sub_style),
                Paragraph(COLLEGE_PHONE, sub_style),
            ]
        ]]
        header_table = Table(header_data, colWidths=[2.5 * cm, content_width - 2.5 * cm])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
    else:
        story.append(Paragraph(COLLEGE_NAME, college_name_style))
        story.append(Paragraph(COLLEGE_SUBTITLE, sub_style))
        story.append(Paragraph(COLLEGE_AFFIL, sub_style))
        story.append(Paragraph(COLLEGE_PHONE, sub_style))

    # Decorative divider
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1a237e')))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#1a237e'),
                             spaceAfter=4))

    # Certificate title
    story.append(Paragraph(CERT_TITLES.get(cert_type, 'CERTIFICATE'), cert_title_style))
    story.append(Paragraph('─ ─ ─ ─ ─ ─ ─ ─ ─ ─', underline_style))

    # Serial / date row
    serial_no = f"Cert. No.: CSMSS/{datetime.now().year}/{cert.id:04d}"
    date_para  = Paragraph(f"Date: {date_str}", serial_style)
    serial_para = Paragraph(serial_no, serial_style)

    meta_table = Table([[serial_para, date_para]],
                       colWidths=[content_width / 2, content_width / 2])
    meta_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Body text
    for line in body_text.split('\n\n'):
        story.append(Paragraph(line.replace('\n', '<br/>'), body_style))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 16))

    # Student detail mini-table
    detail_data = [
        ['Student Name', ':', name],
        ['PRN No.', ':', prn],
        ['Class / Year', ':', f"{class_name} ({year_label})"],
        ['Department', ':', department],
    ]
    if student.roll_no:
        detail_data.insert(2, ['Roll No.', ':', student.roll_no])

    detail_table = Table(detail_data,
                         colWidths=[3.5 * cm, 0.5 * cm, content_width - 4 * cm])
    detail_table.setStyle(TableStyle([
        ('FONTNAME',    (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE',    (0, 0), (-1, -1), 10),
        ('TEXTCOLOR',   (0, 0), (-1, -1), colors.HexColor('#222222')),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(detail_table)
    story.append(Spacer(1, 24))

    # Approver name
    approver = cert.approver
    approver_name = approver.name if approver else 'Class Teacher'

    # Signature section
    sign_data = [[
        Paragraph('', sign_style),
        Paragraph(
            f"_______________________<br/><b>{approver_name}</b><br/>"
            "Class Teacher / HOD<br/>CSMSS College of Engineering",
            sign_style
        ),
    ]]
    sign_table = Table(sign_data, colWidths=[content_width * 0.55, content_width * 0.45])
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(sign_table)

    story.append(Spacer(1, 20))

    # Stamp box hint
    stamp_text = (
        "<font color='#aaaaaa' size='8'>"
        "[  Official Stamp / Seal  ]"
        "</font>"
    )
    story.append(Paragraph(stamp_text, ParagraphStyle('stamp', alignment=TA_LEFT, fontSize=8)))

    story.append(Spacer(1, 10))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#cccccc')))

    footer_note = (
        "<font size='7.5' color='#888888'>"
        "This certificate is computer-generated and is valid only when signed and stamped "
        "by an authorised signatory of CSMSS Chh. Shahu College of Engineering."
        "</font>"
    )
    story.append(Paragraph(footer_note,
                            ParagraphStyle('Footer', fontSize=7.5, alignment=TA_CENTER,
                                           textColor=colors.HexColor('#888888'), spaceBefore=4)))

    # Build PDF
    doc.build(story)
    return buf.getvalue()
