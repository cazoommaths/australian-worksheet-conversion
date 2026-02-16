#!/usr/bin/env python3
"""
extract_with_vision.py - Advanced worksheet extraction using Claude Vision API

This script uses Claude's Vision API to analyze worksheet PDFs as images,
extracting rich structured metadata including topics, skills, diagrams, and difficulty.

Features:
- Converts PDF pages to images for Vision API processing
- Extracts comprehensive structured data (title, topics, skills, sections, diagrams)
- Rate limiting (10 requests/minute)
- Automatic retry with exponential backoff
- Detailed error handling and logging

Usage:
    python scripts/extract_with_vision.py --file data/input/worksheet.pdf
    python scripts/extract_with_vision.py --folder data/input --output data/vision_extracts.json
"""

import os
import json
import time
import base64
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image
from anthropic import Anthropic
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Constants
MODEL = "claude-sonnet-4-20250514"
MAX_REQUESTS_PER_MINUTE = 10
REQUEST_DELAY = 60 / MAX_REQUESTS_PER_MINUTE  # 6 seconds between requests

# Vision extraction prompt
VISION_EXTRACTION_PROMPT = """Analyze this mathematics worksheet page and extract detailed information.

Return a JSON object with the following structure:

{
  "title": "The worksheet title (if visible)",
  "year_level": "UK year level (e.g., Year 5, GCSE, KS2)",
  "topic": "Main topic (e.g., Fractions, Algebra)",
  "subtopic": "Specific subtopic (e.g., Adding Fractions, Linear Equations)",
  "strand": "ACARA strand classification (Number and Algebra, Measurement and Geometry, or Statistics and Probability)",
  "skills_covered": ["skill1", "skill2", "skill3"],
  "prerequisite_skills": ["prereq1", "prereq2"],
  "sections": [
    {
      "label": "Section name or number",
      "type": "question_set|worked_example|instructions|challenge",
      "question_count": 5,
      "has_diagrams": true,
      "diagram_descriptions": ["bar chart showing rainfall", "grid for plotting coordinates"]
    }
  ],
  "difficulty_progression": "constant|easy_to_hard|mixed|scaffolded",
  "diagram_inventory": {
    "count": 3,
    "types": ["graph", "geometric_shape", "number_line"],
    "descriptions": ["coordinate grid with axes", "triangle with labeled sides", "number line from -5 to 5"]
  },
  "uk_specific_elements": {
    "currency": ["£2.50", "35p"],
    "places": ["London", "Manchester"],
    "terms": ["Key Stage 2", "SATs"]
  },
  "content_flags": {
    "has_word_problems": true,
    "has_real_world_context": true,
    "has_calculator_questions": false,
    "has_extension_tasks": true
  }
}

Be thorough and accurate. If information is not visible or unclear, use null or empty arrays."""


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, requests_per_minute: int):
        self.delay = 60 / requests_per_minute
        self.last_request_time = 0

    def wait(self):
        """Wait if necessary to respect rate limit."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()


class VisionExtractor:
    """Extract worksheet data using Claude Vision API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = Anthropic(api_key=self.api_key)
        self.rate_limiter = RateLimiter(MAX_REQUESTS_PER_MINUTE)

    def pdf_to_images(self, pdf_path: str, dpi: int = 150) -> List[Image.Image]:
        """
        Convert PDF pages to PIL Images.

        Args:
            pdf_path: Path to PDF file
            dpi: Resolution for rendering (150 is good balance of quality/size)

        Returns:
            List of PIL Image objects, one per page
        """
        images = []
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render page to pixmap at specified DPI
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)

        doc.close()
        return images

    def image_to_base64(self, image: Image.Image, format: str = "PNG") -> str:
        """Convert PIL Image to base64 string."""
        buffered = BytesIO()
        image.save(buffered, format=format)
        img_bytes = buffered.getvalue()
        return base64.b64encode(img_bytes).decode('utf-8')

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def extract_page_data(self, image: Image.Image, page_num: int) -> Dict:
        """
        Extract structured data from a single worksheet page using Vision API.

        Args:
            image: PIL Image of the worksheet page
            page_num: Page number (for logging)

        Returns:
            Dictionary with extracted structured data
        """
        # Rate limiting
        self.rate_limiter.wait()

        # Convert image to base64
        img_base64 = self.image_to_base64(image)

        print(f"  Analyzing page {page_num} with Vision API...")

        # Call Claude Vision API
        response = self.client.messages.create(
            model=MODEL,
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": VISION_EXTRACTION_PROMPT
                        }
                    ],
                }
            ],
        )

        # Extract JSON from response
        response_text = response.content[0].text

        # Try to parse JSON from response
        try:
            # Look for JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                data = json.loads(json_str)
                return data
            else:
                print(f"  Warning: No JSON found in response for page {page_num}")
                return {"error": "No JSON in response", "raw_response": response_text}
        except json.JSONDecodeError as e:
            print(f"  Warning: Failed to parse JSON from page {page_num}: {e}")
            return {"error": str(e), "raw_response": response_text}

    def extract_from_pdf(self, pdf_path: str) -> Dict:
        """
        Extract comprehensive data from all pages of a PDF worksheet.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary with aggregated extraction results
        """
        print(f"\nProcessing: {pdf_path}")
        start_time = time.time()

        # Convert PDF to images
        print("  Converting PDF to images...")
        images = self.pdf_to_images(pdf_path)
        print(f"  Found {len(images)} pages")

        # Extract data from each page
        page_data = []
        for i, image in enumerate(images, 1):
            try:
                data = self.extract_page_data(image, i)
                page_data.append({
                    "page_number": i,
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                print(f"  Error processing page {i}: {e}")
                page_data.append({
                    "page_number": i,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })

        # Aggregate data from all pages
        result = self._aggregate_pages(page_data, pdf_path)

        elapsed = time.time() - start_time
        print(f"  Completed in {elapsed:.1f}s")

        return result

    def _aggregate_pages(self, page_data: List[Dict], pdf_path: str) -> Dict:
        """
        Aggregate extraction data from multiple pages into a single result.

        For single-page worksheets, returns that page's data.
        For multi-page worksheets, intelligently merges data.
        """
        if not page_data:
            return {"error": "No pages processed"}

        # If single page, return its data directly
        if len(page_data) == 1:
            result = page_data[0]["data"]
        else:
            # Multi-page: use first page for most fields, aggregate sections
            result = page_data[0]["data"].copy() if "data" in page_data[0] else {}

            # Aggregate sections from all pages
            all_sections = []
            for page in page_data:
                if "data" in page and "sections" in page["data"]:
                    for section in page["data"]["sections"]:
                        section["page"] = page["page_number"]
                        all_sections.append(section)
            result["sections"] = all_sections

            # Aggregate skills from all pages
            all_skills = set()
            for page in page_data:
                if "data" in page and "skills_covered" in page["data"]:
                    all_skills.update(page["data"]["skills_covered"])
            result["skills_covered"] = list(all_skills)

        # Add metadata
        result["_metadata"] = {
            "file_path": pdf_path,
            "file_name": os.path.basename(pdf_path),
            "page_count": len(page_data),
            "extraction_timestamp": datetime.now().isoformat(),
            "model": MODEL,
            "method": "vision_api"
        }

        # Add raw page data for reference
        result["_pages"] = page_data

        return result


def process_single_file(pdf_path: str, output_file: Optional[str] = None):
    """Process a single PDF and optionally save results."""
    extractor = VisionExtractor()
    result = extractor.extract_from_pdf(pdf_path)

    # Print summary
    print("\n" + "="*60)
    print("EXTRACTION SUMMARY")
    print("="*60)
    print(f"File: {result['_metadata']['file_name']}")
    print(f"Title: {result.get('title', 'N/A')}")
    print(f"Year Level: {result.get('year_level', 'N/A')}")
    print(f"Topic: {result.get('topic', 'N/A')}")
    print(f"Subtopic: {result.get('subtopic', 'N/A')}")
    print(f"Strand: {result.get('strand', 'N/A')}")
    print(f"Skills Covered: {len(result.get('skills_covered', []))}")
    print(f"Sections: {len(result.get('sections', []))}")
    print(f"Diagrams: {result.get('diagram_inventory', {}).get('count', 0)}")
    print("="*60)

    # Save if output file specified
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to: {output_file}")

    return result


def process_folder(input_folder: str, output_file: str):
    """Process all PDFs in a folder and save results."""
    input_path = Path(input_folder)
    pdf_files = sorted(list(input_path.glob('*.pdf')) + list(input_path.glob('*.PDF')))

    if not pdf_files:
        print(f"No PDF files found in {input_folder}")
        return

    print(f"Found {len(pdf_files)} PDF files to process")
    print(f"Rate limit: {MAX_REQUESTS_PER_MINUTE} requests/minute")
    print(f"Estimated time: {len(pdf_files) * REQUEST_DELAY / 60:.1f} minutes minimum\n")

    extractor = VisionExtractor()
    results = []

    for i, pdf_file in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_file.name}")
        try:
            result = extractor.extract_from_pdf(str(pdf_file))
            results.append(result)
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "error": str(e),
                "_metadata": {
                    "file_path": str(pdf_file),
                    "file_name": pdf_file.name,
                    "extraction_timestamp": datetime.now().isoformat()
                }
            })

    # Save all results
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Batch processing complete!")
    print(f"Processed: {len(results)} worksheets")
    print(f"Results saved to: {output_file}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract worksheet data using Claude Vision API'
    )
    parser.add_argument(
        '--file', '-f',
        help='Process a single PDF file'
    )
    parser.add_argument(
        '--folder', '-d',
        help='Process all PDFs in a folder'
    )
    parser.add_argument(
        '--output', '-o',
        help='Output JSON file path'
    )

    args = parser.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found: {args.file}")
            return

        output_file = args.output or args.file.replace('.pdf', '_vision.json')
        process_single_file(args.file, output_file)

    elif args.folder:
        if not os.path.exists(args.folder):
            print(f"Error: Folder not found: {args.folder}")
            return

        output_file = args.output or "data/vision_extracts.json"
        process_folder(args.folder, output_file)

    else:
        print("Please specify either --file or --folder")
        parser.print_help()


if __name__ == '__main__':
    main()
