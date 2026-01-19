"""Tests for HSBC Statement PDF Parser."""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from parser import HSBCStatementParser, generate_csv


class TestHSBCStatementParser:
    """Test suite for the HSBC statement parser."""

    @pytest.fixture
    def parser(self):
        """Create a parser instance."""
        return HSBCStatementParser()

    @pytest.fixture
    def example_pdfs(self):
        """Get list of example PDF files."""
        example_dir = Path(__file__).parent.parent / 'example'
        return sorted(example_dir.glob('*.pdf'))

    def test_parser_initialization(self, parser):
        """Test that parser initializes correctly."""
        assert parser is not None

    def test_parse_nonexistent_file(self, parser):
        """Test parsing a non-existent file."""
        result = parser.parse('nonexistent.pdf')
        assert not result.success
        assert len(result.errors) > 0

    def test_parse_all_example_pdfs(self, parser, example_pdfs):
        """Test parsing all example PDF files."""
        assert len(example_pdfs) > 0, "No example PDFs found"

        for pdf_path in example_pdfs:
            result = parser.parse(pdf_path)

            # Should successfully extract transactions
            assert result.success, f"Failed to parse {pdf_path.name}: {result.errors}"
            assert len(result.transactions) > 0, f"No transactions extracted from {pdf_path.name}"

            # Should have a summary
            assert result.summary is not None, f"No summary extracted from {pdf_path.name}"

    def test_income_totals_match(self, parser, example_pdfs):
        """Test that extracted income totals match expected."""
        for pdf_path in example_pdfs:
            result = parser.parse(pdf_path)

            if result.success and result.summary:
                total_in = sum(t.paid_in or 0 for t in result.transactions)
                expected_in = result.summary.payments_in

                assert abs(total_in - expected_in) < 0.02, \
                    f"Income mismatch for {pdf_path.name}: got {total_in}, expected {expected_in}"

    def test_expense_totals_match(self, parser, example_pdfs):
        """Test that extracted expense totals match expected."""
        for pdf_path in example_pdfs:
            result = parser.parse(pdf_path)

            if result.success and result.summary:
                total_out = sum(t.paid_out or 0 for t in result.transactions)
                expected_out = result.summary.payments_out

                assert abs(total_out - expected_out) < 0.02, \
                    f"Expense mismatch for {pdf_path.name}: got {total_out}, expected {expected_out}"

    def test_balance_calculation(self, parser, example_pdfs):
        """Test that balance calculations are correct."""
        for pdf_path in example_pdfs:
            result = parser.parse(pdf_path)

            if result.success and result.summary:
                total_in = sum(t.paid_in or 0 for t in result.transactions)
                total_out = sum(t.paid_out or 0 for t in result.transactions)
                calculated_closing = result.summary.opening_balance + total_in - total_out

                assert abs(calculated_closing - result.summary.closing_balance) < 0.02, \
                    f"Balance mismatch for {pdf_path.name}"

    def test_csv_generation(self, parser, example_pdfs):
        """Test CSV generation from parsed transactions."""
        if not example_pdfs:
            pytest.skip("No example PDFs found")

        result = parser.parse(example_pdfs[0])
        assert result.success

        csv_content = generate_csv(result.transactions)

        # Check CSV has header
        lines = csv_content.strip().split('\n')
        assert len(lines) > 1
        assert 'Date' in lines[0]
        assert 'Bank' in lines[0]
        assert 'Description' in lines[0]
        assert 'Income' in lines[0]
        assert 'Expenses' in lines[0]

        # Check CSV has data rows
        assert len(lines) == len(result.transactions) + 1  # +1 for header

    def test_transaction_dates_are_valid(self, parser, example_pdfs):
        """Test that all transaction dates are valid."""
        for pdf_path in example_pdfs:
            result = parser.parse(pdf_path)

            if result.success:
                for tx in result.transactions:
                    assert tx.date is not None, f"Transaction has no date in {pdf_path.name}"
                    assert tx.date.year >= 2020, f"Invalid date year in {pdf_path.name}"
                    assert tx.date.year <= 2030, f"Invalid date year in {pdf_path.name}"

    def test_transaction_has_amount(self, parser, example_pdfs):
        """Test that all transactions have at least one amount."""
        for pdf_path in example_pdfs:
            result = parser.parse(pdf_path)

            if result.success:
                for tx in result.transactions:
                    has_amount = (tx.paid_in and tx.paid_in > 0) or (tx.paid_out and tx.paid_out > 0)
                    assert has_amount, f"Transaction without amount in {pdf_path.name}: {tx.description}"

    def test_no_negative_amounts(self, parser, example_pdfs):
        """Test that no amounts are negative (they should be in the right column)."""
        for pdf_path in example_pdfs:
            result = parser.parse(pdf_path)

            if result.success:
                for tx in result.transactions:
                    if tx.paid_in is not None:
                        assert tx.paid_in >= 0, f"Negative paid_in in {pdf_path.name}"
                    if tx.paid_out is not None:
                        assert tx.paid_out >= 0, f"Negative paid_out in {pdf_path.name}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
