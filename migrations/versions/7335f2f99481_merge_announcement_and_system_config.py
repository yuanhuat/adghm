"""merge announcement and system config

Revision ID: 7335f2f99481
Revises: add_announcement_table, add_system_config_table
Create Date: 2025-08-09 15:02:17.549769

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7335f2f99481'
down_revision = ('add_announcement_table', 'add_system_config_table')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
