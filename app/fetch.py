"""Download official PMFBY sources to data/raw/ and write a manifest."""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST_FILE = RAW / "manifest.json"

SOURCES = {
    "pmfby_faq.html": "https://pmfby.gov.in/faq",
    "revamped_ogs_final.pdf": "https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf",
    "revised_operational_guidelines.pdf": "https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf",
    "revamped_guidelines_2020.pdf": "https://pmfby.gov.in/pdf/Revamped%20Operational%20Guidelines_17th%20August%202020.pdf",
}


def build_manifest(raw_dir: Path = RAW) -> list[dict]:
    """Build a reproducible manifest of downloaded raw files."""
    entries = []
    for name, url in SOURCES.items():
        path = raw_dir / name
        if path.exists():
            data = path.read_bytes()
            entries.append(
                {
                    "filename": name,
                    "source_url": url,
                    "bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )
    return entries


def main():
    logging.basicConfig(level=logging.INFO)
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        try:
            response = requests.get(url, timeout=(10, 60))
            response.raise_for_status()
            (RAW / name).write_bytes(response.content)
            logging.info("Downloaded %s (%s bytes)", name, len(response.content))
        except requests.RequestException as exc:
            logging.warning("Could not download %s: %s", url, exc)

    manifest = build_manifest(RAW)
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Wrote manifest with %s entries to %s", len(manifest), MANIFEST_FILE)


if __name__ == "__main__":
    main()
