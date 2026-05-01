from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    PracticalSession, PracticalRecord, EventSession, EventRecord,
    Student, Subject, Class, User, Roles, ApprovalStatus, EventType
)
from app.utils.decorators import role_required
from app.utils.helpers import get_class_for_ct, get_dept_for_hod
from datetime import date

sessions_bp = Blueprint('sessions', __name__, url_prefix='/sessions')

BATCHES = ['S1', 'S2', 'S3']


# ── Helper: get classes in scope for current user ────────────────────────────
def _scoped_classes():
    role = current_user.role
    if role == Roles.SUPER_ADMIN:
        return Class.query.all()
    elif role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        return Class.query.filter_by(department_id=dept_id).all() if dept_id else []
    elif role == Roles.CLASS_TEACHER:
        cls = get_class_for_ct(current_user.id)
        return [cls] if cls else []
    else:  # TEACHER
        # Teacher can mark practical for subjects they teach
        taught = Subject.query.filter_by(teacher_id=current_user.id).all()
        class_ids = list({s.class_id for s in taught})
        return Class.query.filter(Class.id.in_(class_ids)).all()


def _scoped_subjects():
    role = current_user.role
    if role == Roles.SUPER_ADMIN:
        return Subject.query.all()
    elif role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        class_ids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()]
        return Subject.query.filter(Subject.class_id.in_(class_ids)).all()
    elif role == Roles.CLASS_TEACHER:
        cls = get_class_for_ct(current_user.id)
        return Subject.query.filter_by(class_id=cls.id).all() if cls else []
    else:
        return Subject.query.filter_by(teacher_id=current_user.id).all()


# ════════════════════════════════════════════════════════════════════════════
# STAFF DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
@sessions_bp.route('/')
@login_required
def index():
    if current_user.role in [Roles.STUDENT, Roles.CR]:
        return redirect(url_for('sessions.student_view'))

    classes = _scoped_classes()
    class_ids = [c.id for c in classes]

    # Recent practical sessions
    recent_practicals = PracticalSession.query.filter(
        PracticalSession.class_id.in_(class_ids)
    ).order_by(PracticalSession.date.desc(), PracticalSession.created_at.desc()).limit(20).all()

    # Recent event sessions
    recent_events = EventSession.query.filter(
        EventSession.class_id.in_(class_ids)
    ).order_by(EventSession.date.desc(), EventSession.created_at.desc()).limit(20).all()

    return render_template('sessions/index.html',
                           recent_practicals=recent_practicals,
                           recent_events=recent_events,
                           classes=classes)


# ════════════════════════════════════════════════════════════════════════════
# PRACTICAL SESSIONS
# ════════════════════════════════════════════════════════════════════════════
@sessions_bp.route('/practical/mark', methods=['GET', 'POST'])
@login_required
@role_required(Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def mark_practical():
    subjects  = _scoped_subjects()
    subject_id = request.args.get('subject_id') or request.form.get('subject_id')
    batch      = request.args.get('batch') or request.form.get('batch', 'S1')
    att_date   = request.args.get('date') or request.form.get('date', str(date.today()))

    selected_subject = None
    students = []
    existing = {}
    existing_session = None

    if subject_id:
        selected_subject = Subject.query.get(subject_id)
        if selected_subject and selected_subject not in subjects:
            abort(403)

        if selected_subject and batch in BATCHES:
            # Students in this class with this batch assignment
            students = Student.query.filter_by(
                class_id=selected_subject.class_id,
                approval_status=ApprovalStatus.APPROVED,
                batch=batch
            ).order_by(Student.roll_no).all()

            sel_date = date.fromisoformat(att_date)
            # Check if session already exists for this subject+batch+date
            existing_session = PracticalSession.query.filter_by(
                subject_id=selected_subject.id,
                batch=batch,
                date=sel_date
            ).first()
            if existing_session:
                existing = {r.student_id: r.status
                            for r in existing_session.records.all()}

    if request.method == 'POST' and selected_subject and batch in BATCHES:
        sel_date   = date.fromisoformat(request.form.get('date', str(date.today())))
        title      = request.form.get('title', '').strip() or f'Practical – {sel_date}'
        present_ids = [int(x) for x in request.form.getlist('present')]

        # Get or create the session
        session = PracticalSession.query.filter_by(
            subject_id=selected_subject.id, batch=batch, date=sel_date
        ).first()
        if not session:
            session = PracticalSession(
                subject_id=selected_subject.id,
                class_id=selected_subject.class_id,
                batch=batch, date=sel_date, title=title,
                marked_by=current_user.id
            )
            db.session.add(session)
            db.session.flush()  # get session.id
        else:
            session.title = title

        # Upsert records
        students_to_mark = Student.query.filter_by(
            class_id=selected_subject.class_id,
            approval_status=ApprovalStatus.APPROVED,
            batch=batch
        ).all()

        for stu in students_to_mark:
            is_present = stu.id in present_ids
            rec = PracticalRecord.query.filter_by(
                session_id=session.id, student_id=stu.id
            ).first()
            if rec:
                rec.status = is_present
            else:
                db.session.add(PracticalRecord(
                    session_id=session.id,
                    student_id=stu.id,
                    status=is_present
                ))

        db.session.commit()
        flash(f'Practical attendance saved — {batch} · {selected_subject.name} · {sel_date.strftime("%d %b %Y")}', 'success')
        return redirect(url_for('sessions.mark_practical',
                                subject_id=selected_subject.id,
                                batch=batch, date=str(sel_date)))

    return render_template('sessions/mark_practical.html',
                           subjects=subjects, selected_subject=selected_subject,
                           students=students, batches=BATCHES,
                           selected_batch=batch, att_date=att_date,
                           existing=existing, existing_session=existing_session)


@sessions_bp.route('/practical/<int:session_id>')
@login_required
@role_required(Roles.TEACHER, Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def practical_detail(session_id):
    session = PracticalSession.query.get_or_404(session_id)
    # Scope check
    allowed_ids = [c.id for c in _scoped_classes()]
    if session.class_id not in allowed_ids:
        abort(403)
    records = session.records.all()
    present = sum(1 for r in records if r.status)
    return render_template('sessions/practical_detail.html',
                           session=session, records=records,
                           present=present, absent=len(records) - present)


# ════════════════════════════════════════════════════════════════════════════
# EVENT SESSIONS
# ════════════════════════════════════════════════════════════════════════════
@sessions_bp.route('/event/create', methods=['GET', 'POST'])
@login_required
@role_required(Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def create_event():
    classes = _scoped_classes()

    if request.method == 'POST':
        name        = request.form.get('name', '').strip()
        event_type  = request.form.get('event_type', EventType.OTHER)
        class_id    = request.form.get('class_id', type=int)
        att_date    = request.form.get('date', str(date.today()))
        description = request.form.get('description', '').strip()

        if not name or not class_id:
            flash('Event name and class are required.', 'danger')
            return render_template('sessions/create_event.html',
                                   classes=classes, event_types=EventType.LABELS)

        cls = Class.query.get_or_404(class_id)
        # Scope check: ensure this class is within the user's scope
        allowed_ids = [c.id for c in classes]
        if class_id not in allowed_ids:
            flash('You are not authorised to create events for this class.', 'danger')
            return redirect(url_for('sessions.index'))
        sel_date = date.fromisoformat(att_date)
        present_ids = [int(x) for x in request.form.getlist('present')]

        # Create event session
        ev = EventSession(
            name=name, event_type=event_type,
            class_id=class_id, date=sel_date,
            description=description,
            marked_by=current_user.id
        )
        db.session.add(ev)
        db.session.flush()

        # Mark all class students
        students = Student.query.filter_by(
            class_id=class_id, approval_status=ApprovalStatus.APPROVED
        ).all()
        for stu in students:
            db.session.add(EventRecord(
                session_id=ev.id,
                student_id=stu.id,
                status=(stu.id in present_ids)
            ))

        db.session.commit()
        flash(f'Event "{name}" attendance saved for {cls.name}.', 'success')
        return redirect(url_for('sessions.event_detail', session_id=ev.id))

    # GET: show form with students of first available class
    preload_class_id = request.args.get('class_id', type=int)
    preload_class = None
    preload_students = []
    if preload_class_id:
        preload_class = Class.query.get(preload_class_id)
        if preload_class:
            preload_students = Student.query.filter_by(
                class_id=preload_class_id, approval_status=ApprovalStatus.APPROVED
            ).order_by(Student.roll_no).all()

    return render_template('sessions/create_event.html',
                           classes=classes, event_types=EventType.LABELS,
                           preload_class=preload_class,
                           preload_students=preload_students)


@sessions_bp.route('/event/<int:session_id>')
@login_required
def event_detail(session_id):
    ev = EventSession.query.get_or_404(session_id)

    # Students and CRs can only see their own class event records
    if current_user.role in [Roles.STUDENT, Roles.CR]:
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student or student.class_id != ev.class_id:
            abort(403)

    records = ev.records.all()
    present = sum(1 for r in records if r.status)
    return render_template('sessions/event_detail.html',
                           ev=ev, records=records,
                           present=present, absent=len(records) - present)


@sessions_bp.route('/event/<int:session_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def edit_event(session_id):
    ev = EventSession.query.get_or_404(session_id)

    # Scope check
    classes = _scoped_classes()
    class_ids = [c.id for c in classes]
    if ev.class_id not in class_ids:
        abort(403)

    if request.method == 'POST':
        # Update event metadata
        ev.name        = request.form.get('name', ev.name).strip() or ev.name
        ev.event_type  = request.form.get('event_type', ev.event_type)
        ev.description = request.form.get('description', '').strip()
        new_date       = request.form.get('date', '')
        if new_date:
            ev.date = date.fromisoformat(new_date)

        present_ids = [int(x) for x in request.form.getlist('present')]

        # Upsert attendance records for all class students
        students = Student.query.filter_by(
            class_id=ev.class_id, approval_status=ApprovalStatus.APPROVED
        ).all()
        for stu in students:
            rec = EventRecord.query.filter_by(
                session_id=ev.id, student_id=stu.id
            ).first()
            is_present = stu.id in present_ids
            if rec:
                rec.status = is_present
            else:
                db.session.add(EventRecord(
                    session_id=ev.id,
                    student_id=stu.id,
                    status=is_present
                ))

        db.session.commit()
        flash(f'Event "{ev.name}" attendance updated.', 'success')
        return redirect(url_for('sessions.event_detail', session_id=ev.id))

    # GET — load students with existing status
    students = Student.query.filter_by(
        class_id=ev.class_id, approval_status=ApprovalStatus.APPROVED
    ).order_by(Student.roll_no).all()
    existing = {r.student_id: r.status for r in ev.records.all()}

    return render_template('sessions/edit_event.html',
                           ev=ev, students=students,
                           existing=existing,
                           event_types=EventType.LABELS)


# ════════════════════════════════════════════════════════════════════════════
# STUDENT VIEW
# ════════════════════════════════════════════════════════════════════════════
@sessions_bp.route('/student')
@login_required
def student_view():
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student and current_user.role != Roles.STUDENT:
        return redirect(url_for('sessions.index'))
    if not student:
        flash('Student profile not found.', 'danger')
        return redirect(url_for('dashboard.index'))

    # ── Practical attendance grouped by subject ──────────────────────────────
    subjects = Subject.query.filter_by(class_id=student.class_id).all()
    practical_summary = []
    for sub in subjects:
        sessions = PracticalSession.query.filter_by(
            subject_id=sub.id,
            class_id=student.class_id,
            batch=student.batch
        ).order_by(PracticalSession.date.desc()).all()

        if not sessions:
            continue
        session_ids = [s.id for s in sessions]
        records = PracticalRecord.query.filter(
            PracticalRecord.session_id.in_(session_ids),
            PracticalRecord.student_id == student.id
        ).all()
        rec_map  = {r.session_id: r.status for r in records}
        total    = len(sessions)
        present  = sum(1 for s in sessions if rec_map.get(s.id, False))
        practical_summary.append({
            'subject':  sub,
            'sessions': sessions,
            'rec_map':  rec_map,
            'total':    total,
            'present':  present,
            'pct':      round((present / total) * 100, 1) if total else 0,
        })

    # ── Event attendance ──────────────────────────────────────────────────────
    event_sessions = EventSession.query.filter_by(
        class_id=student.class_id
    ).order_by(EventSession.date.desc()).all()
    ev_ids   = [e.id for e in event_sessions]
    ev_recs  = EventRecord.query.filter(
        EventRecord.session_id.in_(ev_ids),
        EventRecord.student_id == student.id
    ).all()
    ev_map   = {r.session_id: r.status for r in ev_recs}
    ev_total   = len(event_sessions)
    ev_present = sum(1 for e in event_sessions if ev_map.get(e.id, False))

    return render_template('sessions/student_view.html',
                           student=student,
                           practical_summary=practical_summary,
                           event_sessions=event_sessions,
                           ev_map=ev_map,
                           ev_total=ev_total,
                           ev_present=ev_present)


# ── AJAX: load students for a class (used in create_event form) ─────────────
@sessions_bp.route('/api/class-students/<int:class_id>')
@login_required
@role_required(Roles.CLASS_TEACHER, Roles.HOD, Roles.SUPER_ADMIN)
def api_class_students(class_id):
    from flask import jsonify
    # Scope check: only return students from classes this user is authorized for
    allowed_ids = [c.id for c in _scoped_classes()]
    if class_id not in allowed_ids:
        return jsonify({'error': 'unauthorized'}), 403

    students = Student.query.filter_by(
        class_id=class_id, approval_status=ApprovalStatus.APPROVED
    ).order_by(Student.roll_no).all()
    return jsonify([{
        'id': s.id,
        'name': s.user.name,
        'roll_no': s.roll_no or '',
        'batch': s.batch or '',
    } for s in students])
