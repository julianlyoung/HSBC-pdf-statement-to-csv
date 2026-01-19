"""CSV generation from extracted transactions."""

import csv
import io
from pathlib import Path
from typing import Optional
import logging

from .transaction_extractor import Transaction

logger = logging.getLogger(__name__)


def generate_csv(
    transactions: list[Transaction],
    output_path: Optional[str | Path] = None,
    include_header: bool = True
) -> str:
    """
    Generate CSV content from transactions.

    Args:
        transactions: List of Transaction objects
        output_path: Optional path to write CSV file
        include_header: Whether to include header row

    Returns:
        CSV content as string
    """
    output = io.StringIO()
    fieldnames = ['Date', 'Bank', 'Description', 'Income', 'Expenses']

    writer = csv.DictWriter(output, fieldnames=fieldnames)

    if include_header:
        writer.writeheader()

    for tx in transactions:
        row = tx.to_csv_row()
        writer.writerow(row)

    csv_content = output.getvalue()

    # Write to file if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(csv_content, encoding='utf-8')
        logger.info(f"CSV written to {output_path}")

    return csv_content


def generate_combined_csv(
    all_transactions: list[list[Transaction]],
    output_path: Optional[str | Path] = None
) -> str:
    """
    Generate a single CSV from multiple statement transaction lists.

    Transactions are sorted by date across all statements.

    Args:
        all_transactions: List of transaction lists (one per statement)
        output_path: Optional path to write CSV file

    Returns:
        CSV content as string
    """
    # Flatten and sort all transactions by date
    combined = []
    for tx_list in all_transactions:
        combined.extend(tx_list)

    combined.sort(key=lambda t: t.date)

    return generate_csv(combined, output_path)


def format_amount_for_csv(amount: Optional[float], is_expense: bool = False) -> str:
    """
    Format an amount for CSV output.

    Args:
        amount: The amount value (or None)
        is_expense: Whether this is an expense (should be negative)

    Returns:
        Formatted string with £ symbol
    """
    if amount is None or amount == 0:
        return ''

    if is_expense:
        return f'-£{amount:,.2f}'
    else:
        return f'£{amount:,.2f}'
