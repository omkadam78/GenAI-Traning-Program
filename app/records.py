"""Reusable record-loading and search functions."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
JSON_FILE = ROOT / "data" / "records.json"

def load_records():
    """Load JSON records when available, otherwise starter Python records."""
    if JSON_FILE.exists():
        with JSON_FILE.open(encoding="utf-8") as f:
            return json.load(f)
    from data.sample_records import SAMPLE_RECORDS
    return SAMPLE_RECORDS

def search(records, keyword):
    """Search all record values, case-insensitively."""
    keyword = keyword.strip().casefold()
    return [r for r in records if keyword and keyword in " ".join(map(str, r.values())).casefold()]

def count_by(records, field):
    """Count records grouped by a dictionary field."""
    counts = {}
    for record in records:
        key = record.get(field, "Unknown")
        counts[key] = counts.get(key, 0) + 1
    return counts

def get_by_id(records, record_id):
    """Find one record by ID; return None if absent."""
    return next((r for r in records if r.get("id") == record_id), None)
