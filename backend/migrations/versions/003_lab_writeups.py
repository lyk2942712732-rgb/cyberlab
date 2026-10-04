"""Persist editable reference solutions without changing lab/runtime data."""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"


def upgrade():
    op.add_column("lab_templates", sa.Column("writeup", sa.Text(), nullable=False, server_default=""))


def downgrade():
    op.drop_column("lab_templates", "writeup")
