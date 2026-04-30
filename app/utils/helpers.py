from app.models import Notification
from app.extensions import db


def send_notification(user_id, message, notif_type='info', link=None):
    """
    Create an in-app notification for a user and commit it.
    Uses a nested savepoint so it never breaks the caller's transaction.
    """
    try:
        notif = Notification(
            user_id=user_id,
            message=message,
            type=notif_type,
            link=link
        )
        db.session.add(notif)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[Notification] Failed to save notification: {e}")


def send_bulk_notification(user_ids, message, notif_type='info', link=None):
    """Send notification to multiple users in a single commit."""
    if not user_ids:
        return
    try:
        for uid in user_ids:
            notif = Notification(
                user_id=uid,
                message=message,
                type=notif_type,
                link=link
            )
            db.session.add(notif)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[Notification] Bulk notification failed: {e}")


def calculate_attendance_percentage(student_id, subject_id=None):
    from app.models import Attendance
    query = Attendance.query.filter_by(student_id=student_id)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    total = query.count()
    if total == 0:
        return 0
    present = query.filter_by(status=True).count()
    return round((present / total) * 100, 2)


def get_grade(percentage):
    if percentage >= 90: return ('O',  'Outstanding',   'success')
    if percentage >= 80: return ('A+', 'Excellent',     'primary')
    if percentage >= 70: return ('A',  'Very Good',     'info')
    if percentage >= 60: return ('B+', 'Good',          'secondary')
    if percentage >= 50: return ('B',  'Average',       'warning')
    if percentage >= 40: return ('C',  'Below Average', 'warning')
    return ('F', 'Fail', 'danger')


def classes_needed_for_75(present, total):
    """Calculate how many consecutive classes needed to reach 75%."""
    if total == 0:
        return 0
    current_pct = (present / total) * 100
    if current_pct >= 75:
        return 0
    # Solve: (present + x) / (total + x) >= 0.75
    x = (0.75 * total - present) / 0.25
    return max(0, int(x) + 1)


def get_dept_for_hod(user_id):
    """Get the department_id for an HOD user."""
    from app.models import Teacher
    teacher = Teacher.query.filter_by(user_id=user_id).first()
    return teacher.department_id if teacher else None


def get_class_for_ct(user_id):
    """Get the Class assigned to a Class Teacher user."""
    from app.models import Class
    return Class.query.filter_by(class_teacher_id=user_id).first()


def get_tg_student_ids(user_id):
    """Return list of student IDs for which this user is Teacher Guardian."""
    from app.models import Student
    return [s.id for s in Student.query.filter_by(tg_id=user_id).all()]


def get_students_for_subject(subject):
    """
    Return the list of students enrolled in a subject.
    If the subject is elective, returns only students explicitly enrolled in it.
    If it is a regular subject, returns all approved students in the subject's class.
    """
    from app.models import Student, ApprovalStatus
    if subject.is_elective:
        # Enrolled students via the student_subjects association table
        return sorted(subject.enrolled_students, key=lambda s: (s.roll_no is None, s.roll_no))
    else:
        # All approved students in the class
        return Student.query.filter_by(class_id=subject.class_id, approval_status=ApprovalStatus.APPROVED).order_by(Student.roll_no).all()

