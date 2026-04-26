"""
CSMSS College ERP -- Database Seeder
Run once: python seed.py

Reads ALL 74 real student records directly from the Excel data JSON
(student_data_raw.json generated from the official enrollment sheet).
"""
import sys, io, json, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.extensions import db, bcrypt
from app.models import (
    User, Department, Class, Student, Teacher, Subject,
    Attendance, Marks, Grievance, Certificate, Notice,
    Assignment, Timetable, Notification,
    Roles, Status, ApprovalStatus, ExamType, GrievanceType, CertificateType
)
from datetime import date, timedelta, datetime
import random

app = create_app()

# ── Staff Accounts ────────────────────────────────────────────────────────────
STAFF_ACCOUNTS = [
    ("Dr. S. R. Patil",      "principal@csmss.edu",    "admin123",   Roles.SUPER_ADMIN,   "9876543210"),
    ("Prof. A. D. Kulkarni", "hod@csmss.edu",          "admin123",   Roles.HOD,           "9876543211"),
    ("Prof. M. K. Jadhav",   "classteacher@csmss.edu", "admin123",   Roles.CLASS_TEACHER, "9876543212"),
    ("Prof. R. S. More",     "teacher@csmss.edu",      "admin123",   Roles.TEACHER,       "9876543213"),
    ("Prof. P. N. Shinde",   "teacher2@csmss.edu",     "admin123",   Roles.TEACHER,       "9876543214"),
]

def hashed(pw):
    return bcrypt.generate_password_hash(pw).decode('utf-8')

def title_case(s):
    return ' '.join(w.capitalize() for w in str(s).split()) if s else ''

def load_students_from_json():
    """Load exact student data from the JSON generated from the Excel file."""
    json_path = os.path.join(os.path.dirname(__file__), 'student_data_raw.json')
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    headers = data['headers']
    rows    = data['rows']

    def idx(col):
        return headers.index(col)

    students = []
    for row in rows:
        prn      = str(row[idx('PRN')]                      or '').strip()
        name     = str(row[idx('Students Full Name')]        or '').strip()
        gender   = str(row[idx('Gender')]                   or '').strip()
        gender_c = 'M' if gender.lower().startswith('m') else 'F'
        dob      = str(row[idx('DOB')]                      or '').strip()
        category = str(row[idx('Category')]                 or '').strip()
        mobile   = str(row[idx('Mobile No')]                or '').strip()
        email    = str(row[idx('Email-Id')]                 or '').strip().lower()
        blood    = str(row[idx('Blood Group')]              or '').strip()
        aadhar   = str(row[idx('Aadhar Number')]            or '').strip()
        city     = title_case(str(row[idx('Student_City/Village')] or '').strip())
        district = str(row[idx('Student District')]         or '').strip().title()
        state    = str(row[idx('Student State')]            or '').strip().title()
        pincode  = str(row[idx('Student Location Pincode')] or '').strip()

        if not prn or not name or not email:
            continue

        students.append({
            'prn': prn, 'name': name, 'gender': gender_c,
            'dob': dob, 'category': category, 'mobile': mobile,
            'email': email, 'blood': blood, 'aadhar': aadhar,
            'city': city, 'district': district, 'state': state, 'pincode': pincode,
        })
    return students


def seed():
    with app.app_context():
        print("🗑️  Dropping existing tables...")
        db.drop_all()
        print("🏗️  Creating tables...")
        db.create_all()

        # ── Staff Users ──────────────────────────────────────────────────────
        print("👤 Creating staff accounts...")
        users = {}
        for name, email, pw, role, phone in STAFF_ACCOUNTS:
            user = User(name=name, email=email, phone=phone,
                        password_hash=hashed(pw), role=role, status=Status.ACTIVE)
            db.session.add(user)
            db.session.flush()
            users[email] = user

        # ── Departments ──────────────────────────────────────────────────────
        print("🏛️  Creating departments...")
        hod_user = users["hod@csmss.edu"]
        ece_dept  = Department(name="Electronics & Computer Engineering",
                               code="ECE", hod_id=hod_user.id)
        cse_dept  = Department(name="Computer Engineering",   code="CSE")
        mech_dept = Department(name="Mechanical Engineering", code="MECH")
        db.session.add_all([ece_dept, cse_dept, mech_dept])
        db.session.flush()

        # ── Teacher Profiles ─────────────────────────────────────────────────
        print("👨‍🏫 Creating teacher profiles...")
        ct_user = users["classteacher@csmss.edu"]
        for email in ["hod@csmss.edu", "classteacher@csmss.edu",
                      "teacher@csmss.edu", "teacher2@csmss.edu"]:
            u = users[email]
            t = Teacher(user_id=u.id, department_id=ece_dept.id,
                        teacher_type='subject', designation='Assistant Professor')
            db.session.add(t)
        db.session.flush()

        # ── Classes ──────────────────────────────────────────────────────────
        print("🏫 Creating classes...")
        te_ece = Class(name="TE ECE", year=3, section="A",
                       department_id=ece_dept.id, class_teacher_id=ct_user.id)
        se_ece = Class(name="SE ECE", year=2, section="A", department_id=ece_dept.id)
        be_ece = Class(name="BE ECE", year=4, section="A", department_id=ece_dept.id)
        se_cse = Class(name="SE CSE", year=2, section="A", department_id=cse_dept.id)
        db.session.add_all([te_ece, se_ece, be_ece, se_cse])
        db.session.flush()

        # ── Subjects (ECE Sem V) ─────────────────────────────────────────────
        print("📚 Creating subjects (ECE Sem V)...")
        teacher_u  = users["teacher@csmss.edu"]
        teacher2_u = users["teacher2@csmss.edu"]
        subjects_data = [
            ("Digital Signal Processing",          "DSP",   te_ece.id, teacher_u.id,  4),
            ("Microcontroller & Embedded Systems", "MES",   te_ece.id, teacher_u.id,  4),
            ("Control Systems",                    "CS",    te_ece.id, teacher2_u.id, 3),
            ("VLSI Design",                        "VLSI",  te_ece.id, teacher2_u.id, 3),
            ("Communication Engineering",          "CE",    te_ece.id, teacher_u.id,  4),
            ("Engineering Mathematics IV",         "EM4",   te_ece.id, teacher2_u.id, 3),
        ]
        subjects = []
        for name, code, cls_id, t_id, credits in subjects_data:
            sub = Subject(name=name, code=code, class_id=cls_id,
                          teacher_id=t_id, credits=credits)
            db.session.add(sub)
            db.session.flush()
            subjects.append(sub)

        # ── Load Real Students from JSON ─────────────────────────────────────
        print("📂 Loading student data from enrollment sheet...")
        student_data = load_students_from_json()
        print(f"   Found {len(student_data)} students in enrollment data.")

        print(f"🧑‍🎓 Creating {len(student_data)} real student accounts...")
        student_objs = []
        roll_counter = 1

        for i, s in enumerate(student_data):
            # Default password = PRN@CSMSS
            default_pw = f"{s['prn']}@CSMSS"
            tc_name = title_case(s['name'])

            user = User(
                name=tc_name,
                email=s['email'],
                phone=s['mobile'],
                password_hash=hashed(default_pw),
                role=Roles.STUDENT,
                status=Status.ACTIVE
            )
            db.session.add(user)
            db.session.flush()

            # Assign TG: half to teacher_u, half to teacher2_u
            assigned_tg_id = teacher_u.id if i % 2 == 0 else teacher2_u.id

            student = Student(
                user_id=user.id,
                class_id=te_ece.id,
                prn=s['prn'],
                roll_no=str(roll_counter).zfill(2),
                approval_status=ApprovalStatus.APPROVED,
                approved_by=ct_user.id,
                tg_id=assigned_tg_id,
                # Extended profile from Excel sheet
                dob=s['dob'],
                gender=s['gender'],
                category=s['category'],
                blood_group=s['blood'] or None,
                aadhar_no=s['aadhar'] or None,
                city=s['city'] or None,
                district=s['district'] or None,
                state=s['state'] or 'Maharashtra',
                pincode=s['pincode'] or None,
                current_year=3,
                semester=5,
            )
            db.session.add(student)
            db.session.flush()
            student_objs.append(student)
            roll_counter += 1

        print(f"   ✅ {len(student_objs)} students created successfully.")

        # ── Attendance (demo for first 10 students) ──────────────────────────
        print("📅 Creating sample attendance records...")
        today = date.today()
        demo_students = student_objs[:10]
        att_rates = [0.82, 0.70, 0.91, 0.60, 0.88, 0.76, 0.93, 0.65, 0.80, 0.72]
        for i, student in enumerate(demo_students):
            rate = att_rates[i]
            for sub in subjects:
                for days_ago in range(30, 0, -1):
                    att_date = today - timedelta(days=days_ago)
                    if att_date.weekday() >= 6:
                        continue
                    att = Attendance(
                        student_id=student.id, subject_id=sub.id,
                        date=att_date, status=(random.random() < rate),
                        marked_by=teacher_u.id
                    )
                    db.session.add(att)

        # ── Marks (demo for first 10 students) ───────────────────────────────
        print("📊 Creating sample marks...")
        for student in demo_students:
            for sub in subjects:
                m_int = Marks(student_id=student.id, subject_id=sub.id,
                              marks=random.randint(55, 95), max_marks=100,
                              exam_type=ExamType.INTERNAL, uploaded_by=teacher_u.id)
                m_prc = Marks(student_id=student.id, subject_id=sub.id,
                              marks=random.randint(30, 50), max_marks=50,
                              exam_type=ExamType.PRACTICAL, uploaded_by=teacher_u.id)
                db.session.add_all([m_int, m_prc])

        # ── Grievances ────────────────────────────────────────────────────────
        print("⚠️  Creating sample grievances...")
        grievances_data = [
            (student_objs[0], GrievanceType.ATTENDANCE,
             "My attendance was marked absent on 15th April but I was present.", "pending"),
            (student_objs[1], GrievanceType.MARKS,
             "I scored 38 in DSP internal but got 28 in the system. Please recheck.", "approved"),
            (student_objs[2], GrievanceType.FACILITY,
             "The ECE lab projector is not working since last week.", "pending"),
        ]
        for student, gtype, desc, status in grievances_data:
            g = Grievance(student_id=student.id, type=gtype, description=desc,
                          status=status,
                          assigned_to=ct_user.id if status != 'pending' else None,
                          comment="Will be resolved soon." if status == 'approved' else None)
            db.session.add(g)

        # ── Certificates ──────────────────────────────────────────────────────
        print("📜 Creating certificate requests...")
        db.session.add(Certificate(
            student_id=student_objs[0].id, type=CertificateType.BONAFIDE,
            reason="Required for bank account opening", status=ApprovalStatus.PENDING))
        db.session.add(Certificate(
            student_id=student_objs[1].id, type=CertificateType.CHARACTER,
            reason="For scholarship application",
            status=ApprovalStatus.APPROVED, approved_by=hod_user.id))

        # ── Notices ───────────────────────────────────────────────────────────
        print("📢 Creating notices...")
        principal_u = users["principal@csmss.edu"]
        for title, content, target, urgent in [
            ("🗓️ Internal Exam Schedule – Sem V",
             "Internal examinations for TE ECE batch will be held from 28th April to 3rd May 2025. All students must carry their ID cards.",
             None, True),
            ("📚 Syllabus Update – DSP",
             "Unit 5 topics (FIR/IIR filters) will now be covered before Unit 4. Please update your notes accordingly.",
             "STUDENT", False),
            ("🏖️ Holiday Notice",
             "The college will remain closed on 1st May (Maharashtra Day). Classes resume on 2nd May.",
             None, False),
            ("📋 Assignment Reminder",
             "All pending assignments must be submitted by this Friday. Late submissions will not be accepted.",
             "STUDENT", False),
            ("👨‍🏫 Faculty Meeting",
             "All faculty members are requested to attend the department meeting on Thursday at 4 PM in ECE seminar hall.",
             "TEACHER", False),
        ]:
            db.session.add(Notice(title=title, content=content, target_role=target,
                                  posted_by=principal_u.id, is_urgent=urgent))

        # ── Assignments ───────────────────────────────────────────────────────
        print("📝 Creating assignments...")
        db.session.add(Assignment(
            subject_id=subjects[0].id, title="DSP: Implement FIR Filter",
            description="Design and implement a low-pass FIR filter using windowing method in MATLAB. Submit .m file with plots.",
            deadline=datetime.now() + timedelta(days=7),
            max_marks=10, created_by=teacher_u.id))
        db.session.add(Assignment(
            subject_id=subjects[1].id, title="MES: Traffic Light Controller",
            description="Program a traffic light controller using 8051 microcontroller. Submit hex file and circuit diagram.",
            deadline=datetime.now() + timedelta(days=3),
            max_marks=10, created_by=teacher_u.id))

        # ── Timetable ─────────────────────────────────────────────────────────
        print("📅 Creating timetable...")
        for cls_id, sub_id, day, st, et in [
            (te_ece.id, subjects[0].id, "Monday",    "09:00", "10:00"),
            (te_ece.id, subjects[1].id, "Monday",    "10:00", "11:00"),
            (te_ece.id, subjects[2].id, "Monday",    "11:00", "12:00"),
            (te_ece.id, subjects[0].id, "Tuesday",   "09:00", "10:00"),
            (te_ece.id, subjects[3].id, "Tuesday",   "10:00", "11:00"),
            (te_ece.id, subjects[4].id, "Tuesday",   "11:00", "12:00"),
            (te_ece.id, subjects[1].id, "Wednesday", "09:00", "10:00"),
            (te_ece.id, subjects[2].id, "Wednesday", "10:00", "11:00"),
            (te_ece.id, subjects[3].id, "Thursday",  "09:00", "10:00"),
            (te_ece.id, subjects[4].id, "Thursday",  "10:00", "11:00"),
            (te_ece.id, subjects[5].id, "Thursday",  "11:00", "12:00"),
            (te_ece.id, subjects[0].id, "Friday",    "09:00", "10:00"),
            (te_ece.id, subjects[5].id, "Friday",    "10:00", "11:00"),
        ]:
            db.session.add(Timetable(class_id=cls_id, subject_id=sub_id,
                                     day=day, start_time=st, end_time=et))

        # ── Notifications ─────────────────────────────────────────────────────
        print("🔔 Creating welcome notifications...")
        for student in student_objs[:20]:
            db.session.add(Notification(
                user_id=student.user_id,
                message="🎉 Welcome to CSMSS ERP! Please update your profile to complete your setup.",
                type='success'))
            db.session.add(Notification(
                user_id=student.user_id,
                message="📢 New notice: Internal Exam Schedule – Sem V", type='warning'))

        db.session.commit()

        # ── Summary ───────────────────────────────────────────────────────────
        print("\n" + "=" * 65)
        print("✅  DATABASE SEEDED SUCCESSFULLY!")
        print("=" * 65)
        print(f"\n🎓 Total Students Imported : {len(student_objs)}")
        print(f"📘 Department              : Electronics & Computer Engg.")
        print(f"🏫 Class                   : TE ECE – Year 3, Semester V")
        print(f"\n🔑 DEFAULT STUDENT LOGIN:")
        print(f"   Email    : <email from enrollment sheet>")
        print(f"   Password : <PRN>@CSMSS")
        print(f"   Example  : PRN 23025331844046 → Password: 23025331844046@CSMSS")
        print(f"   Example  : Harshad Dhuppe     → Email: dhuppeh@gmail.com")
        print("\n📋 STAFF ACCOUNTS:")
        print("-" * 65)
        print(f"{'Role':<20} {'Email':<35} {'Password'}")
        print("-" * 65)
        for name, email, pw, role, _ in STAFF_ACCOUNTS:
            print(f"{role:<20} {email:<35} {pw}")
        print("-" * 65)
        print("\n🌐 Run: python run.py  →  http://localhost:5001\n")


if __name__ == '__main__':
    seed()
