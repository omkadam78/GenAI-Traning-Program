"""Exploratory data analysis of FasalBima Sathi PMFBY records using pandas."""
import pandas as pd

from app.records import load_records


def analyze_records() -> dict:
    """Compute summary facts about the loaded PMFBY records."""
    records = load_records()
    df = pd.DataFrame(records)

    version_counts = df["og_version"].value_counts().to_dict()
    has_numeric_deadline_or_rate = int(
        df["deadline_or_rate"].str.contains(r"\d", regex=True, na=False).sum()
    )
    source_counts = df["source_url"].value_counts().to_dict()
    avg_words = round(float(df["rule_text"].str.split().str.len().mean()), 1)

    return {
        "total_records": int(len(df)),
        "version_counts": version_counts,
        "records_with_numeric_deadline_or_rate": has_numeric_deadline_or_rate,
        "source_counts": source_counts,
        "avg_rule_words": avg_words,
    }


def main():
    stats = analyze_records()
    print("=== FasalBima Sathi Dataset Facts (pandas) ===")
    print(f"Fact 1 - Total records & guideline versions: {stats['total_records']} records across {len(stats['version_counts'])} version citations.")
    for ver, cnt in list(stats["version_counts"].items())[:5]:
        print(f"   * {ver}: {cnt}")
    print(
        f"Fact 2 - Actionable numbers: {stats['records_with_numeric_deadline_or_rate']} of "
        f"{stats['total_records']} records contain concrete numeric rates or timelines "
        "(e.g., 2.0%, 1.5%, 5%, 72 hours, 48 hours, 14 days)."
    )
    print(
        f"Fact 3 - Source coverage & length: average rule text is {stats['avg_rule_words']} words; "
        f"records span {len(stats['source_counts'])} official pmfby.gov.in sources:"
    )
    for url, cnt in stats["source_counts"].items():
        print(f"   * {url}: {cnt}")


if __name__ == "__main__":
    main()

