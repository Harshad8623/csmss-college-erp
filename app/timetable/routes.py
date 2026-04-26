from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Timetable, Class, Subject, Roles, Student
from app.utils.decorators import role_required

timetable_bp = Blueprint('timetable', __name__, url_prefix='/timetable')

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

@timetable_bp.route('/')
@login_required
def index():
    if current_user.role == Roles.STUDENT:
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
            timetable_data[day] = sorted(
                [e for e in entries if e.day == day],
                key=lambda x: x.start_time
            )
    else:
        for day in DAYS:
            timetable_data[day] = []

    return render_template('timetable/index.html',
        timetable_data=timetable_data, days=DAYS,
        classes=classes, selected_class=selected_class)

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
        entry = Timetable(class_id=class_id, subject_id=subject_id,
                          day=day, start_time=start_time, end_time=end_time)
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
