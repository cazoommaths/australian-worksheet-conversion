#!/usr/bin/env python3
"""
generate_embeddings.py - Generate vector embeddings for semantic search

This script creates embeddings for worksheet content using Claude API's
text embeddings, enabling semantic similarity search in the database.

Features:
- Generate embeddings for title and content separately
- Batch processing with progress tracking
- Update Supabase database with embeddings
- Resume capability for interrupted runs

Usage:
    python scripts/generate_embeddings.py --all
    python scripts/generate_embeddings.py --worksheet-id <uuid>
    python scripts/generate_embeddings.py --missing-only
"""

import os
import json
import argparse
from typing import List, Optional, Dict
from datetime import datetime

from anthropic import Anthropic
from supabase import create_client, Client
from dotenv import load_dotenv
from tqdm import tqdm
import time

# Load environment variables
load_dotenv()

# Constants
EMBEDDING_MODEL = "voyage-3"  # Anthropic's recommended embedding model
EMBEDDING_DIMENSION = 1024
BATCH_SIZE = 10  # Process 10 worksheets at a time
RATE_LIMIT_DELAY = 0.5  # Delay between API calls (seconds)


class EmbeddingGenerator:
    """Generate and store embeddings for worksheets."""

    def __init__(self):
        # Initialize Anthropic client
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        self.anthropic = Anthropic(api_key=api_key)

        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        self.supabase: Client = create_client(supabase_url, supabase_key)

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for a text string.

        Note: As of early 2024, Anthropic doesn't have a native embedding endpoint.
        This is a placeholder that uses a workaround. You may want to use:
        - OpenAI's embedding API
        - Voyage AI
        - Or another embedding service

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        # PLACEHOLDER: Replace with actual embedding API call
        # For now, we'll use OpenAI as a fallback since Anthropic doesn't have embeddings yet

        try:
            import openai
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                client = openai.OpenAI(api_key=openai_key)
                response = client.embeddings.create(
                    model="text-embedding-3-large",
                    input=text,
                    dimensions=EMBEDDING_DIMENSION
                )
                return response.data[0].embedding
            else:
                raise ValueError("OPENAI_API_KEY not found - needed for embeddings")

        except ImportError:
            raise ImportError("OpenAI package required for embeddings. Install with: pip install openai")

    def create_content_text(self, worksheet: Dict) -> str:
        """
        Create a rich text representation of worksheet content for embedding.

        Combines title, topics, skills, and other metadata into a single string.
        """
        parts = []

        # Title
        if worksheet.get('title'):
            parts.append(f"Title: {worksheet['title']}")

        # Topics
        if worksheet.get('au_topic'):
            parts.append(f"Topic: {worksheet['au_topic']}")
        if worksheet.get('au_subtopic'):
            parts.append(f"Subtopic: {worksheet['au_subtopic']}")

        # Year level and strand
        if worksheet.get('au_year_level'):
            parts.append(f"Year Level: {worksheet['au_year_level']}")
        if worksheet.get('acara_strand'):
            parts.append(f"Strand: {worksheet['acara_strand']}")

        # Skills
        if worksheet.get('skills_covered'):
            skills = ', '.join(worksheet['skills_covered'])
            parts.append(f"Skills: {skills}")

        # Prerequisites
        if worksheet.get('prerequisite_skills'):
            prereqs = ', '.join(worksheet['prerequisite_skills'])
            parts.append(f"Prerequisites: {prereqs}")

        # Sections description
        if worksheet.get('sections'):
            sections = worksheet['sections']
            if isinstance(sections, str):
                sections = json.loads(sections)
            section_types = [s.get('type', '') for s in sections if isinstance(s, dict)]
            if section_types:
                parts.append(f"Sections: {', '.join(section_types)}")

        # Difficulty
        if worksheet.get('difficulty_progression'):
            parts.append(f"Difficulty: {worksheet['difficulty_progression']}")

        # Diagrams
        if worksheet.get('diagram_inventory'):
            diagram_inv = worksheet['diagram_inventory']
            if isinstance(diagram_inv, str):
                diagram_inv = json.loads(diagram_inv)
            if isinstance(diagram_inv, dict) and 'types' in diagram_inv:
                types = ', '.join(diagram_inv['types'])
                parts.append(f"Diagrams: {types}")

        return '\n'.join(parts)

    def generate_worksheet_embeddings(self, worksheet_id: str) -> Dict[str, List[float]]:
        """
        Generate both title and content embeddings for a worksheet.

        Args:
            worksheet_id: UUID of the worksheet

        Returns:
            Dict with 'title' and 'content' embedding vectors
        """
        # Fetch worksheet from database
        response = self.supabase.table('worksheets').select('*').eq('id', worksheet_id).single().execute()
        worksheet = response.data

        embeddings = {}

        # Generate title embedding
        if worksheet.get('title'):
            print(f"  Generating title embedding...")
            embeddings['title'] = self.generate_embedding(worksheet['title'])
            time.sleep(RATE_LIMIT_DELAY)

        # Generate content embedding
        print(f"  Generating content embedding...")
        content_text = self.create_content_text(worksheet)
        embeddings['content'] = self.generate_embedding(content_text)
        time.sleep(RATE_LIMIT_DELAY)

        return embeddings

    def update_worksheet_embeddings(self, worksheet_id: str, embeddings: Dict[str, List[float]]):
        """
        Update worksheet in database with generated embeddings.

        Args:
            worksheet_id: UUID of the worksheet
            embeddings: Dict with 'title' and 'content' embeddings
        """
        update_data = {}

        if 'title' in embeddings:
            update_data['embedding_title'] = embeddings['title']
        if 'content' in embeddings:
            update_data['embedding_content'] = embeddings['content']

        if update_data:
            self.supabase.table('worksheets').update(update_data).eq('id', worksheet_id).execute()
            print(f"  ✓ Updated embeddings in database")

    def process_worksheet(self, worksheet_id: str):
        """Process a single worksheet: generate and store embeddings."""
        print(f"\nProcessing worksheet: {worksheet_id}")
        try:
            embeddings = self.generate_worksheet_embeddings(worksheet_id)
            self.update_worksheet_embeddings(worksheet_id, embeddings)
            return True
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False

    def process_all_worksheets(self, missing_only: bool = False):
        """
        Process all worksheets in the database.

        Args:
            missing_only: If True, only process worksheets without embeddings
        """
        # Build query
        query = self.supabase.table('worksheets').select('id, file_name, title, status')

        if missing_only:
            query = query.is_('embedding_content', 'null')

        # Only process completed worksheets
        query = query.eq('status', 'completed')

        # Execute query
        response = query.execute()
        worksheets = response.data

        if not worksheets:
            print("No worksheets found to process")
            return

        print(f"Found {len(worksheets)} worksheets to process")
        print(f"Estimated time: {len(worksheets) * 2 * RATE_LIMIT_DELAY / 60:.1f} minutes\n")

        success_count = 0
        error_count = 0

        # Process with progress bar
        for worksheet in tqdm(worksheets, desc="Generating embeddings"):
            worksheet_id = worksheet['id']
            title = worksheet.get('title', worksheet.get('file_name', 'Unknown'))
            print(f"\n{title}")

            success = self.process_worksheet(worksheet_id)
            if success:
                success_count += 1
            else:
                error_count += 1

        # Summary
        print("\n" + "="*60)
        print("EMBEDDING GENERATION SUMMARY")
        print("="*60)
        print(f"Total processed: {len(worksheets)}")
        print(f"Successful: {success_count}")
        print(f"Errors: {error_count}")
        print("="*60)

    def get_worksheet_statistics(self):
        """Get statistics about worksheet embeddings."""
        # Total worksheets
        total = self.supabase.table('worksheets').select('id', count='exact').execute()
        total_count = total.count

        # Worksheets with embeddings
        with_embeddings = self.supabase.table('worksheets').select('id', count='exact').not_.is_('embedding_content', 'null').execute()
        embedded_count = with_embeddings.count

        # Worksheets ready but not embedded
        ready = self.supabase.table('worksheets').select('id', count='exact').eq('status', 'completed').is_('embedding_content', 'null').execute()
        ready_count = ready.count

        print("\n" + "="*60)
        print("EMBEDDING STATISTICS")
        print("="*60)
        print(f"Total worksheets: {total_count}")
        print(f"With embeddings: {embedded_count}")
        print(f"Without embeddings (completed): {ready_count}")
        print(f"Coverage: {(embedded_count / total_count * 100) if total_count > 0 else 0:.1f}%")
        print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Generate vector embeddings for worksheet semantic search'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Process all completed worksheets'
    )
    parser.add_argument(
        '--missing-only',
        action='store_true',
        help='Only process worksheets without embeddings'
    )
    parser.add_argument(
        '--worksheet-id',
        help='Process a specific worksheet by ID'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show embedding statistics'
    )

    args = parser.parse_args()

    generator = EmbeddingGenerator()

    if args.stats:
        generator.get_worksheet_statistics()
    elif args.worksheet_id:
        generator.process_worksheet(args.worksheet_id)
    elif args.all:
        generator.process_all_worksheets(missing_only=False)
    elif args.missing_only:
        generator.process_all_worksheets(missing_only=True)
    else:
        print("Please specify --all, --missing-only, --worksheet-id, or --stats")
        parser.print_help()


if __name__ == '__main__':
    main()
