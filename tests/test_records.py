from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.records import count_by, get_by_id, load_records, search

records = load_records()
assert len(records) >= 15
assert search(records, "premium")
assert sum(count_by(records, "rule_topic").values()) == len(records)
assert get_by_id(records, 1) is not None
assert get_by_id(records, 9999) is None

if __name__ == "__main__":
    print("All basic checks passed.")
