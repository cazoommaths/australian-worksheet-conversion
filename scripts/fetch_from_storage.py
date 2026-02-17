#!/usr/bin/env python3
"""
fetch_from_storage.py - Fetch PDF worksheets from Supabase Storage

Lists all PDFs in the configured Supabase Storage bucket and downloads them
to data/input/ for processing by the batch pipeline.

Usage:
    python scripts/fetch_from_storage.py                      # Download all
    python scripts/fetch_from_storage.py --limit 5            # Download first 5
    python scripts/fetch_from_storage.py --list               # List without downloading
    python scripts/fetch_from_storage.py --overwrite          # Re-download existing files
"""

import os
import argparse
from pathlib import Path
from typing import Optional

from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
BUCKET_NAME = os.getenv("SUPABASE_STORAGE_BUCKET", "worksheets")
OUTPUT_DIR = "data/input"


def get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError(
            "Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env"
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def list_pdfs(supabase: Client, folder: str = "") -> list[dict]:
    """Return list of PDF file objects from the storage bucket."""
    response = supabase.storage.from_(BUCKET_NAME).list(
        folder,
        {"limit": 1000, "sortBy": {"column": "name", "order": "asc"}},
    )
    pdfs = [f for f in response if f["name"].lower().endswith(".pdf")]
    return pdfs


def download_pdf(supabase: Client, storage_name: str, dest_path: str) -> bool:
    """Download a single PDF from storage to dest_path."""
    try:
        data = supabase.storage.from_(BUCKET_NAME).download(storage_name)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"  ✗ Error downloading {storage_name}: {e}")
        return False


def fetch_worksheets(
    limit: Optional[int] = None,
    overwrite: bool = False,
    list_only: bool = False,
    folder: str = "",
):
    supabase = get_supabase_client()

    print(f"Connecting to bucket: '{BUCKET_NAME}' on {SUPABASE_URL}")
    print(f"Listing PDFs...")

    pdfs = list_pdfs(supabase, folder)

    if not pdfs:
        print(f"\nNo PDFs found in bucket '{BUCKET_NAME}'.")
        print("Upload some worksheets via the Supabase dashboard:")
        print(f"  Storage → {BUCKET_NAME} → Upload files")
        return

    if limit:
        pdfs = pdfs[:limit]

    print(f"Found {len(pdfs)} PDF(s)\n")

    if list_only:
        print(f"{'#':<4} {'File Name':<50} {'Size':>10}")
        print("-" * 66)
        for i, f in enumerate(pdfs, 1):
            size_kb = f.get("metadata", {}).get("size", 0) / 1024
            print(f"{i:<4} {f['name']:<50} {size_kb:>9.1f}KB")
        return

    # Download
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    success, skipped, errors = 0, 0, 0

    for i, f in enumerate(pdfs, 1):
        name = f["name"]
        dest = os.path.join(OUTPUT_DIR, name)
        storage_path = f"{folder}/{name}".lstrip("/") if folder else name

        if os.path.exists(dest) and not overwrite:
            size_kb = os.path.getsize(dest) / 1024
            print(f"[{i}/{len(pdfs)}] ⊘ {name} (already exists, {size_kb:.1f}KB)")
            skipped += 1
            continue

        print(f"[{i}/{len(pdfs)}] Downloading: {name}")
        ok = download_pdf(supabase, storage_path, dest)

        if ok:
            size_kb = os.path.getsize(dest) / 1024
            print(f"  ✓ Saved to {dest} ({size_kb:.1f}KB)")
            success += 1
        else:
            errors += 1

    print("\n" + "=" * 60)
    print("FETCH SUMMARY")
    print("=" * 60)
    print(f"Total found:  {len(pdfs)}")
    print(f"Downloaded:   {success}")
    print(f"Skipped:      {skipped}  (already in data/input)")
    print(f"Errors:       {errors}")
    print(f"Saved to:     {OUTPUT_DIR}/")
    print("=" * 60)

    if success > 0:
        print("\nNext step:")
        print("  python scripts/batch_process.py --folder data/input")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch PDF worksheets from Supabase Storage"
    )
    parser.add_argument(
        "--limit", type=int, help="Max number of PDFs to download"
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-download files that already exist in data/input",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="List available PDFs without downloading",
    )
    parser.add_argument(
        "--folder",
        default="",
        help="Sub-folder within the storage bucket (default: root)",
    )
    parser.add_argument(
        "--bucket",
        default=None,
        help="Override the storage bucket name (default: from SUPABASE_STORAGE_BUCKET env)",
    )

    args = parser.parse_args()

    if args.bucket:
        global BUCKET_NAME
        BUCKET_NAME = args.bucket

    fetch_worksheets(
        limit=args.limit,
        overwrite=args.overwrite,
        list_only=args.list_only,
        folder=args.folder,
    )


if __name__ == "__main__":
    main()
