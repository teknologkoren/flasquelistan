"""empty message

Revision ID: 2f6230539132
Revises: 
Create Date: 2019-09-15 22:18:32.972912

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f6230539132'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('group', sa.Column('on_startpage', sa.Boolean(), nullable=False, server_default='1'))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('group', 'on_startpage')
    # ### end Alembic commands ###
