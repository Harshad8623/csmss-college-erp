from datetime import datetime
from app.extensions import db, login_manager
from flask_login import UserMixin

# ─────────────────────────────────────────────────────────────────────────────
# ENUMS / CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
class Roles:
    SUPER_ADMIN   = 'SUPER_ADMIN'
    HOD           = 'HOD'
    CLASS_TEACHER = 'CLASS_TEACHER'
    TEACHER       = 'TEACHER'
    CR            = 'CR'
    STUDENT       = 'STUDENT'

    ALL = [SUPER_ADMIN, HOD, CLASS_TEACHER, TEACHER, CR, STUDENT]
    STAFF = [SUPER_ADMIN, HOD, CLASS_TEACHER, TEACHER]
    ADMIN_ROLES = [SUPER_ADMIN, HOD, CLASS_TEACHER]

class Status:
    ACTIVE  = 'active'
    PENDING = 'pending'
    BLOCKED = 'blocked'

class ApprovalStatus:
    PENDING  = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'

class ExamType:
    CT1  = 'class_test_1'
    OBT1 = 'open_book_test_1'
    CT2  = 'class_test_2'
    OBT2 = 'open_book_test_2'
    MSE  = 'mid_sem_exam'
    OBT3 = 'open_book_test_3'

    ALL = [CT1, OBT1, CT2, OBT2, MSE, OBT3]

    LABELS = {
        CT1:  'CT-1 (Class Test 1)',
        OBT1: 'OBT-1 (Open Book Test 1)',
        CT2:  'CT-2 (Class Test 2)',
        OBT2: 'OBT-2 (Open Book Test 2)',
        MSE:  'MSE (Mid Sem Exam)',
        OBT3: 'OBT-3 (Open Book Test 3)',
    }

class GrievanceType:
    MARKS      = 'marks'
    ATTENDANCE = 'attendance'
    FACULTY    = 'faculty'
    FACILITY   = 'facility'
    OTHER      = 'other'

class GrievancePriority:
    LOW    = 'low'
    MEDIUM = 'medium'
    HIGH   = 'high'
    URGENT = 'urgent'

class CertificateType:
    BONAFIDE  = 'bonafide'
    LEAVING   = 'leaving'
    CHARACTER = 'character'
    TRANSFER  = 'transfer'

class LeaveStatus:
    PENDING_TG = 'pending_tg'
    PENDING_CT = 'pending_ct'
    APPROVED   = 'approved'
    REJECTED   = 'rejected'

class LeaveType:
    SINGLE_DAY        = 'single_day'
    MULTI_DAY         = 'multi_day'
    SPECIFIC_LECTURES = 'specific_lectures'

# ─────────────────────────────────────────────────────────────────────────────
# USER LOADER
# ─────────────────────────────────────────────────────────────────────────────
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ─────────────────────────────────────────────────────────────────────────────
# CORE MODELS
# ─────────────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(120), nullable=False)
    email         = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role          = db.Column(db.String(30), nullable=False, default=Roles.STUDENT, index=True)
    status        = db.Column(db.String(20), default=Status.PENDING, index=True)
    phone         = db.Column(db.String(15))
    profile_pic   = db.Column(db.String(200), default='default.png')
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)  # Force pw change on first login
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    student_profile     = db.relationship('Student', backref='user', uselist=False, foreign_keys='Student.user_id')
    teacher_profile     = db.relationship('Teacher', backref='user', uselist=False, foreign_keys='Teacher.user_id')
    notifications       = db.relationship('Notification', backref='user', lazy='dynamic', foreign_keys='Notification.user_id')
    sent_messages       = db.relationship('Message', backref='sender', lazy='dynamic', foreign_keys='Message.sender_id')
    received_messages   = db.relationship('Message', backref='receiver', lazy='dynamic', foreign_keys='Message.receiver_id')

    def is_active_status(self):
        return self.status == Status.ACTIVE

    def has_role(self, *roles):
        return self.role in roles

    def is_admin(self):
        return self.role in Roles.ADMIN_ROLES

    def __repr__(self):
        return f'<User {self.email} [{self.role}]>'


class Department(db.Model):
    __tablename__ = 'departments'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False)
    code       = db.Column(db.String(10))
    hod_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    hod      = db.relationship('User', foreign_keys=[hod_id])
    classes  = db.relationship('Class', backref='department', lazy='dynamic')
    teachers = db.relationship('Teacher', backref='department', lazy='dynamic')

    def __repr__(self):
        return f'<Department {self.name}>'


class Class(db.Model):
    __tablename__ = 'classes'
    id               = db.Column(db.Integer, primary_key=True)
    name             = db.Column(db.String(100), nullable=False)
    year             = db.Column(db.Integer)
    section          = db.Column(db.String(10))
    department_id    = db.Column(db.Integer, db.ForeignKey('departments.id'))
    class_teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    class_teacher  = db.relationship('User', foreign_keys=[class_teacher_id])
    students       = db.relationship('Student', backref='class_', lazy='dynamic')
    subjects       = db.relationship('Subject', backref='class_', lazy='dynamic')
    timetable      = db.relationship('Timetable', backref='class_', lazy='dynamic')

    @property
    def full_name(self):
        return f"{self.name} - Year {self.year} [{self.section}]"

    def __repr__(self):
        return f'<Class {self.name}>'


# Association table for elective subject enrollments
student_subjects = db.Table('student_subjects',
    db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
    db.Column('subject_id', db.Integer, db.ForeignKey('subjects.id'), primary_key=True)
)

class Student(db.Model):
    __tablename__ = 'students'
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    class_id        = db.Column(db.Integer, db.ForeignKey('classes.id'), index=True)
    roll_no         = db.Column(db.String(20), index=True)
    prn             = db.Column(db.String(30), unique=True, index=True)
    approval_status = db.Column(db.String(20), default=ApprovalStatus.PENDING, index=True)
    approved_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    tg_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True) # Teacher Guardian
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    tg = db.relationship('User', foreign_keys=[tg_id])

    # ── Extended Profile Fields (from real enrollment data) ──────────────────
    dob             = db.Column(db.String(20))          # DD-MM-YYYY
    gender          = db.Column(db.String(10))          # M / F
    category        = db.Column(db.String(20))          # OPEN/OBC/SC/ST/NT2/NT3/VJA/SBC
    blood_group     = db.Column(db.String(10))
    aadhar_no       = db.Column(db.String(20))
    mother_name     = db.Column(db.String(120))
    address         = db.Column(db.String(300))
    city            = db.Column(db.String(80))
    district        = db.Column(db.String(80))
    state           = db.Column(db.String(80), default='Maharashtra')
    pincode         = db.Column(db.String(10))
    current_year    = db.Column(db.Integer, default=3)  # 3rd Year
    semester        = db.Column(db.Integer, default=5)  # Semester V
    batch           = db.Column(db.String(5), nullable=True)  # S1 | S2 | S3

    attendance     = db.relationship('Attendance', backref='student', lazy='dynamic')
    marks          = db.relationship('Marks', backref='student', lazy='dynamic')
    grievances     = db.relationship('Grievance', backref='student', lazy='dynamic')
    certificates   = db.relationship('Certificate', backref='student', lazy='dynamic')
    submissions    = db.relationship('AssignmentSubmission', backref='student', lazy='dynamic')
    practical_records = db.relationship('PracticalRecord', backref='student', lazy='dynamic')
    event_records     = db.relationship('EventRecord',     backref='student', lazy='dynamic')

    def attendance_percentage(self, subject_id=None):
        """Overall attendance = theory + events. Practicals are excluded."""
        from sqlalchemy import func, cast, Integer
        
        # ── Per-subject logic (only theory) ──
        if subject_id:
            res = db.session.query(
                func.count(Attendance.id),
                func.sum(cast(Attendance.status, Integer))
            ).filter(
                Attendance.student_id == self.id,
                Attendance.subject_id == subject_id
            ).first()
            total = res[0] or 0
            present = res[1] or 0
            return round((present / total) * 100, 2) if total > 0 else 0

        # ── Overall: theory + event attendance ──
        # Theory counts
        theory_res = db.session.query(
            func.count(Attendance.id),
            func.sum(cast(Attendance.status, Integer))
        ).filter(Attendance.student_id == self.id).first()
        theory_total = theory_res[0] or 0
        theory_present = theory_res[1] or 0

        # Event counts
        event_res = db.session.query(
            func.count(EventRecord.id),
            func.sum(cast(EventRecord.status, Integer))
        ).join(EventSession).filter(
            EventRecord.student_id == self.id,
            EventSession.class_id == self.class_id
        ).first()
        event_total = event_res[0] or 0
        event_present = event_res[1] or 0

        total = theory_total + event_total
        present = theory_present + event_present
        return round((present / total) * 100, 2) if total > 0 else 0

    def is_defaulter(self):
        return self.attendance_percentage() < 75

    def __repr__(self):
        return f'<Student {self.user.name}>'


class Teacher(db.Model):
    __tablename__ = 'teachers'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    teacher_type  = db.Column(db.String(30))   # subject / lab / TG
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), index=True)
    designation   = db.Column(db.String(100))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # Note: subjects are linked via Subject.teacher_id -> users.id
    # Access teacher's subjects via Subject.query.filter_by(teacher_id=teacher.user_id)


class Subject(db.Model):
    __tablename__ = 'subjects'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    code       = db.Column(db.String(20))
    class_id   = db.Column(db.Integer, db.ForeignKey('classes.id'), index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True)
    credits    = db.Column(db.Integer, default=3)
    is_elective = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    teacher_user = db.relationship('User', foreign_keys=[teacher_id])
    attendance   = db.relationship('Attendance', backref='subject', lazy='dynamic')
    marks        = db.relationship('Marks', backref='subject', lazy='dynamic')
    assignments  = db.relationship('Assignment', backref='subject', lazy='dynamic')
    timetable    = db.relationship('Timetable', backref='subject', lazy='dynamic')
    enrolled_students = db.relationship('Student', secondary=student_subjects, lazy='subquery',
        backref=db.backref('elective_subjects', lazy=True))

    def __repr__(self):
        return f'<Subject {self.name}>'

# ─────────────────────────────────────────────────────────────────────────────
# ACADEMIC MODELS
# ─────────────────────────────────────────────────────────────────────────────
class Attendance(db.Model):
    __tablename__ = 'attendance'
    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    date       = db.Column(db.Date, nullable=False)
    status     = db.Column(db.Boolean, default=False)   # True=Present
    marked_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint + targeted indexes for the most common query patterns:
    # 1. student_id + date   → "all attendance for student on date X"
    # 2. subject_id + date   → "mark attendance for subject on date X"
    # 3. subject_id + status → "count presents/absences per subject"
    __table_args__ = (
        db.UniqueConstraint('student_id', 'subject_id', 'date'),
        db.Index('ix_att_student_date',  'student_id', 'date'),
        db.Index('ix_att_subject_date',  'subject_id', 'date'),
        db.Index('ix_att_subject_status','subject_id', 'status'),
    )
    marker = db.relationship('User', foreign_keys=[marked_by])


class AbsenteeReason(db.Model):
    __tablename__ = 'absentee_reasons'
    id            = db.Column(db.Integer, primary_key=True)
    attendance_id = db.Column(db.Integer, db.ForeignKey('attendance.id'), nullable=False, unique=True)
    requested_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason_text   = db.Column(db.Text, nullable=True)
    status        = db.Column(db.String(20), default='REQUESTED') # REQUESTED, SUBMITTED
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attendance    = db.relationship('Attendance', backref=db.backref('absentee_reason', uselist=False))
    requester     = db.relationship('User', foreign_keys=[requested_by])


class Marks(db.Model):
    __tablename__ = 'marks'
    id          = db.Column(db.Integer, primary_key=True)
    student_id  = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    subject_id  = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    marks       = db.Column(db.Float, nullable=False)
    max_marks   = db.Column(db.Float, default=100)
    exam_type   = db.Column(db.String(30), default=ExamType.CT1)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    uploader = db.relationship('User', foreign_keys=[uploaded_by])

    # Prevent duplicate marks rows for the same student+subject+exam
    __table_args__ = (
        db.UniqueConstraint('student_id', 'subject_id', 'exam_type',
                            name='uq_marks_student_subject_exam'),
        db.Index('ix_marks_student_subject', 'student_id', 'subject_id'),
    )

    @property
    def percentage(self):
        if self.max_marks == 0:
            return 0
        return round((self.marks / self.max_marks) * 100, 2)

    @property
    def grade(self):
        p = self.percentage
        if p >= 90: return 'O'
        if p >= 80: return 'A+'
        if p >= 70: return 'A'
        if p >= 60: return 'B+'
        if p >= 50: return 'B'
        if p >= 40: return 'C'
        return 'F'


class Grievance(db.Model):
    __tablename__ = 'grievances'
    id          = db.Column(db.Integer, primary_key=True)
    student_id  = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    type        = db.Column(db.String(30), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status      = db.Column(db.String(20), default=ApprovalStatus.PENDING)
    priority    = db.Column(db.String(10), default='medium')  # low/medium/high/urgent
    attachment  = db.Column(db.String(255), nullable=True)    # uploaded filename
    deadline    = db.Column(db.DateTime, nullable=True)        # SLA deadline
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    comment     = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assignee = db.relationship('User', foreign_keys=[assigned_to])
    replies  = db.relationship('GrievanceReply', backref='grievance',
                               lazy='dynamic', order_by='GrievanceReply.created_at')


class GrievanceReply(db.Model):
    __tablename__ = 'grievance_replies'
    id           = db.Column(db.Integer, primary_key=True)
    grievance_id = db.Column(db.Integer, db.ForeignKey('grievances.id'), nullable=False)
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message      = db.Column(db.Text, nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    author = db.relationship('User', foreign_keys=[user_id])


class Certificate(db.Model):
    __tablename__ = 'certificates'
    id          = db.Column(db.Integer, primary_key=True)
    student_id  = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    type        = db.Column(db.String(30), nullable=False)
    reason      = db.Column(db.Text)
    status      = db.Column(db.String(20), default=ApprovalStatus.PENDING)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes       = db.Column(db.Text)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    approver = db.relationship('User', foreign_keys=[approved_by])


class Notice(db.Model):
    __tablename__ = 'notices'
    id             = db.Column(db.Integer, primary_key=True)
    title          = db.Column(db.String(200), nullable=False)
    content        = db.Column(db.Text, nullable=False)
    target_role    = db.Column(db.String(30))   # null = all
    target_class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    posted_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    is_urgent      = db.Column(db.Boolean, default=False)
    
    # Advanced Workflow fields
    status         = db.Column(db.String(30), default='APPROVED') # PENDING, APPROVED, REJECTED
    approved_by    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at    = db.Column(db.DateTime, nullable=True)
    is_deleted     = db.Column(db.Boolean, default=False)
    
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    poster       = db.relationship('User', foreign_keys=[posted_by])
    approver     = db.relationship('User', foreign_keys=[approved_by])
    target_class = db.relationship('Class', foreign_keys=[target_class_id])


class Assignment(db.Model):
    __tablename__ = 'assignments'
    id          = db.Column(db.Integer, primary_key=True)
    subject_id  = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    deadline    = db.Column(db.DateTime, nullable=False)
    max_marks   = db.Column(db.Float, default=10)
    created_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    file_path   = db.Column(db.String(300))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    creator     = db.relationship('User', foreign_keys=[created_by])
    submissions = db.relationship('AssignmentSubmission', backref='assignment', lazy='dynamic')


class LeaveApplication(db.Model):
    __tablename__ = 'leave_applications'
    id          = db.Column(db.Integer, primary_key=True)
    student_id  = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    type        = db.Column(db.String(30), nullable=False) # single_day, multi_day, specific_lectures
    start_date  = db.Column(db.Date, nullable=False)
    end_date    = db.Column(db.Date, nullable=False)
    specific_lectures = db.Column(db.String(300))
    reason      = db.Column(db.Text, nullable=False)
    
    status      = db.Column(db.String(30), default=LeaveStatus.PENDING_TG)
    
    tg_status      = db.Column(db.String(20), default=ApprovalStatus.PENDING)
    tg_approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    tg_comment     = db.Column(db.Text)
    
    ct_status      = db.Column(db.String(20), default=ApprovalStatus.PENDING)
    ct_approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    ct_comment     = db.Column(db.Text)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    student     = db.relationship('Student', foreign_keys=[student_id], backref='leave_applications')
    tg_approver = db.relationship('User', foreign_keys=[tg_approved_by])
    ct_approver = db.relationship('User', foreign_keys=[ct_approved_by])


class AssignmentSubmission(db.Model):
    __tablename__ = 'assignment_submissions'
    id            = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey('assignments.id'), nullable=False)
    student_id    = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    file_path     = db.Column(db.String(300))
    marks         = db.Column(db.Float)
    feedback      = db.Column(db.Text)
    submitted_at  = db.Column(db.DateTime, default=datetime.utcnow)
    is_late       = db.Column(db.Boolean, default=False)


class Timetable(db.Model):
    __tablename__ = 'timetable'
    id         = db.Column(db.Integer, primary_key=True)
    class_id   = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    day        = db.Column(db.String(10), nullable=False)   # Monday–Saturday
    start_time = db.Column(db.String(10), nullable=False)   # HH:MM
    end_time   = db.Column(db.String(10), nullable=False)
    entry_type = db.Column(db.String(20), default='theory') # theory | practical
    batch      = db.Column(db.String(10), nullable=True)    # S1 | S2 | S3 | None

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM MODELS
# ─────────────────────────────────────────────────────────────────────────────
class Notification(db.Model):
    __tablename__ = 'notifications'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    message    = db.Column(db.String(500), nullable=False)
    type       = db.Column(db.String(30), default='info')   # info/warning/success/danger
    link       = db.Column(db.String(200))
    is_read    = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Composite index for the most frequent query: unread count per user
    # SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=false
    __table_args__ = (
        db.Index('ix_notif_user_unread', 'user_id', 'is_read'),
    )


class Message(db.Model):
    __tablename__ = 'messages'
    id         = db.Column(db.Integer, primary_key=True)
    sender_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'))
    action     = db.Column(db.String(200), nullable=False)
    module     = db.Column(db.String(50))    # Notices, Admin, Certificates, etc.
    details    = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])


class OTPRequest(db.Model):
    __tablename__ = 'otp_requests'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    otp_hash   = db.Column(db.String(256), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])


class PushSubscription(db.Model):
    """Stores a user's browser Web Push subscription endpoint."""
    __tablename__ = 'push_subscriptions'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    endpoint   = db.Column(db.Text, nullable=False, unique=True)
    p256dh     = db.Column(db.Text, nullable=False)
    auth       = db.Column(db.Text, nullable=False)
    user_agent = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])


# ─────────────────────────────────────────────────────────────────────────────
# PRACTICAL SESSION MODELS  (batch-wise lab attendance — NOT in 75% calc)
# ─────────────────────────────────────────────────────────────────────────────
class PracticalSession(db.Model):
    """One lab session for a specific batch on a given date."""
    __tablename__ = 'practical_sessions'
    id         = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False, index=True)
    class_id   = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    batch      = db.Column(db.String(5), nullable=False)   # S1 | S2 | S3
    date       = db.Column(db.Date, nullable=False, index=True)
    title      = db.Column(db.String(200))                 # Experiment / practical name
    marked_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subject = db.relationship('Subject', foreign_keys=[subject_id])
    class_  = db.relationship('Class',   foreign_keys=[class_id])
    marker  = db.relationship('User',    foreign_keys=[marked_by])
    records = db.relationship('PracticalRecord', backref='session', lazy='dynamic',
                              cascade='all, delete-orphan')


class PracticalRecord(db.Model):
    """Attendance record for one student in one practical session."""
    __tablename__ = 'practical_records'
    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('practical_sessions.id'),
                           nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'),
                           nullable=False, index=True)
    status     = db.Column(db.Boolean, default=False)   # True = Present

    __table_args__ = (db.UniqueConstraint('session_id', 'student_id'),)


# ─────────────────────────────────────────────────────────────────────────────
# EVENT SESSION MODELS  (seminars, visits, cultural, etc. — counted in 75%)
# ─────────────────────────────────────────────────────────────────────────────
class EventType:
    SEMINAR          = 'seminar'
    WORKSHOP         = 'workshop'
    INDUSTRIAL_VISIT = 'industrial_visit'
    CULTURAL         = 'cultural'
    SPORTS           = 'sports'
    OTHER            = 'other'

    ALL = [SEMINAR, WORKSHOP, INDUSTRIAL_VISIT, CULTURAL, SPORTS, OTHER]
    LABELS = {
        SEMINAR:          'Seminar',
        WORKSHOP:         'Workshop',
        INDUSTRIAL_VISIT: 'Industrial Visit',
        CULTURAL:         'Cultural Event',
        SPORTS:           'Sports / Games',
        OTHER:            'Other Activity',
    }


class EventSession(db.Model):
    """A college event/activity session for a class. Counts toward overall attendance."""
    __tablename__ = 'event_sessions'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    event_type  = db.Column(db.String(30), nullable=False, default=EventType.OTHER)
    class_id    = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False, index=True)
    date        = db.Column(db.Date, nullable=False, index=True)
    description = db.Column(db.Text)
    marked_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    class_  = db.relationship('Class', foreign_keys=[class_id])
    marker  = db.relationship('User',  foreign_keys=[marked_by])
    records = db.relationship('EventRecord', backref='session', lazy='dynamic',
                              cascade='all, delete-orphan')


class EventRecord(db.Model):
    """Attendance record for one student in one event session."""
    __tablename__ = 'event_records'
    id         = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('event_sessions.id'),
                           nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'),
                           nullable=False, index=True)
    status     = db.Column(db.Boolean, default=False)   # True = Present

    __table_args__ = (db.UniqueConstraint('session_id', 'student_id'),)
