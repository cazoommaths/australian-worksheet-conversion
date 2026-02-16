#!/usr/bin/env python3
"""
import_spreadsheet.py - Import worksheet catalog from spreadsheet to Supabase

Import worksheet metadata from CSV or Google Sheets into the Supabase database.
Useful for bootstrapping the database with existing catalog data.

Usage:
    python scripts/import_spreadsheet.py --csv data/worksheets_SAMPLE.csv
    python scripts/import_spreadsheet.py --csv data/full_catalog.csv --update-existing
"""

import os
import argparse
from typing import Dict, Optional
from datetime import datetime

import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()


class SpreadsheetImporter:
    """Import worksheet catalog from spreadsheets to Supabase."""

    def __init__(self):
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

        self.supabase: Client = create_client(supabase_url, supabase_key)

    def sanitize_filename(self, name: str) -> str:
        """Convert worksheet name to a safe filename."""
        safe = name.replace(' ', '-').replace('/', '-').replace('\\', '-')
        safe = safe.replace(':', '').replace('?', '').replace('*', '')
        safe = safe.replace('"', '').replace('<', '').replace('>', '').replace('|', '')

        if not safe.lower().endswith('.pdf'):
            safe += '.pdf'

        return safe

    def worksheet_exists(self, file_name: str) -> Optional[str]:
        """
        Check if worksheet already exists in database.

        Returns worksheet ID if exists, None otherwise.
        """
        try:
            response = self.supabase.table('worksheets').select('id').eq('file_name', file_name).execute()
            if response.data and len(response.data) > 0:
                return response.data[0]['id']
            return None
        except Exception:
            return None

    def import_worksheet(self, row: Dict, update_existing: bool = False) -> bool:
        """
        Import a single worksheet from spreadsheet row.

        Args:
            row: Dictionary with worksheet metadata
            update_existing: If True, update existing worksheets

        Returns:
            True if successful, False otherwise
        """
        try:
            # Extract data from row
            worksheet_name = row.get('worksheet_name', '')
            if not worksheet_name:
                print("  ⊘ Skipping (no name)")
                return False

            file_name = self.sanitize_filename(worksheet_name)

            # Check if exists
            existing_id = self.worksheet_exists(file_name)
            if existing_id and not update_existing:
                print(f"  ⊘ Skipping {file_name} (already exists)")
                return False

            # Prepare data
            data = {
                'file_name': file_name,
                'dropbox_url': row.get('dropbox_link'),
                'uk_year_level': row.get('uk_year_level'),
                'uk_topic': row.get('topic'),
                'uk_subtopic': row.get('subtopic'),
                'status': 'pending',  # Mark as pending for processing
                'extraction_method': None,
            }

            # Insert or update
            if existing_id:
                # Update existing
                self.supabase.table('worksheets').update(data).eq('id', existing_id).execute()
                print(f"  ✓ Updated {file_name}")
            else:
                # Insert new
                self.supabase.table('worksheets').insert(data).execute()
                print(f"  ✓ Imported {file_name}")

            return True

        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False

    def import_from_csv(self, csv_path: str, update_existing: bool = False,
                       limit: Optional[int] = None):
        """
        Import worksheet catalog from CSV file.

        Args:
            csv_path: Path to CSV file
            update_existing: If True, update existing worksheets
            limit: Optional limit on number to import
        """
        print(f"Reading worksheet catalog from: {csv_path}")
        df = pd.read_csv(csv_path)

        if limit:
            df = df.head(limit)
            print(f"Limiting to first {limit} worksheets")

        print(f"Found {len(df)} worksheets to import\n")

        success_count = 0
        skip_count = 0
        error_count = 0

        for idx, row in tqdm(df.iterrows(), total=len(df), desc="Importing"):
            row_dict = row.to_dict()
            worksheet_name = row_dict.get('worksheet_name', f"Row {idx}")

            print(f"\n[{idx + 1}/{len(df)}] {worksheet_name}")

            # Check if exists first
            file_name = self.sanitize_filename(worksheet_name)
            exists = self.worksheet_exists(file_name)

            if exists and not update_existing:
                skip_count += 1
                continue

            success = self.import_worksheet(row_dict, update_existing)

            if success:
                success_count += 1
            else:
                error_count += 1

        # Summary
        print("\n" + "="*70)
        print("IMPORT SUMMARY")
        print("="*70)
        print(f"Total rows: {len(df)}")
        print(f"Successfully imported/updated: {success_count}")
        print(f"Skipped (already exist): {skip_count}")
        print(f"Errors: {error_count}")
        print("="*70)

    def get_import_statistics(self):
        """Display statistics about imported worksheets."""
        try:
            # Total worksheets
            total = self.supabase.table('worksheets').select('id', count='exact').execute()
            total_count = total.count

            # By status
            pending = self.supabase.table('worksheets').select('id', count='exact').eq('status', 'pending').execute()
            completed = self.supabase.table('worksheets').select('id', count='exact').eq('status', 'completed').execute()
            processing = self.supabase.table('worksheets').select('id', count='exact').eq('status', 'processing').execute()
            error = self.supabase.table('worksheets').select('id', count='exact').eq('status', 'error').execute()

            print("\n" + "="*70)
            print("DATABASE STATISTICS")
            print("="*70)
            print(f"Total worksheets: {total_count}")
            print(f"  Pending processing: {pending.count}")
            print(f"  Currently processing: {processing.count}")
            print(f"  Completed: {completed.count}")
            print(f"  Errors: {error.count}")
            print("="*70)

        except Exception as e:
            print(f"Error getting statistics: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='Import worksheet catalog from spreadsheet to Supabase'
    )
    parser.add_argument(
        '--csv',
        required=True,
        help='CSV file with worksheet catalog'
    )
    parser.add_argument(
        '--update-existing',
        action='store_true',
        help='Update worksheets that already exist in database'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of worksheets to import'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show database statistics'
    )

    args = parser.parse_args()

    importer = SpreadsheetImporter()

    if args.stats:
        importer.get_import_statistics()
    else:
        importer.import_from_csv(
            args.csv,
            update_existing=args.update_existing,
            limit=args.limit
        )
        # Show stats after import
        importer.get_import_statistics()


if __name__ == '__main__':
    main()
