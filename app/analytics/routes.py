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
    """Single-query attendance percentage (was 2 sequential counts)."""
    if not student_ids:
        return 0
    q = db.session.query(
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(Attendance.student_id.in_(student_ids))
    if subject_id:
        q = q.filter(Attendance.subject_id == subject_id)
    if d:
        q = q.filter(Attendance.date == d)
    row = q.one()
    if not row.total:
        return 0
    return round((row.present or 0) / row.total * 100, 2)

def _today_counts(student_ids):
    """Single-query today present/absent count."""
    if not student_ids:
        return 0, 0, 0
    recs = db.session.query(
        Attendance.student_id,
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('p'),
        func.sum(db.case((Attendance.status == False, 1), else_=0)).label('a')
    ).filter(
        Attendance.student_id.in_(student_ids),
        Attendance.date == date.today()
    ).group_by(Attendance.student_id).all()
    present = sum(1 for r in recs if r.p > 0 and r.a == 0)
    absent  = sum(1 for r in recs if r.a > 0)
    return present, absent, len(recs)

def _week_trend(student_ids, days=7):
    """Single-query 7-day trend (was 14 queries: 2 per day x 7 days)."""
    today = date.today()
    start = today - timedelta(days=days - 1)
    if not student_ids:
        labels = [(start + timedelta(days=i)).strftime('%d %b') for i in range(days)]
        return labels, [0]*days, [0]*days

    rows = db.session.query(
        Attendance.date,
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(
        Attendance.student_id.in_(student_ids),
        Attendance.date >= start,
        Attendance.date <= today
    ).group_by(Attendance.date).all()
    day_map = {r.date: (r.present or 0, r.total - (r.present or 0)) for r in rows}

    labels, p_data, a_data = [], [], []
    for i in range(days):
        d = start + timedelta(days=i)
        p, a = day_map.get(d, (0, 0))
        labels.append(d.strftime('%d %b'))
        p_data.append(p); a_data.append(a)
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

    # Single query: get all today's attendance grouped by student_id
    all_class_ids = [c.id for c in Class.query.with_entities(Class.id).all()]
    # Build student_id -> dept_id map in one query
    student_dept = db.session.query(
        Student.id, Class.department_id
    ).join(Class, Student.class_id == Class.id).filter(
        Class.department_id.in_([d.id for d in depts])
    ).all()
    sid_to_dept = {row[0]: row[1] for row in student_dept}
    all_sids = list(sid_to_dept.keys())

    today_recs = db.session.query(
        Attendance.student_id,
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('p'),
        func.sum(db.case((Attendance.status == False, 1), else_=0)).label('a')
    ).filter(
        Attendance.student_id.in_(all_sids),
        Attendance.date == date.today()
    ).group_by(Attendance.student_id).all()

    dept_stats = {d.id: {'p': 0, 'a': 0, 'total': 0} for d in depts}
    for sid, cnt in sid_to_dept.items():
        dept_stats[cnt]['total'] += 1
    for r in today_recs:
        did = sid_to_dept.get(r.student_id)
        if did and did in dept_stats:
            if r.p > 0 and r.a == 0: dept_stats[did]['p'] += 1
            elif r.a > 0:            dept_stats[did]['a'] += 1

    labels = [d.code or d.name[:8] for d in depts]
    present_d = [dept_stats[d.id]['p'] for d in depts]
    absent_d  = [dept_stats[d.id]['a'] for d in depts]
    total_d   = [dept_stats[d.id]['total'] for d in depts]
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
    sids = [s.id for s in Student.query.filter_by(class_id=class_id).with_entities(Student.id).all()]
    recs = Attendance.query.filter(
        Attendance.student_id.in_(sids), Attendance.date == date.today()
    ).all()
    # Pre-fetch all subjects to avoid lazy N+1 on r.subject.name inside loop
    subject_ids = list({r.subject_id for r in recs})
    subj_name_map = {
        s.id: s.name for s in Subject.query.filter(Subject.id.in_(subject_ids)).all()
    } if subject_ids else {}

    subj_map = {}
    for r in recs:
        sid = r.subject_id
        if sid not in subj_map:
            subj_map[sid] = {'p': 0, 'a': 0, 'name': subj_name_map.get(sid, str(sid))}
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
    sids = [s.id for s in Student.query.filter(
        Student.class_id.in_(cids), Student.approval_status == ApprovalStatus.APPROVED
    ).with_entities(Student.id).all()] if cids else []
    p, a, _ = _today_counts(sids)

    # Bulk defaulter count — replaces N+1 s.attendance_percentage() loop
    from sqlalchemy import func as sqlfunc
    stats = db.session.query(
        Attendance.student_id,
        sqlfunc.count(Attendance.id).label('total'),
        sqlfunc.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(Attendance.student_id.in_(sids)).group_by(Attendance.student_id).all() if sids else []
    def_count = sum(1 for r in stats if r.total > 0 and (r.present or 0) / r.total * 100 < 75)

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
    # Pre-fetch subject names to avoid lazy-load N+1 inside loop
    subject_ids = list({r.subject_id for r in recs})
    subj_name_map = {
        s.id: s.name for s in Subject.query.filter(Subject.id.in_(subject_ids)).all()
    } if subject_ids else {}
    subj_map = {}
    for r in recs:
        k = r.subject_id
        if k not in subj_map: subj_map[k] = {'p': 0, 'a': 0, 'name': subj_name_map.get(k, str(k))}
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
    sids = [s.id for s in students]
    labels, data, student_info = [], [], []
    # Bulk aggregate to avoid N+1 s.attendance_percentage() calls
    stats = db.session.query(
        Attendance.student_id,
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(Attendance.student_id.in_(sids)).group_by(Attendance.student_id).all() if sids else []
    pct_map = {
        r.student_id: round((r.present or 0) / r.total * 100, 2) if r.total > 0 else 0
        for r in stats
    }
    for s in students:
        pct = pct_map.get(s.id, 0)
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
    # Pre-fetch subject names to avoid lazy-load N+1 inside loop
    subject_ids = list({r.subject_id for r in recs})
    subj_name_map = {
        s.id: s.name for s in Subject.query.filter(Subject.id.in_(subject_ids)).all()
    } if subject_ids else {}
    subj_map = {}
    for r in recs:
        k = r.subject_id
        if k not in subj_map: subj_map[k] = {'p': 0, 'a': 0, 'name': subj_name_map.get(k, str(k))}
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
    # Bulk SQL aggregate — replaces N+1 s.attendance_percentage() loop
    stats = db.session.query(
        Attendance.student_id,
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(Attendance.student_id.in_(sids)).group_by(Attendance.student_id).all()
    def_count = sum(1 for r in stats if r.total > 0 and (r.present or 0) / r.total * 100 < 75)
    pct = _att_pct(sids)
    return jsonify({'total': len(sids), 'present': p, 'absent': a, 'defaulters': def_count, 'avg_pct': pct})

@analytics_bp.route('/api/tg/student-attendance')
@login_required
def tg_student_attendance():
    sids = get_tg_student_ids(current_user.id)
    if not sids: return jsonify({'labels': [], 'data': [], 'students': []})
    students = Student.query.filter(Student.id.in_(sids)).all()
    labels, data, info = [], [], []
    # Bulk aggregate — replaces N+1 s.attendance_percentage() calls
    stats = db.session.query(
        Attendance.student_id,
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(Attendance.student_id.in_(sids)).group_by(Attendance.student_id).all()
    pct_map = {
        r.student_id: round((r.present or 0) / r.total * 100, 2) if r.total > 0 else 0
        for r in stats
    }
    for s in students:
        pct  = pct_map.get(s.id, 0)
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
    subjects = Subject.query.filter_by(
        class_id=student.class_id,
        count_in_attendance=True
    ).all()
    sids = [student.id]
    subj_ids = [s.id for s in subjects]
    # Single bulk query instead of N+1 attendance_percentage(subject_id=...) per subject
    stats = db.session.query(
        Attendance.subject_id,
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(
        Attendance.student_id == student.id,
        Attendance.subject_id.in_(subj_ids)
    ).group_by(Attendance.subject_id).all() if subj_ids else []
    pct_map = {
        r.subject_id: round((r.present or 0) / r.total * 100, 2) if r.total > 0 else 0
        for r in stats
    }
    labels = [s.name for s in subjects]
    data   = [pct_map.get(s.id, 0) for s in subjects]
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
    # Bulk aggregate per subject — replaces N+1 s.attendance_percentage(subject_id=subj_id) calls
    stats = db.session.query(
        Attendance.student_id,
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(
        Attendance.student_id.in_(sids),
        Attendance.subject_id == subj_id
    ).group_by(Attendance.student_id).all() if sids else []
    def_count = sum(1 for r in stats if r.total > 0 and (r.present or 0) / r.total * 100 < 75)
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
    sids = [s.id for s in students]
    labels, data, info = [], [], []
    # Bulk aggregate per subject — replaces N+1 s.attendance_percentage(subject_id=subj_id) calls
    stats = db.session.query(
        Attendance.student_id,
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(
        Attendance.student_id.in_(sids),
        Attendance.subject_id == subj_id
    ).group_by(Attendance.student_id).all() if sids else []
    pct_map = {
        r.student_id: round((r.present or 0) / r.total * 100, 2) if r.total > 0 else 0
        for r in stats
    }
    for s in students:
        pct = pct_map.get(s.id, 0)
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
    start = today - timedelta(days=29)
    # Single GROUP BY query instead of 60 sequential COUNT queries (2 per day × 30 days)
    rows = db.session.query(
        Attendance.date,
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present'),
        func.count(Attendance.id).label('total')
    ).filter(
        Attendance.subject_id == subj_id,
        Attendance.date >= start,
        Attendance.date <= today
    ).group_by(Attendance.date).order_by(Attendance.date).all()
    labels = [r.date.strftime('%d %b') for r in rows if r.total > 0]
    data   = [int(r.present or 0) for r in rows if r.total > 0]
    return jsonify({'labels': labels, 'data': data})

# Legacy endpoints kept for backward compatibility
@analytics_bp.route('/api/attendance-overview')
@login_required
def attendance_overview():
    return principal_dept_overall()

@analytics_bp.route('/api/defaulters')
@login_required
def defaulters():
    # Scoped: only SUPER_ADMIN gets college-wide defaulter data
    if current_user.role != Roles.SUPER_ADMIN:
        return jsonify({'error': 'unauthorized'}), 403
    classes = Class.query.all()
    labels, counts = [], []
    for c in classes:
        sids = [s.id for s in Student.query.filter_by(
            class_id=c.id, approval_status=ApprovalStatus.APPROVED
        ).with_entities(Student.id).all()]
        if not sids:
            labels.append(c.name); counts.append(0)
            continue
        # Bulk SQL aggregate — replaces N+1 s.attendance_percentage() per student
        stats = db.session.query(
            Attendance.student_id,
            func.count(Attendance.id).label('total'),
            func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
        ).filter(Attendance.student_id.in_(sids)).group_by(Attendance.student_id).all()
        dc = sum(1 for r in stats if r.total > 0 and (r.present or 0) / r.total * 100 < 75)
        labels.append(c.name); counts.append(dc)
    return jsonify({'labels': labels, 'data': counts})

@analytics_bp.route('/api/attendance-trend')
@login_required
def attendance_trend():
    # Scoped: only SUPER_ADMIN sees college-wide trend via this legacy endpoint
    if current_user.role != Roles.SUPER_ADMIN:
        return jsonify({'error': 'unauthorized'}), 403
    today = date.today()
    start = today - timedelta(days=29)
    # Single GROUP BY query — replaces 60 sequential COUNT queries (2 per day * 30 days)
    rows = db.session.query(
        Attendance.date,
        func.count(Attendance.id).label('total'),
        func.sum(db.case((Attendance.status == True, 1), else_=0)).label('present')
    ).filter(
        Attendance.date >= start,
        Attendance.date <= today
    ).group_by(Attendance.date).all()
    day_map = {r.date: (r.present or 0, r.total - (r.present or 0)) for r in rows}
    labels, p_data, a_data = [], [], []
    for i in range(30):
        d = start + timedelta(days=i)
        p, a = day_map.get(d, (0, 0))
        labels.append(d.strftime('%d %b'))
        p_data.append(p); a_data.append(a)
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
