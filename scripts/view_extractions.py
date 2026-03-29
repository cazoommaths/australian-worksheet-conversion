#!/usr/bin/env python3
"""
View extracted worksheet data from the database
"""
import os
from supabase import create_client
from dotenv import load_dotenv
import json

load_dotenv()

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_KEY')
)

print("=" * 80)
print("WORKSHEET EXTRACTIONS")
print("=" * 80)

# Query the extractions
response = supabase.table('worksheet_extractions').select(
    'id, file_name, title, uk_year_level, au_year_level, acara_strand, '
    'skills_covered, total_questions, estimated_time_minutes, difficulty_level, '
    'has_diagrams, has_word_problems, has_worked_examples, has_real_world_context, '
    'uk_specific_elements, extracted_at'
).order('file_name').execute()

if not response.data:
    print("No extractions found yet.")
    print("\nRun: python scripts/batch_process.py --folder data/input")
    exit(0)

for i, extraction in enumerate(response.data, 1):
    print(f"\n[{i}] {extraction['file_name']}")
    print("-" * 80)
    print(f"Title:              {extraction['title']}")
    print(f"UK Year Level:      {extraction['uk_year_level']}")
    print(f"AU Year Level:      {extraction['au_year_level']}")
    print(f"ACARA Strand:       {extraction['acara_strand']}")
    print(f"Total Questions:    {extraction['total_questions']}")
    print(f"Est. Time (mins):   {extraction['estimated_time_minutes']}")
    print(f"Difficulty:         {extraction['difficulty_level']}")
    print(f"Has Diagrams:       {'✓' if extraction['has_diagrams'] else '✗'}")
    print(f"Has Word Problems:  {'✓' if extraction['has_word_problems'] else '✗'}")
    print(f"Has Examples:       {'✓' if extraction['has_worked_examples'] else '✗'}")
    print(f"Real World Context: {'✓' if extraction['has_real_world_context'] else '✗'}")

    if extraction['skills_covered']:
        print(f"\nSkills Covered ({len(extraction['skills_covered'])}):")
        for skill in extraction['skills_covered'][:5]:  # Show first 5
            print(f"  • {skill}")
        if len(extraction['skills_covered']) > 5:
            print(f"  ... and {len(extraction['skills_covered']) - 5} more")

    if extraction['uk_specific_elements']:
        elements = extraction['uk_specific_elements']
        print(f"\nUK-Specific Elements to Localize:")
        if elements.get('currency_symbols'):
            print(f"  Currency: {', '.join(elements['currency_symbols'])}")
        if elements.get('place_names'):
            print(f"  Places: {', '.join(elements['place_names'][:3])}")
        if elements.get('terminology'):
            print(f"  Terms: {', '.join(elements['terminology'][:3])}")

    print(f"\nExtracted: {extraction['extracted_at']}")

print("\n" + "=" * 80)
print(f"Total Extractions: {len(response.data)}")
print("=" * 80)
