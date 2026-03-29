#!/usr/bin/env python3
"""
map_curriculum.py - Apply Australian curriculum mappings to extracted worksheet data

This script reads worksheet records from Supabase and applies/refines AU curriculum
mappings using the config files (au_curriculum_mapping.json, terminology.json).

It handles two populations:
  - completed  : worksheets already through Vision API extraction
  - pending    : worksheets imported from master CSV but not yet Vision-extracted
                 (broad mappings only, e.g. from resource_type)

For each worksheet it:
  1. Maps UK year level → AU year level
  2. Infers ACARA strand from topic keywords
  3. Maps UK topic → AU topic
  4. Identifies terminology changes needed (currency, places, education terms)
  5. Updates the worksheets table with refined AU fields
  6. Upserts a shared record in curriculum_mappings for topic/year combinations

Usage:
    # Map all completed worksheets (Vision-extracted)
    python scripts/map_curriculum.py

    # Map completed AND pending (broad resource_type mappings)
    python scripts/map_curriculum.py --include-pending

    # Preview without writing
    python scripts/map_curriculum.py --dry-run

    # Limit number processed (for testing)
    python scripts/map_curriculum.py --limit 20

    # Show current mapping coverage stats
    python scripts/map_curriculum.py --stats
"""

import os
import json
import sys
import re
import argparse
from pathlib import Path
from typing import Optional
from datetime import datetime

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ─── ACARA strand keyword detection ───────────────────────────────────────────

STRAND_KEYWORDS = {
    "Number and Algebra": [
        "number", "place value", "addition", "subtraction", "multiplication",
        "division", "fraction", "decimal", "percentage", "ratio", "proportion",
        "algebra", "equation", "expression", "sequence", "pattern", "money",
        "finance", "surds", "indices", "powers", "standard form", "scientific notation",
        "integers", "negative", "prime", "factor", "multiple", "rounding",
        "number bonds", "times table", "times tables", "mental maths", "mental math",
        "number facts", "written methods", "vectors", "matrices", "polynomial",
        "quadratic", "linear", "simultaneous", "inequality",
    ],
    "Measurement and Geometry": [
        "length", "mass", "weight", "capacity", "volume", "time", "area",
        "perimeter", "2d shape", "3d shape", "angle", "position", "direction",
        "coordinate", "transformation", "symmetry", "rotation", "reflection",
        "translation", "enlargement", "scale", "bearing", "construction",
        "loci", "locus", "circle", "trigonometry", "pythagoras", "geometry",
        "measure", "shape", "units", "speed", "density", "compound measures",
        "rates", "conversion",
    ],
    "Statistics and Probability": [
        "data", "statistic", "graph", "chart", "table", "bar chart", "pie chart",
        "line graph", "scatter", "histogram", "average", "mean", "median", "mode",
        "range", "probability", "chance", "likelihood", "frequency", "tally",
        "pictogram", "box plot", "cumulative", "quartile", "interquartile",
        "stem and leaf", "two-way table", "venn diagram",
    ],
}


def detect_strand(topic: str, subtopic: str = "") -> tuple[str, float]:
    """
    Infer ACARA strand from topic / subtopic text.

    Returns (strand_name, confidence) where confidence is 0.0–1.0.
    """
    combined = f"{topic or ''} {subtopic or ''}".lower()

    scores = {}
    for strand, keywords in STRAND_KEYWORDS.items():
        hit = sum(1 for kw in keywords if kw in combined)
        scores[strand] = hit

    best_strand = max(scores, key=scores.get)
    best_score  = scores[best_strand]

    if best_score == 0:
        return ("Number and Algebra", 0.3)   # safe default

    total = sum(scores.values())
    confidence = min(round(best_score / total, 2) if total else 0.3, 1.0)
    return (best_strand, confidence)


# ─── UK-specific terminology change detection ─────────────────────────────────

def detect_terminology_changes(
    uk_elements: dict,
    terminology_config: dict,
) -> list[dict]:
    """
    Build a list of {from, to, category} terminology change records
    that should be applied to this worksheet.
    """
    changes: list[dict] = []
    terms = terminology_config.get("terminology", {})

    # Currency
    has_currency = uk_elements.get("has_currency", False)
    currency_mentions = uk_elements.get("currency_mentions", [])
    if has_currency or currency_mentions:
        for uk, au in terms.get("currency", {}).items():
            changes.append({"from": uk, "to": au, "category": "currency"})

    # Places
    uk_places = uk_elements.get("places_mentioned", [])
    place_map = terms.get("places", {})
    for place in uk_places:
        if place in place_map:
            changes.append({"from": place, "to": place_map[place], "category": "place"})
        elif place in place_map.values():
            pass  # Already an AU place
        else:
            for uk_p, au_p in place_map.items():
                if uk_p.lower() == place.lower():
                    changes.append({"from": place, "to": au_p, "category": "place"})
                    break

    # Education terms
    uk_edu_terms = uk_elements.get("education_terms", [])
    edu_map = terms.get("education", {})
    for term in uk_edu_terms:
        if term in edu_map:
            changes.append({"from": term, "to": edu_map[term], "category": "education"})

    # Sports / culture
    sports_map = terms.get("sports_and_culture", {})
    uk_sport_terms = uk_elements.get("sports_mentioned", [])
    for term in uk_sport_terms:
        if term in sports_map:
            changes.append({"from": term, "to": sports_map[term], "category": "sport"})

    # Deduplicate by (from, to) pair
    seen = set()
    deduped = []
    for c in changes:
        key = (c["from"], c["to"])
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    return deduped


# ─── Main mapper ───────────────────────────────────────────────────────────────

class CurriculumMapper:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
            sys.exit(1)

        self.supabase: Client = create_client(supabase_url, supabase_key)
        self._load_configs()

    def _load_configs(self):
        config_dir = Path(__file__).parent.parent / "config"

        with open(config_dir / "au_curriculum_mapping.json") as f:
            self.curriculum = json.load(f)

        with open(config_dir / "terminology.json") as f:
            self.terminology = json.load(f)

        # Build quick-access dicts
        self.year_map   = self.curriculum.get("year_level_mapping", {})
        self.ks_map     = self.curriculum.get("key_stage_mapping", {})
        self.topic_map  = self.curriculum.get("topic_mapping", {})

    # ── Year-level mapping ────────────────────────────────────────────────────

    def map_year_level(self, uk_year: Optional[str]) -> Optional[str]:
        """Return the AU year level for a UK year/key-stage string."""
        if not uk_year:
            return None

        # Direct match
        for mapping_dict in (self.year_map, self.ks_map):
            if uk_year in mapping_dict:
                return mapping_dict[uk_year]

        # Partial key-stage match (e.g. "KS3 (Years 7-9)")
        for ks_key, ks_val in self.ks_map.items():
            if ks_key.lower() in uk_year.lower():
                return ks_val

        # Fall back: return as-is (might already be AU style)
        return uk_year

    # ── Topic mapping ─────────────────────────────────────────────────────────

    def map_topic(self, uk_topic: Optional[str]) -> Optional[str]:
        if not uk_topic:
            return uk_topic
        return self.topic_map.get(uk_topic, uk_topic)

    # ── Per-worksheet logic ───────────────────────────────────────────────────

    def build_au_fields(self, worksheet: dict) -> dict:
        """
        Compute the AU curriculum fields for one worksheet row.

        Returns a dict of updates to apply to the worksheets table.
        """
        uk_year    = worksheet.get("uk_year_level")
        uk_topic   = worksheet.get("uk_topic") or ""
        uk_subtopic = worksheet.get("uk_subtopic") or ""
        uk_elements = worksheet.get("uk_specific_elements") or {}

        # Preserve any existing AU fields; only fill gaps
        au_year  = worksheet.get("au_year_level") or self.map_year_level(uk_year)
        au_topic = worksheet.get("au_topic") or self.map_topic(uk_topic)

        # Strand: prefer existing value from Vision extraction
        existing_strand = worksheet.get("acara_strand")
        if existing_strand and existing_strand.strip():
            strand     = existing_strand
            confidence = 0.85   # Vision-assigned, reasonably confident
        else:
            strand, confidence = detect_strand(uk_topic, uk_subtopic)

        # Terminology changes
        terminology_changes = detect_terminology_changes(uk_elements, self.terminology)

        return {
            "au_year_level": au_year,
            "au_topic":      au_topic,
            "acara_strand":  strand,
            "uk_specific_elements": uk_elements,   # preserve existing
            # Store computed terminology changes back into the json column
            # We merge them into uk_specific_elements under a sub-key
            "_terminology_changes": terminology_changes,
            "_strand_confidence":   confidence,
        }

    def update_worksheet(self, worksheet: dict) -> bool:
        """Apply AU mapping to one worksheet. Returns True on success."""
        ws_id    = worksheet["id"]
        title    = (worksheet.get("title") or worksheet.get("file_name") or ws_id)[:60]

        au_fields = self.build_au_fields(worksheet)

        # Pull out non-DB keys
        terminology_changes = au_fields.pop("_terminology_changes")
        strand_confidence   = au_fields.pop("_strand_confidence")

        # Merge terminology changes into uk_specific_elements json column
        uk_elements = dict(au_fields.get("uk_specific_elements") or {})
        if terminology_changes:
            uk_elements["terminology_changes"] = terminology_changes
        au_fields["uk_specific_elements"] = uk_elements

        if self.dry_run:
            print(f"  [DRY RUN] {title}")
            print(f"    au_year_level : {au_fields['au_year_level']}")
            print(f"    au_topic      : {au_fields['au_topic']}")
            print(f"    acara_strand  : {au_fields['acara_strand']} (conf={strand_confidence})")
            print(f"    term_changes  : {len(terminology_changes)} items")
            return True

        try:
            self.supabase.table("worksheets") \
                .update(au_fields) \
                .eq("id", ws_id) \
                .execute()
            print(f"  ✓  {title}")
            return True
        except Exception as e:
            print(f"  ✗  {title}: {e}")
            return False

    def upsert_curriculum_mapping(self, worksheet: dict, au_fields: dict,
                                   strand_confidence: float) -> None:
        """
        Insert or update a shared curriculum_mappings record for the
        UK year+topic combination encountered in this worksheet.
        """
        uk_year    = worksheet.get("uk_year_level") or ""
        uk_topic   = worksheet.get("uk_topic") or ""
        uk_subtopic = worksheet.get("uk_subtopic")

        if not uk_year or not uk_topic:
            return

        record = {
            "uk_year_level": uk_year,
            "uk_key_stage":  self._infer_key_stage(uk_year),
            "uk_topic":      uk_topic,
            "uk_subtopic":   uk_subtopic,
            "au_year_level": au_fields.get("au_year_level") or "",
            "au_topic":      au_fields.get("au_topic") or uk_topic,
            "acara_strand":  au_fields.get("acara_strand") or "Number and Algebra",
            "confidence_score": strand_confidence,
            "mapping_source": "config",
        }

        if self.dry_run:
            return

        try:
            # Upsert: conflict on (uk_year_level, uk_topic, uk_subtopic)
            self.supabase.table("curriculum_mappings") \
                .upsert(record, on_conflict="uk_year_level,uk_topic,uk_subtopic") \
                .execute()
        except Exception as e:
            # Non-fatal: table may not have the upsert constraint yet
            pass

    def _infer_key_stage(self, uk_year: str) -> Optional[str]:
        """Infer key stage label from a UK year/KS string."""
        text = uk_year.lower()
        if "ks1" in text or "key stage 1" in text or "years 1-2" in text:
            return "KS1"
        if "ks2" in text or "key stage 2" in text or "years 3-6" in text:
            return "KS2"
        if "ks3" in text or "key stage 3" in text or "years 7" in text:
            return "KS3"
        if "ks4" in text or "key stage 4" in text or "gcse" in text or "years 10" in text:
            return "KS4"
        if "ks5" in text or "a-level" in text or "a level" in text or "years 12" in text:
            return "KS5"
        return None

    # ── Batch processing ──────────────────────────────────────────────────────

    def fetch_worksheets(self, include_pending: bool = False,
                          limit: Optional[int] = None) -> list[dict]:
        """
        Fetch worksheets from Supabase that need AU mapping.
        By default only 'completed' (Vision-extracted) worksheets are returned.
        """
        statuses = ["completed"]
        if include_pending:
            statuses.append("pending")

        query = self.supabase.table("worksheets") \
            .select(
                "id, file_name, title, status, "
                "uk_year_level, uk_topic, uk_subtopic, "
                "au_year_level, au_topic, acara_strand, "
                "uk_specific_elements, resource_type"
            )

        # Filter by status
        if len(statuses) == 1:
            query = query.eq("status", statuses[0])
        else:
            query = query.in_("status", statuses)

        if limit:
            query = query.limit(limit)

        response = query.execute()
        return response.data or []

    def run(self, include_pending: bool = False, limit: Optional[int] = None):
        """Main entry point: fetch and map all eligible worksheets."""
        print(f"\nFetching worksheets from Supabase...")
        worksheets = self.fetch_worksheets(include_pending=include_pending, limit=limit)

        if not worksheets:
            print("No worksheets found to map.")
            return

        total = len(worksheets)
        print(f"Found {total} worksheet(s) to map\n")

        success = 0
        errors  = 0

        for ws in worksheets:
            au_fields_raw = self.build_au_fields(ws)
            # Separate internal keys before passing to upsert helper
            term_changes   = au_fields_raw.pop("_terminology_changes", [])
            strand_conf    = au_fields_raw.pop("_strand_confidence", 0.5)

            ok = self.update_worksheet(ws)
            if ok:
                success += 1
                self.upsert_curriculum_mapping(ws, au_fields_raw, strand_conf)
            else:
                errors += 1

        print(f"\n{'='*60}")
        print("CURRICULUM MAPPING SUMMARY")
        print(f"  Total     : {total}")
        print(f"  Updated   : {success}")
        print(f"  Errors    : {errors}")
        if self.dry_run:
            print("  [DRY RUN — nothing written to database]")
        print(f"{'='*60}")

    # ── Stats ─────────────────────────────────────────────────────────────────

    def show_stats(self):
        """Print a coverage summary of AU curriculum fields in Supabase."""
        total    = self.supabase.table("worksheets").select("id", count="exact").execute()
        mapped   = self.supabase.table("worksheets").select("id", count="exact") \
                       .not_.is_("acara_strand", "null").execute()
        unmapped = self.supabase.table("worksheets").select("id", count="exact") \
                       .is_("acara_strand", "null").execute()
        cm_total = self.supabase.table("curriculum_mappings").select("id", count="exact").execute()

        print("\nWorksheets AU mapping coverage:")
        print(f"  Total worksheets     : {total.count}")
        print(f"  With acara_strand    : {mapped.count}")
        print(f"  Missing acara_strand : {unmapped.count}")
        print(f"  Curriculum mappings  : {cm_total.count} unique UK topic/year entries")

        # Strand breakdown
        rows = self.supabase.table("worksheets") \
            .select("acara_strand") \
            .not_.is_("acara_strand", "null") \
            .execute()

        from collections import Counter
        strand_counts = Counter(r["acara_strand"] for r in rows.data)
        if strand_counts:
            print("\nWorksheets by ACARA strand:")
            for strand, n in sorted(strand_counts.items(), key=lambda x: -x[1]):
                print(f"  {strand:<40} {n}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Apply Australian curriculum mappings to worksheet records in Supabase"
    )
    parser.add_argument(
        "--include-pending", action="store_true",
        help="Also map pending worksheets (not yet Vision-extracted)"
    )
    parser.add_argument(
        "--limit", type=int, metavar="N",
        help="Process at most N worksheets (useful for testing)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview changes without writing to the database"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="Show current mapping coverage stats and exit"
    )

    args = parser.parse_args()

    mapper = CurriculumMapper(dry_run=args.dry_run)

    if args.stats:
        mapper.show_stats()
        return

    if args.dry_run:
        print("DRY RUN MODE — no database writes will occur\n")

    mapper.run(include_pending=args.include_pending, limit=args.limit)


if __name__ == "__main__":
    main()
