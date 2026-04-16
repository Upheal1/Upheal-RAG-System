"""
services/ingestion/pdf_utils.py
==============================

PDF extraction and noise filtering for the UpHeal ingestion pipeline.

This module handles:
1. **Text extraction** from PDFs using pdfplumber (preserving structure)
2. **Noise filtering** to remove irrelevant content:
   - Bibliography and references
   - Running headers/footers
   - Legal disclaimers
   - Index sections
3. **Unicode normalization** and whitespace cleanup

Usage
-----
    from services.ingestion.pdf_utils import extract_clean_text

    text, metadata = extract_clean_text("/data/clinical_pdfs/inbox/dsm5.pdf")

    # Or process a directory of PDFs
    for result in extract_all_pdfs("/data/clinical_pdfs/inbox"):
        print(result["source_path"], result["page_count"])
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

try:
    import pdfplumber
except ImportError:
    pdfplumber = None  # type: ignore

from services.shared.logging import get_logger, log_pdf_start


logger = get_logger(__name__)


BIBLIOGRAPHY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\[\d{4}\]"),  # [2020], [1999]
    re.compile(r"\([12]\d{3}\)"),  # (2020), (1999)
    re.compile(r"https?://[^\s]+"),  # DOI URLs, web links
    re.compile(r"doi:\s*\d+", re.IGNORECASE),  # doi: 10.xxxx
    re.compile(r"\bReferences?\b", re.IGNORECASE),  # References / Reference
    re.compile(r"\bBibliography\b", re.IGNORECASE),
    re.compile(r"\bFurther\s+Reading\b", re.IGNORECASE),
    re.compile(r"\bSuggested\s+Reading\b", re.IGNORECASE),
]

DISCLAIMER_KEYWORDS: list[str] = [
    "disclaimer",
    "not a substitute for professional",
    "not a substitute for medical",
    "for informational purposes only",
    "not intended to diagnose",
    "not intended to treat",
    "seek professional advice",
    "consult a qualified",
    "© copyright",
    "all rights reserved",
    "no part of this publication",
    "reproduction prohibited",
]

HEADER_FOOTER_KEYWORDS: list[str] = [
    "chapter",
    "section",
    "page",
    "copyright",
]

INDEX_LEADER_PATTERN = re.compile(r"^[\s\.\-_]{10,}\d+$")

MAX_HEADER_FOOTER_LENGTH = 100
MIN_PAGE_CONTENT_LENGTH = 50


@dataclass
class ExtractionResult:
    """Result of PDF extraction with metadata."""

    source_path: str
    text: str
    page_count: int
    sha256: str
    pages: list[str]
    warnings: list[str]


@dataclass
class PageMetadata:
    """Metadata extracted from a single page."""

    page_number: int
    width: float
    height: float
    text: str
    is_header: bool = False
    is_footer: bool = False
    is_bibliography: bool = False
    is_disclaimer: bool = False
    is_index: bool = False


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def is_noise_line(line: str) -> bool:
    """
    Check if a line is likely noise content.

    Checks for:
    - Very short repeated lines (header/footer candidates)
    - Lines with mostly punctuation/dots (index entries)
    - Lines matching bibliography patterns
    """
    stripped = line.strip()
    if not stripped:
        return False

    if len(stripped) > MAX_HEADER_FOOTER_LENGTH:
        return False

    if INDEX_LEADER_PATTERN.match(stripped):
        return True

    for pattern in BIBLIOGRAPHY_PATTERNS:
        if pattern.search(stripped):
            return True

    return False


def contains_disclaimer(text: str) -> bool:
    """Check if text contains disclaimer keywords."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in DISCLAIMER_KEYWORDS)


def detect_references_section(
    text: str, page_num: int, all_pages_text: list[str]
) -> bool:
    """
    Detect if this page starts the references/bibliography section.

    Heuristic: If "References" appears prominently (as a standalone line or heading),
    subsequent pages are marked as bibliography.
    """
    lines = text.split("\n")
    for line in lines:
        stripped = line.strip()
        if stripped and len(stripped) < 50:
            if re.search(r"\bReferences?\b", stripped, re.IGNORECASE):
                return True

            if re.search(r"\bBibliography\b", stripped, re.IGNORECASE):
                return True

            if re.search(r"\bFurther\s+Reading\b", stripped, re.IGNORECASE):
                return True

    return False


def is_header_footer_line(line: str, prev_line: Optional[str]) -> bool:
    """
    Determine if a line is likely a header or footer.

    Heuristics:
    - Line is very short
    - Line appears to be repeated (checking against previous line)
    - Line is all uppercase (common in headers)
    - Line contains only page numbers or page-related text
    """
    stripped = line.strip()
    if not stripped:
        return False

    if len(stripped) > MAX_HEADER_FOOTER_LENGTH:
        return False

    if len(stripped) < 3:
        return True

    if prev_line is not None:
        if stripped == prev_line.strip():
            return True

    words = stripped.split()
    if len(words) <= 3:
        header_keywords_count = sum(
            1 for kw in HEADER_FOOTER_KEYWORDS if kw.lower() in stripped.lower()
        )
        if header_keywords_count > 0:
            return True

    if stripped.isupper() and len(words) <= 5:
        return True

    if re.match(r"^\d+$", stripped):
        return True

    return False


def normalize_unicode(text: str) -> str:
    """
    Normalize Unicode characters and clean up whitespace.

    - Converts to NFC form
    - Replaces common Unicode quotes with ASCII
    - Collapses multiple spaces/newlines
    - Preserves paragraph breaks
    """
    text = unicodedata.normalize("NFC", text)

    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "--",
        "\u00a0": " ",
        "\u200b": "",
        "\ufeff": "",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[ \t]+", " ", text)

    text = re.sub(r"\n{3,}", "\n\n", text)

    text = re.sub(r" *\n *", "\n", text)

    return text.strip()


def extract_page_text(page: "pdfplumber.pdf.Page") -> str:
    """
    Extract text from a pdfplumber page while preserving structure.

    Attempts to extract:
    - Text with layout information
    - Tables (as tab-separated text)
    """
    if pdfplumber is None:
        raise ImportError(
            "pdfplumber is required. Install with: pip install pdfplumber"
        )

    text = page.extract_text()

    if text is None:
        text = ""

    tables = page.extract_tables()
    if tables:
        for table in tables:
            table_text = "\n".join(
                "\t".join(str(cell) if cell else "" for cell in row) for row in table
            )
            text += "\n\n[TABLE]\n" + table_text + "\n[/TABLE]\n"

    return text


def extract_clean_page(
    page: "pdfplumber.pdf.Page",
    page_num: int,
    prev_lines: Optional[list[str]] = None,
    in_references: bool = False,
) -> tuple[str, bool]:
    """
    Extract and clean text from a single page.

    Args:
        page: pdfplumber page object
        page_num: Page number (1-indexed)
        prev_lines: Previous page's lines for header/footer detection
        in_references: Whether previous page was in references section

    Returns:
        Tuple of (cleaned_text, is_still_in_references)
    """
    raw_text = extract_page_text(page)
    if not raw_text:
        return "", in_references

    lines = raw_text.split("\n")

    cleaned_lines: list[str] = []
    still_in_references = in_references
    prev_line = prev_lines[-1] if prev_lines else None

    if detect_references_section(raw_text, page_num, []):
        still_in_references = True

    for i, line in enumerate(lines):
        prev_for_check = lines[i - 1] if i > 0 else prev_line

        if still_in_references and is_noise_line(line):
            continue

        if is_header_footer_line(line, prev_for_check):
            continue

        if is_noise_line(line):
            continue

        if contains_disclaimer(line):
            continue

        if not line.strip():
            cleaned_lines.append("")
            continue

        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines)

    cleaned_text = normalize_unicode(cleaned_text)

    return cleaned_text, still_in_references


def extract_clean_text(
    pdf_path: str | Path,
    *,
    log_events: bool = True,
) -> ExtractionResult:
    """
    Extract clean text from a PDF file.

    Args:
        pdf_path: Path to the PDF file
        log_events: Whether to emit structured log events

    Returns:
        ExtractionResult with extracted text, metadata, and SHA256

    Raises:
        ImportError: If pdfplumber is not installed
        FileNotFoundError: If PDF file doesn't exist
    """
    if pdfplumber is None:
        raise ImportError(
            "pdfplumber is required. Install with: pip install pdfplumber"
        )

    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    sha256_hash = compute_sha256(pdf_path)

    if log_events:
        log_pdf_start(str(pdf_path), sha256_hash, logger=logger)

    warnings: list[str] = []
    all_pages: list[str] = []
    prev_lines: Optional[list[str]] = None
    in_references = False

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                page_num = i + 1

                try:
                    cleaned_text, in_references = extract_clean_page(
                        page, page_num, prev_lines, in_references
                    )

                    if in_references and page_num < page_count * 0.8:
                        warnings.append(
                            f"Page {page_num}: References section detected early"
                        )

                    if cleaned_text.strip():
                        all_pages.append(cleaned_text)
                        prev_lines = cleaned_text.split("\n")
                    else:
                        prev_lines = None

                except Exception as e:
                    warnings.append(f"Page {page_num}: Extraction error - {str(e)}")

    except Exception as e:
        raise ValueError(f"Failed to open PDF: {pdf_path}. Error: {str(e)}")

    full_text = "\n\n".join(all_pages)

    return ExtractionResult(
        source_path=str(pdf_path),
        text=full_text,
        page_count=len(all_pages),
        sha256=sha256_hash,
        pages=all_pages,
        warnings=warnings,
    )


def extract_all_pdfs(directory: str | Path) -> Iterator[ExtractionResult]:
    """
    Extract clean text from all PDFs in a directory.

    Args:
        directory: Path to directory containing PDF files

    Yields:
        ExtractionResult for each PDF found

    Example:
        for result in extract_all_pdfs("/data/clinical_pdfs/inbox"):
            print(f"{result.source_path}: {result.page_count} pages")
    """
    directory = Path(directory)

    if not directory.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    pdf_files = sorted(directory.glob("*.pdf"))

    for pdf_file in pdf_files:
        try:
            result = extract_clean_text(pdf_file)
            yield result
        except Exception as e:
            logger.warning(
                "pdf.extraction.failed",
                source_path=str(pdf_file),
                error=str(e),
            )
            continue


def extract_text_chunks(
    pdf_path: str | Path,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> Iterator[tuple[int, str, list[int]]]:
    """
    Extract text as overlapping chunks for downstream processing.

    Args:
        pdf_path: Path to PDF file
        chunk_size: Target size of each chunk (characters)
        overlap: Overlap between chunks (15% of chunk_size = 150 by default)

    Yields:
        Tuple of (chunk_index, text, byte_span)

    Example:
        for idx, text, span in extract_text_chunks("/data/dsm5.pdf"):
            print(f"Chunk {idx}: {len(text)} chars")
    """
    result = extract_clean_text(pdf_path)

    position = 0
    chunk_index = 0

    while position < len(result.text):
        end_position = min(position + chunk_size, len(result.text))

        if end_position < len(result.text):
            search_start = max(position + chunk_size - 200, position)
            period_pos = result.text.rfind(".", search_start, end_position + 50)
            if period_pos > position:
                end_position = period_pos + 1

        chunk_text = result.text[position:end_position].strip()

        if chunk_text:
            byte_span = [
                position,
                end_position,
            ]
            yield chunk_index, chunk_text, byte_span
            chunk_index += 1

        position = end_position - overlap
        if position <= 0:
            position = end_position
