"""Remove deleted model tables

Revision ID: 20250812_220030
Revises: 70b932ff82d8
Create Date: 2025-08-12 22:00:30.279409

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250812_220030'
down_revision = '70b932ff82d8'
branch_labels = None
depends_on = None


def upgrade():
    """Drop tables for deleted models"""
    
    # List of tables to drop
    tables_to_drop = [
        'incidents',
        'credentials', 
        'vul_in_target',
        'collections',
        'collected_files'
    ]
    
    # Check if table exists before dropping
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()
    
    for table_name in tables_to_drop:
        if table_name in existing_tables:
            print(f"Dropping table: {table_name}")
            op.drop_table(table_name)
        else:
            print(f"Table {table_name} does not exist, skipping...")


def downgrade():
    """Recreate the dropped tables (basic structure only)"""
    
    # Note: This is a basic recreation - data will be lost
    # In production, you should backup data before running upgrade()
    
    # Recreate incidents table
    op.create_table('incidents',
        sa.Column('incident_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_type', sa.Enum('MALWARE', 'PHISHING', 'DATA_BREACH', 'UNAUTHORIZED_ACCESS', 'DENIAL_OF_SERVICE', 'OTHER', name='incidenttype'), nullable=False),
        sa.Column('target_device', sa.String(length=255), nullable=True),
        sa.Column('resolution_status', sa.Enum('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', name='resolutionstatus'), nullable=False),
        sa.Column('impact_summary', sa.Text(), nullable=True),
        sa.Column('related_email_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('incident_id')
    )
    
    # Recreate credentials table
    op.create_table('credentials',
        sa.Column('credential_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('privilege_level', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'ADMIN', 'ROOT', name='privilegelevel'), nullable=False),
        sa.Column('breach_date', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['server_id'], ['targets.server_id'], ),
        sa.PrimaryKeyConstraint('credential_id')
    )
    
    # Recreate vul_in_target table
    op.create_table('vul_in_target',
        sa.Column('id_vul_in_target', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('attack_vector', sa.String(length=255), nullable=False),
        sa.Column('detection_date', sa.DateTime(), nullable=False),
        sa.Column('resolution_status', sa.Enum('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED', name='resolutionstatus'), nullable=False),
        sa.Column('impact_summary', sa.Text(), nullable=True),
        sa.Column('related_email_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['incident_id'], ['incidents.incident_id'], ),
        sa.ForeignKeyConstraint(['server_id'], ['targets.server_id'], ),
        sa.PrimaryKeyConstraint('id_vul_in_target')
    )
    
    # Recreate collections table
    op.create_table('collections',
        sa.Column('collection_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('collected_at', sa.DateTime(), nullable=False),
        sa.Column('folder_archive_path', sa.Text(), nullable=True),
        sa.Column('db_size_mb', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['server_id'], ['targets.server_id'], ),
        sa.PrimaryKeyConstraint('collection_id')
    )
    
    # Recreate collected_files table
    op.create_table('collected_files',
        sa.Column('file_id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('collection_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_archive_path', sa.Text(), nullable=True),
        sa.Column('file_size_kb', sa.Float(), nullable=True),
        sa.Column('file_type', sa.Enum('DOCUMENT', 'IMAGE', 'VIDEO', 'AUDIO', 'ARCHIVE', 'CODE', 'DATABASE', 'OTHER', name='filetype'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.collection_id'], ),
        sa.PrimaryKeyConstraint('file_id')
    )
