"""Add missing FK indexes for perf-critical tables.

Revision ID: add_perf_indexes_001
Revises: add_progress_001
Create Date: 2026-06-04 22:00:00.000000

Why each index:
- ``documents.project_id``: every "list documents in project" query and
  every cascade lookup uses this column. PG does NOT auto-index FKs.
- ``projects.user_id``: dashboards / login flows scan projects by owner.
- ``document_chunks(document_id, chunk_index)``: chunk loader and analyser
  read chunks ordered by ``chunk_index`` for a single document.

We use ``CREATE INDEX IF NOT EXISTS`` so re-running on a partially-applied
DB is safe.
"""
from alembic import op


revision = "add_perf_indexes_001"
down_revision = "add_progress_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_documents_project_id "
        "ON documents (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_projects_user_id "
        "ON projects (user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id_chunk_index "
        "ON document_chunks (document_id, chunk_index)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_document_id_chunk_index")
    op.execute("DROP INDEX IF EXISTS idx_projects_user_id")
    op.execute("DROP INDEX IF EXISTS idx_documents_project_id")
