-- Migration 005: Worksheet Extractions Table
-- Separates Vision API extraction results from catalog metadata

-- Create worksheet_extractions table
CREATE TABLE IF NOT EXISTS worksheet_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to catalog (via file_name for now, could add FK later)
    file_name TEXT NOT NULL UNIQUE,

    -- Basic metadata from Vision
    title TEXT,
    uk_year_level TEXT,
    au_year_level TEXT,
    uk_topic TEXT,
    uk_subtopic TEXT,
    acara_strand TEXT,

    -- Skills and prerequisites
    skills_covered TEXT[] DEFAULT '{}',
    prerequisite_skills TEXT[] DEFAULT '{}',

    -- Structured content
    sections JSONB,
    diagram_inventory JSONB,

    -- Worksheet characteristics
    total_questions INTEGER,
    estimated_time_minutes INTEGER,
    difficulty_level TEXT,
    difficulty_progression TEXT,

    -- Content flags
    has_diagrams BOOLEAN DEFAULT false,
    has_word_problems BOOLEAN DEFAULT false,
    has_worked_examples BOOLEAN DEFAULT false,
    has_real_world_context BOOLEAN DEFAULT false,
    has_multi_step_problems BOOLEAN DEFAULT false,
    has_equations BOOLEAN DEFAULT false,
    equation_types TEXT[] DEFAULT '{}',

    -- Localization needs
    uk_specific_elements JSONB,

    -- Additional content flags
    content_flags JSONB,

    -- Raw extraction data
    extraction_data JSONB,

    -- Extraction metadata
    extraction_method TEXT DEFAULT 'claude_vision',
    model_version TEXT,
    extraction_confidence FLOAT,
    extracted_at TIMESTAMPTZ DEFAULT NOW(),

    -- Vector embedding for semantic search
    embedding_content vector(1024),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_extractions_file_name ON worksheet_extractions(file_name);
CREATE INDEX idx_extractions_au_year_level ON worksheet_extractions(au_year_level);
CREATE INDEX idx_extractions_acara_strand ON worksheet_extractions(acara_strand);
CREATE INDEX idx_extractions_uk_year_level ON worksheet_extractions(uk_year_level);
CREATE INDEX idx_extractions_difficulty ON worksheet_extractions(difficulty_level);

-- GIN indexes for array searches
CREATE INDEX idx_extractions_skills ON worksheet_extractions USING GIN (skills_covered);
CREATE INDEX idx_extractions_equation_types ON worksheet_extractions USING GIN (equation_types);

-- JSONB indexes for structured content
CREATE INDEX idx_extractions_sections ON worksheet_extractions USING GIN (sections);
CREATE INDEX idx_extractions_diagrams ON worksheet_extractions USING GIN (diagram_inventory);
CREATE INDEX idx_extractions_uk_elements ON worksheet_extractions USING GIN (uk_specific_elements);

-- Vector index for semantic similarity search (HNSW for fast approximate search)
CREATE INDEX idx_extractions_embedding ON worksheet_extractions
USING hnsw (embedding_content vector_cosine_ops);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_worksheet_extractions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER worksheet_extractions_updated_at
    BEFORE UPDATE ON worksheet_extractions
    FOR EACH ROW
    EXECUTE FUNCTION update_worksheet_extractions_updated_at();

-- View to join catalog with extractions
CREATE OR REPLACE VIEW worksheets_with_extractions AS
SELECT
    w.id as worksheet_id,
    w.master_id,
    w.file_name,
    w.dropbox_url,
    w.is_free,
    w.resource_type,
    w.tags,
    w.status as catalog_status,
    e.id as extraction_id,
    e.title,
    e.uk_year_level,
    e.au_year_level,
    e.uk_topic,
    e.uk_subtopic,
    e.acara_strand,
    e.skills_covered,
    e.prerequisite_skills,
    e.total_questions,
    e.estimated_time_minutes,
    e.difficulty_level,
    e.difficulty_progression,
    e.has_diagrams,
    e.has_word_problems,
    e.has_worked_examples,
    e.has_real_world_context,
    e.sections,
    e.diagram_inventory,
    e.uk_specific_elements,
    e.extracted_at,
    e.embedding_content
FROM worksheets w
LEFT JOIN worksheet_extractions e ON e.file_name = w.file_name;

-- Function to search extractions with hybrid search
CREATE OR REPLACE FUNCTION search_extractions_hybrid(
    search_query TEXT DEFAULT NULL,
    year_level_filter TEXT DEFAULT NULL,
    strand_filter TEXT DEFAULT NULL,
    skill_filter TEXT DEFAULT NULL,
    difficulty_filter TEXT DEFAULT NULL,
    min_questions INTEGER DEFAULT NULL,
    max_questions INTEGER DEFAULT NULL,
    has_diagrams_filter BOOLEAN DEFAULT NULL,
    has_word_problems_filter BOOLEAN DEFAULT NULL,
    limit_results INTEGER DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    file_name TEXT,
    title TEXT,
    au_year_level TEXT,
    acara_strand TEXT,
    skills_covered TEXT[],
    total_questions INTEGER,
    difficulty_level TEXT,
    has_diagrams BOOLEAN,
    has_word_problems BOOLEAN,
    relevance_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.file_name,
        e.title,
        e.au_year_level,
        e.acara_strand,
        e.skills_covered,
        e.total_questions,
        e.difficulty_level,
        e.has_diagrams,
        e.has_word_problems,
        1.0::FLOAT as relevance_score
    FROM worksheet_extractions e
    WHERE
        (year_level_filter IS NULL OR e.au_year_level = year_level_filter)
        AND (strand_filter IS NULL OR e.acara_strand = strand_filter)
        AND (skill_filter IS NULL OR skill_filter = ANY(e.skills_covered))
        AND (difficulty_filter IS NULL OR e.difficulty_level = difficulty_filter)
        AND (min_questions IS NULL OR e.total_questions >= min_questions)
        AND (max_questions IS NULL OR e.total_questions <= max_questions)
        AND (has_diagrams_filter IS NULL OR e.has_diagrams = has_diagrams_filter)
        AND (has_word_problems_filter IS NULL OR e.has_word_problems = has_word_problems_filter)
        AND (
            search_query IS NULL
            OR e.title ILIKE '%' || search_query || '%'
            OR e.uk_topic ILIKE '%' || search_query || '%'
            OR EXISTS (
                SELECT 1 FROM unnest(e.skills_covered) skill
                WHERE skill ILIKE '%' || search_query || '%'
            )
        )
    ORDER BY
        CASE
            WHEN search_query IS NOT NULL AND e.title ILIKE '%' || search_query || '%' THEN 1
            WHEN search_query IS NOT NULL AND e.uk_topic ILIKE '%' || search_query || '%' THEN 2
            ELSE 3
        END,
        e.title
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- Function to find similar worksheets based on embedding
CREATE OR REPLACE FUNCTION find_similar_extractions(
    extraction_id_input UUID,
    limit_results INTEGER DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    file_name TEXT,
    title TEXT,
    au_year_level TEXT,
    acara_strand TEXT,
    skills_covered TEXT[],
    similarity_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        e.id,
        e.file_name,
        e.title,
        e.au_year_level,
        e.acara_strand,
        e.skills_covered,
        1 - (e.embedding_content <=> ref.embedding_content) as similarity_score
    FROM worksheet_extractions e
    CROSS JOIN (
        SELECT embedding_content
        FROM worksheet_extractions
        WHERE id = extraction_id_input
    ) ref
    WHERE e.id != extraction_id_input
    AND e.embedding_content IS NOT NULL
    ORDER BY e.embedding_content <=> ref.embedding_content
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- Statistics view
CREATE OR REPLACE VIEW extraction_statistics AS
SELECT
    COUNT(*) as total_extracted,
    COUNT(DISTINCT au_year_level) as year_levels_covered,
    COUNT(DISTINCT acara_strand) as strands_covered,
    AVG(total_questions) as avg_questions,
    AVG(estimated_time_minutes) as avg_time_minutes,
    COUNT(*) FILTER (WHERE has_diagrams) as with_diagrams,
    COUNT(*) FILTER (WHERE has_word_problems) as with_word_problems,
    COUNT(*) FILTER (WHERE has_worked_examples) as with_examples,
    COUNT(*) FILTER (WHERE embedding_content IS NOT NULL) as with_embeddings,
    MIN(extracted_at) as first_extraction,
    MAX(extracted_at) as last_extraction
FROM worksheet_extractions;

COMMENT ON TABLE worksheet_extractions IS 'Vision API extraction results - separate from catalog metadata';
COMMENT ON VIEW worksheets_with_extractions IS 'Combined view of catalog metadata + extraction results';
COMMENT ON FUNCTION search_extractions_hybrid IS 'Hybrid search across extracted worksheet content';
COMMENT ON FUNCTION find_similar_extractions IS 'Find similar worksheets using vector similarity';
