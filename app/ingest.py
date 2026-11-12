"""Parse downloaded PMFBY documents in data/raw/ and export normalized JSON."""
from dataclasses import asdict
import json
import logging
from pathlib import Path
import re

from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.models import Record

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT_FILE = ROOT / "data" / "records.json"

REVAMPED_PDF = RAW / "revamped_ogs_final.pdf"
REVISED_PDF = RAW / "revised_operational_guidelines.pdf"
FAQ_HTML = RAW / "pmfby_faq.html"

REVAMPED_URL = "https://pmfby.gov.in/pdf/Revamped%20OGs_Final.pdf"
REVISED_URL = "https://pmfby.gov.in/pdf/Revised_Operational_Guidelines.pdf"
FAQ_URL = "https://pmfby.gov.in/faq"

REQUIRED = (
    "id",
    "rule_topic",
    "rule_text",
    "og_version",
    "applies_to",
    "deadline_or_rate",
    "source_url",
)


def _clean_pdf_text(text: str) -> str:
    """Normalize whitespace and broken line wraps from PDF extraction."""
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def _load_pdf_pages(pdf_path: Path) -> list[str]:
    """Extract text per page from a PDF file."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"Missing raw PDF: {pdf_path}. Run `python -m app.fetch` first.")
    reader = PdfReader(str(pdf_path))
    return [_clean_pdf_text(page.extract_text() or "") for page in reader.pages]


def _extract_snippet(
    pages: list[str],
    page_num: int,
    start_marker: str,
    end_marker: str | None = None,
    max_len: int = 360,
) -> str:
    """Extract a bounded, clean snippet from a 1-based PDF page."""
    text = pages[page_num - 1]
    match = re.search(re.escape(start_marker), text, re.IGNORECASE)
    if not match:
        raise ValueError(f"Marker '{start_marker}' not found on page {page_num}")
    snippet = text[match.start() :]
    if end_marker:
        end_match = re.search(re.escape(end_marker), snippet[len(start_marker) :], re.IGNORECASE)
        if end_match:
            snippet = snippet[: len(start_marker) + end_match.start()]
    snippet = snippet.strip()
    if len(snippet) > max_len:
        cut = snippet[:max_len].rsplit(" ", 1)[0]
        snippet = cut.rstrip(" ,;:") + "..."
    return snippet


def _parse_faq_html(html_path: Path) -> dict:
    """Parse title and meta description from the downloaded PMFBY FAQ HTML."""
    if not html_path.exists():
        raise FileNotFoundError(f"Missing FAQ HTML: {html_path}")
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "PMFBY Official Portal"
    desc_tag = soup.find("meta", attrs={"name": "description"})
    desc = desc_tag.get("content", "").strip() if desc_tag else ""
    return {"title": title, "description": desc}


def clean_record(row: dict) -> dict:
    """Validate required fields and return a normalized record dict."""
    cleaned = {}
    for field in REQUIRED:
        value = row.get(field)
        if value is None or str(value).strip() == "":
            raise ValueError(f"Missing {field}")
        cleaned[field] = value.strip() if isinstance(value, str) else value
    if not isinstance(cleaned["id"], int):
        raise ValueError("id must be int")
    return asdict(Record.from_dict(cleaned))


def extract_records() -> list[dict]:
    """Parse raw PMFBY PDFs and HTML in data/raw/ into structured rule records."""
    revamped_pages = _load_pdf_pages(REVAMPED_PDF)
    revised_pages = _load_pdf_pages(REVISED_PDF)
    faq_meta = _parse_faq_html(FAQ_HTML)

    specs = [
        (
            "Voluntary enrolment (Kharif 2020 onwards)",
            lambda: _extract_snippet(revamped_pages, 11, "3.1.1.1", "All those farmers"),
            "Revamped OG (Kharif 2020), Para 3.1.1.1",
            "All loanee (KCC) and non-loanee farmers",
            "Opt-out at least 7 days before enrolment cut-off",
            REVAMPED_URL,
        ),
        (
            "Crop categories covered",
            lambda: _extract_snippet(revamped_pages, 12, "4. Coverage of Crops", "5. Coverage"),
            "Revamped OG (Kharif 2020), Para 4",
            "Notified crops per state/season notification",
            "Food crops, oilseeds, annual commercial/horticultural",
            REVAMPED_URL,
        ),
        (
            "Basic cover (standing crop yield loss)",
            lambda: _extract_snippet(revamped_pages, 12, "5.1 Basic Cover:", "5.2 Add-On"),
            "Revamped OG (Kharif 2020), Para 5.1",
            "Standing crops from sowing to harvesting (area approach)",
            "Non-preventable natural perils",
            REVAMPED_URL,
        ),
        (
            "Prevented sowing / planting risk",
            lambda: (
                _extract_snippet(revamped_pages, 12, "5.2.1 Prevented Sowing", "5.2.2", 180)
                + " "
                + _extract_snippet(revamped_pages, 64, "21.3.2.7", "21.3.3", 170)
            ),
            "Revamped OG (Kharif 2020), Para 5.2.1 & 21.3.2.7",
            "Notified area (>75% prevented from sowing)",
            "25% of Sum Insured; cover terminates",
            REVAMPED_URL,
        ),
        (
            "Mid-season adversity relief",
            lambda: (
                _extract_snippet(revamped_pages, 12, "5.2.2 Mid-Season Adversity:", "5.2.3", 190)
                + " "
                + _extract_snippet(revamped_pages, 69, "21.4.2.7", "21.4.2.8", 150)
            ),
            "Revamped OG (Kharif 2020), Para 5.2.2 & 21.4.2.7",
            "Notified unit when expected yield < 50% of normal",
            "25% of likely claims (on-account within 30 days)",
            REVAMPED_URL,
        ),
        (
            "Post-harvest losses (14-day drying window)",
            lambda: _extract_snippet(revamped_pages, 12, "5.2.3 Post-Harvest Losses:", "5.2.4"),
            "Revamped OG (Kharif 2020), Para 5.2.3 & 21.6.2.3",
            "Harvested crops in cut-and-spread / small bundled condition",
            "Up to 2 weeks (14 days) from harvest",
            REVAMPED_URL,
        ),
        (
            "Localized calamities (hailstorm, landslide, inundation)",
            lambda: _extract_snippet(revamped_pages, 13, "5.2.4 Localized Calamities", "5.2.5"),
            "Revamped OG (Kharif 2020), Para 5.2.4 & 21.5.1",
            "Isolated insured farms in notified area (e.g. hailstorm)",
            "Individual farm-level loss assessment",
            REVAMPED_URL,
        ),
        (
            "Wild animal crop loss add-on",
            lambda: _extract_snippet(revamped_pages, 13, "5.2.5 Add-on coverage", "5.3 States"),
            "Revamped OG (Kharif 2020), Para 5.2.5",
            "Areas where state notifies wild animal attack add-on",
            "Optional farmer add-on cover",
            REVAMPED_URL,
        ),
        (
            "General exclusions",
            lambda: _extract_snippet(revamped_pages, 13, "5.4 General Exclusions:", "5.5 Loss/damage"),
            "Revamped OG (Kharif 2020), Para 5.4",
            "All PMFBY policies",
            "War, nuclear risks, malicious damage, preventable risks excluded",
            REVAMPED_URL,
        ),
        (
            "Kharif foodgrain and oilseed premium cap",
            lambda: "Maximum Premium Rate payable by farmer (% of Sum Insured): "
            + _extract_snippet(
                revamped_pages,
                30,
                "Kharif All Food grain and Oilseeds crops",
                "Rabi All Food grain",
            ),
            "Revamped OG (Kharif 2020), Para 13.1 Table 1",
            "Kharif cereals, millets, pulses, and oilseeds (e.g. soybean)",
            "2.0% of Sum Insured or actuarial rate, whichever is less",
            REVAMPED_URL,
        ),
        (
            "Rabi foodgrain and oilseed premium cap",
            lambda: "Maximum Premium Rate payable by farmer (% of Sum Insured): "
            + _extract_snippet(
                revamped_pages,
                30,
                "Rabi All Food grain and Oilseeds crops",
                "Kharif and Rabi Annual Commercial",
            ),
            "Revamped OG (Kharif 2020), Para 13.1 Table 1",
            "Rabi cereals, millets, pulses, and oilseeds (e.g. wheat, gram)",
            "1.5% of Sum Insured or actuarial rate, whichever is less",
            REVAMPED_URL,
        ),
        (
            "Commercial and horticultural premium cap",
            lambda: "Maximum Premium Rate payable by farmer (% of Sum Insured): "
            + _extract_snippet(
                revamped_pages,
                30,
                "Annual Commercial/ Annual Horticultural crops",
                "* Premium paid",
            ),
            "Revamped OG (Kharif 2020), Para 13.1 Table 1",
            "Kharif and Rabi annual commercial/horticultural crops (e.g. cotton)",
            "5% of Sum Insured or actuarial rate, whichever is less",
            REVAMPED_URL,
        ),
        (
            "Sum insured and Scale of Finance formula",
            lambda: _extract_snippet(revamped_pages, 39, "17.5.2", "17.5.3", 320),
            "Revamped OG (Kharif 2020), Para 17.5.2 & 17.5.6",
            "Loanee and non-loanee insured crop acreage in hectares",
            "Sum Insured = Scale of Finance per ha x insured area (ha)",
            REVAMPED_URL,
        ),
        (
            "Claim intimation timeline (72 hours)",
            lambda: _extract_snippet(revamped_pages, 73, "21.5.4.1", "C. Premium payment"),
            "Revamped OG (Kharif 2020), Para 21.5.4.1 & 35.9.4",
            "Localized calamities and post-harvest losses",
            "Within 72 hours of loss occurrence",
            REVAMPED_URL,
        ),
        (
            "Loss reporting channels",
            lambda: _extract_snippet(revamped_pages, 74, "21.5.4.2 Channel of reporting", "21.5.4.3"),
            "Revamped OG (Kharif 2020), Para 21.5.4.2",
            "Farmers reporting localized calamity or post-harvest loss",
            "Crop Insurance App, Centralized Toll-Free (14447), insurer, bank, agri office",
            REVAMPED_URL,
        ),
        (
            "Bank and official forwarding timeline (48 hours)",
            lambda: _extract_snippet(revamped_pages, 74, "21.5.4.4", "21.5.5"),
            "Revamped OG (Kharif 2020), Para 21.5.4.4 & 21.6.3.4",
            "Bank branch or district/agriculture officials forwarding intimation",
            "Within next 48 hours of receiving farmer intimation",
            REVAMPED_URL,
        ),
        (
            "Intimation form completion timeline",
            lambda: _extract_snippet(revamped_pages, 74, "21.5.5.1", "21.5.5.2"),
            "Revamped OG (Kharif 2020), Para 21.5.5.1 & 21.6.4.1",
            "Farmers submitting semi-filled claim intimation form",
            "Complete details within 7 days of loss",
            REVAMPED_URL,
        ),
        (
            "Claim payout and branch beneficiary display",
            lambda: _extract_snippet(revamped_pages, 95, "29.2.4", "29.2.5"),
            "Revamped OG (Kharif 2020), Para 29.2.3 & 29.2.4",
            "Direct benefit transfer to eligible farmers & bank branches",
            "Branch displays beneficiary list within 7 days",
            REVAMPED_URL,
        ),
        (
            "Grievance redressal committees (DGRC & SGRC)",
            lambda: _extract_snippet(revamped_pages, 96, "30.4", "This Committee will be headed"),
            "Revamped OG (Kharif 2020), Para 30.3-30.6",
            "Unresolved farmer, bank, or insurer disputes",
            "DGRC discussion within 7 days; appeal to SGRC within 15 days",
            REVAMPED_URL,
        ),
        (
            "Version evolution: 2016 vs Revised/Revamped intimation",
            lambda: (
                "Earlier 2016 Operational Guidelines required 48-hour farmer loss intimation, "
                "which was expanded to 72 hours for farmers in Revised & Revamped OGs while retaining 48 hours for bank/official forwarding: "
                + _extract_snippet(revised_pages, 51, "21.4.3.2 Channel of reporting", "First mode", 220)
            ),
            "Revised OG (Para 21.4.3.2) vs 2016 OG & Revamped OG (Para 21.5.4.2)",
            "Comparing 2016 48-hour rule against current 72-hour farmer rule",
            "2016 OG: 48 hours -> Revised/Revamped OG: 72 hours (farmer)",
            REVISED_URL,
        ),
        (
            "Official portal and live claim status scope",
            lambda: (
                f"{faq_meta['title']} - {faq_meta['description']} "
                "Static guidelines explain scheme rules and deadlines; individual farmer claim approval status is not stored here and must be checked on NCIP / pmfby.gov.in."
            ),
            "Official PMFBY Portal (pmfby.gov.in/faq)",
            "Individual claim status & live season notifications",
            "Check pmfby.gov.in / NCIP or Helpline 14447",
            FAQ_URL,
        ),
    ]

    valid = []
    for idx, (topic, extractor, og_ver, applies_to, rate, url) in enumerate(specs, 1):
        try:
            rule_text = extractor()
            row = {
                "id": idx,
                "rule_topic": topic,
                "rule_text": rule_text,
                "og_version": og_ver,
                "applies_to": applies_to,
                "deadline_or_rate": rate,
                "source_url": url,
            }
            valid.append(clean_record(row))
        except (AttributeError, IndexError, TypeError, ValueError, FileNotFoundError) as exc:
            logging.warning("Record %s (%s) skipped: %s", idx, topic, exc)

    return valid


def main():
    logging.basicConfig(level=logging.INFO)
    records = extract_records()
    OUT_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logging.info("Parsed and saved %s records from data/raw/ to %s", len(records), OUT_FILE)


if __name__ == "__main__":
    main()
