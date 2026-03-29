-- Migration 005: Enhanced Extraction Fields
-- Adds new columns for richer Vision API extraction output
-- and fields to store data imported from the master UK worksheets table

-- ─── New extraction fields ───────────────────────────────────────────────────

ALTER TABLE worksheets
    ADD COLUMN IF NOT EXISTS total_questions    INTEGER,          -- Total question count across all sections
    ADD COLUMN IF NOT EXISTS estimated_time_minutes INTEGER,      -- Estimated student completion time (mins)
    ADD COLUMN IF NOT EXISTS difficulty_level   TEXT,             -- foundation | core | higher | mixed
    ADD COLUMN IF NOT EXISTS has_equations      BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS equation_types     TEXT[];           -- linear | quadratic | simultaneous | trigonometric | etc.

-- ─── Master table import fields ──────────────────────────────────────────────
-- These store data imported from the existing cazoommaths.com master DB

ALTER TABLE worksheets
    ADD COLUMN IF NOT EXISTS master_id          TEXT,             -- Original master DB UUID
    ADD COLUMN IF NOT EXISTS wp_id              TEXT,             -- WordPress post ID
    ADD COLUMN IF NOT EXISTS legacy_id          TEXT,             -- Legacy system ID
    ADD COLUMN IF NOT EXISTS description        TEXT,             -- HTML description from master table
    ADD COLUMN IF NOT EXISTS learning_objective TEXT,             -- UK learning objective
    ADD COLUMN IF NOT EXISTS prerequisite_knowledge TEXT,         -- Free-text prerequisite (master table)
    ADD COLUMN IF NOT EXISTS resource_type      TEXT,             -- KS3_KS4 | KS1_KS2 | KS3 | KS4 etc.
    ADD COLUMN IF NOT EXISTS gcse_tier          TEXT,             -- Foundation | Higher | Both
    ADD COLUMN IF NOT EXISTS target_grade       TEXT,             -- GCSE grade range e.g. "1-3", "4-9"
    ADD COLUMN IF NOT EXISTS worksheet_download_url TEXT,         -- s2member / direct PDF download URL
    ADD COLUMN IF NOT EXISTS answer_download_url TEXT,            -- Answer sheet download URL
    ADD COLUMN IF NOT EXISTS dropbox_url        TEXT,             -- Dropbox sharing link (if available)
    ADD COLUMN IF NOT EXISTS master_url         TEXT,             -- Canonical worksheet page URL
    ADD COLUMN IF NOT EXISTS featured_image_url TEXT,             -- Thumbnail image URL
    ADD COLUMN IF NOT EXISTS is_free            BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS master_status      TEXT;             -- Status in master table (published etc.)

-- ─── Index new columns ───────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_worksheets_difficulty_level
    ON worksheets(difficulty_level);

CREATE INDEX IF NOT EXISTS idx_worksheets_resource_type
    ON worksheets(resource_type);

CREATE INDEX IF NOT EXISTS idx_worksheets_gcse_tier
    ON worksheets(gcse_tier);

CREATE INDEX IF NOT EXISTS idx_worksheets_master_id
    ON worksheets(master_id);

CREATE INDEX IF NOT EXISTS idx_worksheets_total_questions
    ON worksheets(total_questions);

-- ─── Update the AU-mapped view to include new fields ─────────────────────────

CREATE OR REPLACE VIEW worksheets_au_mapped AS
SELECT
    id,
    file_name,
    title,
    uk_year_level,
    au_year_level,
    uk_topic,
    au_topic,
    uk_subtopic,
    au_subtopic,
    acara_strand,
    resource_type,
    gcse_tier,
    difficulty_level,
    difficulty_progression,
    total_questions,
    estimated_time_minutes,
    has_diagrams,
    has_equations,
    has_word_problems,
    has_extension_tasks,
    array_length(skills_covered, 1) AS skill_count,
    status,
    extraction_method,
    created_at
FROM worksheets
WHERE au_year_level IS NOT NULL;

-- ─── Catalog summary view ────────────────────────────────────────────────────

CREATE OR REPLACE VIEW worksheets_catalog AS
SELECT
    id,
    master_id,
    title,
    uk_year_level,
    au_year_level,
    resource_type,
    uk_topic,
    uk_subtopic,
    acara_strand,
    difficulty_level,
    gcse_tier,
    total_questions,
    estimated_time_minutes,
    has_diagrams,
    has_equations,
    has_word_problems,
    is_free,
    status,
    extraction_method,
    worksheet_download_url,
    master_url
FROM worksheets
ORDER BY resource_type, uk_topic, uk_subtopic, title;

COMMENT ON COLUMN worksheets.total_questions         IS 'Total number of questions counted across all sections by Vision API';
COMMENT ON COLUMN worksheets.estimated_time_minutes  IS 'Estimated time in minutes for a student to complete the worksheet';
COMMENT ON COLUMN worksheets.difficulty_level        IS 'Overall difficulty: foundation | core | higher | mixed';
COMMENT ON COLUMN worksheets.has_equations           IS 'True if worksheet contains algebraic equations to solve';
COMMENT ON COLUMN worksheets.equation_types          IS 'Types of equations: linear, quadratic, simultaneous, trigonometric, etc.';
COMMENT ON COLUMN worksheets.master_id               IS 'UUID from the original cazoommaths.com master worksheets table';
COMMENT ON COLUMN worksheets.resource_type           IS 'Key stage classification from master table e.g. KS3_KS4';
