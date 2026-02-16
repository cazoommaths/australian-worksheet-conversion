-- Migration 002: Curriculum Mappings
-- Store UK to Australian curriculum mappings and content descriptors

-- Curriculum mappings table: UK to AU equivalents
CREATE TABLE IF NOT EXISTS curriculum_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Source (UK)
    uk_year_level TEXT NOT NULL,
    uk_key_stage TEXT, -- KS1, KS2, KS3, GCSE, A-Level
    uk_topic TEXT NOT NULL,
    uk_subtopic TEXT,

    -- Target (Australian)
    au_year_level TEXT NOT NULL,
    au_topic TEXT NOT NULL,
    au_subtopic TEXT,
    acara_strand TEXT NOT NULL, -- Number and Algebra | Measurement and Geometry | Statistics and Probability

    -- ACARA content descriptors (v9 codes)
    content_descriptor_codes TEXT[], -- e.g., ['AC9M5N01', 'AC9M5N02']

    -- Mapping metadata
    confidence_score DECIMAL(3, 2), -- 0.00 to 1.00 for AI-generated mappings
    mapping_source TEXT DEFAULT 'config', -- config | ai | manual
    mapping_notes TEXT,

    -- Terminology changes needed
    terminology_changes JSONB, -- Array of {from, to, category} objects

    -- Content timing differences
    content_notes TEXT, -- Notes about differences in when topics are taught

    -- Validation
    is_verified BOOLEAN DEFAULT false,
    verified_by TEXT,
    verified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint: one mapping per UK topic/year combination
    UNIQUE(uk_year_level, uk_topic, uk_subtopic)
);

-- ACARA content descriptors table: detailed v9 curriculum codes
CREATE TABLE IF NOT EXISTS acara_content_descriptors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- ACARA identifiers
    code TEXT UNIQUE NOT NULL, -- e.g., AC9M5N01
    year_level TEXT NOT NULL, -- Foundation, Year 1-10
    strand TEXT NOT NULL, -- Number and Algebra | Measurement and Geometry | Statistics and Probability
    sub_strand TEXT, -- e.g., Number and place value, Fractions and decimals

    -- Content
    description TEXT NOT NULL,
    elaborations TEXT[], -- Array of elaboration texts

    -- Relationships
    prerequisite_codes TEXT[], -- Codes that should be learned before this
    builds_to_codes TEXT[], -- Codes this leads to in later years

    -- Achievement standards alignment
    achievement_standard TEXT,

    -- Metadata
    version TEXT DEFAULT 'v9',
    is_current BOOLEAN DEFAULT true,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Worksheet-specific curriculum mappings: links worksheets to curriculum
CREATE TABLE IF NOT EXISTS worksheet_curriculum_mappings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    worksheet_id UUID NOT NULL REFERENCES worksheets(id) ON DELETE CASCADE,
    mapping_id UUID REFERENCES curriculum_mappings(id) ON DELETE SET NULL,

    -- Direct ACARA code assignments (can be multiple per worksheet)
    acara_code TEXT REFERENCES acara_content_descriptors(code),

    -- Mapping confidence and source
    confidence_score DECIMAL(3, 2),
    mapping_source TEXT, -- ai | manual | config

    -- Notes about this specific mapping
    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Unique constraint: one code per worksheet (but worksheets can have many codes)
    UNIQUE(worksheet_id, acara_code)
);

-- Indexes for curriculum mappings
CREATE INDEX idx_curriculum_uk_year ON curriculum_mappings(uk_year_level);
CREATE INDEX idx_curriculum_au_year ON curriculum_mappings(au_year_level);
CREATE INDEX idx_curriculum_uk_topic ON curriculum_mappings(uk_topic);
CREATE INDEX idx_curriculum_strand ON curriculum_mappings(acara_strand);
CREATE INDEX idx_curriculum_verified ON curriculum_mappings(is_verified);
CREATE INDEX idx_curriculum_source ON curriculum_mappings(mapping_source);

-- Indexes for ACARA descriptors
CREATE INDEX idx_acara_code ON acara_content_descriptors(code);
CREATE INDEX idx_acara_year ON acara_content_descriptors(year_level);
CREATE INDEX idx_acara_strand ON acara_content_descriptors(strand);
CREATE INDEX idx_acara_current ON acara_content_descriptors(is_current);

-- Full-text search on ACARA descriptions
CREATE INDEX idx_acara_fts ON acara_content_descriptors USING GIN(
    to_tsvector('english',
        COALESCE(description, '') || ' ' ||
        COALESCE(sub_strand, '')
    )
);

-- Indexes for worksheet curriculum mappings
CREATE INDEX idx_worksheet_curriculum_worksheet ON worksheet_curriculum_mappings(worksheet_id);
CREATE INDEX idx_worksheet_curriculum_mapping ON worksheet_curriculum_mappings(mapping_id);
CREATE INDEX idx_worksheet_curriculum_code ON worksheet_curriculum_mappings(acara_code);

-- Updated timestamp trigger for curriculum_mappings
CREATE TRIGGER update_curriculum_mappings_updated_at
    BEFORE UPDATE ON curriculum_mappings
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Updated timestamp trigger for acara_content_descriptors
CREATE TRIGGER update_acara_content_descriptors_updated_at
    BEFORE UPDATE ON acara_content_descriptors
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- View: Worksheets with full curriculum mapping details
CREATE OR REPLACE VIEW worksheets_with_curriculum AS
SELECT
    w.id,
    w.file_name,
    w.title,
    w.uk_year_level,
    w.uk_topic,
    w.au_year_level,
    w.au_topic,
    w.acara_strand,
    cm.content_descriptor_codes,
    cm.confidence_score as mapping_confidence,
    cm.mapping_source,
    cm.is_verified as mapping_verified,
    w.status,
    w.created_at
FROM worksheets w
LEFT JOIN curriculum_mappings cm
    ON w.uk_year_level = cm.uk_year_level
    AND w.uk_topic = cm.uk_topic
    AND (w.uk_subtopic = cm.uk_subtopic OR cm.uk_subtopic IS NULL)
WHERE w.status = 'completed';

-- View: Summary of curriculum coverage
CREATE OR REPLACE VIEW curriculum_coverage_summary AS
SELECT
    acara_strand,
    au_year_level,
    COUNT(DISTINCT id) as worksheet_count,
    COUNT(DISTINCT au_topic) as topic_count,
    AVG(CASE WHEN is_verified THEN 1.0 ELSE 0.0 END) as verification_rate
FROM curriculum_mappings
GROUP BY acara_strand, au_year_level
ORDER BY acara_strand, au_year_level;

COMMENT ON TABLE curriculum_mappings IS 'UK to Australian curriculum mappings';
COMMENT ON TABLE acara_content_descriptors IS 'ACARA v9 curriculum content descriptors';
COMMENT ON TABLE worksheet_curriculum_mappings IS 'Links worksheets to specific curriculum codes';
COMMENT ON COLUMN curriculum_mappings.confidence_score IS 'AI confidence in mapping (0.00-1.00)';
