"""Document chunking pipeline for FasalBima Sathi PMFBY documents."""
from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any

from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
RECORDS_FILE = ROOT / "data" / "records.json"
CHUNKS_DIR = ROOT / "data" / "chunks"

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 100


@dataclass
class DocumentChunk:
    id: str
    text: str
    source: str
    page: int
    title: str
    og_version: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["metadata"] = {
            "source": self.source,
            "page": self.page,
            "title": self.title,
            "og_version": self.og_version,
        }
        return d


def _clean_text(text: str) -> str:
    """Normalize whitespace and strip non-printable characters."""
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def _split_into_windows(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    """Split text into overlapping character windows cleanly at word boundaries."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            # Try to break at a space or punctuation
            last_space = text.rfind(" ", start, end)
            if last_space > start + (chunk_size // 2):
                end = last_space

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_len:
            break
        start = max(start + 1, end - chunk_overlap)

    return chunks


def _infer_section_title(text: str, default: str) -> str:
    """Detect section heading in text if present."""
    patterns = [
        r"(?:Section\s+)?\b([0-9]{1,2}(?:\.[0-9]{1,2})*\s+[A-Z][A-Za-z0-9\s,\-–/]+)",
        r"\b(Coverage of Risks and Exclusions|Coverage of Crops|Coverage of Farmers|Premium Rates|Localized Calamity|Post-Harvest|Prevented Sowing|Mid-Season Adversity|Grievance Redressal|Table \d+ [A-Za-z\s]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            candidate = m.group(1).strip()
            if 5 < len(candidate) < 80:
                return candidate
    return default


def chunk_pdf(
    pdf_path: Path,
    source_name: str,
    og_version: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    max_pages: int | None = None,
) -> list[DocumentChunk]:
    """Extract and chunk pages from a PMFBY PDF document."""
    if not pdf_path.is_file():
        logging.warning("PDF not found: %s", pdf_path)
        return []

    reader = PdfReader(str(pdf_path))
    chunks: list[DocumentChunk] = []
    total_pages = len(reader.pages) if max_pages is None else min(len(reader.pages), max_pages)

    current_title = f"{og_version} - General Provisions"

    for page_idx in range(total_pages):
        page_num = page_idx + 1
        raw_text = reader.pages[page_idx].extract_text() or ""
        clean_page = _clean_text(raw_text)
        if not clean_page or len(clean_page) < 40:
            continue

        current_title = _infer_section_title(clean_page[:300], current_title)
        windows = _split_into_windows(clean_page, chunk_size, chunk_overlap)

        for w_idx, win in enumerate(windows, 1):
            chunk_id = f"{pdf_path.stem}_p{page_num}_c{w_idx}"
            chunks.append(
                DocumentChunk(
                    id=chunk_id,
                    text=win,
                    source=source_name,
                    page=page_num,
                    title=current_title,
                    og_version=og_version,
                )
            )

    return chunks


def chunk_faq_html(
    html_path: Path,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[DocumentChunk]:
    """Chunk text from PMFBY FAQ HTML."""
    if not html_path.is_file():
        return []

    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    # Remove script and style elements
    for s in soup(["script", "style", "noscript"]):
        s.extract()

    text = _clean_text(soup.get_text())
    if not text:
        return []

    windows = _split_into_windows(text, chunk_size, chunk_overlap)
    chunks = []
    for idx, win in enumerate(windows, 1):
        chunks.append(
            DocumentChunk(
                id=f"pmfby_faq_c{idx}",
                text=win,
                source="pmfby_faq.html",
                page=1,
                title="PMFBY Portal FAQ & Scheme Overview",
                og_version="Official Portal FAQ",
            )
        )
    return chunks


def chunk_records_json(
    records_path: Path,
) -> list[DocumentChunk]:
    """Create curated high-precision chunks from structured PMFBY records."""
    if not records_path.is_file():
        return []

    records = json.loads(records_path.read_text(encoding="utf-8"))
    chunks = []
    for r in records:
        text = (
            f"Topic: {r.get('rule_topic')}. Rule: {r.get('rule_text')} "
            f"Applies to: {r.get('applies_to')}. Rate/Timeline: {r.get('deadline_or_rate')}. "
            f"Version: {r.get('og_version')}."
        )
        chunks.append(
            DocumentChunk(
                id=f"rule_record_{r.get('id')}",
                text=text,
                source=r.get("source_url", "pmfby_rules"),
                page=1,
                title=str(r.get("rule_topic")),
                og_version=str(r.get("og_version")),
            )
        )
    return chunks


def get_all_chunks(
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    include_full_pdfs: bool = True,
) -> list[dict[str, Any]]:
    """Generate all document chunks keeping source, page, title, and version metadata."""
    all_chunks: list[DocumentChunk] = []

    # 1. Curated PMFBY rule records (guarantees core QA coverage)
    all_chunks.extend(chunk_records_json(RECORDS_FILE))

    # 2. FAQ HTML
    all_chunks.extend(chunk_faq_html(RAW_DIR / "pmfby_faq.html", chunk_size, chunk_overlap))

    # 3. Revamped Operational Guidelines (Key Sections & Full Text)
    if include_full_pdfs:
        revamped_path = RAW_DIR / "revamped_ogs_final.pdf"
        all_chunks.extend(
            chunk_pdf(
                revamped_path,
                source_name="revamped_ogs_final.pdf",
                og_version="Revamped OG (Kharif 2020)",
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

        revised_path = RAW_DIR / "revised_operational_guidelines.pdf"
        all_chunks.extend(
            chunk_pdf(
                revised_path,
                source_name="revised_operational_guidelines.pdf",
                og_version="Revised Operational Guidelines",
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )

    return [c.to_dict() for c in all_chunks]


def main():
    logging.basicConfig(level=logging.INFO)
    chunks = get_all_chunks()
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = CHUNKS_DIR / "chunks.json"
    out_file.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Generated %s chunks saved to %s", len(chunks), out_file)
    print(f"Total chunks generated: {len(chunks)}")
    if chunks:
        sample = chunks[0]
        print(f"Sample chunk: id={sample['id']}, source={sample['source']}, page={sample['page']}, title={sample['title']}")


if __name__ == "__main__":
    main()

