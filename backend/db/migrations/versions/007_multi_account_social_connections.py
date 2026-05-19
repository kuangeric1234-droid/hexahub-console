"""multi-account social connections

Revision ID: 007
Revises: 006
Create Date: 2026-05-19 00:00:00.000000

Changes:
- Add account_label column (display name for each connection)
- Add user_access_token column (for ads API, separate from page token)
- Drop unique constraint on provider alone
- Add unique constraint on (provider, page_id) so each page can be
  connected once but multiple pages/providers are allowed
"""
from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: str = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns
    op.add_column("social_connections",
        sa.Column("account_label", sa.String(255), nullable=True))
    op.add_column("social_connections",
        sa.Column("user_access_token", sa.Text, nullable=True))

    # Drop the old unique constraint on provider alone
    op.drop_constraint("social_connections_provider_key", "social_connections", type_="unique")

    # Add new unique constraint on (provider, page_id)
    op.create_unique_constraint(
        "uq_social_connections_provider_page",
        "social_connections",
        ["provider", "page_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_social_connections_provider_page", "social_connections", type_="unique")
    op.create_unique_constraint("social_connections_provider_key", "social_connections", ["provider"])
    op.drop_column("social_connections", "user_access_token")
    op.drop_column("social_connections", "account_label")
