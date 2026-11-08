from app.records import load_records, search, count_by, get_by_id
records = load_records()
assert len(records) >= 15
assert search(records, "premium")
assert sum(count_by(records, "rule_topic").values()) == len(records)
assert get_by_id(records, 1) is not None
assert get_by_id(records, 9999) is None
print("All basic checks passed.")
