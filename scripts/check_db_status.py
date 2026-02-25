#!/usr/bin/env python3
"""
Quick script to check database status
"""
import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv('SUPABASE_URL'),
    os.getenv('SUPABASE_SERVICE_KEY')
)

print("=" * 80)
print("DATABASE STATUS CHECK")
print("=" * 80)

# Check worksheets table
worksheets = supabase.table('worksheets').select('id, file_name, status, extraction_method, created_at').execute()
print(f"\n📋 WORKSHEETS TABLE: {len(worksheets.data)} records")
if worksheets.data:
    print("Latest 5:")
    for ws in worksheets.data[:5]:
        print(f"  • {ws['file_name'][:60]}")
        print(f"    Status: {ws['status']} | Method: {ws.get('extraction_method', 'N/A')}")

# Check worksheet_extractions table
extractions = supabase.table('worksheet_extractions').select('id, file_name, title, extracted_at').execute()
print(f"\n🔍 WORKSHEET_EXTRACTIONS TABLE: {len(extractions.data)} records")
if extractions.data:
    print("Latest 5:")
    for ext in extractions.data[:5]:
        print(f"  • {ext['file_name'][:60]}")
        print(f"    Title: {ext.get('title', 'N/A')}")
        print(f"    Extracted: {ext.get('extracted_at', 'N/A')}")
else:
    print("  (empty)")

# Check if the view works
try:
    view_data = supabase.table('worksheets_with_extractions').select('worksheet_id, extraction_id, file_name, title').limit(5).execute()
    print(f"\n📊 WORKSHEETS_WITH_EXTRACTIONS VIEW: {len(view_data.data)} records")
    if view_data.data:
        for item in view_data.data:
            status = "✓ Has extraction" if item['extraction_id'] else "✗ No extraction"
            print(f"  • {item['file_name'][:60]}")
            print(f"    {status}")
except Exception as e:
    print(f"\n❌ View query failed: {e}")

print("\n" + "=" * 80)
