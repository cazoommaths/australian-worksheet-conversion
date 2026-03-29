#!/usr/bin/env python3
"""
import_spreadsheet.py - Import worksheet catalog from Cazoom Maths CSV to Supabase

CSV columns expected:
    id, country_code, title, slug, description, content, seo_title, seo_description,
    worksheet_url, answer_url, featured_image, resource_type, resource_sub_type,
    difficulty_level, prerequisite_knowledge, learning_objective, estimated_minutes,
    number_questions, is_free, gcse_tier, target_grade

Usage:
    python scripts/import_spreadsheet.py --csv data/worksheets_catalog.csv
    python scripts/import_spreadsheet.py --csv data/worksheets_catalog.csv --update-existing
    python scripts/import_spreadsheet.py --csv data/worksheets_catalog.csv --limit 10 --dry-run
    python scripts/import_spreadsheet.py --stats
"""

import os
import re
import json
import argparse
from urllib.parse import unquote, urlparse
from typing import Optional

import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()


def strip_html(html: str) -> str:
    """Remove HTML tags from a string."""
    if not html or not isinstance(html, str):
        return ""
    # Remove HTML tags
    clean = re.sub(r'<[^>]+>', '', html)
    # Decode common HTML entities
    clean = clean.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    clean = clean.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    # Collapse whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def extract_storage_path(signed_url: str) -> Optional[str]:
    """
    Extract the storage path from a Supabase signed URL.

    Example URL:
        https://xxx.supabase.co/storage/v1/object/sign/worksheets/Cazoom%20Maths.pdf?token=...
    Returns:
        'worksheets/Cazoom Maths.pdf'
    """
    if not signed_url or not isinstance(signed_url, str):
        return None
    try:
        parsed = urlparse(signed_url)
        # Path looks like /storage/v1/object/sign/worksheets/filename.pdf
        path = parsed.path
        marker = '/object/sign/'
        idx = path.find(marker)
        if idx == -1:
            return None
        storage_path = path[idx + len(marker):]
        return unquote(storage_path)
    except Exception:
        return None


def extract_topic_from_storage_path(storage_path: str) -> Optional[str]:
    """
    Extract topic from Supabase storage path.

    Files follow the pattern: 'worksheets/Cazoom Maths. [Topic]. [Title].pdf'
    Returns the topic portion (second segment after the dot separator).
    """
    if not storage_path:
        return None
    # Remove 'worksheets/' prefix and '.pdf' suffix
    name = os.path.basename(storage_path)
    name = re.sub(r'\.pdf$', '', name, flags=re.IGNORECASE)
    # Split by '. ' to get segments: ['Cazoom Maths', 'Topic', 'Title...']
    parts = name.split('. ')
    if len(parts) >= 3:
        return parts[1].strip()
    elif len(parts) == 2:
        return parts[1].strip()
    return None


def infer_uk_year_level(row: dict) -> Optional[str]:
    """
    Infer UK year level from available CSV fields.

    Priority:
    1. resource_sub_type (e.g. 'KS3_KS4', 'KS2')
    2. gcse_tier (Foundation / Higher → GCSE)
    3. target_grade ranges
    """
    resource_sub = str(row.get('resource_sub_type') or '').strip()
    gcse_tier = str(row.get('gcse_tier') or '').strip()
    target_grade = str(row.get('target_grade') or '').strip()

    # Resource sub-type gives the key stage
    if resource_sub and resource_sub.lower() not in ('nan', ''):
        ks_map = {
            'KS1': 'Year 1/2 (KS1)',
            'KS2': 'Year 3-6 (KS2)',
            'KS3': 'Year 7-9 (KS3)',
            'KS4': 'Year 10/11 (KS4)',
            'KS3_KS4': 'Year 7-11 (KS3/KS4)',
            'KS5': 'Year 12/13 (A-Level)',
        }
        for ks, label in ks_map.items():
            if ks in resource_sub.upper():
                return label

    # GCSE tier implies KS4
    if gcse_tier and gcse_tier.lower() not in ('nan', ''):
        return f'Year 10/11 (GCSE {gcse_tier})'

    return None


def title_to_filename(title: str) -> str:
    """Convert worksheet title to a safe filename."""
    if not title:
        return 'unknown.pdf'
    safe = re.sub(r'[^\w\s\-\(\)]', '', title)
    safe = re.sub(r'\s+', '-', safe.strip())
    if not safe.lower().endswith('.pdf'):
        safe += '.pdf'
    return safe


def is_empty(val) -> bool:
    """Check if a value is empty / NaN."""
    if val is None:
        return True
    if isinstance(val, float):
        import math
        return math.isnan(val)
    return str(val).strip().lower() in ('', 'nan', '__', 'none')


class SpreadsheetImporter:
    """Import Cazoom Maths worksheet catalog from CSV to Supabase."""

    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

        self.supabase: Client = create_client(supabase_url, supabase_key)

    def worksheet_exists(self, worksheet_id: str) -> bool:
        """Check if a worksheet with this UUID already exists."""
        try:
            response = (
                self.supabase.table('worksheets')
                .select('id')
                .eq('id', worksheet_id)
                .execute()
            )
            return bool(response.data)
        except Exception:
            return False

    def build_record(self, row: dict) -> Optional[dict]:
        """
        Build a Supabase worksheets record from a CSV row.

        Returns None if the row should be skipped.
        """
        title = str(row.get('title') or '').strip()
        if not title or title.lower() == 'nan':
            return None

        worksheet_url = str(row.get('worksheet_url') or '').strip()
        answer_url = str(row.get('answer_url') or '').strip()

        storage_path = extract_storage_path(worksheet_url)
        topic = extract_topic_from_storage_path(storage_path)
        uk_year_level = infer_uk_year_level(row)

        # Build prerequisite_skills array from the text field
        prereq_text = str(row.get('prerequisite_knowledge') or '').strip()
        prereq_skills = (
            [s.strip() for s in prereq_text.split('.') if s.strip()]
            if not is_empty(prereq_text)
            else []
        )

        # Build skills_covered array from learning objective
        objective_text = str(row.get('learning_objective') or '').strip()
        skills_covered = (
            [s.strip() for s in objective_text.split('.') if s.strip()]
            if not is_empty(objective_text)
            else []
        )

        # Collect extra metadata into extraction_data JSONB
        extra = {}
        for field in ('country_code', 'slug', 'seo_title', 'seo_description',
                      'featured_image', 'resource_type', 'resource_sub_type',
                      'difficulty_level', 'estimated_minutes', 'number_questions',
                      'is_free', 'gcse_tier', 'target_grade'):
            val = row.get(field)
            if not is_empty(val):
                extra[field] = str(val).strip()

        # Strip HTML from description
        desc_html = str(row.get('description') or '')
        content_html = str(row.get('content') or '')
        description_clean = strip_html(desc_html) or strip_html(content_html)
        if description_clean:
            extra['description'] = description_clean

        # Answer URL stored in extraction_data
        if not is_empty(answer_url):
            extra['answer_url'] = answer_url

        record = {
            'id': str(row.get('id')).strip(),
            'file_name': title_to_filename(title),
            'title': title,
            'storage_path': storage_path,
            'storage_url': worksheet_url if not is_empty(worksheet_url) else None,
            'uk_year_level': uk_year_level,
            'uk_topic': topic,
            'prerequisite_skills': prereq_skills if prereq_skills else None,
            'skills_covered': skills_covered if skills_covered else None,
            'status': 'pending',
            'extraction_data': extra if extra else None,
        }

        return record

    def import_worksheet(self, row: dict, update_existing: bool = False,
                         dry_run: bool = False) -> str:
        """
        Import a single worksheet row.

        Returns: 'imported' | 'updated' | 'skipped' | 'error'
        """
        try:
            record = self.build_record(row)
            if record is None:
                return 'skipped'

            worksheet_id = record.get('id')
            exists = self.worksheet_exists(worksheet_id)

            if exists and not update_existing:
                return 'skipped'

            if dry_run:
                action = 'UPDATE' if exists else 'INSERT'
                print(f"  [DRY-RUN] {action}: {record['title']}")
                print(f"    storage_path : {record.get('storage_path')}")
                print(f"    uk_year_level: {record.get('uk_year_level')}")
                print(f"    uk_topic     : {record.get('uk_topic')}")
                return 'imported'

            if exists:
                self.supabase.table('worksheets').update(record).eq('id', worksheet_id).execute()
                return 'updated'
            else:
                self.supabase.table('worksheets').insert(record).execute()
                return 'imported'

        except Exception as e:
            print(f"  ERROR: {e}")
            return 'error'

    def import_from_csv(self, csv_path: str, update_existing: bool = False,
                        limit: Optional[int] = None, dry_run: bool = False):
        """Import worksheet catalog from CSV file."""
        print(f"Reading catalog from: {csv_path}")
        df = pd.read_csv(csv_path, dtype=str)

        if limit:
            df = df.head(limit)
            print(f"Limiting to first {limit} rows")

        print(f"Found {len(df)} worksheets to process\n")

        counts = {'imported': 0, 'updated': 0, 'skipped': 0, 'error': 0}

        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Importing"):
            row_dict = row.to_dict()
            title = str(row_dict.get('title', '')).strip()
            print(f"\n[{idx + 1}/{len(df)}] {title or '(no title)'}")

            result = self.import_worksheet(row_dict, update_existing, dry_run)
            counts[result] = counts.get(result, 0) + 1

            if result == 'imported':
                print(f"  + Imported")
            elif result == 'updated':
                print(f"  ~ Updated")
            elif result == 'skipped':
                print(f"  - Skipped (already exists)")

        print("\n" + "=" * 60)
        print("IMPORT SUMMARY")
        print("=" * 60)
        print(f"Total rows     : {len(df)}")
        print(f"Imported (new) : {counts['imported']}")
        print(f"Updated        : {counts['updated']}")
        print(f"Skipped        : {counts['skipped']}")
        print(f"Errors         : {counts['error']}")
        if dry_run:
            print("\n[DRY-RUN] No data was written to the database.")
        print("=" * 60)

    def get_import_statistics(self):
        """Display statistics about worksheets in the database."""
        try:
            total = self.supabase.table('worksheets').select('id', count='exact').execute()
            pending = self.supabase.table('worksheets').select('id', count='exact').eq('status', 'pending').execute()
            completed = self.supabase.table('worksheets').select('id', count='exact').eq('status', 'completed').execute()
            error = self.supabase.table('worksheets').select('id', count='exact').eq('status', 'error').execute()

            print("\n" + "=" * 60)
            print("DATABASE STATISTICS")
            print("=" * 60)
            print(f"Total worksheets : {total.count}")
            print(f"  Pending        : {pending.count}")
            print(f"  Completed      : {completed.count}")
            print(f"  Errors         : {error.count}")
            print("=" * 60)

        except Exception as e:
            print(f"Error getting statistics: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Import Cazoom Maths worksheet catalog to Supabase'
    )
    parser.add_argument('--csv', help='Path to CSV file')
    parser.add_argument('--update-existing', action='store_true',
                        help='Overwrite existing records')
    parser.add_argument('--limit', type=int,
                        help='Only import first N rows (useful for testing)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview import without writing to database')
    parser.add_argument('--stats', action='store_true',
                        help='Show database statistics and exit')

    args = parser.parse_args()

    importer = SpreadsheetImporter()

    if args.stats:
        importer.get_import_statistics()
        return

    if not args.csv:
        parser.error("--csv is required unless using --stats")

    importer.import_from_csv(
        args.csv,
        update_existing=args.update_existing,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    importer.get_import_statistics()


if __name__ == '__main__':
    main()
