# New Table Architecture: worksheet_extractions

## What Changed

Previously, Vision API extraction data was being pushed directly into the `worksheets` table, which caused conflicts with the existing catalog data imported from CSV. This created duplicate row issues and made it difficult to manage the data.

**New approach:** Vision extraction results now go into a separate `worksheet_extractions` table, keeping catalog metadata and extraction results cleanly separated.

---

## Table Architecture

### `worksheets` (Catalog metadata)
- Master worksheet catalog from CSV/Google Sheets
- Contains: master_id, file_name, dropbox_url, is_free, resource_type, tags, status
- Source: Imported via `import_spreadsheet.py`

### `worksheet_extractions` (Vision API results)
- All Vision API extraction results
- Contains: title, skills, topics, diagrams, content flags, embeddings
- Links to `worksheets` via `file_name`
- Source: Populated via `batch_process.py`

### Combined view: `worksheets_with_extractions`
```sql
-- Join both tables to get full picture
SELECT * FROM worksheets_with_extractions
WHERE au_year_level = 'Year 5'
AND acara_strand = 'Number and Algebra';
```

---

## Migration Applied

**File:** `supabase/migrations/005_worksheet_extractions.sql`

This migration creates:
- ✅ `worksheet_extractions` table with all Vision extraction fields
- ✅ Indexes for fast queries (year level, strand, skills, etc.)
- ✅ Vector index (HNSW) for semantic search
- ✅ `worksheets_with_extractions` view for easy joins
- ✅ `search_extractions_hybrid()` function
- ✅ `find_similar_extractions()` function
- ✅ `extraction_statistics` view

---

## Scripts Updated

### `batch_process.py`
- Now pushes to `worksheet_extractions` instead of `worksheets`
- Removed master_id update logic (no longer needed)
- Uses `file_name` as the linking key

### `generate_embeddings.py`
- Now reads from `worksheet_extractions` instead of `worksheets`
- Generates single content embedding (removed title embedding)
- Updates `embedding_content` column in new table

---

## How to Use

### 1. Apply the migration

In Supabase SQL Editor:
```sql
-- Copy contents of supabase/migrations/005_worksheet_extractions.sql
-- Paste and run
```

### 2. Run batch processing

```bash
# Process PDFs from storage
python scripts/batch_process.py --from-storage --limit 5

# Or process local folder
python scripts/batch_process.py --folder data/input
```

This will now:
- Extract with Vision API
- Store in `worksheet_extractions` table ✅
- No more duplicate row issues ✅

### 3. Generate embeddings

```bash
# Generate for all extractions without embeddings
python scripts/generate_embeddings.py --missing-only

# Check statistics
python scripts/generate_embeddings.py --stats
```

### 4. Query the data

```sql
-- Get all Year 5 fractions worksheets
SELECT * FROM search_extractions_hybrid(
    search_query := 'fractions',
    year_level_filter := 'Year 5',
    limit_results := 10
);

-- Find similar worksheets
SELECT * FROM find_similar_extractions(
    extraction_id_input := '<uuid>',
    limit_results := 5
);

-- Join catalog + extraction data
SELECT
    w.is_free,
    w.resource_type,
    e.title,
    e.skills_covered,
    e.acara_strand
FROM worksheets w
JOIN worksheet_extractions e ON e.file_name = w.file_name
WHERE w.is_free = true;

-- Get extraction statistics
SELECT * FROM extraction_statistics;
```

---

## Benefits

| Issue | Before | After |
|-------|--------|-------|
| **Duplicate rows** | ❌ Vision creates new rows, causing duplicates | ✅ Separate table, no duplicates |
| **Master ID matching** | ❌ Complex logic to find and update existing rows | ✅ Simple: link by file_name |
| **Data corruption risk** | ❌ High - Vision could overwrite catalog data | ✅ None - tables are separate |
| **Schema flexibility** | ❌ Both catalog and extraction share same columns | ✅ Each table has its own schema |
| **Clear separation** | ❌ Mixed responsibilities | ✅ Catalog vs Extraction cleanly split |

---

## Data Flow

```
Master CSV
    ↓
worksheets table (catalog metadata)
    ↑ link by file_name
    ↓
worksheet_extractions (Vision results)
    ↓
embeddings generated
    ↓
searchable via hybrid search
```

---

## Rollback (if needed)

If you need to go back to the old approach:

```sql
DROP VIEW IF EXISTS worksheets_with_extractions;
DROP FUNCTION IF EXISTS search_extractions_hybrid;
DROP FUNCTION IF EXISTS find_similar_extractions;
DROP VIEW IF EXISTS extraction_statistics;
DROP TABLE IF EXISTS worksheet_extractions;
```

Then revert the script changes via git.

---

## Next Steps

1. ✅ Apply migration in Supabase
2. ✅ Test batch processing with 2-3 PDFs
3. ✅ Verify data appears in `worksheet_extractions` table
4. ✅ Generate embeddings for the extractions
5. ✅ Test search functions
6. Scale to full catalog once validated
