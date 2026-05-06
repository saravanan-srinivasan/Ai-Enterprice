-- scripts/init_db.sql
-- Initial database setup for Enterprise AI Assistant
-- Extensions and baseline configuration

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable trigram search (for future full-text search features)
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Performance tuning for analytics workloads
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET work_mem = '32MB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET effective_cache_size = '512MB';

-- Create application schema
-- (Tables are created via SQLAlchemy's create_all on first startup)

-- Create indexes that SQLAlchemy doesn't know about
-- These are created after the ORM runs migrations

DO $$
BEGIN
    RAISE NOTICE 'Database initialization complete for enterprise_ai';
END $$;
