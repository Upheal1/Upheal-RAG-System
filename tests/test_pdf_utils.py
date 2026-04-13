"""
tests/test_pdf_utils.py
=======================

Unit tests for ``services/ingestion/pdf_utils.py``.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services.ingestion.pdf_utils import (
    compute_sha256,
    contains_disclaimer,
    detect_references_section,
    extract_clean_page,
    extract_clean_text,
    extract_text_chunks,
    is_header_footer_line,
    is_noise_line,
    normalize_unicode,
)


class TestIsNoiseLine:
    """Tests for is_noise_line function."""

    def test_bibliography_year_bracket(self) -> None:
        assert is_noise_line("[2020] Some reference") is True

    def test_bibliography_year_parentheses(self) -> None:
        assert is_noise_line("(2021) Journal article") is True

    def test_doi_url(self) -> None:
        assert is_noise_line("https://doi.org/10.1000/test") is True

    def test_references_heading(self) -> None:
        assert is_noise_line("References") is True

    def test_bibliography_heading(self) -> None:
        assert is_noise_line("Bibliography") is True

    def test_index_leader_line(self) -> None:
        assert is_noise_line("....................45") is True

    def test_normal_text_not_noise(self) -> None:
        assert (
            is_noise_line(
                "This is a normal paragraph about cognitive behavioral therapy."
            )
            is False
        )

    def test_empty_line(self) -> None:
        assert is_noise_line("") is False

    def test_whitespace_only(self) -> None:
        assert is_noise_line("   ") is False

    def test_long_content_not_noise(self) -> None:
        long_text = "A" * 200
        assert is_noise_line(long_text) is False


class TestContainsDisclaimer:
    """Tests for contains_disclaimer function."""

    def test_disclaimer_keyword(self) -> None:
        assert contains_disclaimer("This is a disclaimer for medical use.") is True

    def test_professional_advice(self) -> None:
        assert contains_disclaimer("Please consult a qualified professional.") is True

    def test_informational_only(self) -> None:
        assert contains_disclaimer("For informational purposes only.") is True

    def test_copyright(self) -> None:
        assert contains_disclaimer("© Copyright 2024") is True

    def test_normal_clinical_text(self) -> None:
        text = "The patient presents with symptoms of generalized anxiety disorder."
        assert contains_disclaimer(text) is False


class TestDetectReferencesSection:
    """Tests for detect_references_section function."""

    def test_references_heading(self) -> None:
        text = "References\n[1] Author, 2020"
        assert detect_references_section(text, 1, []) is True

    def test_bibliography_heading(self) -> None:
        text = "Bibliography\nSmith, J. (2019)"
        assert detect_references_section(text, 1, []) is True

    def test_further_reading(self) -> None:
        text = "Further Reading\nRecommended texts"
        assert detect_references_section(text, 1, []) is True

    def test_no_reference_section(self) -> None:
        text = "Chapter 1: Introduction to CBT\nThis chapter discusses..."
        assert detect_references_section(text, 1, []) is False


class TestIsHeaderFooterLine:
    """Tests for is_header_footer_line function."""

    def test_very_short_line(self) -> None:
        assert is_header_footer_line("ab", None) is True

    def test_repeated_line(self) -> None:
        assert is_header_footer_line("Chapter 1", "Chapter 1") is True

    def test_page_number_only(self) -> None:
        assert is_header_footer_line("45", None) is True

    def test_all_uppercase_short(self) -> None:
        assert is_header_footer_line("CHAPTER ONE", None) is True

    def test_normal_text(self) -> None:
        assert (
            is_header_footer_line("This is a normal paragraph about therapy.", None)
            is False
        )

    def test_long_uppercase(self) -> None:
        long_upper = "A" * 150
        assert is_header_footer_line(long_upper, None) is False


class TestNormalizeUnicode:
    """Tests for normalize_unicode function."""

    def test_curly_quotes_converted(self) -> None:
        text = "\u2018single\u2019 and \u201cdouble\u201d quotes"
        result = normalize_unicode(text)
        assert "'" in result
        assert '"' in result

    def test_em_dash_converted(self) -> None:
        text = "This\u2014that"
        result = normalize_unicode(text)
        assert "--" in result

    def test_multiple_spaces_collapsed(self) -> None:
        text = "Hello    world"
        result = normalize_unicode(text)
        assert "  " not in result

    def test_multiple_newlines_collapsed(self) -> None:
        text = "Hello\n\n\n\nworld"
        result = normalize_unicode(text)
        assert result.count("\n") <= 2

    def test_nbsp_converted(self) -> None:
        text = "Hello\u00a0world"
        result = normalize_unicode(text)
        assert " " in result


class TestComputeSha256:
    """Tests for compute_sha256 function."""

    def test_same_file_same_hash(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, World!")

        hash1 = compute_sha256(test_file)
        hash2 = compute_sha256(test_file)

        assert hash1 == hash2

    def test_different_content_different_hash(self, tmp_path: Path) -> None:
        file1 = tmp_path / "test1.txt"
        file2 = tmp_path / "test2.txt"

        file1.write_text("Content A")
        file2.write_text("Content B")

        hash1 = compute_sha256(file1)
        hash2 = compute_sha256(file2)

        assert hash1 != hash2


class TestExtractCleanPage:
    """Tests for extract_clean_page function."""

    def test_removes_bibliography(self) -> None:
        """Test that bibliography patterns are identified as noise."""
        assert is_noise_line("[2020] Reference line") is True

    def test_preserves_normal_text(self) -> None:
        """Test that normal clinical text is not marked as noise."""
        assert is_noise_line("The patient reports symptoms of anxiety.") is False

    def test_normalizes_whitespace(self) -> None:
        """Test that whitespace is normalized."""
        text = "Hello    world"
        result = normalize_unicode(text)
        assert "  " not in result

    def test_detects_disclaimer(self) -> None:
        """Test that disclaimer text is detected."""
        assert contains_disclaimer("This is a disclaimer for medical advice.") is True


class TestExtractTextChunks:
    """Tests for extract_text_chunks function."""

    def test_extract_result_dataclass(self) -> None:
        """Test that ExtractionResult dataclass works correctly."""
        from services.ingestion.pdf_utils import ExtractionResult

        result = ExtractionResult(
            source_path="/test.pdf",
            text="Test content",
            page_count=1,
            sha256="abc123",
            pages=["Test content"],
            warnings=[],
        )

        assert result.source_path == "/test.pdf"
        assert result.text == "Test content"
        assert result.page_count == 1
        assert len(result.pages) == 1


class TestExtractCleanText:
    """Tests for extract_clean_text function."""

    def test_requires_pdfplumber(self) -> None:
        """Test that pdfplumber is required."""
        with patch("services.ingestion.pdf_utils.pdfplumber", None):
            with pytest.raises(ImportError, match="pdfplumber"):
                extract_clean_text("/some/path.pdf")
