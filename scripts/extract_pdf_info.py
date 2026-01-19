#!/usr/bin/env python3
"""
extract_pdf_info.py - Extract text and metadata from UK maths worksheets

This script reads PDF files and extracts:
- Full text content
- Detected year level (e.g., "Year 5")
- Detected topic (e.g., "Fractions")
- UK-specific terminology that needs changing

Usage:
    python scripts/extract_pdf_info.py --input data/input --output data/extracted_info.csv
    python scripts/extract_pdf_info.py --file data/input/worksheet.pdf
"""

import os
import re
import json
import argparse
import fitz  # PyMuPDF
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional


def load_config():
    """Load terminology and curriculum mapping configs."""
    config_dir = Path(__file__).parent.parent / "config"
    
    terminology_path = config_dir / "terminology.json"
    curriculum_path = config_dir / "au_curriculum_mapping.json"
    
    terminology = {}
    curriculum = {}
    
    if terminology_path.exists():
        with open(terminology_path, 'r') as f:
            terminology = json.load(f)
    
    if curriculum_path.exists():
        with open(curriculum_path, 'r') as f:
            curriculum = json.load(f)
    
    return terminology, curriculum


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file."""
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
    return text


def detect_year_level(text: str) -> Optional[str]:
    """
    Detect the UK year level from the worksheet text.
    Returns the year level string (e.g., "Year 5") or None if not found.
    """
    # Common patterns for year levels
    patterns = [
        r'\b(Year\s*\d{1,2})\b',           # Year 5, Year 10
        r'\b(Reception)\b',                 # Reception
        r'\b(Key\s*Stage\s*\d)\b',          # Key Stage 2
        r'\b(KS\d)\b',                      # KS2
        r'\b(GCSE)\b',                      # GCSE
        r'\b(A[\s-]?Level)\b',              # A-Level, A Level
        r'\b(Foundation)\b',                # Foundation
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def detect_topic(text: str, curriculum_config: dict) -> Optional[str]:
    """
    Detect the maths topic from the worksheet text.
    Uses the ACARA strands configuration to match topics.
    """
    text_lower = text.lower()
    
    # Build a list of all UK topics from config
    all_topics = []
    if 'acara_strands' in curriculum_config:
        for strand, data in curriculum_config['acara_strands'].items():
            all_topics.extend(data.get('uk_topics', []))
    
    # Also check topic_mapping keys
    if 'topic_mapping' in curriculum_config:
        all_topics.extend(curriculum_config['topic_mapping'].keys())
    
    # Sort by length (longest first) to match most specific topic
    all_topics = sorted(set(all_topics), key=len, reverse=True)
    
    for topic in all_topics:
        if topic.lower() in text_lower:
            return topic
    
    return None


def detect_acara_strand(topic: str, curriculum_config: dict) -> Optional[str]:
    """Map a detected topic to its ACARA strand."""
    if not topic or 'acara_strands' not in curriculum_config:
        return None
    
    topic_lower = topic.lower()
    
    for strand, data in curriculum_config['acara_strands'].items():
        uk_topics = [t.lower() for t in data.get('uk_topics', [])]
        if topic_lower in uk_topics:
            return strand
    
    return None


def find_uk_terminology(text: str, terminology_config: dict) -> List[Dict]:
    """
    Find UK-specific terminology that needs to be changed for Australian version.
    Returns a list of found terms with their suggested replacements.
    """
    found_terms = []
    
    if 'terminology' not in terminology_config:
        return found_terms
    
    for category, mappings in terminology_config['terminology'].items():
        for uk_term, au_term in mappings.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(uk_term) + r'\b'
            matches = re.findall(pattern, text)
            if matches:
                found_terms.append({
                    'category': category,
                    'uk_term': uk_term,
                    'au_term': au_term,
                    'count': len(matches)
                })
    
    return found_terms


def extract_worksheet_info(pdf_path: str) -> Dict:
    """
    Extract all relevant information from a worksheet PDF.
    Returns a dictionary with extracted data.
    """
    terminology_config, curriculum_config = load_config()
    
    # Extract text
    text = extract_text_from_pdf(pdf_path)
    
    # Detect components
    year_level = detect_year_level(text)
    topic = detect_topic(text, curriculum_config)
    acara_strand = detect_acara_strand(topic, curriculum_config) if topic else None
    uk_terms = find_uk_terminology(text, terminology_config)
    
    # Get Australian year level equivalent
    au_year_level = None
    if year_level and 'year_level_mapping' in curriculum_config:
        au_year_level = curriculum_config['year_level_mapping'].get(year_level, year_level)
    elif year_level and 'key_stage_mapping' in curriculum_config:
        au_year_level = curriculum_config['key_stage_mapping'].get(year_level, year_level)
    
    # Get Australian topic name
    au_topic = None
    if topic and 'topic_mapping' in curriculum_config:
        au_topic = curriculum_config['topic_mapping'].get(topic, topic)
    
    return {
        'file_path': pdf_path,
        'file_name': os.path.basename(pdf_path),
        'text_length': len(text),
        'uk_year_level': year_level,
        'au_year_level': au_year_level,
        'uk_topic': topic,
        'au_topic': au_topic or topic,
        'acara_strand': acara_strand,
        'uk_terms_found': len(uk_terms),
        'uk_terms_detail': json.dumps(uk_terms),
        'first_500_chars': text[:500].replace('\n', ' ').strip()
    }


def process_folder(input_folder: str, output_csv: str):
    """Process all PDFs in a folder and save results to CSV."""
    input_path = Path(input_folder)
    pdf_files = list(input_path.glob('*.pdf')) + list(input_path.glob('*.PDF'))
    
    if not pdf_files:
        print(f"No PDF files found in {input_folder}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process...")
    
    results = []
    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"Processing [{i}/{len(pdf_files)}]: {pdf_file.name}")
        info = extract_worksheet_info(str(pdf_file))
        results.append(info)
    
    # Save to CSV
    df = pd.DataFrame(results)
    df.to_csv(output_csv, index=False)
    print(f"\nResults saved to: {output_csv}")
    print(f"Processed {len(results)} worksheets")
    
    # Summary
    print("\n--- Summary ---")
    print(f"Worksheets with detected year level: {df['uk_year_level'].notna().sum()}")
    print(f"Worksheets with detected topic: {df['uk_topic'].notna().sum()}")
    print(f"Total UK terms found: {df['uk_terms_found'].sum()}")


def process_single_file(pdf_path: str):
    """Process a single PDF and print results."""
    print(f"Processing: {pdf_path}\n")
    info = extract_worksheet_info(pdf_path)
    
    print("=" * 50)
    print(f"File: {info['file_name']}")
    print("=" * 50)
    print(f"UK Year Level:    {info['uk_year_level'] or 'Not detected'}")
    print(f"AU Year Level:    {info['au_year_level'] or 'N/A'}")
    print(f"UK Topic:         {info['uk_topic'] or 'Not detected'}")
    print(f"AU Topic:         {info['au_topic'] or 'N/A'}")
    print(f"ACARA Strand:     {info['acara_strand'] or 'Not mapped'}")
    print(f"UK Terms Found:   {info['uk_terms_found']}")
    
    if info['uk_terms_found'] > 0:
        print("\nUK Terms to Replace:")
        terms = json.loads(info['uk_terms_detail'])
        for term in terms:
            print(f"  - '{term['uk_term']}' → '{term['au_term']}' ({term['count']} occurrences)")
    
    print("\nFirst 500 characters of text:")
    print("-" * 50)
    print(info['first_500_chars'])


def main():
    parser = argparse.ArgumentParser(
        description='Extract information from UK maths worksheet PDFs'
    )
    parser.add_argument(
        '--input', '-i',
        help='Input folder containing PDF files'
    )
    parser.add_argument(
        '--output', '-o',
        default='data/extracted_info.csv',
        help='Output CSV file path (default: data/extracted_info.csv)'
    )
    parser.add_argument(
        '--file', '-f',
        help='Process a single PDF file and print results'
    )
    
    args = parser.parse_args()
    
    if args.file:
        # Process single file
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            return
        process_single_file(args.file)
    elif args.input:
        # Process folder
        if not os.path.exists(args.input):
            print(f"Error: Folder not found: {args.input}")
            return
        process_folder(args.input, args.output)
    else:
        print("Please specify either --input folder or --file path")
        parser.print_help()


if __name__ == '__main__':
    main()
