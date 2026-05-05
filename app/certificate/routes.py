from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Certificate, Student, User, Roles, ApprovalStatus, CertificateType
from app.utils.decorators import role_required
from app.utils.helpers import send_notification
from app.utils.certificate_pdf import generate_certificate_pdf, _make_verification_token
from datetime import datetime
import io

certificate_bp = Blueprint('certificate', __name__, url_prefix='/certificate')


@certificate_bp.route('/verify/<int:cert_id>/<string:token>')
def verify(cert_id, token):
    """
    PUBLIC route — no login required.
    QR code on the printed certificate links here.
    Shows verification status and student details so anyone can confirm authenticity.
    """
    cert = Certificate.query.get(cert_id)

    if not cert:
        return render_template('certificate/verify.html',
                               valid=False, error="Certificate not found.")

    expected = _make_verification_token(cert_id, current_app.config.get("SECRET_KEY", "csmss"))
    if token != expected:
        return render_template('certificate/verify.html',
                               valid=False, error="Invalid or tampered QR code.")

    if cert.status != ApprovalStatus.APPROVED:
        return render_template('certificate/verify.html',
                               valid=False, error="This certificate has not been approved.")

    return render_template('certificate/verify.html', valid=True, cert=cert)


@certificate_bp.route('/')
@login_required
def index():
    if current_user.role in [Roles.STUDENT, Roles.CR]:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            flash('Student profile not found. Contact your administrator.', 'warning')
            return redirect(url_for('dashboard.index'))
        certs = Certificate.query.filter_by(student_id=student.id)\
            .order_by(Certificate.created_at.desc()).all()
        return render_template('certificate/admin_view.html', certs=certs)
    elif current_user.role == Roles.CLASS_TEACHER:
        # Only show certificates from students in the teacher's class
        from app.models import Class
        cls = Class.query.filter_by(class_teacher_id=current_user.id).first()
        if cls:
            student_ids = [s.id for s in cls.students.all()]
            certs = Certificate.query.filter(
                Certificate.student_id.in_(student_ids)
            ).order_by(Certificate.created_at.desc()).all()
        else:
            certs = []
        return render_template('certificate/admin_view.html', certs=certs)
    elif current_user.role == Roles.HOD:
        from app.models import Class
        from app.utils.helpers import get_dept_for_hod
        dept_id = get_dept_for_hod(current_user.id)
        if dept_id:
            dept_class_ids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()]
            dept_student_ids = [s.id for s in Student.query.filter(Student.class_id.in_(dept_class_ids)).all()] if dept_class_ids else []
            certs = Certificate.query.filter(
                Certificate.student_id.in_(dept_student_ids)
            ).order_by(Certificate.created_at.desc()).all() if dept_student_ids else []
        else:
            certs = []
        return render_template('certificate/admin_view.html', certs=certs)
    else:
        # Super Admin sees all
        certs = Certificate.query.order_by(Certificate.created_at.desc()).all()
        return render_template('certificate/admin_view.html', certs=certs)


@certificate_bp.route('/apply', methods=['GET', 'POST'])
@login_required
@role_required(Roles.STUDENT, Roles.CR)
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
        db.session.flush()  # get cert.id for notification link

        # Notify only the student's own Class Teacher (not every CT in the college)
        if student.class_ and student.class_.class_teacher_id:
            send_notification(
                student.class_.class_teacher_id,
                f'\U0001f4dc Certificate request: {cert_type} from {current_user.name}',
                'info', url_for('certificate.index')
            )
        # Also notify HOD of the student's department
        if student.class_ and student.class_.department and student.class_.department.hod_id:
            send_notification(
                student.class_.department.hod_id,
                f'\U0001f4dc Certificate request: {cert_type} from {current_user.name}',
                'info', url_for('certificate.index')
            )

        db.session.commit()
        flash('Certificate application submitted successfully!', 'success')
        return redirect(url_for('certificate.index'))

    return render_template('certificate/apply.html', cert_types=[
        (CertificateType.BONAFIDE, 'Bonafide Certificate'),
    ])

@certificate_bp.route('/<int:id>/action', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def action(id):
    cert = Certificate.query.get_or_404(id)

    # Scope check: Class Teacher can only act on their own class's students
    if current_user.role == Roles.CLASS_TEACHER:
        from app.models import Class
        cls = Class.query.filter_by(class_teacher_id=current_user.id).first()
        if not cls or cert.student.class_id != cls.id:
            flash('You are not authorised to act on this certificate.', 'danger')
            return redirect(url_for('certificate.index'))
    elif current_user.role == Roles.HOD:
        from app.utils.helpers import get_dept_for_hod
        from app.models import Class
        dept_id = get_dept_for_hod(current_user.id)
        cls = Class.query.get(cert.student.class_id)
        if not cls or cls.department_id != dept_id:
            flash('You are not authorised to act on this certificate.', 'danger')
            return redirect(url_for('certificate.index'))

    act  = request.form.get('action')
    notes = request.form.get('notes', '').strip()

    if act == 'approve':
        cert.status      = ApprovalStatus.APPROVED
        cert.approved_by = current_user.id
        cert.notes       = notes
        msg       = f'\u2705 Your {cert.type.title()} Certificate has been approved! The staff will hand it to you after signing.'
        notif_type = 'success'
    else:
        cert.status = ApprovalStatus.REJECTED
        cert.notes  = notes
        msg         = f'\u274c Your {cert.type.title()} Certificate was rejected. Reason: {notes or "No reason provided"}'
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

    # Scope check
    if current_user.role == Roles.CLASS_TEACHER:
        from app.models import Class
        cls = Class.query.filter_by(class_teacher_id=current_user.id).first()
        if not cls or cert.student.class_id != cls.id:
            flash('You are not authorised to download this certificate.', 'danger')
            return redirect(url_for('certificate.index'))
    elif current_user.role == Roles.HOD:
        from app.utils.helpers import get_dept_for_hod
        from app.models import Class
        dept_id = get_dept_for_hod(current_user.id)
        cls = Class.query.get(cert.student.class_id)
        if not cls or cls.department_id != dept_id:
            flash('You are not authorised to download this certificate.', 'danger')
            return redirect(url_for('certificate.index'))

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
