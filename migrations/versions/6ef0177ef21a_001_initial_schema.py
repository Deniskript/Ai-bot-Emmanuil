"""001_initial_schema

Revision ID: 001
Create Date: 2025-01-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Таблица courses (если не существует)
    op.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            name TEXT,
            total INTEGER,
            current INTEGER DEFAULT 1,
            done INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_courses_user ON courses(user_id, created_at DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_courses_user")
    op.execute("DROP TABLE IF EXISTS courses")
