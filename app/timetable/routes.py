from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Timetable, Class, Subject, Roles, Student
from app.utils.decorators import role_required
from datetime import datetime

timetable_bp = Blueprint('timetable', __name__, url_prefix='/timetable')

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

# Grid constants
GRID_START   = 10 * 60      # 10:00 in minutes
GRID_END     = 17 * 60 + 15 # 17:15 in minutes
PX_PER_MIN   = 2
GRID_HEIGHT  = (GRID_END - GRID_START) * PX_PER_MIN  # 870px


def _to_minutes(t: str) -> int:
    """Convert 'HH:MM' or 'HH:MM:SS' to total minutes from midnight."""
    try:
        parts = t.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return GRID_START


def _process_day_entries(entries):
    """
    Takes a list of Timetable entries for a single day,
    computes top/height in pixels, and groups overlapping entries
    so they can be rendered side-by-side in the template.
    Returns a list of groups: each group is a list of enriched dicts.
    """
    enriched = []
    for e in entries:
        start_m = _to_minutes(e.start_time)
        end_m   = _to_minutes(e.end_time)
        top     = (start_m - GRID_START) * PX_PER_MIN
        height  = max((end_m - start_m) * PX_PER_MIN, 30)  # min 30px
        enriched.append({
            'entry':    e,
            'start_m':  start_m,
            'end_m':    end_m,
            'top':      top,
            'height':   height,
        })

    # Sort by start time
    enriched.sort(key=lambda x: x['start_m'])

    # Group overlapping entries (any two that share time range)
    groups = []
    used = set()
    for i, a in enumerate(enriched):
        if i in used:
            continue
        group = [a]
        used.add(i)
        for j, b in enumerate(enriched):
            if j in used:
                continue
            # Overlap: a starts before b ends AND b starts before a ends
            if a['start_m'] < b['end_m'] and b['start_m'] < a['end_m']:
                group.append(b)
                used.add(j)
        groups.append(group)

    return groups


def _build_time_axis():
    """Generate time axis labels (15-min steps) from GRID_START to GRID_END."""
    labels = []
    m = GRID_START
    while m <= GRID_END:
        h, mi = divmod(m, 60)
        suffix = 'AM' if h < 12 else 'PM'
        h12 = h % 12 or 12
        labels.append({
            'label': f'{h12}:{mi:02d} {suffix}',
            'top':   (m - GRID_START) * PX_PER_MIN,
        })
        m += 60  # every hour on the axis
    return labels


# Fixed break definitions (top + height in px)
BREAKS = [
    {
        'label': '🍽 Lunch Break',
        'top':    (_to_minutes('12:15') - GRID_START) * PX_PER_MIN,
        'height': (_to_minutes('13:00') - _to_minutes('12:15')) * PX_PER_MIN,
    },
    {
        'label': '☕ Tea Break',
        'top':    (_to_minutes('15:00') - GRID_START) * PX_PER_MIN,
        'height': (_to_minutes('15:15') - _to_minutes('15:00')) * PX_PER_MIN,
    },
]


@timetable_bp.route('/')
@login_required
def index():
    if current_user.role in [Roles.STUDENT, Roles.CR]:
        student = Student.query.filter_by(user_id=current_user.id).first()
        class_id = student.class_id if student else None
    else:
        class_id = request.args.get('class_id')

    classes = Class.query.all()
    timetable_data = {}
    selected_class = None

    if class_id:
        selected_class = Class.query.get(class_id)
        entries = Timetable.query.filter_by(class_id=class_id).all()
        for day in DAYS:
            day_entries = sorted(
                [e for e in entries if e.day == day],
                key=lambda x: x.start_time
            )
            timetable_data[day] = _process_day_entries(day_entries)
    else:
        for day in DAYS:
            timetable_data[day] = []

    return render_template('timetable/index.html',
        timetable_data=timetable_data, days=DAYS,
        classes=classes, selected_class=selected_class,
        grid_height=GRID_HEIGHT,
        time_axis=_build_time_axis(),
        breaks=BREAKS)

@timetable_bp.route('/manage', methods=['GET', 'POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def manage():
    classes = Class.query.all()
    class_id = request.args.get('class_id') or request.form.get('class_id')
    subjects = Subject.query.filter_by(class_id=class_id).all() if class_id else []
    entries = Timetable.query.filter_by(class_id=class_id).all() if class_id else []

    if request.method == 'POST' and request.form.get('action') == 'add':
        day        = request.form.get('day')
        subject_id = request.form.get('subject_id')
        start_time = request.form.get('start_time')
        end_time   = request.form.get('end_time')
        entry_type = request.form.get('entry_type', 'theory')
        batch      = request.form.get('batch', '').strip() or None
        # Only store batch for practical entries
        if entry_type != 'practical':
            batch = None
        entry = Timetable(class_id=class_id, subject_id=subject_id,
                          day=day, start_time=start_time, end_time=end_time,
                          entry_type=entry_type, batch=batch)
        db.session.add(entry)
        db.session.commit()
        flash('Timetable entry added!', 'success')
        return redirect(url_for('timetable.manage', class_id=class_id))

    return render_template('timetable/manage.html',
        classes=classes, selected_class=Class.query.get(class_id) if class_id else None,
        subjects=subjects, entries=entries, days=DAYS)

@timetable_bp.route('/edit/<int:id>', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def edit(id):
    entry = Timetable.query.get_or_404(id)
    class_id = entry.class_id
    entry.day        = request.form.get('day', entry.day)
    entry.subject_id = request.form.get('subject_id', entry.subject_id)
    entry.start_time = request.form.get('start_time', entry.start_time)
    entry.end_time   = request.form.get('end_time', entry.end_time)
    entry.entry_type = request.form.get('entry_type', entry.entry_type or 'theory')
    batch = request.form.get('batch', '').strip() or None
    entry.batch = batch if entry.entry_type == 'practical' else None
    db.session.commit()
    flash('Timetable entry updated!', 'success')
    return redirect(url_for('timetable.manage', class_id=class_id))

@timetable_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@role_required(Roles.SUPER_ADMIN, Roles.HOD, Roles.CLASS_TEACHER)
def delete(id):
    entry = Timetable.query.get_or_404(id)
    class_id = entry.class_id
    db.session.delete(entry)
    db.session.commit()
    flash('Entry removed.', 'info')
    return redirect(url_for('timetable.manage', class_id=class_id))
