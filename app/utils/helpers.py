from app.models import Notification
from app.extensions import db
import logging

logger = logging.getLogger(__name__)


def _fire_web_push(user_id, message, notif_type, link):
    """Send a Web Push notification to all of a user's registered browsers.
    Runs in a background thread — never blocks the main request."""
    try:
        from flask import current_app
        from app.models import PushSubscription
        from pywebpush import webpush, WebPushException
        import json, threading

        subs = PushSubscription.query.filter_by(user_id=user_id).all()
        if not subs:
            return

        pub_key   = current_app.config.get('VAPID_PUBLIC_KEY', '')
        priv_key  = current_app.config.get('VAPID_PRIVATE_KEY', '')
        claims_email = current_app.config.get('VAPID_CLAIMS_EMAIL', 'admin@college.edu')

        if not pub_key or not priv_key:
            return

        payload = json.dumps({
            'title': 'CSMSS College ERP',
            'body':  message,
            'type':  notif_type,
            'url':   link or '/notifications/',
            'icon':  '/static/img/college_logo.png',
        })

        dead_endpoints = []
        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        'endpoint': sub.endpoint,
                        'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                    },
                    data=payload,
                    vapid_private_key=priv_key,
                    vapid_claims={'sub': f'mailto:{claims_email}'},
                )
            except WebPushException as e:
                # 410 Gone = subscription expired/unregistered
                if e.response and e.response.status_code in (404, 410):
                    dead_endpoints.append(sub.endpoint)
                else:
                    logger.warning(f"[WebPush] Failed for user {user_id}: {e}")
            except Exception as e:
                logger.warning(f"[WebPush] Unexpected error for user {user_id}: {e}")

        if dead_endpoints:
            PushSubscription.query.filter(
                PushSubscription.endpoint.in_(dead_endpoints)
            ).delete(synchronize_session=False)
            db.session.commit()

    except Exception as e:
        logger.warning(f"[WebPush] _fire_web_push crashed: {e}")


def send_notification(user_id, message, notif_type='info', link=None):
    """
    Add an in-app notification for a user AND fire a Web Push to their devices.
    Uses a nested savepoint so a notification failure NEVER rolls back
    the caller's outer transaction (e.g., bulk attendance saves).
    The CALLER is responsible for db.session.commit().
    """
    try:
        with db.session.begin_nested():  # savepoint — only this rolls back on failure
            notif = Notification(
                user_id=user_id,
                message=message,
                type=notif_type,
                link=link
            )
            db.session.add(notif)
    except Exception as e:
        logger.warning(f"[Notification] Failed to queue notification for user {user_id}: {e}")

    # Fire Web Push in a background thread — never blocks the request
    try:
        import threading
        from flask import current_app
        app = current_app._get_current_object()
        # Capture values for the closure explicitly to avoid late-binding issues
        _uid, _msg, _type, _link = user_id, message, notif_type, link

        def _push_worker():
            with app.app_context():
                _fire_web_push(_uid, _msg, _type, _link)

        threading.Thread(target=_push_worker, daemon=True).start()
    except Exception:
        pass  # Web push is best-effort


def send_bulk_notification(user_ids, message, notif_type='info', link=None):
    """Queue notifications for multiple users. Caller must commit."""
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
        db.session.flush()
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

