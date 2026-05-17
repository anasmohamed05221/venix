"""add payment_status and stripe_checkout_session_id to orders

Revision ID: d6b804a3647c
Revises: e65f88758d24
Create Date: 2026-04-22 00:03:45.459347

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6b804a3647c'
down_revision: Union[str, Sequence[str], None] = 'e65f88758d24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'stripe'")

    payment_status_enum = sa.Enum('unpaid', 'paid', 'failed', 'refunded', 'expired', name='payment_status')
    payment_status_enum.create(op.get_bind())

    op.add_column('orders', sa.Column('payment_status',
        sa.Enum('unpaid', 'paid', 'failed', 'refunded', 'expired', name='payment_status', create_type=False),
        nullable=False))
    op.add_column('orders', sa.Column('stripe_checkout_session_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders', 'stripe_checkout_session_id')
    op.drop_column('orders', 'payment_status')
    op.execute("DROP TYPE IF EXISTS payment_status")
