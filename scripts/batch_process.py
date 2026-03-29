#!/usr/bin/env python3
"""
batch_process.py - Full pipeline orchestration for worksheet intelligence platform

This script orchestrates the complete workflow:
1. Fetch PDFs from Supabase Storage (via fetch_from_storage.py)
2. Extract with Vision API
3. Store results in Supabase worksheet_extractions table
4. Apply AU curriculum mapping
5. Generate embeddings
6. Log progress and handle errors

Features:
- Resume from where it left off
- Comprehensive error logging
- Progress tracking
- Dry-run mode

Usage:
    # Download from storage then process
    python scripts/batch_process.py --from-storage --limit 5

    # Process PDFs already in data/input
    python scripts/batch_process.py --folder data/input

    # Dry run (no database writes)
    python scripts/batch_process.py --folder data/input --dry-run

    # Resume interrupted run
    python scripts/batch_process.py --resume

    # Reset progress tracking
    python scripts/batch_process.py --reset
"""

import os
import json
import csv
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import time

import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv
from tqdm import tqdm

# Import our other modules
from extract_with_vision import VisionExtractor
from generate_embeddings import EmbeddingGenerator
from fetch_from_storage import fetch_worksheets

# Load environment variables
load_dotenv()

# Constants
PROGRESS_FILE = "data/batch_progress.json"
ERROR_LOG_FILE = "data/batch_errors.log"


class BatchProcessor:
    """Orchestrate the full worksheet processing pipeline."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if supabase_url and supabase_key:
            self.supabase: Client = create_client(supabase_url, supabase_key)
            self.has_supabase = True
        else:
            print("Warning: Supabase credentials not found. Running in file-only mode.")
            self.supabase = None
            self.has_supabase = False

        # Initialize extractors
        self.vision_extractor = VisionExtractor()
        if self.has_supabase:
            self.embedding_generator = EmbeddingGenerator()

        # Load curriculum mapping configs
        self.load_configs()

        # Load progress tracking
        self.progress = self.load_progress()

    def load_configs(self):
        """Load curriculum mapping and terminology configs."""
        config_dir = Path(__file__).parent.parent / "config"

        # Load terminology
        terminology_path = config_dir / "terminology.json"
        if terminology_path.exists():
            with open(terminology_path, 'r') as f:
                self.terminology_config = json.load(f)
        else:
            self.terminology_config = {}

        # Load curriculum mapping
        curriculum_path = config_dir / "au_curriculum_mapping.json"
        if curriculum_path.exists():
            with open(curriculum_path, 'r') as f:
                self.curriculum_config = json.load(f)
        else:
            self.curriculum_config = {}

    def load_progress(self) -> Dict:
        """Load progress from previous run."""
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                return json.load(f)
        return {
            "processed": [],
            "errors": [],
            "last_run": None,
            "status": "not_started"
        }

    def save_progress(self):
        """Save current progress."""
        self.progress["last_run"] = datetime.now().isoformat()
        os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(self.progress, f, indent=2)

    def log_error(self, worksheet_name: str, error: str):
        """Log an error to file."""
        os.makedirs(os.path.dirname(ERROR_LOG_FILE), exist_ok=True)
        with open(ERROR_LOG_FILE, 'a') as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] {worksheet_name}: {error}\n")
        self.progress["errors"].append({
            "worksheet": worksheet_name,
            "error": error,
            "timestamp": timestamp
        })

    def apply_au_curriculum_mapping(self, extraction_data: Dict) -> Dict:
        """
        Apply Australian curriculum mapping to extracted data.

        Uses the config files to map UK year levels and topics to AU equivalents.
        """
        au_data = {}

        # Map year level
        uk_year = extraction_data.get('year_level')
        if uk_year and 'year_level_mapping' in self.curriculum_config:
            au_data['au_year_level'] = self.curriculum_config['year_level_mapping'].get(uk_year, uk_year)
        elif uk_year and 'key_stage_mapping' in self.curriculum_config:
            au_data['au_year_level'] = self.curriculum_config['key_stage_mapping'].get(uk_year, uk_year)

        # Map topic
        uk_topic = extraction_data.get('topic')
        if uk_topic and 'topic_mapping' in self.curriculum_config:
            au_data['au_topic'] = self.curriculum_config['topic_mapping'].get(uk_topic, uk_topic)
        else:
            au_data['au_topic'] = uk_topic

        # Keep subtopic as-is for now
        au_data['au_subtopic'] = extraction_data.get('subtopic')

        # Strand is already in extraction data from Vision API
        au_data['acara_strand'] = extraction_data.get('strand')

        # Find UK-specific elements for localization
        uk_elements = extraction_data.get('uk_specific_elements', {})
        au_data['uk_specific_elements'] = uk_elements

        return au_data

    def store_in_supabase(self, worksheet_data: Dict) -> Optional[str]:
        """
        Store worksheet extraction data in Supabase worksheet_extractions table.

        Returns the extraction ID if successful, None otherwise.
        """
        if not self.has_supabase or self.dry_run:
            print("  [DRY RUN] Would store in Supabase")
            return None

        try:
            # Prepare data for insertion into worksheet_extractions
            content_flags = worksheet_data.get('content_flags', {}) or {}
            diagram_inv   = worksheet_data.get('diagram_inventory', {}) or {}

            insert_data = {
                'file_name': worksheet_data['file_name'],
                'title': worksheet_data.get('title'),

                # UK identifiers
                'uk_year_level': worksheet_data.get('year_level'),
                'uk_topic': worksheet_data.get('topic'),
                'uk_subtopic': worksheet_data.get('subtopic'),

                # AU mapping
                'au_year_level': worksheet_data.get('au_year_level'),
                'acara_strand': worksheet_data.get('acara_strand'),

                # Extracted content
                'extraction_data': worksheet_data.get('extraction_data', {}),
                'skills_covered': worksheet_data.get('skills_covered', []),
                'prerequisite_skills': worksheet_data.get('prerequisite_skills', []),
                'sections': worksheet_data.get('sections', []),
                'difficulty_progression': worksheet_data.get('difficulty_progression'),
                'diagram_inventory': diagram_inv,

                # Worksheet characteristics
                'total_questions': worksheet_data.get('total_questions'),
                'estimated_time_minutes': worksheet_data.get('estimated_time_minutes'),
                'difficulty_level': worksheet_data.get('difficulty_level'),

                # Content flags
                'has_diagrams': (diagram_inv.get('count', 0) or 0) > 0,
                'has_word_problems': content_flags.get('has_word_problems', False),
                'has_worked_examples': content_flags.get('has_worked_examples', False),
                'has_real_world_context': content_flags.get('has_real_world_context', False),
                'has_multi_step_problems': content_flags.get('has_multi_step_problems', False),
                'has_equations': worksheet_data.get('has_equations', False),
                'equation_types': worksheet_data.get('equation_types', []),

                # Localization needs
                'uk_specific_elements': worksheet_data.get('uk_specific_elements', {}),

                # Additional content flags (store full flags object)
                'content_flags': content_flags,

                # Extraction metadata
                'extraction_method': 'claude_vision',
                'model_version': worksheet_data.get('model', 'claude-sonnet-4-20250514'),
                'extraction_confidence': None,  # Can add confidence scoring later
                'extracted_at': datetime.now().isoformat()
            }

            # Check if we already have an extraction for this file (update if exists)
            existing = self.supabase.table('worksheet_extractions') \
                .select('id') \
                .eq('file_name', worksheet_data['file_name']) \
                .limit(1) \
                .execute()

            if existing.data:
                # Update existing extraction
                extraction_id = existing.data[0]['id']
                self.supabase.table('worksheet_extractions') \
                    .update(insert_data) \
                    .eq('id', extraction_id) \
                    .execute()
                print(f"  ✓ Updated extraction (ID: {extraction_id})")
                return extraction_id
            else:
                # Insert new extraction
                response = self.supabase.table('worksheet_extractions').insert(insert_data).execute()
                extraction_id = response.data[0]['id']
                print(f"  ✓ Stored extraction (ID: {extraction_id})")
                return extraction_id

        except Exception as e:
            print(f"  ✗ Supabase error: {e}")
            self.log_error(worksheet_data['file_name'], f"Supabase storage error: {e}")
            return None

    def process_worksheet(self, pdf_path: str, worksheet_info: Optional[Dict] = None) -> bool:
        """
        Process a single worksheet through the complete pipeline.

        Args:
            pdf_path: Path to PDF file
            worksheet_info: Optional metadata from CSV (name, topic, etc.)

        Returns:
            True if successful, False otherwise
        """
        file_name = os.path.basename(pdf_path)

        # Check if already processed
        if file_name in self.progress['processed']:
            print(f"  ⊘ Skipping (already processed)")
            return True

        print(f"\n{'='*70}")
        print(f"Processing: {file_name}")
        print(f"{'='*70}")

        try:
            # Step 1: Extract with Vision API
            print("Step 1: Vision API extraction")
            extraction_result = self.vision_extractor.extract_from_pdf(pdf_path)

            if 'error' in extraction_result:
                raise Exception(f"Vision extraction error: {extraction_result['error']}")

            # Step 2: Apply AU curriculum mapping
            print("Step 2: Applying AU curriculum mapping")
            au_mapping = self.apply_au_curriculum_mapping(extraction_result)

            # Merge AU mapping into extraction result
            worksheet_data = {**extraction_result, **au_mapping}
            worksheet_data['file_name'] = file_name
            worksheet_data['file_path'] = pdf_path

            # Add CSV metadata if available
            if worksheet_info:
                worksheet_data['dropbox_url'] = worksheet_info.get('dropbox_link')
                # CSV data can override extraction if more accurate
                if not worksheet_data.get('uk_year_level'):
                    worksheet_data['uk_year_level'] = worksheet_info.get('uk_year_level')
                if not worksheet_data.get('uk_topic'):
                    worksheet_data['uk_topic'] = worksheet_info.get('topic')

            # Step 3: Store in Supabase
            print("Step 3: Storing in database")
            worksheet_id = self.store_in_supabase(worksheet_data)

            # Step 4: Generate embeddings (if stored successfully)
            if worksheet_id and self.has_supabase and not self.dry_run:
                print("Step 4: Generating embeddings")
                try:
                    self.embedding_generator.process_worksheet(worksheet_id)
                except Exception as e:
                    print(f"  ⚠ Embedding generation failed: {e}")
                    # Don't fail the whole process if just embeddings fail
            elif self.dry_run:
                print("Step 4: [DRY RUN] Would generate embeddings")

            # Mark as processed
            self.progress['processed'].append(file_name)
            self.save_progress()

            print(f"✓ Successfully processed {file_name}")
            return True

        except Exception as e:
            print(f"✗ Error processing {file_name}: {e}")
            self.log_error(file_name, str(e))
            return False

    def process_from_storage(self, limit: Optional[int] = None, folder: str = ""):
        """
        Fetch PDFs from Supabase Storage then process them all.

        Args:
            limit: Optional cap on number of files to fetch and process
            folder: Sub-folder within the storage bucket
        """
        print("\nFetching PDFs from Supabase Storage...")
        fetch_worksheets(limit=limit, folder=folder)

        # Now process whatever landed in data/input
        self.process_folder('data/input', limit=limit)

    def process_folder(self, folder_path: str, limit: Optional[int] = None):
        """
        Process all PDFs in a folder.

        Args:
            folder_path: Path to folder containing PDFs
            limit: Optional limit on number to process
        """
        folder = Path(folder_path)
        pdf_files = sorted(list(folder.glob('*.pdf')) + list(folder.glob('*.PDF')))

        if limit:
            pdf_files = pdf_files[:limit]

        if not pdf_files:
            print(f"No PDF files found in {folder_path}")
            return

        print(f"Found {len(pdf_files)} PDF files to process\n")

        success_count = 0
        error_count = 0

        for pdf_path in pdf_files:
            success = self.process_worksheet(str(pdf_path))
            if success:
                success_count += 1
            else:
                error_count += 1

        # Final summary
        print("\n" + "="*70)
        print("BATCH PROCESSING SUMMARY")
        print("="*70)
        print(f"Total worksheets: {len(pdf_files)}")
        print(f"Successfully processed: {success_count}")
        print(f"Errors: {error_count}")
        print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Batch process worksheets through the intelligence platform pipeline'
    )

    # Input sources (mutually exclusive)
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        '--from-storage',
        action='store_true',
        help='Fetch PDFs from Supabase Storage then process (default if no source given)'
    )
    source_group.add_argument(
        '--folder',
        metavar='PATH',
        help='Process PDFs already in a local folder (default: data/input)'
    )

    # Options
    parser.add_argument('--limit', type=int, help='Limit number of worksheets to process')
    parser.add_argument('--storage-folder', default='', help='Sub-folder within storage bucket')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    parser.add_argument('--dry-run', action='store_true', help='Dry run - do not write to database')
    parser.add_argument('--reset', action='store_true', help='Reset progress tracking')

    args = parser.parse_args()

    # Reset progress if requested
    if args.reset:
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            print("Progress reset")
        return

    # Initialize processor
    processor = BatchProcessor(dry_run=args.dry_run)

    if args.dry_run:
        print("⚠ DRY RUN MODE - No database writes will occur\n")

    # Process based on input source
    if args.folder:
        processor.process_folder(args.folder, limit=args.limit)
    else:
        # Default: fetch from Supabase Storage then process
        processor.process_from_storage(limit=args.limit, folder=args.storage_folder)


if __name__ == '__main__':
    main()
