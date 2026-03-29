-- Migration 003: Skills and Learning Relationships
-- Track mathematical skills, prerequisites, and learning progressions

-- Skills table: master list of mathematical skills
CREATE TABLE IF NOT EXISTS skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Skill identification
    name TEXT NOT NULL UNIQUE,
    slug TEXT NOT NULL UNIQUE, -- URL-friendly version
    category TEXT NOT NULL, -- number | algebra | geometry | measurement | statistics | problem_solving

    -- Skill description
    description TEXT,
    examples TEXT[], -- Array of example problems or concepts

    -- Curriculum alignment
    acara_strand TEXT, -- Number and Algebra | Measurement and Geometry | Statistics and Probability
    typical_year_levels TEXT[], -- e.g., ['Year 4', 'Year 5', 'Year 6']

    -- Difficulty
    difficulty_level INTEGER, -- 1-10 scale
    complexity_tags TEXT[], -- e.g., ['procedural', 'conceptual', 'application']

    -- Metadata
    is_foundational BOOLEAN DEFAULT false, -- Core skill that many others depend on
    is_active BOOLEAN DEFAULT true,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Skill prerequisites: which skills are needed before others
CREATE TABLE IF NOT EXISTS skill_prerequisites (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    prerequisite_skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,

    -- Strength of prerequisite relationship
    importance TEXT DEFAULT 'required', -- required | recommended | helpful

    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Can't have a skill be its own prerequisite
    CHECK (skill_id != prerequisite_skill_id),

    -- One prerequisite relationship per pair
    UNIQUE(skill_id, prerequisite_skill_id)
);

-- Worksheet-skills junction table: which skills each worksheet covers
CREATE TABLE IF NOT EXISTS worksheet_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    worksheet_id UUID NOT NULL REFERENCES worksheets(id) ON DELETE CASCADE,
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,

    -- Coverage details
    coverage_level TEXT DEFAULT 'covered', -- introduced | practiced | mastered | assessed
    question_count INTEGER, -- How many questions target this skill

    -- Source of this association
    detection_source TEXT DEFAULT 'vision_api', -- vision_api | manual | inferred

    -- Confidence
    confidence_score DECIMAL(3, 2), -- 0.00 to 1.00

    notes TEXT,

    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- One skill per worksheet (but can appear at different coverage levels in different analyses)
    UNIQUE(worksheet_id, skill_id)
);

-- Diagram types table: categorize visual elements
CREATE TABLE IF NOT EXISTS worksheet_diagrams (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    worksheet_id UUID NOT NULL REFERENCES worksheets(id) ON DELETE CASCADE,

    -- Diagram details
    diagram_type TEXT NOT NULL, -- graph | geometric_shape | number_line | chart | table | grid | illustration
    description TEXT,
    page_number INTEGER,
    section_label TEXT,

    -- Diagram properties
    is_labeled BOOLEAN DEFAULT false,
    is_gridded BOOLEAN DEFAULT false,
    has_axes BOOLEAN DEFAULT false,
    complexity TEXT, -- simple | moderate | complex

    -- Educational purpose
    purpose TEXT, -- instruction | practice | assessment | decoration

    -- Extraction metadata
    detected_by TEXT DEFAULT 'vision_api',
    confidence_score DECIMAL(3, 2),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Learning plans table: suggested worksheet sequences
CREATE TABLE IF NOT EXISTS learning_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Plan identification
    name TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    description TEXT,

    -- Target audience
    target_year_level TEXT,
    acara_strand TEXT,
    topic TEXT,

    -- Plan metadata
    estimated_duration_minutes INTEGER,
    difficulty_level INTEGER, -- 1-10

    -- Plan structure (ordered array of worksheet IDs with metadata)
    worksheet_sequence JSONB NOT NULL, -- [{worksheet_id, order, notes, estimated_time}]

    -- Status
    is_published BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,

    -- Authorship
    created_by TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for skills
CREATE INDEX idx_skills_category ON skills(category);
CREATE INDEX idx_skills_strand ON skills(acara_strand);
CREATE INDEX idx_skills_difficulty ON skills(difficulty_level);
CREATE INDEX idx_skills_foundational ON skills(is_foundational);
CREATE INDEX idx_skills_name ON skills(name);

-- Full-text search on skills
CREATE INDEX idx_skills_fts ON skills USING GIN(
    to_tsvector('english',
        COALESCE(name, '') || ' ' ||
        COALESCE(description, '')
    )
);

-- Indexes for prerequisites
CREATE INDEX idx_prerequisites_skill ON skill_prerequisites(skill_id);
CREATE INDEX idx_prerequisites_prereq ON skill_prerequisites(prerequisite_skill_id);

-- Indexes for worksheet_skills
CREATE INDEX idx_worksheet_skills_worksheet ON worksheet_skills(worksheet_id);
CREATE INDEX idx_worksheet_skills_skill ON worksheet_skills(skill_id);
CREATE INDEX idx_worksheet_skills_coverage ON worksheet_skills(coverage_level);

-- Indexes for diagrams
CREATE INDEX idx_diagrams_worksheet ON worksheet_diagrams(worksheet_id);
CREATE INDEX idx_diagrams_type ON worksheet_diagrams(diagram_type);
CREATE INDEX idx_diagrams_purpose ON worksheet_diagrams(purpose);

-- Indexes for learning plans
CREATE INDEX idx_learning_plans_year ON learning_plans(target_year_level);
CREATE INDEX idx_learning_plans_strand ON learning_plans(acara_strand);
CREATE INDEX idx_learning_plans_published ON learning_plans(is_published);

-- Updated timestamp triggers
CREATE TRIGGER update_skills_updated_at
    BEFORE UPDATE ON skills
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_learning_plans_updated_at
    BEFORE UPDATE ON learning_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- View: Skills with prerequisite count
CREATE OR REPLACE VIEW skills_with_prerequisites AS
SELECT
    s.id,
    s.name,
    s.category,
    s.difficulty_level,
    s.is_foundational,
    COUNT(DISTINCT sp.prerequisite_skill_id) as prerequisite_count,
    COUNT(DISTINCT ws.worksheet_id) as worksheet_count
FROM skills s
LEFT JOIN skill_prerequisites sp ON s.id = sp.skill_id
LEFT JOIN worksheet_skills ws ON s.id = ws.skill_id
WHERE s.is_active = true
GROUP BY s.id, s.name, s.category, s.difficulty_level, s.is_foundational
ORDER BY s.category, s.name;

-- View: Worksheet skill coverage summary
CREATE OR REPLACE VIEW worksheet_skill_summary AS
SELECT
    w.id as worksheet_id,
    w.file_name,
    w.title,
    w.au_year_level,
    w.au_topic,
    COUNT(DISTINCT ws.skill_id) as skill_count,
    COUNT(DISTINCT CASE WHEN ws.coverage_level = 'introduced' THEN ws.skill_id END) as introduced_count,
    COUNT(DISTINCT CASE WHEN ws.coverage_level = 'practiced' THEN ws.skill_id END) as practiced_count,
    COUNT(DISTINCT CASE WHEN ws.coverage_level = 'mastered' THEN ws.skill_id END) as mastered_count,
    COUNT(DISTINCT wd.id) as diagram_count
FROM worksheets w
LEFT JOIN worksheet_skills ws ON w.id = ws.worksheet_id
LEFT JOIN worksheet_diagrams wd ON w.id = wd.worksheet_id
WHERE w.status = 'completed'
GROUP BY w.id, w.file_name, w.title, w.au_year_level, w.au_topic;

-- Function: Get all prerequisites for a skill (recursive)
CREATE OR REPLACE FUNCTION get_skill_prerequisites(skill_id_input UUID)
RETURNS TABLE (
    prerequisite_id UUID,
    prerequisite_name TEXT,
    depth INTEGER
) AS $$
WITH RECURSIVE prereq_tree AS (
    -- Base case: direct prerequisites
    SELECT
        sp.prerequisite_skill_id as id,
        s.name,
        1 as depth
    FROM skill_prerequisites sp
    JOIN skills s ON s.id = sp.prerequisite_skill_id
    WHERE sp.skill_id = skill_id_input

    UNION ALL

    -- Recursive case: prerequisites of prerequisites
    SELECT
        sp.prerequisite_skill_id,
        s.name,
        pt.depth + 1
    FROM skill_prerequisites sp
    JOIN skills s ON s.id = sp.prerequisite_skill_id
    JOIN prereq_tree pt ON pt.id = sp.skill_id
    WHERE pt.depth < 10 -- Prevent infinite recursion
)
SELECT DISTINCT id, name, depth
FROM prereq_tree
ORDER BY depth, name;
$$ LANGUAGE SQL;

-- Function: Find worksheets that cover a specific skill
CREATE OR REPLACE FUNCTION find_worksheets_by_skill(skill_name_input TEXT)
RETURNS TABLE (
    worksheet_id UUID,
    worksheet_title TEXT,
    year_level TEXT,
    coverage_level TEXT,
    confidence_score DECIMAL
) AS $$
SELECT
    w.id,
    w.title,
    w.au_year_level,
    ws.coverage_level,
    ws.confidence_score
FROM worksheets w
JOIN worksheet_skills ws ON w.id = ws.worksheet_id
JOIN skills s ON ws.skill_id = s.id
WHERE s.name ILIKE '%' || skill_name_input || '%'
    AND w.status = 'completed'
ORDER BY w.au_year_level, w.title;
$$ LANGUAGE SQL;

COMMENT ON TABLE skills IS 'Master list of mathematical skills across all year levels';
COMMENT ON TABLE skill_prerequisites IS 'Learning dependencies between skills';
COMMENT ON TABLE worksheet_skills IS 'Which skills each worksheet covers';
COMMENT ON TABLE worksheet_diagrams IS 'Visual elements extracted from worksheets';
COMMENT ON TABLE learning_plans IS 'Curated sequences of worksheets for learning paths';
