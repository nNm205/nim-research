-- Initial Postgres setup for the NIM Research stack.
--
-- Runs once on first container start (Postgres only executes scripts under
-- /docker-entrypoint-initdb.d if the data directory is empty). On subsequent
-- starts this is a no-op.
--
-- We need:
--   - vector  : pgvector for chunk embeddings (semantic search)
--   - pg_trgm : trigram GIN indexes for the knowledge-base fuzzy search
--   - btree_gin: composite GIN indexes used by some performance migrations

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
