# Cazoom Maths: UK to Australian Curriculum Converter

## Project Overview

This project converts UK curriculum maths worksheets to Australian curriculum format. Cazoom Maths has thousands of PDF worksheets created for the UK education system that need to be adapted for Australian schools.

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

## Data Sources

### Primary: Google Sheets
- Contains worksheet catalogue with: Name, UK Year Level, Topic, Subtopic, Dropbox Link
- Export as CSV for processing

### Secondary: Supabase Database
- Table: `worksheets` (or similar)
- Contains comprehensive worksheet metadata
- Use for production, not initial testing

### File Storage: Dropbox
- All PDF worksheets stored here
- Download via Dropbox API or direct links

## Project Phases

### Phase 1: Extract & Analyse (Current)
1. Download worksheet catalogue from Google Sheets
2. Download sample PDFs from Dropbox (10 worksheets for testing)
3. Extract text and metadata from PDFs
4. Generate mapping report (what needs to change)

### Phase 2: AI Curriculum Mapping
1. Use Claude API to analyse each worksheet
2. Map UK curriculum to Australian ACARA standards
3. Generate specific edit instructions for each PDF
4. Create terminology replacement list

### Phase 3: PDF Editing (Future)
1. Apply text changes to PDFs
2. Update headers/footers with Australian branding
3. Save new versions with "AU" prefix
4. Quality check output

## File Structure

```
cazoom-au-converter/
├── CLAUDE.md                    # This file - project instructions
├── config/
│   ├── au_curriculum_mapping.json   # UK → AU grade/topic mappings
│   └── terminology.json             # Word/phrase replacements
├── scripts/
│   ├── download_worksheets.py       # Download from Dropbox
│   ├── extract_pdf_info.py          # Extract text from PDFs
│   ├── map_curriculum.py            # Apply UK→AU mapping
│   └── generate_report.py           # Create edit report
├── data/
│   ├── input/                       # Downloaded UK PDFs
│   ├── output/                      # Converted AU PDFs
│   ├── worksheets.csv               # Catalogue from Google Sheets
│   └── mapping_report.csv           # Generated edit instructions
└── requirements.txt
```

## Commands for Claude Code

### Setup
```bash
# Install dependencies
pip install pandas openpyxl PyMuPDF requests python-dotenv

# Create directory structure
mkdir -p data/input data/output config scripts
```

### Download Worksheets
```bash
python scripts/download_worksheets.py --csv data/worksheets.csv --limit 10
```

### Extract PDF Information
```bash
python scripts/extract_pdf_info.py --input data/input --output data/extracted_info.csv
```

### Generate Mapping Report
```bash
python scripts/map_curriculum.py --input data/extracted_info.csv --output data/mapping_report.csv
```

## Environment Variables Needed

Create a `.env` file with:
```
DROPBOX_ACCESS_TOKEN=your_token_here
ANTHROPIC_API_KEY=your_key_here  # For AI curriculum mapping
```

## Important Notes

1. **Start small**: Test with 10 worksheets before scaling
2. **Manual review**: Always review AI-generated mappings before applying
3. **Preserve originals**: Never overwrite UK versions
4. **Version control**: Track all changes made

## Australian Curriculum Resources

- ACARA: https://www.australiancurriculum.edu.au/
- Mathematics curriculum: https://v9.australiancurriculum.edu.au/f-10-curriculum/learning-areas/mathematics

## Questions to Resolve

1. Which state curriculum to prioritise? (NSW, VIC, QLD have slight variations)
2. Should we create separate versions for different states?
3. What's the naming convention for Australian versions? (e.g., "AU - Fractions Year 5")
