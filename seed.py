"""
CSMSS College ERP -- Minimal Seeder
Creates only the Principal (Super Admin) account.
All other users (HODs, Teachers, Students) are added by the Principal via the admin panel.
Run once: python seed.py
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app import create_app
from app.extensions import db, bcrypt
from app.models import User, Roles, Status

app = create_app()

def hashed(pw):
    return bcrypt.generate_password_hash(pw).decode('utf-8')

def seed():
    with app.app_context():
        print("🗑️  Dropping existing tables...")
        db.drop_all()
        print("🏗️  Creating tables...")
        db.create_all()

        # ── Principal (Super Admin) ──────────────────────────────────────────
        print("👑 Creating Principal account...")
        principal = User(
            name          = "Dr. G. B. Dongre",
            email         = "principal@csmss.edu",
            phone         = "9999999999",
            password_hash = hashed("admin123"),
            role          = Roles.SUPER_ADMIN,
            status        = Status.ACTIVE
        )
        db.session.add(principal)
        db.session.commit()

if __name__ == '__main__':
    seed()
