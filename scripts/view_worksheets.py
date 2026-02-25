#!/usr/bin/env python3
"""
View extracted worksheet data from worksheets table
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
print("EXTRACTED WORKSHEETS (from worksheets table)")
print("=" * 80)

# Query worksheets with extraction data
response = supabase.table('worksheets').select(
    'id, file_name, title, uk_year_level, au_year_level, acara_strand, '
    'skills_covered, uk_topic, uk_subtopic, au_topic, au_subtopic, '
    'has_diagrams, has_word_problems, difficulty_progression, '
    'extraction_method, status, extracted_at, page_count'
).eq('status', 'completed').order('file_name').limit(20).execute()

if not response.data:
    print("No completed worksheets found.")
    exit(0)

for i, ws in enumerate(response.data, 1):
    print(f"\n[{i}] {ws['file_name']}")
    print("-" * 80)
    print(f"Title:              {ws.get('title', 'N/A')}")
    print(f"UK Year Level:      {ws.get('uk_year_level', 'N/A')}")
    print(f"AU Year Level:      {ws.get('au_year_level', 'N/A')}")
    print(f"UK Topic:           {ws.get('uk_topic', 'N/A')}")
    print(f"AU Topic:           {ws.get('au_topic', 'N/A')}")
    print(f"ACARA Strand:       {ws.get('acara_strand', 'N/A')}")
    print(f"Difficulty Prog:    {ws.get('difficulty_progression', 'N/A')}")
    print(f"Page Count:         {ws.get('page_count', 'N/A')}")
    print(f"Has Diagrams:       {'✓' if ws.get('has_diagrams') else '✗'}")
    print(f"Has Word Problems:  {'✓' if ws.get('has_word_problems') else '✗'}")

    if ws.get('skills_covered'):
        print(f"\nSkills Covered ({len(ws['skills_covered'])}):")
        for skill in ws['skills_covered'][:5]:  # Show first 5
            print(f"  • {skill}")
        if len(ws['skills_covered']) > 5:
            print(f"  ... and {len(ws['skills_covered']) - 5} more")

    print(f"\nExtraction Method:  {ws.get('extraction_method', 'N/A')}")
    print(f"Extracted At:       {ws.get('extracted_at', 'N/A')}")

print("\n" + "=" * 80)
print(f"Total Worksheets: {len(response.data)}")
print("=" * 80)
