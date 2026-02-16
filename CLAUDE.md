# Cazoom Maths: Worksheet Intelligence Platform

## Project Overview

This platform provides intelligent processing and conversion of UK curriculum maths worksheets to Australian curriculum format. It combines advanced AI extraction (Claude Vision API), semantic search capabilities, and comprehensive curriculum mapping to create a scalable worksheet intelligence system.

**Core Capabilities:**
- 🔍 Advanced PDF analysis using Claude Vision API (structured extraction)
- 🗄️ Supabase PostgreSQL database with vector search (pgvector)
- 🎯 Intelligent UK → AU curriculum mapping
- 🔎 Hybrid search (structured filters + full-text + semantic similarity)
- 📊 Skills tracking and learning progressions
- 🎨 Diagram detection and classification
- 🔗 ACARA content descriptor alignment

## What Needs to Change

### 1. Grade/Year Level Mapping

| UK Level | UK Age | Australian Equivalent |
|----------|--------|----------------------|
| Year 1 | 5-6 | Year 1 (Foundation) |
| Year 2 | 6-7 | Year 2 |
| Year 3 | 7-8 | Year 3 |
| Year 4 | 8-9 | Year 4 |
| Year 5 | 9-10 | Year 5 |
| Year 6 | 10-11 | Year 6 |
| Year 7 | 11-12 | Year 7 |
| Year 8 | 12-13 | Year 8 |
| Year 9 | 13-14 | Year 9 |
| Year 10 | 14-15 | Year 10 |
| Year 11 (GCSE) | 15-16 | Year 11 |
| Year 12 (A-Level) | 16-17 | Year 12 |
| Year 13 (A-Level) | 17-18 | Year 12 (Senior) |

**Note:** UK and Australian year levels align fairly well (both use "Year X" terminology), but curriculum content timing differs. Australian curriculum follows ACARA (Australian Curriculum, Assessment and Reporting Authority) standards.

### 2. Terminology Changes

| UK Term | Australian Term |
|---------|-----------------|
| Maths | Maths ✓ (same) |
| Centre | Centre ✓ (same) |
| Colour | Colour ✓ (same) |
| £ (pounds) | $ (AUD) |
| pence (p) | cents (c) |
| metres | metres ✓ (same) |
| litres | litres ✓ (same) |
| Programme | Program |
| Practise (verb) | Practise ✓ (same) |
| Autumn term | Term 1/2 |
| Spring term | Term 2/3 |
| Summer term | Term 3/4 |
| Key Stage 1 | Foundation - Year 2 |
| Key Stage 2 | Years 3-6 |
| Key Stage 3 | Years 7-10 |
| GCSE | Year 11/12 or Senior Secondary |
| A-Level | Year 12 / HSC / VCE / QCE / SACE |

### 3. Currency Conversions in Word Problems

- Replace £ with $ (Australian dollars)
- Replace pence with cents
- Adjust amounts to be realistic for Australian context
- Example: "£2.50" → "$4.00" (approximate equivalent)

### 4. Context Localisation

| UK Context | Australian Context |
|------------|-------------------|
| Football (soccer) | AFL, Rugby, Cricket, Soccer |
| Cricket | Cricket ✓ (same) |
| London, Manchester, etc. | Sydney, Melbourne, Brisbane, Perth |
| Motorway | Highway/Freeway |
| Petrol | Petrol ✓ (same) |
| Holiday | Holiday ✓ (same) |

### 5. Topic Alignment to ACARA

Map UK National Curriculum topics to Australian Curriculum strands:
- **Number and Algebra** (Number, Money, Algebra, Patterns)
- **Measurement and Geometry** (Length, Mass, Capacity, Time, Shapes, Position)
- **Statistics and Probability** (Data, Chance)

## Architecture Overview

### Data Flow Pipeline

```
CSV Catalog → Download PDFs → Vision Extraction → Supabase Storage → AU Mapping → Embeddings → Searchable
```

### Technology Stack

**AI & Extraction:**
- Claude Vision API (claude-sonnet-4-20250514) for structured PDF analysis
- PyMuPDF (fallback for basic text extraction)
- Rate limiting: 10 requests/minute

**Database:**
- Supabase (PostgreSQL) for structured data
- pgvector extension for semantic search
- Full-text search (PostgreSQL GIN indexes)
- HNSW indexes for fast vector similarity

**Search Capabilities:**
- Structured filters (year level, strand, topic, flags)
- Full-text search (PostgreSQL tsvector)
- Semantic search (vector embeddings with cosine similarity)
- Hybrid scoring combining all three approaches

**Skills & Curriculum:**
- ACARA v9 content descriptor alignment
- Prerequisite skill tracking
- Learning progression mapping
- Diagram inventory and classification

### Data Sources

**Primary: Google Sheets / CSV**
- Contains worksheet catalogue with: Name, UK Year Level, Topic, Subtopic, Dropbox Link
- Export as CSV for batch processing

**Production: Supabase Database**
- `worksheets` - Core worksheet metadata and extraction results
- `curriculum_mappings` - UK → AU mappings
- `acara_content_descriptors` - ACARA v9 curriculum codes
- `skills` - Mathematical skills catalog
- `worksheet_skills` - Skills covered per worksheet
- `worksheet_diagrams` - Diagram inventory
- `learning_plans` - Curated worksheet sequences

**File Storage: Dropbox**
- All PDF worksheets stored here
- Download via direct links (converted from sharing URLs)

## Project Phases

### ✅ Phase 1: Foundation (Complete)
1. ✓ Project structure and configuration files
2. ✓ Terminology and curriculum mapping configs
3. ✓ PyMuPDF-based extraction (fallback)
4. ✓ Sample worksheet catalog

### 🚀 Phase 2: Intelligence Platform (Current)
1. ✓ Claude Vision API integration for rich extraction
2. ✓ Supabase database schema with migrations
3. ✓ Vector embeddings for semantic search
4. ✓ Batch processing pipeline
5. ⏳ Testing and validation
6. ⏳ AU curriculum mapping automation

### 📋 Phase 3: Production Scale (Future)
1. Process full worksheet catalog (thousands)
2. ACARA content descriptor database population
3. Skills taxonomy completion
4. Learning plan generation
5. Search API and UI
6. Quality assurance workflows

### 🎯 Phase 4: PDF Editing (Future)
1. Apply text changes to PDFs
2. Update headers/footers with Australian branding
3. Save new versions with "AU" prefix
4. Automated quality checks

## File Structure

```
australian-worksheet-conversion/
├── CLAUDE.md                         # Project instructions (this file)
├── BEGINNERS_GUIDE.md               # Setup guide for non-technical users
├── requirements.txt                  # Python dependencies
│
├── config/                           # Configuration files
│   ├── terminology.json             # ✓ UK → AU terminology replacements
│   ├── au_curriculum_mapping.json   # ✓ UK → AU curriculum mappings
│   └── au_content_descriptors.json  # TODO: ACARA v9 codes
│
├── supabase/                         # Database migrations
│   └── migrations/
│       ├── 001_worksheets.sql       # ✓ Core worksheets table
│       ├── 002_curriculum.sql       # ✓ Curriculum mappings
│       ├── 003_skills.sql           # ✓ Skills and relationships
│       └── 004_search_functions.sql # ✓ Hybrid search functions
│
├── scripts/                          # Processing scripts
│   ├── extract_pdf_info.py          # ✓ Fallback PyMuPDF extraction
│   ├── extract_with_vision.py       # ✓ Claude Vision API extraction
│   ├── generate_embeddings.py       # ✓ Vector embeddings for search
│   ├── batch_process.py             # ✓ Full pipeline orchestration
│   ├── download_worksheets.py       # ✓ Download from Dropbox
│   ├── import_spreadsheet.py        # ✓ Import CSV to Supabase
│   └── map_curriculum.py            # TODO: Apply AU mappings
│
└── data/                             # Data files
    ├── worksheets_SAMPLE.csv        # ✓ Sample catalog (10 worksheets)
    ├── input/                       # Downloaded PDFs
    ├── output/                      # Processed/converted PDFs
    ├── batch_progress.json          # Resume tracking
    └── batch_errors.log             # Error logging
```

## Commands & Usage

### Initial Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# Create .env file with credentials
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
OPENAI_API_KEY=sk-...  # For embeddings (until Anthropic has native embeddings)
DROPBOX_ACCESS_TOKEN=optional  # If using official SDK
EOF

# Run Supabase migrations (in Supabase dashboard or CLI)
# Apply migrations in order: 001, 002, 003, 004
```

### Workflow Commands

**1. Download PDFs from Dropbox**
```bash
# Download sample worksheets
python scripts/download_worksheets.py --csv data/worksheets_SAMPLE.csv --limit 10

# Download all worksheets from catalog
python scripts/download_worksheets.py --csv data/full_catalog.csv
```

**2. Import Catalog to Database**
```bash
# Import worksheet metadata to Supabase
python scripts/import_spreadsheet.py --csv data/worksheets_SAMPLE.csv

# Update existing entries
python scripts/import_spreadsheet.py --csv data/worksheets.csv --update-existing
```

**3. Extract with Vision API (Single File)**
```bash
# Test Vision extraction on one PDF
python scripts/extract_with_vision.py --file data/input/worksheet.pdf

# Extract from folder
python scripts/extract_with_vision.py --folder data/input --output data/vision_extracts.json
```

**4. Batch Process (Full Pipeline)**
```bash
# Process sample worksheets (downloads → Vision → Supabase → embeddings)
python scripts/batch_process.py --csv data/worksheets_SAMPLE.csv --limit 10

# Process all PDFs in folder (skip download)
python scripts/batch_process.py --folder data/input --skip-download

# Dry run (test without writing to database)
python scripts/batch_process.py --csv data/worksheets_SAMPLE.csv --dry-run

# Resume interrupted run
python scripts/batch_process.py --resume

# Reset progress tracking
python scripts/batch_process.py --reset
```

**5. Generate Embeddings**
```bash
# Generate embeddings for worksheets missing them
python scripts/generate_embeddings.py --missing-only

# Regenerate all embeddings
python scripts/generate_embeddings.py --all

# Generate for specific worksheet
python scripts/generate_embeddings.py --worksheet-id <uuid>

# Show embedding statistics
python scripts/generate_embeddings.py --stats
```

**6. Fallback: PyMuPDF Extraction**
```bash
# Extract text with PyMuPDF (fallback method)
python scripts/extract_pdf_info.py --file data/input/worksheet.pdf

# Batch extract from folder
python scripts/extract_pdf_info.py --input data/input --output data/extracted_info.csv
```

### Database Queries (Supabase SQL)

```sql
-- Find all Year 5 Number and Algebra worksheets
SELECT * FROM worksheets
WHERE au_year_level = 'Year 5'
AND acara_strand = 'Number and Algebra'
AND status = 'completed';

-- Search worksheets by keyword and year
SELECT * FROM search_worksheets_hybrid(
    search_query := 'fractions',
    year_level_filter := 'Year 5',
    limit_results := 10
);

-- Find similar worksheets to a given one
SELECT * FROM find_similar_worksheets(
    worksheet_id_input := '<uuid>',
    limit_results := 5
);

-- Get worksheet statistics by strand and year
SELECT * FROM get_worksheet_statistics();
```

## Environment Variables

Create a `.env` file in the project root:

```bash
# Required: Claude Vision API
ANTHROPIC_API_KEY=sk-ant-api03-...
# Get from: https://console.anthropic.com/settings/keys

# Required: Supabase Database
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGc...
# Get from: Supabase Dashboard → Settings → API

# Required: Embeddings (until Anthropic has native embeddings)
OPENAI_API_KEY=sk-proj-...
# Get from: https://platform.openai.com/api-keys
# Used for text-embedding-3-large (1024 dimensions)

# Optional: Dropbox (if using official SDK)
DROPBOX_ACCESS_TOKEN=sl.xxxxx...
# Get from: https://www.dropbox.com/developers/apps
```

## Vision API Extraction

The Vision extraction (`extract_with_vision.py`) sends PDF pages as images to Claude's Vision API with a structured prompt. It returns rich JSON with:

**Extracted Fields:**
- `title` - Worksheet title
- `year_level` - UK year level (Year 5, GCSE, etc.)
- `topic` / `subtopic` - Main topic and specific focus
- `strand` - ACARA strand classification
- `skills_covered` - Array of mathematical skills
- `prerequisite_skills` - Required prior knowledge
- `sections` - Breakdown of worksheet sections with:
  - `label`, `type`, `question_count`, `has_diagrams`, `diagram_descriptions`
- `difficulty_progression` - constant | easy_to_hard | mixed | scaffolded
- `diagram_inventory` - Count, types, descriptions of visual elements
- `uk_specific_elements` - Currency, places, terms needing localization
- `content_flags` - has_word_problems, has_real_world_context, etc.

**Rate Limiting:**
- Max 10 requests/minute (configurable)
- 6-second delay between API calls
- Automatic retry with exponential backoff

**Model:**
- `claude-sonnet-4-20250514` - Cost-effective for scale
- Can upgrade to Opus for higher accuracy if needed

## Database Schema

### Core Tables

**worksheets** - Main worksheet data
- Metadata: file_name, title, dropbox_url
- UK identifiers: uk_year_level, uk_topic, uk_subtopic
- AU mapping: au_year_level, au_topic, acara_strand, acara_content_codes
- Extracted content: skills_covered, sections, diagram_inventory
- Flags: has_diagrams, has_word_problems, difficulty_progression
- Embeddings: embedding_title, embedding_content (vector(1024))
- Status tracking: status, extraction_method, extracted_at

**curriculum_mappings** - UK → AU mappings
- UK: year_level, key_stage, topic, subtopic
- AU: year_level, topic, strand, content_descriptor_codes
- Metadata: confidence_score, mapping_source, is_verified

**acara_content_descriptors** - ACARA v9 curriculum codes
- code (e.g., AC9M5N01), year_level, strand, sub_strand
- description, elaborations, achievement_standard
- Relationships: prerequisite_codes, builds_to_codes

**skills** - Mathematical skills catalog
- name, category, description, examples
- acara_strand, typical_year_levels, difficulty_level
- is_foundational flag for core skills

**worksheet_skills** - Skills per worksheet
- worksheet_id → skill_id junction
- coverage_level: introduced | practiced | mastered | assessed
- confidence_score, detection_source

**worksheet_diagrams** - Diagram inventory
- diagram_type, description, page_number, section_label
- Properties: is_labeled, is_gridded, has_axes, complexity
- purpose: instruction | practice | assessment | decoration

**learning_plans** - Curated worksheet sequences
- name, target_year_level, topic, acara_strand
- worksheet_sequence (ordered JSON array)
- estimated_duration_minutes, is_published

### Search Functions

- `search_worksheets_hybrid()` - Combines semantic + keyword + filters
- `search_worksheets_semantic()` - Vector similarity only (fast)
- `find_similar_worksheets()` - Find worksheets like a given one
- `search_acara_descriptors()` - Full-text search ACARA codes
- `find_worksheets_by_skill_progression()` - Learning path for skill
- `get_worksheet_statistics()` - Coverage summaries

## Testing & Validation

### Test on Sample First

Before processing the full catalog, test the pipeline on the 10 sample worksheets:

```bash
# 1. Download samples
python scripts/download_worksheets.py --csv data/worksheets_SAMPLE.csv

# 2. Test Vision extraction on one file
python scripts/extract_with_vision.py --file data/input/Adding-Fractions-Same-Denominators.pdf

# 3. Run batch processing on samples
python scripts/batch_process.py --csv data/worksheets_SAMPLE.csv --limit 3

# 4. Check database results
python scripts/import_spreadsheet.py --stats

# 5. Generate embeddings
python scripts/generate_embeddings.py --missing-only

# 6. Verify search works (in Supabase SQL editor)
SELECT * FROM search_worksheets_hybrid(
    search_query := 'fractions',
    limit_results := 5
);
```

### Validation Checklist

- [ ] Vision API successfully extracts title, topics, skills from PDFs
- [ ] UK year levels correctly detected (Year 5, GCSE, etc.)
- [ ] ACARA strands properly classified
- [ ] Skills arrays populated with relevant skills
- [ ] Diagrams detected and categorized
- [ ] UK-specific elements identified (£, pence, London, etc.)
- [ ] AU curriculum mapping applied correctly
- [ ] Data stored in Supabase without errors
- [ ] Embeddings generated successfully
- [ ] Hybrid search returns relevant results
- [ ] Similar worksheets function works

## Important Notes

1. **Start small**: Always test with 10 worksheets before scaling to hundreds/thousands
2. **Manual review**: Review AI-generated mappings before applying to production
3. **Preserve originals**: Never overwrite UK versions, always create new AU versions
4. **Rate limits**: Vision API limited to 10 req/min, respect limits to avoid errors
5. **Cost management**: Vision API charges per image, monitor usage on large batches
6. **Resume capability**: batch_process.py tracks progress, can resume if interrupted
7. **Error logging**: Check data/batch_errors.log for processing failures
8. **Embeddings**: Use OpenAI embeddings until Anthropic releases native embedding API

## Australian Curriculum Resources

- **ACARA Homepage**: https://www.australiancurriculum.edu.au/
- **Mathematics v9 Curriculum**: https://v9.australiancurriculum.edu.au/f-10-curriculum/learning-areas/mathematics
- **Content Descriptors**: Search by code (e.g., AC9M5N01) in ACARA portal
- **Achievement Standards**: Year-level proficiency descriptions

## Open Questions & Future Work

### State Curriculum Variations
1. Which state to prioritize? (NSW HSC, VIC VCE, QLD QCE, SA SACE, WA WACE)
2. Create separate versions for different states?
3. Store state-specific variations in database?

### Naming Conventions
1. File naming for AU versions: "AU-{topic}-{year}.pdf" or "{topic}-{year}-AU.pdf"?
2. Version numbering for updates?
3. Preserve original UK filenames in metadata?

### Quality Assurance
1. How to verify Vision extraction accuracy at scale?
2. Manual review process for curriculum mappings?
3. Feedback loop for improving extraction prompts?

### Scale & Performance
1. Batch size optimization for Vision API?
2. Parallel processing strategies?
3. Caching strategies for repeated analyses?

### Future Features
1. Generate learning plans automatically based on prerequisites?
2. Recommend worksheet sequences for specific skills?
3. Track student progress through worksheets?
4. Analytics dashboard for worksheet library?
5. API for external integrations?

## Next Steps

1. **Immediate**: Test Vision extraction on sample PDFs
2. **This Week**: Process 50-100 worksheets, validate results
3. **This Month**: Process full catalog, populate ACARA descriptors
4. **Future**: Build search UI, learning plan generator, PDF editing pipeline
