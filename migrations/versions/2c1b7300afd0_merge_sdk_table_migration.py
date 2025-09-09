"""merge sdk table migration

Revision ID: 2c1b7300afd0
Revises: 12218412b1c4, add_sdk_table
Create Date: 2025-09-09 20:04:15.670763

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2c1b7300afd0'
down_revision = ('12218412b1c4', 'add_sdk_table')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
