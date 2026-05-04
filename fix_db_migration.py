"""
fix_db_migration.py
-------------------
Emergency fix for broken alembic_version table on production.

The production database has an alembic_version state that Alembic cannot
resolve (likely due to a multi-branch migration chain getting out of sync).
This script directly patches the alembic_version table via raw SQL so that
`flask db upgrade` can run cleanly afterwards.

Usage (in Render build command):
  pip install -r requirements.txt && python fix_db_migration.py && flask db upgrade
"""

import os
import sys

# ── The revision that represents the current merged head ──────────────────────
TARGET_REVISION = 'bba8d69cd7a5'

def get_db_url():
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        print("ERROR: DATABASE_URL environment variable not set.")
        sys.exit(1)
    # SQLAlchemy 1.4+ requires postgresql:// not postgres://
    return url.replace('postgres://', 'postgresql://', 1)


def fix_alembic_version():
    try:
        import sqlalchemy as sa
    except ImportError:
        print("ERROR: sqlalchemy not installed.")
        sys.exit(1)

    url = get_db_url()
    engine = sa.create_engine(url)

    with engine.connect() as conn:
        # Check if alembic_version table exists
        inspector = sa.inspect(engine)
        if 'alembic_version' not in inspector.get_table_names():
            print("alembic_version table does not exist yet — skipping stamp fix.")
            return

        # Read current stamps
        result = conn.execute(sa.text("SELECT version_num FROM alembic_version"))
        current_stamps = [row[0] for row in result.fetchall()]
        print(f"Current alembic_version stamps: {current_stamps}")

        if current_stamps == [TARGET_REVISION]:
            print(f"DB already stamped to {TARGET_REVISION} — no fix needed.")
            return

        # Wipe all existing stamps and set the correct single head
        conn.execute(sa.text("DELETE FROM alembic_version"))
        conn.execute(
            sa.text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
            {"rev": TARGET_REVISION}
        )
        conn.commit()
        print(f"✅ alembic_version fixed: cleared {current_stamps} → stamped to {TARGET_REVISION}")


if __name__ == '__main__':
    fix_alembic_version()
