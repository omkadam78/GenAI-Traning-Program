"""Validate starter records and export normalized JSON."""
import json, logging
from pathlib import Path
from data.sample_records import SAMPLE_RECORDS
ROOT = Path(__file__).resolve().parents[1]
REQUIRED = ("id","rule_topic","rule_text","og_version","applies_to","deadline_or_rate","source_url")

def clean_record(row):
    cleaned = {}
    for field in REQUIRED:
        value = row.get(field)
        if value is None or str(value).strip() == "": raise ValueError(f"Missing {field}")
        cleaned[field] = value.strip() if isinstance(value, str) else value
    if not isinstance(cleaned["id"], int): raise ValueError("id must be int")
    return cleaned

def main():
    logging.basicConfig(level=logging.INFO)
    valid = []
    for number, row in enumerate(SAMPLE_RECORDS, 1):
        try: valid.append(clean_record(row))
        except (AttributeError, TypeError, ValueError) as exc: logging.warning("Row %s skipped: %s", number, exc)
    output = ROOT / "data" / "records.json"
    output.write_text(json.dumps(valid, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Saved %s records to %s", len(valid), output)

if __name__ == "__main__": main()
