"""merge openlist and vip migrations

Revision ID: 16fff44585ef
Revises: 
Create Date: 2025-09-06 20:57:20.434139

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '16fff44585ef'
down_revision = ('add_openlist_config_table', 'add_vip_functionality')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
