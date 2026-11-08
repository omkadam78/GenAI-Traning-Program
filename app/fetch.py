"""Download three official PMFBY sources to data/raw/."""
from pathlib import Path
import logging
import requests
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
SOURCES = {
    "pmfby_faq.html": "https://pmfby.gov.in/faq",
    "revised_operational_guidelines.pdf": "https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf",
    "revamped_guidelines_2020.pdf": "https://pmfby.gov.in/pdf/Revamped%20Operational%20Guidelines_17th%20August%202020.pdf",
}
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

if __name__ == "__main__": main()
