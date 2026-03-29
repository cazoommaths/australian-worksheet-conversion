#!/usr/bin/env python3
"""
setup_database.py - One-shot database and storage setup

Runs all SQL migrations against your Supabase project and creates
the worksheets storage bucket if it doesn't already exist.

Requirements:
  - SUPABASE_URL and SUPABASE_SERVICE_KEY set in .env
  - The service key must have permission to execute DDL (use the service_role key)

Usage:
    python scripts/setup_database.py               # Run migrations + create bucket
    python scripts/setup_database.py --bucket-only # Only create storage bucket
    python scripts/setup_database.py --migrations-only
    python scripts/setup_database.py --status      # Check what's already set up
"""

import os
import sys
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
BUCKET_NAME = os.getenv("SUPABASE_STORAGE_BUCKET", "worksheets")

MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"
MIGRATION_FILES = [
    "001_worksheets.sql",
    "002_curriculum.sql",
    "003_skills.sql",
    "004_search_functions.sql",
]


# ---------------------------------------------------------------------------
# SQL execution via Supabase REST
# ---------------------------------------------------------------------------

def run_sql(sql: str) -> dict:
    """
    Execute raw SQL against the Supabase database.

    Uses the /rest/v1/rpc/exec_sql endpoint if available, otherwise
    falls back to the pg endpoint (requires service role key).
    """
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }

    # Try the management endpoint (available with service key)
    url = f"{SUPABASE_URL}/pg/query"
    resp = requests.post(url, json={"query": sql}, headers=headers, timeout=30)

    if resp.status_code == 404:
        # Older Supabase — fall back to RPC
        url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
        resp = requests.post(url, json={"sql": sql}, headers=headers, timeout=30)

    return {"status": resp.status_code, "body": resp.text}


def run_migrations():
    """Run all migration files in order."""
    print("\n" + "=" * 60)
    print("RUNNING DATABASE MIGRATIONS")
    print("=" * 60)

    all_ok = True

    for migration_file in MIGRATION_FILES:
        path = MIGRATIONS_DIR / migration_file
        if not path.exists():
            print(f"  ✗ Missing: {migration_file}")
            all_ok = False
            continue

        sql = path.read_text()
        print(f"\n[{migration_file}]")

        result = run_sql(sql)

        if result["status"] in (200, 201, 204):
            print(f"  ✓ Applied successfully")
        elif result["status"] == 404:
            # Endpoint not available — print instructions
            print(f"  ⚠ Cannot execute SQL via API (status 404)")
            print(f"    → Run this migration manually in Supabase SQL Editor:")
            print(f"      {SUPABASE_URL.replace('/rest/v1', '')}/dashboard/project/_/sql/new")
            all_ok = False
        else:
            body = result["body"]
            # "already exists" errors are fine (idempotent migrations)
            if "already exists" in body:
                print(f"  ✓ Already applied (skipping)")
            else:
                print(f"  ✗ Error (HTTP {result['status']}): {body[:300]}")
                all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Storage bucket
# ---------------------------------------------------------------------------

def create_storage_bucket(supabase: Client):
    """Create the worksheets storage bucket if it doesn't exist."""
    print("\n" + "=" * 60)
    print("SETTING UP STORAGE BUCKET")
    print("=" * 60)

    try:
        # List existing buckets
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]

        if BUCKET_NAME in bucket_names:
            print(f"  ✓ Bucket '{BUCKET_NAME}' already exists")
            return True

        # Create bucket (private by default)
        supabase.storage.create_bucket(
            BUCKET_NAME,
            options={
                "public": False,          # Require signed URLs
                "allowed_mime_types": ["application/pdf"],
                "file_size_limit": 52428800,  # 50 MB
            },
        )
        print(f"  ✓ Created bucket '{BUCKET_NAME}' (private, PDF only, 50MB limit)")
        return True

    except Exception as e:
        err = str(e)
        if "already exists" in err.lower() or "Duplicate" in err:
            print(f"  ✓ Bucket '{BUCKET_NAME}' already exists")
            return True
        print(f"  ✗ Could not create bucket: {e}")
        print(f"\n  Create it manually in the Supabase dashboard:")
        print(f"    Storage → New bucket → Name: '{BUCKET_NAME}' → Private")
        return False


def check_status(supabase: Client):
    """Print the current setup status."""
    print("\n" + "=" * 60)
    print("CURRENT SETUP STATUS")
    print("=" * 60)

    # Check worksheets table
    try:
        result = supabase.table("worksheets").select("id").limit(1).execute()
        count_result = supabase.table("worksheets").select("id", count="exact").execute()
        count = count_result.count if hasattr(count_result, 'count') else "?"
        print(f"  ✓ worksheets table exists  ({count} rows)")
    except Exception as e:
        print(f"  ✗ worksheets table missing  → run migrations")

    # Check other tables
    for table in ["curriculum_mappings", "skills", "acara_content_descriptors"]:
        try:
            supabase.table(table).select("id").limit(1).execute()
            print(f"  ✓ {table} table exists")
        except Exception:
            print(f"  ✗ {table} table missing  → run migrations")

    # Check bucket
    try:
        buckets = supabase.storage.list_buckets()
        names = [b.name for b in buckets]
        if BUCKET_NAME in names:
            files = supabase.storage.from_(BUCKET_NAME).list()
            pdf_count = sum(1 for f in files if f["name"].lower().endswith(".pdf"))
            print(f"  ✓ Storage bucket '{BUCKET_NAME}' exists  ({pdf_count} PDFs)")
        else:
            print(f"  ✗ Storage bucket '{BUCKET_NAME}' not found  → run setup")
    except Exception as e:
        print(f"  ✗ Could not check storage bucket: {e}")

    print()


def main():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Set up Supabase database and storage")
    parser.add_argument("--bucket-only", action="store_true", help="Only create storage bucket")
    parser.add_argument("--migrations-only", action="store_true", help="Only run SQL migrations")
    parser.add_argument("--status", action="store_true", help="Show current setup status")
    args = parser.parse_args()

    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    if args.status:
        check_status(supabase)
        return

    if args.bucket_only:
        create_storage_bucket(supabase)
        return

    if args.migrations_only:
        run_migrations()
        return

    # Default: run everything
    ok_migrations = run_migrations()
    ok_bucket = create_storage_bucket(supabase)

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)

    if ok_migrations and ok_bucket:
        print("  ✓ Database tables ready")
        print(f"  ✓ Storage bucket '{BUCKET_NAME}' ready")
        print()
        print("Next steps:")
        print(f"  1. Upload sample PDFs via Supabase dashboard:")
        print(f"     Storage → {BUCKET_NAME} → Upload files")
        print(f"  2. List uploaded files:")
        print(f"     python scripts/fetch_from_storage.py --list")
        print(f"  3. Download and process:")
        print(f"     python scripts/batch_process.py --from-storage --limit 3")
    else:
        print("  ⚠ Some steps require manual action - see messages above")
        print()
        print("  If migrations failed, run them manually:")
        print(f"    {SUPABASE_URL}/dashboard/project/_/sql/new")
        print(f"    (paste each file in supabase/migrations/ in order)")


if __name__ == "__main__":
    main()
