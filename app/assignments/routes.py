from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Assignment, AssignmentSubmission, Subject, Student, Roles, ApprovalStatus, Class
from app.utils.decorators import role_required
from app.utils.helpers import send_notification
from datetime import datetime
import os
import uuid
from werkzeug.utils import secure_filename

assignments_bp = Blueprint('assignments', __name__, url_prefix='/assignments')

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'jpg', 'png', 'zip', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@assignments_bp.route('/')
@login_required
def index():
    if current_user.role in [Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN]:
        assignments = Assignment.query.filter_by(created_by=current_user.id)\
            .order_by(Assignment.created_at.desc()).all()
        if current_user.role == Roles.SUPER_ADMIN:
            assignments = Assignment.query.order_by(Assignment.created_at.desc()).all()
        elif current_user.role == Roles.HOD:
            from app.utils.helpers import get_dept_for_hod
            dept_id = get_dept_for_hod(current_user.id)
            if dept_id:
                dept_class_ids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()]
                dept_subject_ids = [s.id for s in Subject.query.filter(Subject.class_id.in_(dept_class_ids)).all()] if dept_class_ids else []
                assignments = Assignment.query.filter(
                    Assignment.subject_id.in_(dept_subject_ids)
                ).order_by(Assignment.created_at.desc()).all() if dept_subject_ids else []
            else:
                assignments = []
        return render_template('assignments/teacher_view.html', assignments=assignments)
    else:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            return redirect(url_for('dashboard.index'))
        subjects = Subject.query.filter_by(class_id=student.class_id).all()
        subject_ids = [s.id for s in subjects]
        assignments = Assignment.query.filter(Assignment.subject_id.in_(subject_ids))\
            .order_by(Assignment.deadline.asc()).all()
        submissions = {s.assignment_id: s for s in
            AssignmentSubmission.query.filter_by(student_id=student.id).all()}
        return render_template('assignments/student_view.html',
            assignments=assignments, submissions=submissions, now=datetime.utcnow())

@assignments_bp.route('/create', methods=['GET', 'POST'])
@login_required
@role_required(Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def create():
    from app.utils.helpers import get_dept_for_hod, get_class_for_ct
    # Scope subjects properly by role
    if current_user.role == Roles.SUPER_ADMIN:
        subjects = Subject.query.all()
    elif current_user.role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        class_ids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()] if dept_id else []
        subjects = Subject.query.filter(Subject.class_id.in_(class_ids)).all()
    elif current_user.role == Roles.CLASS_TEACHER:
        cls = get_class_for_ct(current_user.id)
        subjects = Subject.query.filter_by(class_id=cls.id).all() if cls else []
    else:
        subjects = Subject.query.filter_by(teacher_id=current_user.id).all()

    if request.method == 'POST':
        title      = request.form.get('title', '').strip()
        desc       = request.form.get('description', '').strip()
        subject_id = request.form.get('subject_id')
        deadline   = request.form.get('deadline')
        max_marks  = request.form.get('max_marks', '10').strip()

        if not title:
            flash('Assignment title is required.', 'danger')
            return render_template('assignments/create.html', subjects=subjects)
        if not subject_id:
            flash('Please select a subject.', 'danger')
            return render_template('assignments/create.html', subjects=subjects)

        try:
            max_marks = float(max_marks)
        except ValueError:
            max_marks = 10.0

        try:
            deadline_dt = datetime.strptime(deadline, '%Y-%m-%dT%H:%M') if deadline else datetime.utcnow()
        except ValueError:
            flash('Invalid deadline format.', 'danger')
            return render_template('assignments/create.html', subjects=subjects)

        asgn = Assignment(title=title, description=desc, subject_id=subject_id,
                          deadline=deadline_dt, max_marks=max_marks, created_by=current_user.id)
        db.session.add(asgn)
        db.session.commit()

        # Notify students in the subject's class
        subject = Subject.query.get(subject_id)
        if subject:
            students = Student.query.filter_by(class_id=subject.class_id,
                approval_status=ApprovalStatus.APPROVED).all()
            for s in students:
                send_notification(s.user_id,
                    f'📝 New Assignment: {title} — Due {deadline_dt.strftime("%d %b %Y %H:%M")}',
                    'info', url_for('assignments.index'))

        flash(f'Assignment "{title}" created!', 'success')
        return redirect(url_for('assignments.index'))

    return render_template('assignments/create.html', subjects=subjects)

@assignments_bp.route('/<int:id>/submit', methods=['POST'])
@login_required
@role_required(Roles.STUDENT, Roles.CR)
def submit(id):
    assignment = Assignment.query.get_or_404(id)
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('assignments.index'))

    # Scope check: student must belong to the assignment's class
    if assignment.subject and assignment.subject.class_id != student.class_id:
        flash('You are not enrolled in this assignment.', 'danger')
        return redirect(url_for('assignments.index'))

    existing = AssignmentSubmission.query.filter_by(assignment_id=id, student_id=student.id).first()
    is_late = datetime.utcnow() > assignment.deadline

    file_path = None
    if 'file' in request.files:
        file = request.files['file']
        if file and file.filename and allowed_file(file.filename):
            ext = os.path.splitext(secure_filename(file.filename))[1].lower()
            # UUID prefix prevents two students overwriting each other's file
            filename = f"asgn_{id}_{student.id}_{uuid.uuid4().hex[:8]}{ext}"
            upload_dir = os.path.join(current_app.static_folder, 'uploads', 'assignments')
            os.makedirs(upload_dir, exist_ok=True)
            file.save(os.path.join(upload_dir, filename))
            file_path = filename

    if existing:
        existing.file_path = file_path or existing.file_path
        existing.submitted_at = datetime.utcnow()
        existing.is_late = is_late
    else:
        sub = AssignmentSubmission(assignment_id=id, student_id=student.id,
                                   file_path=file_path, is_late=is_late)
        db.session.add(sub)

    db.session.commit()
    msg = '\u2705 Assignment submitted!' if not is_late else '\u26a0\ufe0f Assignment submitted (late).'
    flash(msg, 'success' if not is_late else 'warning')
    return redirect(url_for('assignments.index'))

@assignments_bp.route('/<int:id>/submissions')
@login_required
@role_required(Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN, Roles.CR)
def submissions(id):
    assignment = Assignment.query.get_or_404(id)
    
    # Scope check
    if current_user.role == Roles.CR:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student or assignment.subject.class_id != student.class_id:
            from flask import abort
            abort(403)
    elif current_user.role == Roles.HOD:
        from app.utils.helpers import get_dept_for_hod
        dept_id = get_dept_for_hod(current_user.id)
        if assignment.subject and assignment.subject.class_:
            if assignment.subject.class_.department_id != dept_id:
                from flask import abort
                abort(403)
    elif current_user.role not in [Roles.SUPER_ADMIN] and assignment.created_by != current_user.id:
        from flask import abort
        abort(403)

    subs = AssignmentSubmission.query.filter_by(assignment_id=id).all()
    return render_template('assignments/submissions.html', assignment=assignment, submissions=subs)
