"""phase 3: clip sharing and upload state

Adds the three columns the upload/share flow needs:
  share_token  — random public id for /c/<token>, unique, null until shared
  shared_at    — when it was first made public
  upload_error — why the last attempt failed, so the Pi can say something
                 better than "failed"

Revision ID: c41d7ae9b3f2
Revises: 8f8b2b7d50e2
Create Date: 2026-08-03 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c41d7ae9b3f2'
down_revision = '8f8b2b7d50e2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clips', schema=None) as batch_op:
        batch_op.add_column(sa.Column('upload_error', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('share_token', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('shared_at', sa.DateTime(timezone=True), nullable=True))
        # Unique but nullable: many clips share NULL, only real tokens collide.
        batch_op.create_unique_constraint('uq_clips_share_token', ['share_token'])


def downgrade():
    with op.batch_alter_table('clips', schema=None) as batch_op:
        batch_op.drop_constraint('uq_clips_share_token', type_='unique')
        batch_op.drop_column('shared_at')
        batch_op.drop_column('share_token')
        batch_op.drop_column('upload_error')
