"""Accept cancellation without waiting for the provisioning transaction."""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"


def upgrade():
    # No FK: checking it would acquire a lock on the busy session row.
    op.create_table(
        "session_stop_requests",
        sa.Column("session_id", sa.String(36), primary_key=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("session_stop_requests")
