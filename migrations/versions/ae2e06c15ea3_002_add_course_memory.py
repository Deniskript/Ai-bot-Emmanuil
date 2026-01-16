"""002_add_course_memory

Revision ID: 002
Create Date: 2025-01-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS course_memory (
            id SERIAL PRIMARY KEY,
            course_id INTEGER REFERENCES courses(id) ON DELETE CASCADE,
            user_id BIGINT,
            completed_topics JSONB DEFAULT '[]',
            problem_zones JSONB DEFAULT '[]',
            student_name TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_course_memory_course_id UNIQUE (course_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_course_memory_course_id ON course_memory(course_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_course_memory_user_id ON course_memory(user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_course_memory_user_id")
    op.execute("DROP INDEX IF EXISTS idx_course_memory_course_id")
    op.execute("DROP TABLE IF EXISTS course_memory")
