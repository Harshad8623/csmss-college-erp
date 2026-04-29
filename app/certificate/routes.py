from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Certificate, Student, User, Roles, ApprovalStatus, CertificateType
from app.utils.decorators import role_required
from app.utils.helpers import send_notification
from app.utils.certificate_pdf import generate_certificate_pdf
from datetime import datetime
import io

certificate_bp = Blueprint('certificate', __name__, url_prefix='/certificate')

@certificate_bp.route('/')
@login_required
def index():
    if current_user.role == Roles.STUDENT:
        student = Student.query.filter_by(user_id=current_user.id).first()
        certs = Certificate.query.filter_by(student_id=student.id)\
            .order_by(Certificate.created_at.desc()).all() if student else []
        return render_template('certificate/student_view.html', certs=certs)
    else:
        certs = Certificate.query.order_by(Certificate.created_at.desc()).all()
        return render_template('certificate/admin_view.html', certs=certs)

@certificate_bp.route('/apply', methods=['GET', 'POST'])
@login_required
@role_required(Roles.STUDENT)
def apply():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        cert_type = request.form.get('type', CertificateType.BONAFIDE)
        reason = request.form.get('reason', '').strip()

        # Check for duplicate pending
        existing = Certificate.query.filter_by(
            student_id=student.id, type=cert_type, status=ApprovalStatus.PENDING
        ).first()
        if existing:
            flash('You already have a pending request for this certificate type.', 'warning')
            return redirect(url_for('certificate.index'))

        cert = Certificate(student_id=student.id, type=cert_type, reason=reason,
                           status=ApprovalStatus.PENDING)
        db.session.add(cert)

        # Notify admins
        admins = User.query.filter(User.role.in_([Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER])).all()
        for admin in admins:
            send_notification(admin.id,
                f'📜 Certificate request: {cert_type} from {current_user.name}',
                'info', url_for('certificate.index'))

        db.session.commit()
        flash('Certificate application submitted successfully!', 'success')
        return redirect(url_for('certificate.index'))

    return render_template('certificate/apply.html', cert_types=[
        (CertificateType.BONAFIDE,  'Bonafide Certificate'),
        (CertificateType.LEAVING,   'Leaving Certificate'),
        (CertificateType.CHARACTER, 'Character Certificate'),
        (CertificateType.TRANSFER,  'Transfer Certificate'),
    ])

@certificate_bp.route('/<int:id>/action', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def action(id):
    cert = Certificate.query.get_or_404(id)
    act  = request.form.get('action')
    notes = request.form.get('notes', '').strip()

    if act == 'approve':
        cert.status      = ApprovalStatus.APPROVED
        cert.approved_by = current_user.id
        cert.notes       = notes
        msg       = f'✅ Your {cert.type.title()} Certificate has been approved! The staff will hand it to you after signing.'
        notif_type = 'success'
    else:
        cert.status = ApprovalStatus.REJECTED
        cert.notes  = notes
        msg         = f'❌ Your {cert.type.title()} Certificate was rejected. Reason: {notes}'
        notif_type  = 'danger'

    send_notification(cert.student.user_id, msg, notif_type, url_for('certificate.index'))
    db.session.commit()
    flash(f'Certificate {cert.status}.', 'success')
    return redirect(url_for('certificate.index'))


@certificate_bp.route('/<int:id>/download')
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def download_pdf(id):
    """
    Generate and stream the certificate PDF on demand.
    Only accessible by Class Teacher, HOD, and Super Admin.
    Students CANNOT access this route — they receive the physical signed copy.
    """
    cert = Certificate.query.get_or_404(id)

    if cert.status != ApprovalStatus.APPROVED:
        flash('Certificate must be approved before a PDF can be generated.', 'warning')
        return redirect(url_for('certificate.index'))

    try:
        pdf_bytes = generate_certificate_pdf(cert, current_app._get_current_object())
    except Exception as e:
        flash(f'PDF generation failed: {e}', 'danger')
        return redirect(url_for('certificate.index'))

    student_name = cert.student.user.name.replace(' ', '_')
    cert_type    = cert.type.title().replace(' ', '_')
    filename     = f"{cert_type}_Certificate_{student_name}_{cert.id}.pdf"

    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf',
    )
