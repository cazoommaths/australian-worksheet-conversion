-- Migration 004: Hybrid Search Functions
-- Combines structured filters, full-text search, and semantic vector search

-- Function: Hybrid search for worksheets
-- Combines keyword search (FTS), semantic search (vectors), and structured filters
CREATE OR REPLACE FUNCTION search_worksheets_hybrid(
    search_query TEXT DEFAULT NULL,
    query_embedding vector(1024) DEFAULT NULL,
    year_level_filter TEXT DEFAULT NULL,
    strand_filter TEXT DEFAULT NULL,
    topic_filter TEXT DEFAULT NULL,
    has_diagrams_filter BOOLEAN DEFAULT NULL,
    has_word_problems_filter BOOLEAN DEFAULT NULL,
    difficulty_filter TEXT DEFAULT NULL,
    semantic_weight DECIMAL DEFAULT 0.3,
    keyword_weight DECIMAL DEFAULT 0.3,
    limit_results INTEGER DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    file_name TEXT,
    title TEXT,
    au_year_level TEXT,
    au_topic TEXT,
    au_subtopic TEXT,
    acara_strand TEXT,
    skill_count INTEGER,
    has_diagrams BOOLEAN,
    has_word_problems BOOLEAN,
    difficulty_progression TEXT,
    relevance_score DECIMAL,
    semantic_similarity DECIMAL,
    keyword_rank DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    WITH scored_results AS (
        SELECT
            w.id,
            w.file_name,
            w.title,
            w.au_year_level,
            w.au_topic,
            w.au_subtopic,
            w.acara_strand,
            array_length(w.skills_covered, 1) as skill_count,
            w.has_diagrams,
            w.has_word_problems,
            w.difficulty_progression,

            -- Semantic similarity score (cosine distance, lower is better, so we invert)
            CASE
                WHEN query_embedding IS NOT NULL AND w.embedding_content IS NOT NULL
                THEN (1 - (w.embedding_content <=> query_embedding))::DECIMAL
                ELSE 0
            END as semantic_score,

            -- Keyword search rank (using ts_rank for full-text search)
            CASE
                WHEN search_query IS NOT NULL
                THEN ts_rank(
                    to_tsvector('english',
                        COALESCE(w.title, '') || ' ' ||
                        COALESCE(w.uk_topic, '') || ' ' ||
                        COALESCE(w.uk_subtopic, '') || ' ' ||
                        COALESCE(w.au_topic, '') || ' ' ||
                        COALESCE(w.au_subtopic, '') || ' ' ||
                        COALESCE(array_to_string(w.skills_covered, ' '), '')
                    ),
                    plainto_tsquery('english', search_query)
                )::DECIMAL
                ELSE 0
            END as keyword_score

        FROM worksheets w
        WHERE
            -- Status filter
            w.status = 'completed'

            -- Year level filter
            AND (year_level_filter IS NULL OR w.au_year_level = year_level_filter)

            -- Strand filter
            AND (strand_filter IS NULL OR w.acara_strand = strand_filter)

            -- Topic filter (fuzzy match)
            AND (topic_filter IS NULL OR
                 w.au_topic ILIKE '%' || topic_filter || '%' OR
                 w.uk_topic ILIKE '%' || topic_filter || '%')

            -- Diagram filter
            AND (has_diagrams_filter IS NULL OR w.has_diagrams = has_diagrams_filter)

            -- Word problems filter
            AND (has_word_problems_filter IS NULL OR w.has_word_problems = has_word_problems_filter)

            -- Difficulty filter
            AND (difficulty_filter IS NULL OR w.difficulty_progression = difficulty_filter)

            -- Keyword match (if search query provided)
            AND (search_query IS NULL OR
                 to_tsvector('english',
                    COALESCE(w.title, '') || ' ' ||
                    COALESCE(w.uk_topic, '') || ' ' ||
                    COALESCE(w.au_topic, '') || ' ' ||
                    COALESCE(array_to_string(w.skills_covered, ' '), '')
                 ) @@ plainto_tsquery('english', search_query))
    )
    SELECT
        sr.id,
        sr.file_name,
        sr.title,
        sr.au_year_level,
        sr.au_topic,
        sr.au_subtopic,
        sr.acara_strand,
        sr.skill_count,
        sr.has_diagrams,
        sr.has_word_problems,
        sr.difficulty_progression,
        -- Combined relevance score
        (
            (COALESCE(semantic_weight, 0) * sr.semantic_score) +
            (COALESCE(keyword_weight, 0) * sr.keyword_score) +
            ((1 - COALESCE(semantic_weight, 0) - COALESCE(keyword_weight, 0)) * 0.5) -- Baseline score
        )::DECIMAL as relevance_score,
        sr.semantic_score as semantic_similarity,
        sr.keyword_score as keyword_rank
    FROM scored_results sr
    ORDER BY relevance_score DESC, sr.title
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- Function: Semantic search only (fast vector similarity)
CREATE OR REPLACE FUNCTION search_worksheets_semantic(
    query_embedding vector(1024),
    year_level_filter TEXT DEFAULT NULL,
    strand_filter TEXT DEFAULT NULL,
    limit_results INTEGER DEFAULT 20
)
RETURNS TABLE (
    id UUID,
    file_name TEXT,
    title TEXT,
    au_year_level TEXT,
    au_topic TEXT,
    acara_strand TEXT,
    similarity_score DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        w.id,
        w.file_name,
        w.title,
        w.au_year_level,
        w.au_topic,
        w.acara_strand,
        (1 - (w.embedding_content <=> query_embedding))::DECIMAL as similarity_score
    FROM worksheets w
    WHERE
        w.status = 'completed'
        AND w.embedding_content IS NOT NULL
        AND (year_level_filter IS NULL OR w.au_year_level = year_level_filter)
        AND (strand_filter IS NULL OR w.acara_strand = strand_filter)
    ORDER BY w.embedding_content <=> query_embedding
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- Function: Find similar worksheets to a given worksheet
CREATE OR REPLACE FUNCTION find_similar_worksheets(
    worksheet_id_input UUID,
    limit_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    file_name TEXT,
    title TEXT,
    au_year_level TEXT,
    au_topic TEXT,
    similarity_score DECIMAL,
    shared_skills INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH target_worksheet AS (
        SELECT
            embedding_content,
            skills_covered,
            au_year_level,
            acara_strand
        FROM worksheets
        WHERE id = worksheet_id_input
    )
    SELECT
        w.id,
        w.file_name,
        w.title,
        w.au_year_level,
        w.au_topic,
        (1 - (w.embedding_content <=> tw.embedding_content))::DECIMAL as similarity_score,
        -- Count shared skills
        (
            SELECT COUNT(*)
            FROM unnest(w.skills_covered) skill
            WHERE skill = ANY(tw.skills_covered)
        )::INTEGER as shared_skills
    FROM worksheets w, target_worksheet tw
    WHERE
        w.id != worksheet_id_input
        AND w.status = 'completed'
        AND w.embedding_content IS NOT NULL
        AND tw.embedding_content IS NOT NULL
        -- Optional: same year level or adjacent
        AND (
            w.au_year_level = tw.au_year_level OR
            w.acara_strand = tw.acara_strand
        )
    ORDER BY w.embedding_content <=> tw.embedding_content
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- Function: Full-text search for ACARA content descriptors
CREATE OR REPLACE FUNCTION search_acara_descriptors(
    search_query TEXT,
    year_level_filter TEXT DEFAULT NULL,
    strand_filter TEXT DEFAULT NULL,
    limit_results INTEGER DEFAULT 20
)
RETURNS TABLE (
    code TEXT,
    year_level TEXT,
    strand TEXT,
    sub_strand TEXT,
    description TEXT,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        acd.code,
        acd.year_level,
        acd.strand,
        acd.sub_strand,
        acd.description,
        ts_rank(
            to_tsvector('english', COALESCE(acd.description, '') || ' ' || COALESCE(acd.sub_strand, '')),
            plainto_tsquery('english', search_query)
        ) as rank
    FROM acara_content_descriptors acd
    WHERE
        acd.is_current = true
        AND to_tsvector('english', COALESCE(acd.description, '') || ' ' || COALESCE(acd.sub_strand, ''))
            @@ plainto_tsquery('english', search_query)
        AND (year_level_filter IS NULL OR acd.year_level = year_level_filter)
        AND (strand_filter IS NULL OR acd.strand = strand_filter)
    ORDER BY rank DESC, acd.code
    LIMIT limit_results;
END;
$$ LANGUAGE plpgsql;

-- Function: Find worksheets by skill progression
-- Returns worksheets ordered by learning progression for a given skill
CREATE OR REPLACE FUNCTION find_worksheets_by_skill_progression(
    skill_name_input TEXT,
    start_year TEXT DEFAULT 'Year 1'
)
RETURNS TABLE (
    worksheet_id UUID,
    worksheet_title TEXT,
    year_level TEXT,
    topic TEXT,
    coverage_level TEXT,
    difficulty INTEGER,
    prerequisite_skills_covered INTEGER
) AS $$
BEGIN
    RETURN QUERY
    WITH target_skill AS (
        SELECT id, name, difficulty_level
        FROM skills
        WHERE name ILIKE '%' || skill_name_input || '%'
        LIMIT 1
    ),
    prerequisite_skills AS (
        SELECT prerequisite_id as skill_id
        FROM get_skill_prerequisites((SELECT id FROM target_skill))
    )
    SELECT
        w.id,
        w.title,
        w.au_year_level,
        w.au_topic,
        ws.coverage_level,
        (SELECT difficulty_level FROM target_skill) as difficulty,
        -- Count how many prerequisite skills this worksheet covers
        (
            SELECT COUNT(DISTINCT ps.skill_id)
            FROM prerequisite_skills ps
            JOIN worksheet_skills ws2 ON ws2.skill_id = ps.skill_id
            WHERE ws2.worksheet_id = w.id
        )::INTEGER as prerequisite_skills_covered
    FROM worksheets w
    JOIN worksheet_skills ws ON w.id = ws.worksheet_id
    JOIN target_skill ts ON ws.skill_id = ts.id
    WHERE w.status = 'completed'
    ORDER BY
        CASE w.au_year_level
            WHEN 'Foundation' THEN 0
            WHEN 'Year 1' THEN 1
            WHEN 'Year 2' THEN 2
            WHEN 'Year 3' THEN 3
            WHEN 'Year 4' THEN 4
            WHEN 'Year 5' THEN 5
            WHEN 'Year 6' THEN 6
            WHEN 'Year 7' THEN 7
            WHEN 'Year 8' THEN 8
            WHEN 'Year 9' THEN 9
            WHEN 'Year 10' THEN 10
            WHEN 'Year 11' THEN 11
            WHEN 'Year 12' THEN 12
            ELSE 99
        END,
        prerequisite_skills_covered DESC,
        w.title;
END;
$$ LANGUAGE plpgsql;

-- Function: Get worksheet statistics by strand and year
CREATE OR REPLACE FUNCTION get_worksheet_statistics()
RETURNS TABLE (
    acara_strand TEXT,
    au_year_level TEXT,
    worksheet_count BIGINT,
    avg_skill_count DECIMAL,
    diagram_percentage DECIMAL,
    word_problem_percentage DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        w.acara_strand,
        w.au_year_level,
        COUNT(*) as worksheet_count,
        AVG(array_length(w.skills_covered, 1))::DECIMAL as avg_skill_count,
        (AVG(CASE WHEN w.has_diagrams THEN 1.0 ELSE 0.0 END) * 100)::DECIMAL as diagram_percentage,
        (AVG(CASE WHEN w.has_word_problems THEN 1.0 ELSE 0.0 END) * 100)::DECIMAL as word_problem_percentage
    FROM worksheets w
    WHERE w.status = 'completed'
        AND w.au_year_level IS NOT NULL
        AND w.acara_strand IS NOT NULL
    GROUP BY w.acara_strand, w.au_year_level
    ORDER BY
        w.acara_strand,
        CASE w.au_year_level
            WHEN 'Foundation' THEN 0
            WHEN 'Year 1' THEN 1
            WHEN 'Year 2' THEN 2
            WHEN 'Year 3' THEN 3
            WHEN 'Year 4' THEN 4
            WHEN 'Year 5' THEN 5
            WHEN 'Year 6' THEN 6
            WHEN 'Year 7' THEN 7
            WHEN 'Year 8' THEN 8
            WHEN 'Year 9' THEN 9
            WHEN 'Year 10' THEN 10
            WHEN 'Year 11' THEN 11
            WHEN 'Year 12' THEN 12
            ELSE 99
        END;
END;
$$ LANGUAGE plpgsql;

-- Function: Batch update worksheet embeddings
-- Helper function for when we regenerate embeddings
CREATE OR REPLACE FUNCTION update_worksheet_embedding(
    worksheet_id_input UUID,
    title_embedding vector(1024),
    content_embedding vector(1024)
)
RETURNS VOID AS $$
BEGIN
    UPDATE worksheets
    SET
        embedding_title = title_embedding,
        embedding_content = content_embedding,
        updated_at = NOW()
    WHERE id = worksheet_id_input;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION search_worksheets_hybrid IS 'Hybrid search combining semantic vectors, keywords, and structured filters';
COMMENT ON FUNCTION search_worksheets_semantic IS 'Fast semantic search using vector embeddings only';
COMMENT ON FUNCTION find_similar_worksheets IS 'Find worksheets similar to a given worksheet based on content and skills';
COMMENT ON FUNCTION search_acara_descriptors IS 'Full-text search for ACARA curriculum descriptors';
COMMENT ON FUNCTION find_worksheets_by_skill_progression IS 'Find worksheets for a skill ordered by learning progression';
