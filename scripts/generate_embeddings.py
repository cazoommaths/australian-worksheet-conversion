#!/usr/bin/env python3
"""
generate_embeddings.py - Generate vector embeddings for semantic search

This script creates embeddings for worksheet extraction content, enabling
semantic similarity search in the database.

Features:
- Generate embeddings for extraction content
- Batch processing with progress tracking
- Update worksheet_extractions table with embeddings
- Resume capability for interrupted runs

Usage:
    python scripts/generate_embeddings.py --all
    python scripts/generate_embeddings.py --worksheet-id <uuid>
    python scripts/generate_embeddings.py --missing-only
    python scripts/generate_embeddings.py --stats
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

    def generate_worksheet_embeddings(self, extraction_id: str) -> List[float]:
        """
        Generate content embedding for a worksheet extraction.

        Args:
            extraction_id: UUID of the worksheet extraction

        Returns:
            Embedding vector for the content
        """
        # Fetch extraction from database
        response = self.supabase.table('worksheet_extractions').select('*').eq('id', extraction_id).single().execute()
        extraction = response.data

        # Generate content embedding
        print(f"  Generating content embedding...")
        content_text = self.create_content_text(extraction)
        embedding = self.generate_embedding(content_text)
        time.sleep(RATE_LIMIT_DELAY)

        return embedding

    def update_extraction_embeddings(self, extraction_id: str, embedding: List[float]):
        """
        Update worksheet extraction in database with generated embedding.

        Args:
            extraction_id: UUID of the worksheet extraction
            embedding: Content embedding vector
        """
        update_data = {
            'embedding_content': embedding
        }

        self.supabase.table('worksheet_extractions').update(update_data).eq('id', extraction_id).execute()
        print(f"  ✓ Updated embedding in database")

    def process_worksheet(self, extraction_id: str):
        """Process a single worksheet extraction: generate and store embedding."""
        print(f"\nProcessing extraction: {extraction_id}")
        try:
            embedding = self.generate_worksheet_embeddings(extraction_id)
            self.update_extraction_embeddings(extraction_id, embedding)
            return True
        except Exception as e:
            print(f"  ✗ Error: {e}")
            return False

    def process_all_worksheets(self, missing_only: bool = False):
        """
        Process all worksheet extractions in the database.

        Args:
            missing_only: If True, only process extractions without embeddings
        """
        # Build query
        query = self.supabase.table('worksheet_extractions').select('id, file_name, title')

        if missing_only:
            query = query.is_('embedding_content', 'null')

        # Execute query
        response = query.execute()
        extractions = response.data

        if not extractions:
            print("No extractions found to process")
            return

        print(f"Found {len(extractions)} extractions to process")
        print(f"Estimated time: {len(extractions) * RATE_LIMIT_DELAY / 60:.1f} minutes\n")

        success_count = 0
        error_count = 0

        # Process with progress bar
        for extraction in tqdm(extractions, desc="Generating embeddings"):
            extraction_id = extraction['id']
            title = extraction.get('title', extraction.get('file_name', 'Unknown'))
            print(f"\n{title}")

            success = self.process_worksheet(extraction_id)
            if success:
                success_count += 1
            else:
                error_count += 1

        # Summary
        print("\n" + "="*60)
        print("EMBEDDING GENERATION SUMMARY")
        print("="*60)
        print(f"Total processed: {len(extractions)}")
        print(f"Successful: {success_count}")
        print(f"Errors: {error_count}")
        print("="*60)

    def get_worksheet_statistics(self):
        """Get statistics about worksheet extraction embeddings."""
        # Total extractions
        total = self.supabase.table('worksheet_extractions').select('id', count='exact').execute()
        total_count = total.count

        # Extractions with embeddings
        with_embeddings = self.supabase.table('worksheet_extractions').select('id', count='exact').not_.is_('embedding_content', 'null').execute()
        embedded_count = with_embeddings.count

        # Extractions without embeddings
        without_embeddings = self.supabase.table('worksheet_extractions').select('id', count='exact').is_('embedding_content', 'null').execute()
        without_count = without_embeddings.count

        print("\n" + "="*60)
        print("EMBEDDING STATISTICS")
        print("="*60)
        print(f"Total extractions: {total_count}")
        print(f"With embeddings: {embedded_count}")
        print(f"Without embeddings: {without_count}")
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
