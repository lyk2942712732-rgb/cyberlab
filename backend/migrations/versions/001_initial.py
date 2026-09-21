"""Initial CyberLab schema, including the finished-image upload specification.

Schema is frozen here; importing live model metadata in migrations would make
future upgrades depend on the current application version.
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None


def pk():
    return sa.Column("id", sa.String(36), primary_key=True)


def string(name, length=200, nullable=False):
    return sa.Column(name, sa.String(length), nullable=nullable)


def timestamp(name, nullable=False):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def fk(name, target, ondelete=None, nullable=False):
    return sa.Column(name, sa.String(36), sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def upgrade():
    op.create_table("users", pk(), string("username", 64), string("password_hash", 255), string("real_name", 100), string("student_number", 64, True), string("role", 16), timestamp("created_at"), timestamp("updated_at"), sa.UniqueConstraint("username"), sa.UniqueConstraint("student_number"), sa.CheckConstraint("role IN ('STUDENT','ADMIN')"))
    op.create_table("courses", pk(), string("name"), sa.Column("description", sa.Text(), nullable=False), string("status", 20), timestamp("created_at"))
    op.create_table("chapters", pk(), fk("course_id", "courses.id", "CASCADE"), string("title"), sa.Column("sort_order", sa.Integer(), nullable=False))
    op.create_table("target_images", pk(), string("display_name"), string("repository", 255), string("tag", 100), string("image_id", 100, True), string("repo_digest", 300, True), sa.Column("size_bytes", sa.BigInteger(), nullable=False), string("original_filename", 255), sa.Column("description", sa.Text(), nullable=False), string("status", 20), sa.Column("error_message", sa.Text()), sa.Column("upload_path", sa.Text()), timestamp("created_at"), timestamp("updated_at"), sa.UniqueConstraint("image_id"))
    op.create_table("lab_templates", pk(), string("name"), sa.Column("description", sa.Text(), nullable=False), sa.Column("objective", sa.Text(), nullable=False), sa.Column("steps", sa.Text(), nullable=False), string("category", 64), string("difficulty", 20), fk("target_image_id", "target_images.id"), sa.Column("target_port", sa.Integer(), nullable=False), sa.Column("duration_minutes", sa.Integer(), nullable=False), sa.Column("cpu_limit", sa.Float(), nullable=False), sa.Column("memory_limit", sa.Integer(), nullable=False), string("flag", 512), string("status", 20), timestamp("created_at"), timestamp("updated_at"))
    op.create_table("lessons", pk(), fk("chapter_id", "chapters.id", "CASCADE"), string("title"), sa.Column("content", sa.Text(), nullable=False), sa.Column("sort_order", sa.Integer(), nullable=False), fk("related_lab_id", "lab_templates.id", "SET NULL", True), string("status", 20))
    op.create_table("lab_sessions", pk(), fk("user_id", "users.id"), fk("lab_template_id", "lab_templates.id"), string("status", 20), string("network_id", 100, True), timestamp("started_at"), timestamp("expires_at"), timestamp("finished_at", True), sa.Column("error", sa.Text()), sa.Column("generation", sa.Integer(), nullable=False))
    op.create_table("lab_instances", pk(), fk("session_id", "lab_sessions.id", "CASCADE"), string("instance_type", 16), string("runtime_id", 100), string("container_name", 100), string("ip_address", 64), string("image", 255), string("status", 20), timestamp("created_at"), sa.UniqueConstraint("runtime_id"))
    op.create_table("submissions", pk(), fk("user_id", "users.id"), fk("session_id", "lab_sessions.id"), fk("lab_template_id", "lab_templates.id"), string("submitted_flag", 512), sa.Column("correct", sa.Boolean(), nullable=False), sa.Column("score", sa.Integer(), nullable=False), timestamp("created_at"))
    op.create_table("learning_progress", pk(), fk("user_id", "users.id"), fk("lesson_id", "lessons.id", "CASCADE"), sa.Column("completed", sa.Boolean(), nullable=False), timestamp("completed_at"), sa.UniqueConstraint("user_id", "lesson_id"))
    indexes = {
        "chapters": ["course_id"], "lessons": ["chapter_id"], "target_images": ["status"],
        "lab_templates": ["target_image_id", "status"], "lab_sessions": ["user_id", "lab_template_id", "status", "expires_at"],
        "lab_instances": ["session_id"], "submissions": ["user_id", "session_id", "lab_template_id"], "learning_progress": ["user_id", "lesson_id"],
    }
    for table, columns in indexes.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
    active = sa.text("status IN ('CREATING','STARTING','READY','RESETTING','STOPPING','FINISHED')")
    op.create_index("uq_one_active_session_per_user", "lab_sessions", ["user_id"], unique=True, postgresql_where=active, sqlite_where=active)


def downgrade():
    for table in ("learning_progress", "submissions", "lab_instances", "lab_sessions", "lessons", "lab_templates", "target_images", "chapters", "courses", "users"):
        op.drop_table(table)
