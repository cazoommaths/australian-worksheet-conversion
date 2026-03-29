#!/usr/bin/env python3
"""
import_from_master_csv.py - Import the master cazoommaths.com worksheets table into Supabase

This script reads the exported CSV from the original UK master worksheet database,
pre-populates the new Supabase worksheets table with all available metadata, and
marks each record as pending Vision API extraction.

The master CSV columns used:
    id, title, description, content, learning_objective, prerequisite_knowledge,
    worksheet_url, answer_url, featured_image, resource_type, gcse_tier,
    target_grade, is_free, wp_id, legacy_id, url, status, created_at

Usage:
    # Import all records
    python scripts/import_from_master_csv.py --csv path/to/master_export.csv

    # Dry run (preview without writing)
    python scripts/import_from_master_csv.py --csv path/to/master_export.csv --dry-run

    # Limit to first N rows (for testing)
    python scripts/import_from_master_csv.py --csv path/to/master_export.csv --limit 20

    # Update existing records (match by master_id)
    python scripts/import_from_master_csv.py --csv path/to/master_export.csv --update-existing

    # Show stats for what's already in Supabase
    python scripts/import_from_master_csv.py --stats
"""

import os
import re
import json
import argparse
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse, parse_qs

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ─── Key stage / resource type mapping ────────────────────────────────────────

RESOURCE_TYPE_TO_UK_YEAR = {
    "KS1":      "KS1 (Years 1-2)",
    "KS2":      "KS2 (Years 3-6)",
    "KS1_KS2":  "KS1/KS2 (Years 1-6)",
    "KS3":      "KS3 (Years 7-9)",
    "KS4":      "KS4 (Years 10-11)",
    "KS3_KS4":  "KS3/KS4 (Years 7-11)",
    "KS5":      "KS5 / A-Level (Years 12-13)",
    "Primary":  "Primary (Years 1-6)",
    "Secondary":"Secondary (Years 7-11)",
}

RESOURCE_TYPE_TO_AU_YEAR = {
    "KS1":      "Years 1-2",
    "KS2":      "Years 3-6",
    "KS1_KS2":  "Years 1-6",
    "KS3":      "Years 7-9",
    "KS4":      "Years 10-11",
    "KS3_KS4":  "Years 7-11",
    "KS5":      "Year 12",
    "Primary":  "Years 1-6",
    "Secondary":"Years 7-11",
}

# GCSE tier → difficulty_level
GCSE_TIER_TO_DIFFICULTY = {
    "Foundation": "foundation",
    "Higher":     "higher",
    "Both":       "mixed",
}

# ─── URL parsing ──────────────────────────────────────────────────────────────

def parse_topic_from_url(worksheet_url: str) -> tuple[str, str]:
    """
    Extract topic and subtopic from the s2member download URL path.

    Example URL:
      https://www.cazoommaths.com/?s2member_file_download=access-s2member-ccap-secondary/
      Secondary%20School%20Resources/Number/Fractions/Using-the-Fraction-Wall/...

    Returns (topic, subtopic) e.g. ("Number", "Fractions")
    """
    if not worksheet_url or not isinstance(worksheet_url, str):
        return ("", "")

    try:
        parsed = urlparse(worksheet_url)
        qs = parse_qs(parsed.query)

        # s2member path
        s2path = qs.get("s2member_file_download", [""])[0]
        if s2path:
            path = unquote(s2path)
            # Strip leading prefix up to first known root folder
            for prefix in ["access-s2member-ccap-secondary/", "access-s2member-ccap-primary/"]:
                if prefix in path:
                    path = path.split(prefix, 1)[1]
                    break

            parts = [p for p in path.split("/") if p]
            # Typical structure: Resources/Topic/Subtopic/Filename
            # Strip generic folder names
            skip = {"Secondary School Resources", "Primary School Resources",
                    "Maths Resources", "Resources", "GCSE", "A Level"}
            clean = [p for p in parts[:-1] if p not in skip]  # exclude filename
            topic    = clean[0] if len(clean) > 0 else ""
            subtopic = clean[1] if len(clean) > 1 else ""
            return (topic, subtopic)

        # Fallback: parse from page URL slug
        # e.g. /maths-worksheet/adding-fractions-same-denominator-worksheet/
        page_path = parsed.path.strip("/")
        slug_parts = page_path.split("/")
        if len(slug_parts) >= 2:
            slug = slug_parts[-1].replace("-worksheet", "").replace("-", " ").title()
            return ("", slug)

    except Exception:
        pass

    return ("", "")


def strip_html(html: str) -> str:
    """Remove HTML tags from a string."""
    if not html or not isinstance(html, str):
        return ""
    clean = re.sub(r"<[^>]+>", " ", html)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def safe_bool(value) -> bool:
    """Parse various truthy representations."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "t")
    return bool(value)


# ─── Main importer ────────────────────────────────────────────────────────────

class MasterCSVImporter:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
            sys.exit(1)

        self.supabase: Client = create_client(supabase_url, supabase_key)

    def build_record(self, row: pd.Series) -> dict:
        """Convert one CSV row into a Supabase worksheets insert dict."""

        worksheet_url = row.get("worksheet_url", "") or row.get("worksheet_url_backup", "") or ""
        answer_url    = row.get("answer_url", "")    or row.get("answer_url_backup", "")    or ""
        resource_type = str(row.get("resource_type", "") or "").strip()
        gcse_tier     = str(row.get("gcse_tier", "") or "").strip()

        # Topic / subtopic from URL path
        topic, subtopic = parse_topic_from_url(str(worksheet_url))

        # File name derived from worksheet URL path (last segment)
        file_name = ""
        if worksheet_url:
            try:
                parsed = urlparse(str(worksheet_url))
                qs = parse_qs(parsed.query)
                s2path = qs.get("s2member_file_download", [""])[0]
                if s2path:
                    file_name = unquote(s2path).split("/")[-1]
            except Exception:
                pass
        if not file_name:
            file_name = str(row.get("title", "unknown")).strip()[:100] + ".pdf"

        # Difficulty level from GCSE tier
        difficulty_level = GCSE_TIER_TO_DIFFICULTY.get(gcse_tier, None)

        # UK year level from resource_type
        uk_year_level = RESOURCE_TYPE_TO_UK_YEAR.get(resource_type, resource_type or None)
        au_year_level = RESOURCE_TYPE_TO_AU_YEAR.get(resource_type, None)

        # Prerequisite skills as array (split on full stop or semicolon)
        prereq_text = str(row.get("prerequisite_knowledge", "") or "").strip()
        prereq_skills = [s.strip() for s in re.split(r"[.;]", prereq_text) if s.strip()] if prereq_text else []

        record = {
            # Master table cross-reference
            "master_id":             str(row.get("id", "") or "").strip() or None,
            "wp_id":                 str(row.get("wp_id", "") or "").strip() or None,
            "legacy_id":             str(row.get("legacy_id", "") or "").strip() or None,

            # Core metadata
            "file_name":             file_name,
            "title":                 str(row.get("title", "") or "").strip() or None,
            "description":           strip_html(str(row.get("description", "") or "")),
            "learning_objective":    str(row.get("learning_objective", "") or "").strip() or None,
            "prerequisite_knowledge":prereq_text or None,
            "prerequisite_skills":   prereq_skills,

            # UK curriculum
            "uk_year_level":         uk_year_level,
            "uk_topic":              topic or None,
            "uk_subtopic":           subtopic or None,
            "resource_type":         resource_type or None,
            "gcse_tier":             gcse_tier or None,
            "target_grade":          str(row.get("target_grade", "") or "").strip() or None,

            # AU curriculum (broad mapping from resource_type; Vision will refine)
            "au_year_level":         au_year_level,

            # URLs
            "worksheet_download_url": str(worksheet_url).strip() or None,
            "answer_download_url":   str(answer_url).strip() or None,
            "master_url":            str(row.get("url", "") or "").strip() or None,
            "featured_image_url":    str(row.get("featured_image", "") or "").strip() or None,

            # Flags
            "is_free":               safe_bool(row.get("is_free", False)),
            "difficulty_level":      difficulty_level,

            # Status
            "master_status":         str(row.get("status", "") or "").strip() or None,
            "status":                "pending",        # Needs Vision extraction
            "extraction_method":     None,
        }

        return record

    def get_existing_master_ids(self) -> set:
        """Fetch all master_id values already in the database."""
        response = self.supabase.table("worksheets") \
            .select("master_id") \
            .not_.is_("master_id", "null") \
            .execute()
        return {row["master_id"] for row in response.data if row.get("master_id")}

    def import_csv(self, csv_path: str, limit: Optional[int] = None,
                   update_existing: bool = False) -> None:
        print(f"\nReading CSV: {csv_path}")
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        print(f"Rows in CSV: {len(df)}")

        if limit:
            df = df.head(limit)
            print(f"Limited to first {limit} rows")

        # Only import published records (skip drafts)
        if "status" in df.columns:
            published = df[df["status"] == "published"]
            skipped   = len(df) - len(published)
            if skipped:
                print(f"Skipping {skipped} non-published records")
            df = published

        print(f"Records to process: {len(df)}")

        if not self.dry_run:
            existing_ids = self.get_existing_master_ids()
            print(f"Already in Supabase: {len(existing_ids)} records")
        else:
            existing_ids = set()

        inserted = 0
        updated  = 0
        skipped  = 0
        errors   = 0

        for idx, row in df.iterrows():
            master_id = str(row.get("id", "") or "").strip()
            title     = str(row.get("title", "") or "").strip()[:60]

            try:
                record = self.build_record(row)

                if master_id in existing_ids:
                    if update_existing:
                        if not self.dry_run:
                            self.supabase.table("worksheets") \
                                .update(record) \
                                .eq("master_id", master_id) \
                                .execute()
                        print(f"  [UPDATE] {title}")
                        updated += 1
                    else:
                        skipped += 1
                        continue
                else:
                    if not self.dry_run:
                        self.supabase.table("worksheets").insert(record).execute()
                    print(f"  [INSERT] {title}")
                    inserted += 1

            except Exception as e:
                print(f"  [ERROR]  {title}: {e}")
                errors += 1

        print(f"\n{'='*60}")
        print(f"IMPORT COMPLETE")
        print(f"  Inserted : {inserted}")
        print(f"  Updated  : {updated}")
        print(f"  Skipped  : {skipped}  (already exist, use --update-existing to overwrite)")
        print(f"  Errors   : {errors}")
        if self.dry_run:
            print("  [DRY RUN - nothing was written to the database]")
        print(f"{'='*60}")

    def show_stats(self):
        """Print a summary of what's currently in the worksheets table."""
        total = self.supabase.table("worksheets").select("id", count="exact").execute()
        pending = self.supabase.table("worksheets").select("id", count="exact") \
            .eq("status", "pending").execute()
        completed = self.supabase.table("worksheets").select("id", count="exact") \
            .eq("status", "completed").execute()

        print("\nWorksheets table stats:")
        print(f"  Total:     {total.count}")
        print(f"  Pending:   {pending.count}  (needs Vision extraction)")
        print(f"  Completed: {completed.count} (Vision extraction done)")

        # By resource type
        print("\nBreakdown by resource_type:")
        rows = self.supabase.table("worksheets").select("resource_type").execute()
        from collections import Counter
        counts = Counter(r["resource_type"] or "unknown" for r in rows.data)
        for rt, n in sorted(counts.items(), key=lambda x: -x[1]):
            print(f"  {rt:<20} {n}")


def main():
    parser = argparse.ArgumentParser(
        description="Import master cazoommaths.com worksheet CSV into Supabase"
    )
    parser.add_argument("--csv",              help="Path to the exported master CSV file")
    parser.add_argument("--limit",  type=int, help="Limit to first N rows (for testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview import without writing to database")
    parser.add_argument("--update-existing", action="store_true",
                        help="Update records that already exist (match by master_id)")
    parser.add_argument("--stats", action="store_true",
                        help="Show current database stats and exit")

    args = parser.parse_args()

    importer = MasterCSVImporter(dry_run=args.dry_run)

    if args.stats:
        importer.show_stats()
        return

    if not args.csv:
        print("ERROR: --csv is required (unless using --stats)")
        parser.print_help()
        sys.exit(1)

    if not Path(args.csv).exists():
        print(f"ERROR: File not found: {args.csv}")
        sys.exit(1)

    if args.dry_run:
        print("DRY RUN MODE — no database writes will occur\n")

    importer.import_csv(
        csv_path=args.csv,
        limit=args.limit,
        update_existing=args.update_existing,
    )


if __name__ == "__main__":
    main()
