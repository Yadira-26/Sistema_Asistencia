"""Agregar campo modo a Attendance

Revision ID: add_modo_field
Revises: 9231431f7785
Create Date: 2025-08-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_modo_field'
down_revision = '9231431f7785'
branch_labels = None
depends_on = None


def upgrade():
    # Solo agregar la columna modo
    op.add_column('attendance', sa.Column('modo', sa.String(length=10), nullable=True))
    
    # Actualizar registros existentes para que tengan valor por defecto
    op.execute("UPDATE attendance SET modo = 'Temprano' WHERE modo IS NULL")


def downgrade():
    # Eliminar la columna modo
    op.drop_column('attendance', 'modo')
