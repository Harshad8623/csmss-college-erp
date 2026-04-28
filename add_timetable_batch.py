from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE timetable ADD COLUMN entry_type VARCHAR(20) DEFAULT 'theory'"))
            conn.commit()
            print("OK: entry_type added")
        except Exception as e:
            print("entry_type:", e)
        try:
            conn.execute(text("ALTER TABLE timetable ADD COLUMN batch VARCHAR(10)"))
            conn.commit()
            print("OK: batch added")
        except Exception as e:
            print("batch:", e)
