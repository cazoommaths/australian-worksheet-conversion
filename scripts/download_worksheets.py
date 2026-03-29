#!/usr/bin/env python3
"""
download_worksheets.py - Download worksheets from Dropbox

Downloads PDF worksheets from Dropbox URLs listed in a CSV file.

Usage:
    python scripts/download_worksheets.py --csv data/worksheets_SAMPLE.csv --limit 10
    python scripts/download_worksheets.py --csv data/worksheets.csv --output data/input
"""

import os
import argparse
import time
from pathlib import Path
from typing import Optional
import requests
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv()


def sanitize_filename(name: str) -> str:
    """Convert worksheet name to a safe filename."""
    # Remove or replace problematic characters
    safe = name.replace(' ', '-').replace('/', '-').replace('\\', '-')
    safe = safe.replace(':', '').replace('?', '').replace('*', '')
    safe = safe.replace('"', '').replace('<', '').replace('>', '').replace('|', '')

    # Ensure it ends with .pdf
    if not safe.lower().endswith('.pdf'):
        safe += '.pdf'

    return safe


def convert_dropbox_url(url: str) -> str:
    """
    Convert Dropbox sharing URL to direct download URL.

    Dropbox share links (www.dropbox.com/s/...) need to be converted
    to direct download links (dl.dropboxusercontent.com/...)
    """
    if 'dropbox.com' in url:
        # Replace dl=0 with dl=1 for direct download
        if 'dl=0' in url:
            return url.replace('dl=0', 'dl=1')
        elif 'dl=1' not in url:
            # Add dl=1 parameter
            separator = '&' if '?' in url else '?'
            return f"{url}{separator}dl=1"
    return url


def download_file(url: str, output_path: str, timeout: int = 60) -> bool:
    """
    Download a file from a URL.

    Args:
        url: URL to download from
        output_path: Path to save file
        timeout: Request timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert Dropbox URL if needed
        download_url = convert_dropbox_url(url)

        # Make request
        response = requests.get(download_url, timeout=timeout, stream=True)
        response.raise_for_status()

        # Get file size if available
        file_size = int(response.headers.get('content-length', 0))

        # Download with progress
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        with open(output_path, 'wb') as f:
            if file_size > 0:
                # Show progress for large files
                with tqdm(total=file_size, unit='B', unit_scale=True, desc=f"  Downloading") as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
            else:
                # No size info, just download
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        return True

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Download error: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Unexpected error: {e}")
        return False


def download_from_csv(csv_path: str, output_dir: str, limit: Optional[int] = None,
                     overwrite: bool = False, delay: float = 1.0):
    """
    Download worksheets listed in a CSV file.

    Args:
        csv_path: Path to CSV file
        output_dir: Directory to save PDFs
        limit: Optional limit on number to download
        overwrite: If True, re-download existing files
        delay: Delay between downloads (seconds) to be polite
    """
    print(f"Reading worksheet list from: {csv_path}")
    df = pd.read_csv(csv_path)

    if limit:
        df = df.head(limit)
        print(f"Limiting to first {limit} worksheets")

    print(f"Found {len(df)} worksheets to download\n")

    success_count = 0
    skip_count = 0
    error_count = 0

    for idx, row in df.iterrows():
        worksheet_name = row.get('worksheet_name', f"worksheet_{idx}")
        dropbox_url = row.get('dropbox_link')

        if pd.isna(dropbox_url) or not dropbox_url:
            print(f"⊘ Skipping {worksheet_name} (no Dropbox link)")
            skip_count += 1
            continue

        # Create filename
        filename = sanitize_filename(worksheet_name)
        output_path = os.path.join(output_dir, filename)

        # Check if already exists
        if os.path.exists(output_path) and not overwrite:
            print(f"⊘ Skipping {filename} (already exists)")
            skip_count += 1
            continue

        # Download
        print(f"\n[{idx + 1}/{len(df)}] {worksheet_name}")
        print(f"  URL: {dropbox_url}")
        print(f"  Saving to: {output_path}")

        success = download_file(dropbox_url, output_path)

        if success:
            # Verify it's a valid PDF
            try:
                with open(output_path, 'rb') as f:
                    header = f.read(4)
                    if header != b'%PDF':
                        print(f"  ⚠ Warning: File may not be a valid PDF")
            except Exception:
                pass

            file_size = os.path.getsize(output_path)
            print(f"  ✓ Downloaded ({file_size / 1024:.1f} KB)")
            success_count += 1
        else:
            error_count += 1

        # Polite delay between downloads
        if idx < len(df) - 1:
            time.sleep(delay)

    # Summary
    print("\n" + "="*70)
    print("DOWNLOAD SUMMARY")
    print("="*70)
    print(f"Total worksheets: {len(df)}")
    print(f"Successfully downloaded: {success_count}")
    print(f"Skipped: {skip_count}")
    print(f"Errors: {error_count}")
    print(f"Files saved to: {output_dir}")
    print("="*70)


def main():
    parser = argparse.ArgumentParser(
        description='Download PDF worksheets from Dropbox'
    )
    parser.add_argument(
        '--csv',
        required=True,
        help='CSV file with worksheet list (must have worksheet_name and dropbox_link columns)'
    )
    parser.add_argument(
        '--output', '-o',
        default='data/input',
        help='Output directory for PDFs (default: data/input)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of worksheets to download'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Re-download files that already exist'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=1.0,
        help='Delay between downloads in seconds (default: 1.0)'
    )

    args = parser.parse_args()

    download_from_csv(
        args.csv,
        args.output,
        limit=args.limit,
        overwrite=args.overwrite,
        delay=args.delay
    )


if __name__ == '__main__':
    main()
