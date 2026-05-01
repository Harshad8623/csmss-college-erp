from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from app.models import (
    Student, Teacher, Department, Class, Subject,
    Attendance, Marks, Grievance, User, Roles, ApprovalStatus, AbsenteeReason
)
from app.extensions import db, cache
from sqlalchemy import func
from datetime import date, timedelta, datetime
from app.utils.helpers import get_dept_for_hod, get_class_for_ct, get_tg_student_ids, get_students_for_subject

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')

STAFF_ROLES = [Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER, Roles.TEACHER]

# ── Helper ──────────────────────────────────────────────────────────────────
def _att_pct(student_ids, subject_id=None, d=None):
    q = Attendance.query.filter(Attendance.student_id.in_(student_ids))
    if subject_id:
        q = q.filter_by(subject_id=subject_id)
    if d:
        q = q.filter_by(date=d)
    total = q.count()
    if total == 0:
        return 0
    present = q.filter_by(status=True).count()
    return round(present / total * 100, 2)

def _today_counts(student_ids):
    recs = Attendance.query.filter(
        Attendance.student_id.in_(student_ids),
        Attendance.date == date.today()
    ).all()
    seen = {}
    for r in recs:
        if r.student_id not in seen:
            seen[r.student_id] = {'p': 0, 'a': 0}
        if r.status:
            seen[r.student_id]['p'] += 1
        else:
            seen[r.student_id]['a'] += 1
    present = sum(1 for v in seen.values() if v['a'] == 0 and v['p'] > 0)
    absent  = sum(1 for v in seen.values() if v['a'] > 0)
    return present, absent, len(seen)

def _week_trend(student_ids, days=7):
    today = date.today()
    labels, p_data, a_data = [], [], []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        q = Attendance.query.filter(Attendance.student_id.in_(student_ids), Attendance.date == d)
        total = q.count()
        pres  = q.filter_by(status=True).count()
        labels.append(d.strftime('%d %b'))
        p_data.append(pres)
        a_data.append(total - pres)
    return labels, p_data, a_data

# ── Main page ────────────────────────────────────────────────────────────────
@analytics_bp.route('/')
@login_required
def index():
    if current_user.role not in STAFF_ROLES:
        from flask import abort; abort(403)

    ctx = {'role': current_user.role}

    if current_user.role == Roles.SUPER_ADMIN:
        ctx['departments'] = Department.query.all()
        ctx['all_classes'] = Class.query.all()

    elif current_user.role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        ctx['hod_dept'] = Department.query.get(dept_id) if dept_id else None
        ctx['dept_classes'] = Class.query.filter_by(department_id=dept_id).all() if dept_id else []

    elif current_user.role == Roles.CLASS_TEACHER:
        ct_class = get_class_for_ct(current_user.id)
        ctx['ct_class'] = ct_class

    elif current_user.role == Roles.TEACHER:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        tg_ids = get_tg_student_ids(current_user.id)
        my_subjects = Subject.query.filter_by(teacher_id=current_user.id).all()
        ctx['is_tg'] = len(tg_ids) > 0
        ctx['tg_count'] = len(tg_ids)
        ctx['my_subjects'] = my_subjects
        selected_subj = request.args.get('subject_id', type=int)
        if not selected_subj and my_subjects:
            selected_subj = my_subjects[0].id
        ctx['selected_subject_id'] = selected_subj
        ctx['selected_subject'] = Subject.query.get(selected_subj) if selected_subj else None

    return render_template('analytics/index.html', **ctx)

# ═══════════════════════════════════════════════════════════════════════════
# PRINCIPAL APIs
# ═══════════════════════════════════════════════════════════════════════════
@analytics_bp.route('/api/principal/summary')
@login_required
def principal_summary():
    if current_user.role not in [Roles.SUPER_ADMIN, Roles.HOD]:
        return jsonify({'error': 'unauthorized'}), 403
    total_students = Student.query.filter_by(approval_status=ApprovalStatus.APPROVED).count()
    total_teachers = Teacher.query.count()
    all_ids = [s.id for s in Student.query.with_entities(Student.id).filter_by(approval_status=ApprovalStatus.APPROVED).all()]
    pres, abs_, seen = _today_counts(all_ids)
    # Efficient defaulter count using bulk aggregation instead of N Python loops
    from sqlalchemy import func as sqlfunc
    stats = db.session.query(
        Attendance.student_id,
        sqlfunc.count(Attendance.id).label('total'),
        sqlfunc.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(Attendance.student_id.in_(all_ids)).group_by(Attendance.student_id).all()
    defaulters = sum(1 for r in stats if r.total > 0 and (r.present or 0) / r.total * 100 < 75)
    return jsonify({'students': total_students, 'teachers': total_teachers,
                    'present_today': pres, 'absent_today': abs_,
                    'defaulters': defaulters, 'depts': Department.query.count()})

@analytics_bp.route('/api/principal/dept-today')
@login_required
def principal_dept_today():
    if current_user.role not in [Roles.SUPER_ADMIN]:
        return jsonify({'error': 'unauthorized'}), 403
    depts = Department.query.all()
    labels, present_d, absent_d, total_d = [], [], [], []
    for dept in depts:
        cids = [c.id for c in Class.query.filter_by(department_id=dept.id).all()]
        sids = [s.id for s in Student.query.filter(Student.class_id.in_(cids)).all()]
        p, a, _ = _today_counts(sids)
        labels.append(dept.code or dept.name[:8])
        present_d.append(p); absent_d.append(a); total_d.append(len(sids))
    return jsonify({'labels': labels, 'present': present_d, 'absent': absent_d, 'total': total_d})

@analytics_bp.route('/api/principal/weekwise')
@login_required
@cache.cached(timeout=300, key_prefix='principal_weekwise')
def principal_weekwise():
    all_ids = [s.id for s in Student.query.filter_by(approval_status=ApprovalStatus.APPROVED).all()]
    labels, p, a = _week_trend(all_ids, 7)
    return jsonify({'labels': labels, 'present': p, 'absent': a})

@analytics_bp.route('/api/principal/dept-overall')
@login_required
@cache.cached(timeout=300, key_prefix='principal_dept_overall')
def principal_dept_overall():
    depts = Department.query.all()
    labels, data = [], []
    for dept in depts:
        cids = [c.id for c in Class.query.filter_by(department_id=dept.id).all()]
        sids = [s.id for s in Student.query.filter(Student.class_id.in_(cids)).all()]
        pct = _att_pct(sids)
        labels.append(dept.code or dept.name[:10]); data.append(pct)
    return jsonify({'labels': labels, 'data': data})

@analytics_bp.route('/api/principal/classwise')
@login_required
def principal_classwise():
    if current_user.role not in [Roles.SUPER_ADMIN]:
        return jsonify({'error': 'unauthorized'}), 403
    classes = Class.query.all()
    labels, data = [], []
    for c in classes:
        sids = [s.id for s in Student.query.filter_by(class_id=c.id).all()]
        pct = _att_pct(sids)
        labels.append(c.name); data.append(pct)
    return jsonify({'labels': labels, 'data': data})

@analytics_bp.route('/api/principal/defaulters-dept')
@login_required
def principal_defaulters_dept():
    if current_user.role not in [Roles.SUPER_ADMIN, Roles.HOD]:
        return jsonify({'error': 'unauthorized'}), 403
    depts = Department.query.all()
    labels, safe_d, risk_d = [], [], []
    for dept in depts:
        cids = [c.id for c in Class.query.filter_by(department_id=dept.id).all()]
        students = Student.query.filter(Student.class_id.in_(cids), Student.approval_status==ApprovalStatus.APPROVED).all()
        # Efficient bulk defaulter count
        sids = [s.id for s in students]
        from sqlalchemy import func as sqlfunc
        stats = db.session.query(
            Attendance.student_id,
            sqlfunc.count(Attendance.id).label('total'),
            sqlfunc.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
        ).filter(Attendance.student_id.in_(sids)).group_by(Attendance.student_id).all() if sids else []
        def_count = sum(1 for r in stats if r.total > 0 and (r.present or 0) / r.total * 100 < 75)
        labels.append(dept.code or dept.name[:8])
        risk_d.append(def_count); safe_d.append(len(students) - def_count)
    return jsonify({'labels': labels, 'safe': safe_d, 'defaulters': risk_d})

@analytics_bp.route('/api/principal/lecture-today')
@login_required
def principal_lecture_today():
    class_id = request.args.get('class_id', type=int)
    if not class_id:
        return jsonify({'labels': [], 'present': [], 'absent': []})
    sids = [s.id for s in Student.query.filter_by(class_id=class_id).all()]
    recs = Attendance.query.filter(
        Attendance.student_id.in_(sids), Attendance.date == date.today()
    ).all()
    subj_map = {}
    for r in recs:
        sid = r.subject_id
        if sid not in subj_map:
            subj_map[sid] = {'p': 0, 'a': 0, 'name': r.subject.name if r.subject else str(sid)}
        if r.status: subj_map[sid]['p'] += 1
        else:        subj_map[sid]['a'] += 1
    labels = [v['name'] for v in subj_map.values()]
    present = [v['p'] for v in subj_map.values()]
    absent  = [v['a'] for v in subj_map.values()]
    return jsonify({'labels': labels, 'present': present, 'absent': absent})

# ═══════════════════════════════════════════════════════════════════════════
# HOD APIs
# ═══════════════════════════════════════════════════════════════════════════
def _hod_dept_id():
    return get_dept_for_hod(current_user.id)

@analytics_bp.route('/api/hod/summary')
@login_required
def hod_summary():
    dept_id = _hod_dept_id()
    cids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()]
    sids = [s.id for s in Student.query.filter(Student.class_id.in_(cids), Student.approval_status==ApprovalStatus.APPROVED).all()]
    p, a, _ = _today_counts(sids)
    def_count = sum(1 for s in Student.query.filter(Student.class_id.in_(cids), Student.approval_status==ApprovalStatus.APPROVED).all() if s.attendance_percentage() < 75)
    pct = _att_pct(sids)
    return jsonify({'total': len(sids), 'present': p, 'absent': a, 'defaulters': def_count, 'avg_pct': pct})

@analytics_bp.route('/api/hod/classwise-today')
@login_required
def hod_classwise_today():
    dept_id = _hod_dept_id()
    classes = Class.query.filter_by(department_id=dept_id).all()
    labels, pres, abs_ = [], [], []
    for c in classes:
        sids = [s.id for s in Student.query.filter_by(class_id=c.id).all()]
        p, a, _ = _today_counts(sids)
        labels.append(c.name); pres.append(p); abs_.append(a)
    return jsonify({'labels': labels, 'present': pres, 'absent': abs_})

@analytics_bp.route('/api/hod/weekwise')
@login_required
def hod_weekwise():
    dept_id = _hod_dept_id()
    cids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()]
    sids = [s.id for s in Student.query.filter(Student.class_id.in_(cids)).all()]
    labels, p, a = _week_trend(sids, 7)
    return jsonify({'labels': labels, 'present': p, 'absent': a})

@analytics_bp.route('/api/hod/subject-attendance')
@login_required
def hod_subject_attendance():
    dept_id = _hod_dept_id()
    cids = [c.id for c in Class.query.filter_by(department_id=dept_id).all()]
    subjects = Subject.query.filter(Subject.class_id.in_(cids)).all()
    labels, data = [], []
    for subj in subjects:
        sids = [s.id for s in Student.query.filter_by(class_id=subj.class_id).all()]
        pct = _att_pct(sids, subject_id=subj.id)
        labels.append(subj.name); data.append(pct)
    return jsonify({'labels': labels, 'data': data})

@analytics_bp.route('/api/hod/defaulters')
@login_required
def hod_defaulters():
    dept_id = _hod_dept_id()
    if not dept_id:
        return jsonify({'error': 'unauthorized'}), 403
    classes = Class.query.filter_by(department_id=dept_id).all()
    labels, counts = [], []
    for c in classes:
        sids = [s.id for s in Student.query.filter_by(class_id=c.id, approval_status=ApprovalStatus.APPROVED).all()]
        if not sids:
            labels.append(c.name); counts.append(0)
            continue
        # Bulk SQL aggregate - avoids N+1 per student
        stats = db.session.query(
            Attendance.student_id,
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
        ).filter(Attendance.student_id.in_(sids)).group_by(Attendance.student_id).all()
        dc = sum(1 for r in stats if r.total > 0 and (r.present or 0) / r.total * 100 < 75)
        labels.append(c.name); counts.append(dc)
    return jsonify({'labels': labels, 'data': counts})

@analytics_bp.route('/api/hod/lecture-today')
@login_required
def hod_lecture_today():
    class_id = request.args.get('class_id', type=int)
    if not class_id: return jsonify({'labels': [], 'present': [], 'absent': []})
    dept_id = _hod_dept_id()
    cls = Class.query.get(class_id)
    if not cls or cls.department_id != dept_id:
        return jsonify({'error': 'unauthorized'}), 403
    sids = [s.id for s in Student.query.filter_by(class_id=class_id).all()]
    recs = Attendance.query.filter(Attendance.student_id.in_(sids), Attendance.date == date.today()).all()
    subj_map = {}
    for r in recs:
        k = r.subject_id
        if k not in subj_map: subj_map[k] = {'p': 0, 'a': 0, 'name': r.subject.name if r.subject else str(k)}
        if r.status: subj_map[k]['p'] += 1
        else: subj_map[k]['a'] += 1
    return jsonify({'labels': [v['name'] for v in subj_map.values()],
                    'present': [v['p'] for v in subj_map.values()],
                    'absent':  [v['a'] for v in subj_map.values()]})

# ═══════════════════════════════════════════════════════════════════════════
# CLASS TEACHER APIs
# ═══════════════════════════════════════════════════════════════════════════
def _ct_class():
    return get_class_for_ct(current_user.id)

@analytics_bp.route('/api/ct/summary')
@login_required
def ct_summary():
    cls = _ct_class()
    if not cls: return jsonify({'total': 0, 'present': 0, 'absent': 0, 'avg_pct': 0, 'defaulters': 0})
    sids = [s.id for s in Student.query.filter_by(class_id=cls.id, approval_status=ApprovalStatus.APPROVED).all()]
    p, a, _ = _today_counts(sids)
    pct = _att_pct(sids)
    # Bulk SQL aggregate - avoids N+1 per student
    def_count = 0
    if sids:
        stats = db.session.query(
            Attendance.student_id,
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
        ).filter(Attendance.student_id.in_(sids)).group_by(Attendance.student_id).all()
        def_count = sum(1 for r in stats if r.total > 0 and (r.present or 0) / r.total * 100 < 75)
    return jsonify({'total': len(sids), 'present': p, 'absent': a, 'avg_pct': pct, 'defaulters': def_count})

@analytics_bp.route('/api/ct/weekwise')
@login_required
def ct_weekwise():
    cls = _ct_class()
    if not cls: return jsonify({'labels': [], 'present': [], 'absent': []})
    sids = [s.id for s in Student.query.filter_by(class_id=cls.id).all()]
    labels, p, a = _week_trend(sids, 7)
    return jsonify({'labels': labels, 'present': p, 'absent': a})

@analytics_bp.route('/api/ct/subject-attendance')
@login_required
def ct_subject_attendance():
    cls = _ct_class()
    if not cls: return jsonify({'labels': [], 'data': []})
    subjects = Subject.query.filter_by(class_id=cls.id).all()
    sids = [s.id for s in Student.query.filter_by(class_id=cls.id).all()]
    labels, data = [], []
    for subj in subjects:
        pct = _att_pct(sids, subject_id=subj.id)
        labels.append(subj.name); data.append(pct)
    return jsonify({'labels': labels, 'data': data})

@analytics_bp.route('/api/ct/student-list')
@login_required
def ct_student_list():
    cls = _ct_class()
    if not cls: return jsonify({'labels': [], 'data': [], 'students': []})
    students = Student.query.filter_by(class_id=cls.id, approval_status=ApprovalStatus.APPROVED).order_by(Student.roll_no).all()
    labels, data, student_info = [], [], []
    for s in students:
        pct = s.attendance_percentage()
        labels.append(s.user.name if s.user else 'N/A')
        data.append(pct)
        student_info.append({'name': s.user.name if s.user else 'N/A', 'roll': s.roll_no, 'pct': pct, 'defaulter': pct < 75})
    return jsonify({'labels': labels, 'data': data, 'students': student_info})

@analytics_bp.route('/api/ct/lecture-today')
@login_required
def ct_lecture_today():
    cls = _ct_class()
    if not cls: return jsonify({'labels': [], 'present': [], 'absent': []})
    sids = [s.id for s in Student.query.filter_by(class_id=cls.id).all()]
    recs = Attendance.query.filter(Attendance.student_id.in_(sids), Attendance.date == date.today()).all()
    subj_map = {}
    for r in recs:
        k = r.subject_id
        if k not in subj_map: subj_map[k] = {'p': 0, 'a': 0, 'name': r.subject.name if r.subject else str(k)}
        if r.status: subj_map[k]['p'] += 1
        else: subj_map[k]['a'] += 1
    return jsonify({'labels': [v['name'] for v in subj_map.values()],
                    'present': [v['p'] for v in subj_map.values()],
                    'absent':  [v['a'] for v in subj_map.values()]})

# ═══════════════════════════════════════════════════════════════════════════
# TG TEACHER APIs
# ═══════════════════════════════════════════════════════════════════════════
@analytics_bp.route('/api/tg/summary')
@login_required
def tg_summary():
    sids = get_tg_student_ids(current_user.id)
    if not sids: return jsonify({'total': 0, 'present': 0, 'absent': 0, 'defaulters': 0, 'avg_pct': 0})
    p, a, _ = _today_counts(sids)
    students = Student.query.filter(Student.id.in_(sids)).all()
    def_count = sum(1 for s in students if s.attendance_percentage() < 75)
    pct = _att_pct(sids)
    return jsonify({'total': len(sids), 'present': p, 'absent': a, 'defaulters': def_count, 'avg_pct': pct})

@analytics_bp.route('/api/tg/student-attendance')
@login_required
def tg_student_attendance():
    sids = get_tg_student_ids(current_user.id)
    if not sids: return jsonify({'labels': [], 'data': [], 'students': []})
    students = Student.query.filter(Student.id.in_(sids)).all()
    labels, data, info = [], [], []
    for s in students:
        pct = s.attendance_percentage()
        name = s.user.name if s.user else 'N/A'
        labels.append(name); data.append(pct)
        info.append({'name': name, 'roll': s.roll_no, 'pct': pct, 'defaulter': pct < 75})
    return jsonify({'labels': labels, 'data': data, 'students': info})

@analytics_bp.route('/api/tg/weekwise')
@login_required
def tg_weekwise():
    sids = get_tg_student_ids(current_user.id)
    if not sids: return jsonify({'labels': [], 'present': [], 'absent': []})
    labels, p, a = _week_trend(sids, 7)
    return jsonify({'labels': labels, 'present': p, 'absent': a})

@analytics_bp.route('/api/tg/subject-breakdown/<int:student_id>')
@login_required
def tg_subject_breakdown(student_id):
    allowed = get_tg_student_ids(current_user.id)
    if student_id not in allowed: return jsonify({'error': 'unauthorized'}), 403
    student = Student.query.get_or_404(student_id)
    subjects = Subject.query.filter_by(class_id=student.class_id).all()
    labels, data = [], []
    for subj in subjects:
        pct = student.attendance_percentage(subject_id=subj.id)
        labels.append(subj.name); data.append(pct)
    return jsonify({'labels': labels, 'data': data, 'student': student.user.name if student.user else ''})

# ═══════════════════════════════════════════════════════════════════════════
# SUBJECT TEACHER APIs
# ═══════════════════════════════════════════════════════════════════════════
@analytics_bp.route('/api/subject/summary')
@login_required
def subject_summary():
    subj_id = request.args.get('subject_id', type=int)
    if not subj_id: return jsonify({'total': 0, 'avg_pct': 0, 'defaulters': 0, 'lectures': 0})
    subj = Subject.query.get_or_404(subj_id)
    if subj.teacher_id != current_user.id and current_user.role not in [Roles.HOD, Roles.SUPER_ADMIN]:
        return jsonify({'error': 'unauthorized'}), 403
    students = get_students_for_subject(subj)
    sids = [s.id for s in students]
    lectures = Attendance.query.filter(Attendance.subject_id==subj_id).with_entities(Attendance.date).distinct().count()
    pct = _att_pct(sids, subject_id=subj_id)
    def_count = sum(1 for s in students if s.attendance_percentage(subject_id=subj_id) < 75)
    return jsonify({'total': len(students), 'avg_pct': pct, 'defaulters': def_count, 'lectures': lectures})

@analytics_bp.route('/api/subject/student-attendance')
@login_required
def subject_student_attendance():
    subj_id = request.args.get('subject_id', type=int)
    if not subj_id: return jsonify({'labels': [], 'data': [], 'students': []})
    subj = Subject.query.get_or_404(subj_id)
    if subj.teacher_id != current_user.id and current_user.role not in [Roles.HOD, Roles.SUPER_ADMIN]:
        return jsonify({'error': 'unauthorized'}), 403
    students = get_students_for_subject(subj)
    labels, data, info = [], [], []
    for s in students:
        pct = s.attendance_percentage(subject_id=subj_id)
        name = s.user.name if s.user else 'N/A'
        labels.append(name); data.append(pct)
        info.append({'name': name, 'roll': s.roll_no, 'pct': pct, 'defaulter': pct < 75})
    return jsonify({'labels': labels, 'data': data, 'students': info})

@analytics_bp.route('/api/subject/trend')
@login_required
def subject_trend():
    subj_id = request.args.get('subject_id', type=int)
    if not subj_id: return jsonify({'labels': [], 'data': []})
    subj = Subject.query.get_or_404(subj_id)
    # Scope check: only the subject's teacher, CT for the class, HOD, or SUPER_ADMIN
    if current_user.role == Roles.TEACHER:
        if subj.teacher_id != current_user.id:
            return jsonify({'error': 'unauthorized'}), 403
    elif current_user.role == Roles.CLASS_TEACHER:
        cls = get_class_for_ct(current_user.id)
        if not cls or subj.class_id != cls.id:
            return jsonify({'error': 'unauthorized'}), 403
    elif current_user.role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        cls = Class.query.get(subj.class_id)
        if not cls or cls.department_id != dept_id:
            return jsonify({'error': 'unauthorized'}), 403
    today = date.today()
    labels, data = [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        total = Attendance.query.filter_by(subject_id=subj_id, date=d).count()
        if total == 0: continue
        present = Attendance.query.filter_by(subject_id=subj_id, date=d, status=True).count()
        labels.append(d.strftime('%d %b')); data.append(present)
    return jsonify({'labels': labels, 'data': data})

# Legacy endpoints kept for backward compatibility
@analytics_bp.route('/api/attendance-overview')
@login_required
def attendance_overview():
    return principal_dept_overall()

@analytics_bp.route('/api/defaulters')
@login_required
def defaulters():
    if current_user.role not in STAFF_ROLES:
        return jsonify({'error': 'unauthorized'}), 403
    classes = Class.query.all()
    labels, counts = [], []
    for c in classes:
        students = Student.query.filter_by(class_id=c.id, approval_status=ApprovalStatus.APPROVED).all()
        dc = sum(1 for s in students if s.attendance_percentage() < 75)
        labels.append(c.name); counts.append(dc)
    return jsonify({'labels': labels, 'data': counts})

@analytics_bp.route('/api/attendance-trend')
@login_required
def attendance_trend():
    if current_user.role not in STAFF_ROLES:
        return jsonify({'error': 'unauthorized'}), 403
    today = date.today()
    labels, p_data, a_data = [], [], []
    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        total = Attendance.query.filter_by(date=d).count()
        present = Attendance.query.filter_by(date=d, status=True).count()
        labels.append(d.strftime('%d %b'))
        p_data.append(present); a_data.append(total - present)
    return jsonify({'labels': labels, 'present': p_data, 'absent': a_data})

@analytics_bp.route('/api/summary')
@login_required
def summary():
    return principal_summary()

@analytics_bp.route('/request-reason/<int:attendance_id>', methods=['POST'])
@login_required
def request_reason(attendance_id):
    from app.utils.helpers import get_class_for_ct, get_dept_for_hod
    attendance = Attendance.query.get_or_404(attendance_id)

    # Scope: only staff who are responsible for this student's class may request reasons
    student = Student.query.get(attendance.student_id)
    if not student:
        from flask import abort; abort(404)
    if current_user.role == Roles.TEACHER:
        # Only if this teacher teaches the subject OR is TG for the student
        is_tg = (student.tg_id == current_user.id)
        teaches = (attendance.subject and attendance.subject.teacher_id == current_user.id)
        if not is_tg and not teaches:
            from flask import abort; abort(403)
    elif current_user.role == Roles.CLASS_TEACHER:
        cls = get_class_for_ct(current_user.id)
        if not cls or student.class_id != cls.id:
            from flask import abort; abort(403)
    elif current_user.role == Roles.HOD:
        dept_id = get_dept_for_hod(current_user.id)
        from app.models import Class as Cls
        cls = Cls.query.get(student.class_id)
        if not cls or cls.department_id != dept_id:
            from flask import abort; abort(403)
    elif current_user.role not in [Roles.SUPER_ADMIN]:
        from flask import abort; abort(403)

    if attendance.absentee_reason:
        from flask import flash, redirect, url_for
        flash('Reason already requested.', 'warning')
        return redirect(request.referrer or url_for('analytics.index'))
    new_reason = AbsenteeReason(attendance_id=attendance.id, requested_by=current_user.id, status='REQUESTED')
    db.session.add(new_reason); db.session.commit()
    from flask import flash, redirect, url_for
    flash('Absentee reason requested.', 'success')
    return redirect(request.referrer or url_for('analytics.index'))
