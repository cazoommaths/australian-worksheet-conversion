-- Migration 001: Worksheets Table
-- Core table for storing worksheet metadata and extraction results

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

-- Worksheets table: stores core worksheet information and Vision API extraction results
CREATE TABLE IF NOT EXISTS worksheets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Basic metadata
    file_name TEXT NOT NULL,
    file_path TEXT,
    dropbox_url TEXT,

    -- UK curriculum identifiers
    uk_year_level TEXT,
    uk_topic TEXT,
    uk_subtopic TEXT,

    -- Australian curriculum mapping (from Vision or manual)
    au_year_level TEXT,
    au_topic TEXT,
    au_subtopic TEXT,
    acara_strand TEXT, -- Number and Algebra | Measurement and Geometry | Statistics and Probability
    acara_content_codes TEXT[], -- Array of v9 content descriptor codes

    -- Extracted content (from Vision API)
    title TEXT,
    extraction_data JSONB, -- Full Vision API response
    skills_covered TEXT[],
    prerequisite_skills TEXT[],

    -- Content structure
    sections JSONB, -- Array of section objects with labels, types, question counts
    difficulty_progression TEXT, -- constant | easy_to_hard | mixed | scaffolded

    -- Diagrams and visual elements
    diagram_inventory JSONB, -- Count, types, descriptions
    has_diagrams BOOLEAN DEFAULT false,

    -- UK-specific elements that need localization
    uk_specific_elements JSONB, -- Currency, places, terms found

    -- Content flags
    has_word_problems BOOLEAN DEFAULT false,
    has_real_world_context BOOLEAN DEFAULT false,
    has_calculator_questions BOOLEAN DEFAULT false,
    has_extension_tasks BOOLEAN DEFAULT false,

    -- Processing status
    status TEXT DEFAULT 'pending', -- pending | processing | completed | error
    extraction_method TEXT, -- vision_api | pymupdf | manual
    error_log TEXT,

    -- Embeddings for semantic search
    embedding_title vector(1024), -- Text embedding for title
    embedding_content vector(1024), -- Embedding for full content/skills

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    extracted_at TIMESTAMPTZ,

    -- Metadata
    page_count INTEGER,
    file_size_bytes BIGINT,
    model_version TEXT -- Claude model used for extraction
);

-- Create indexes for common queries
CREATE INDEX idx_worksheets_uk_year ON worksheets(uk_year_level);
CREATE INDEX idx_worksheets_au_year ON worksheets(au_year_level);
CREATE INDEX idx_worksheets_uk_topic ON worksheets(uk_topic);
CREATE INDEX idx_worksheets_au_topic ON worksheets(au_topic);
CREATE INDEX idx_worksheets_strand ON worksheets(acara_strand);
CREATE INDEX idx_worksheets_status ON worksheets(status);
CREATE INDEX idx_worksheets_created_at ON worksheets(created_at DESC);

-- GIN index for JSONB columns (for fast queries on nested data)
CREATE INDEX idx_worksheets_extraction_data ON worksheets USING GIN(extraction_data);
CREATE INDEX idx_worksheets_sections ON worksheets USING GIN(sections);
CREATE INDEX idx_worksheets_acara_codes ON worksheets USING GIN(acara_content_codes);

-- Full-text search index
CREATE INDEX idx_worksheets_fts ON worksheets USING GIN(
    to_tsvector('english',
        COALESCE(title, '') || ' ' ||
        COALESCE(uk_topic, '') || ' ' ||
        COALESCE(uk_subtopic, '') || ' ' ||
        COALESCE(au_topic, '') || ' ' ||
        COALESCE(au_subtopic, '')
    )
);

-- Vector indexes for semantic search (using HNSW for fast approximate nearest neighbor)
CREATE INDEX idx_worksheets_embedding_title ON worksheets
    USING hnsw (embedding_title vector_cosine_ops);

CREATE INDEX idx_worksheets_embedding_content ON worksheets
    USING hnsw (embedding_content vector_cosine_ops);

-- Updated timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_worksheets_updated_at
    BEFORE UPDATE ON worksheets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- View for easy querying of worksheets with AU curriculum mapping
CREATE OR REPLACE VIEW worksheets_au_mapped AS
SELECT
    id,
    file_name,
    title,
    uk_year_level,
    au_year_level,
    uk_topic,
    au_topic,
    acara_strand,
    array_length(skills_covered, 1) as skill_count,
    has_diagrams,
    has_word_problems,
    difficulty_progression,
    status,
    extraction_method,
    created_at
FROM worksheets
WHERE status = 'completed' AND au_year_level IS NOT NULL;

-- View for worksheets pending AU curriculum mapping
CREATE OR REPLACE VIEW worksheets_pending_mapping AS
SELECT
    id,
    file_name,
    title,
    uk_year_level,
    uk_topic,
    uk_subtopic,
    extraction_data,
    status,
    created_at
FROM worksheets
WHERE status = 'completed' AND au_year_level IS NULL;

COMMENT ON TABLE worksheets IS 'Core worksheet metadata and extraction results from Vision API';
COMMENT ON COLUMN worksheets.extraction_data IS 'Full JSON response from Claude Vision API';
COMMENT ON COLUMN worksheets.embedding_title IS 'Vector embedding of worksheet title for semantic search';
COMMENT ON COLUMN worksheets.embedding_content IS 'Vector embedding combining skills, topics, and content for semantic search';
