"""PDF parsing functionality using pdfplumber."""

import pdfplumber
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

from .transaction_extractor import (
    Transaction, StatementSummary,
    extract_transactions_from_words, extract_summary, validate_transactions
)

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a PDF statement."""
    success: bool
    transactions: list[Transaction] = field(default_factory=list)
    summary: Optional[StatementSummary] = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    filename: str = ""
    page_count: int = 0


class HSBCStatementParser:
    """Parser for HSBC bank statement PDFs."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def parse(self, pdf_path: str | Path) -> ParseResult:
        """
        Parse an HSBC statement PDF and extract transactions.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            ParseResult with transactions and validation info
        """
        pdf_path = Path(pdf_path)
        result = ParseResult(
            success=False,
            filename=pdf_path.name,
        )

        if not pdf_path.exists():
            result.errors.append(f"File not found: {pdf_path}")
            return result

        if not pdf_path.suffix.lower() == '.pdf':
            result.errors.append(f"Not a PDF file: {pdf_path}")
            return result

        try:
            # Extract words and text from all pages
            pages_words, pages_text = self._extract_words_and_text(pdf_path)
            result.page_count = len(pages_words)

            if not pages_words:
                result.errors.append("No content could be extracted from PDF")
                return result

            self.logger.info(f"Extracted content from {len(pages_words)} pages")

            # Extract summary from text
            full_text = '\n'.join(pages_text)
            result.summary = extract_summary(full_text)

            # Extract transactions using word-level parsing
            transactions, parse_errors = extract_transactions_from_words(pages_words)
            result.transactions = transactions
            result.errors.extend(parse_errors)

            self.logger.info(f"Extracted {len(transactions)} transactions")

            # Validate
            if result.summary:
                is_valid, validation_errors = validate_transactions(transactions, result.summary)
                if not is_valid:
                    result.warnings.extend(validation_errors)
                    self.logger.warning(f"Validation issues: {validation_errors}")

            result.success = len(result.errors) == 0 and len(transactions) > 0

        except Exception as e:
            result.errors.append(f"Error parsing PDF: {str(e)}")
            self.logger.exception(f"Error parsing {pdf_path}")

        return result

    def _extract_words_and_text(self, pdf_path: Path) -> tuple[list[list[dict]], list[str]]:
        """Extract words with positions and text from each page of the PDF."""
        pages_words = []
        pages_text = []

        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    # Extract words with position data
                    words = page.extract_words()
                    if words:
                        pages_words.append(words)
                        self.logger.debug(f"Page {page_num}: extracted {len(words)} words")
                    else:
                        pages_words.append([])
                        self.logger.warning(f"Page {page_num}: no words extracted")

                    # Also extract text for summary parsing
                    text = page.extract_text()
                    pages_text.append(text or "")

                except Exception as e:
                    self.logger.error(f"Error extracting page {page_num}: {e}")
                    pages_words.append([])
                    pages_text.append("")

        return pages_words, pages_text

    def parse_multiple(self, pdf_paths: list[str | Path]) -> list[ParseResult]:
        """Parse multiple PDF files."""
        results = []
        for pdf_path in pdf_paths:
            self.logger.info(f"Processing: {pdf_path}")
            result = self.parse(pdf_path)
            results.append(result)
        return results
