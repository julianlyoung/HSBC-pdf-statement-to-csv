"""Transaction extraction and parsing from HSBC statement text."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Payment type codes used by HSBC
PAYMENT_TYPES = ['DD', 'VIS', 'BP', 'CR', 'SO', 'OBP', ')))', 'FPO', 'FPI', 'CHQ', 'ATM', 'TFR', 'INT', 'DR', 'DL']

# Regex patterns
DATE_PATTERN = re.compile(r'^(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2})$')
AMOUNT_PATTERN = re.compile(r'^[\d,]+\.\d{2}$')


@dataclass
class Transaction:
    """Represents a single bank transaction."""
    date: datetime
    payment_type: str
    description: str
    paid_out: Optional[float]
    paid_in: Optional[float]
    balance: Optional[float]
    raw_lines: list[str] = field(default_factory=list)

    def to_csv_row(self) -> dict:
        """Convert transaction to CSV row format."""
        income = ''
        expenses = ''

        if self.paid_in and self.paid_in > 0:
            income = f'£{self.paid_in:.2f}'

        if self.paid_out and self.paid_out > 0:
            expenses = f'-£{self.paid_out:.2f}'

        return {
            'Date': self.date.strftime('%d/%m/%Y'),
            'Bank': 'hsbc',
            'Description': self.description.strip(),
            'Income': income,
            'Expenses': expenses,
        }


@dataclass
class StatementSummary:
    """Statement account summary information."""
    opening_balance: float
    closing_balance: float
    payments_in: float
    payments_out: float
    statement_start: Optional[datetime] = None
    statement_end: Optional[datetime] = None


def parse_amount(amount_str: str) -> float:
    """Parse an amount string to float, handling commas."""
    if not amount_str:
        return 0.0
    clean = amount_str.replace(',', '').replace('£', '').strip()
    try:
        return float(clean)
    except ValueError:
        return 0.0


def parse_date_parts(day: str, month: str, year: str) -> Optional[datetime]:
    """Parse date from parts."""
    try:
        date_str = f"{day} {month} {year}"
        return datetime.strptime(date_str, '%d %b %y')
    except ValueError:
        return None


def extract_summary(text: str) -> Optional[StatementSummary]:
    """Extract account summary information from statement text."""
    summary = {}

    patterns = {
        'opening_balance': r'Opening\s*Balance\s*[£]?([\d,]+\.\d{2})',
        'closing_balance': r'Closing\s*Balance\s*[£]?([\d,]+\.\d{2})',
        'payments_in': r'Payments?\s*In\s*[£]?([\d,]+\.\d{2})',
        'payments_out': r'Payments?\s*Out\s*[£]?([\d,]+\.\d{2})',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            summary[key] = parse_amount(match.group(1))

    if len(summary) >= 2:
        return StatementSummary(
            opening_balance=summary.get('opening_balance', 0),
            closing_balance=summary.get('closing_balance', 0),
            payments_in=summary.get('payments_in', 0),
            payments_out=summary.get('payments_out', 0),
        )

    return None


def extract_transactions_from_words(pages_words: list[list[dict]]) -> tuple[list[Transaction], list[str]]:
    """
    Extract transactions using word-level position data.

    Column boundaries (approximate x-coordinates):
    - Date: x < 100
    - Payment Type: 100 <= x < 140
    - Description: 140 <= x < 350
    - Paid Out: 350 <= x < 430
    - Paid In: 430 <= x < 510
    - Balance: x >= 510

    Args:
        pages_words: List of word lists from pdfplumber (one per page)

    Returns:
        tuple: (transactions list, list of parsing errors)
    """
    transactions = []
    errors = []

    # Column boundaries (based on HSBC statement layout)
    COL_DATE_MAX = 100
    COL_PAYMENT_TYPE_MIN = 100
    COL_PAYMENT_TYPE_MAX = 130
    COL_DESCRIPTION_MIN = 130
    COL_PAID_OUT_MIN = 350
    COL_PAID_OUT_MAX = 430
    COL_PAID_IN_MIN = 430
    COL_PAID_IN_MAX = 510
    COL_BALANCE_MIN = 510

    current_date = None
    current_payment_type = None
    current_description_parts = []
    current_paid_out = None
    current_paid_in = None
    current_balance = None

    def save_transaction():
        """Save the current transaction if valid."""
        nonlocal current_date, current_payment_type, current_description_parts
        nonlocal current_paid_out, current_paid_in, current_balance

        if current_date and current_payment_type and (current_paid_out or current_paid_in):
            description = ' '.join(current_description_parts)
            tx = Transaction(
                date=current_date,
                payment_type=current_payment_type,
                description=description,
                paid_out=current_paid_out,
                paid_in=current_paid_in,
                balance=current_balance,
            )
            transactions.append(tx)

        # Reset for next transaction
        current_description_parts = []
        current_paid_out = None
        current_paid_in = None
        current_balance = None

    for page_idx, words in enumerate(pages_words):
        # Group words by y-position (same line)
        lines = {}
        for w in words:
            y = round(w['top'], 0)
            if y not in lines:
                lines[y] = []
            lines[y].append({
                'x': w['x0'],
                'text': w['text'],
            })

        # Process lines in order
        for y in sorted(lines.keys()):
            line_words = sorted(lines[y], key=lambda w: w['x'])

            # Skip header/footer lines
            line_text = ' '.join(w['text'] for w in line_words).upper()
            if any(skip in line_text for skip in [
                'CONTACT TEL', 'TEXT PHONE', 'WWW.HSBC', 'YOUR STATEMENT',
                'ACCOUNT NAME', 'SORTCODE', 'SHEET NUMBER', 'BRANCH IDENTIFIER',
                'INTERNATIONAL BANK', 'OPENINGBALANCE', 'CLOSINGBALANCE',
                'PAYMENTS IN', 'PAYMENTS OUT', 'ARRANGEDOVERDRAFT',
                'HANOVER STREET', 'PAYMENT TYPE AND DETAILS',
                'YOUR BANK ACCOUNT', 'YOUR DEPOSIT', 'FINANCIAL SERVICES',
                'CREDIT INTEREST', 'DEBIT INTEREST', 'AER BALANCE', 'EAR BALANCE',
            ]):
                continue

            # Check for BALANCE BROUGHT/CARRIED FORWARD
            if 'BALANCEBROUGHTFORWARD' in line_text.replace(' ', ''):
                continue
            if 'BALANCECARRIEDFORWARD' in line_text.replace(' ', ''):
                save_transaction()
                current_payment_type = None
                continue

            # Extract components from this line
            date_parts = []
            payment_type = None
            description_words = []
            paid_out = None
            paid_in = None
            balance = None

            for w in line_words:
                x = w['x']
                text = w['text']

                # Check for date parts (day, month, year at start of line)
                if x < 100:
                    if text.isdigit() and len(text) <= 2:
                        date_parts.append(text)
                    elif text in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                        date_parts.append(text)
                    elif text.isdigit() and len(text) == 2 and len(date_parts) == 2:
                        date_parts.append(text)

                # Check for payment type (only in narrow column)
                elif COL_PAYMENT_TYPE_MIN <= x < COL_PAYMENT_TYPE_MAX:
                    if text.upper() in [pt.upper() for pt in PAYMENT_TYPES]:
                        payment_type = text.upper()
                    elif text == ')))':
                        payment_type = ')))'
                    else:
                        # Not a payment type, might be part of description
                        description_words.append(text)

                # Check for amounts by column position
                elif AMOUNT_PATTERN.match(text):
                    amount = parse_amount(text)
                    if COL_PAID_OUT_MIN <= x < COL_PAID_OUT_MAX:
                        paid_out = amount
                    elif COL_PAID_IN_MIN <= x < COL_PAID_IN_MAX:
                        paid_in = amount
                    elif x >= COL_BALANCE_MIN:
                        balance = amount
                    else:
                        # Amount in description area - treat as part of description
                        description_words.append(text)

                # Description words
                elif COL_DESCRIPTION_MIN <= x < COL_PAID_OUT_MIN:
                    description_words.append(text)

            # Process what we found on this line

            # If we found a new date, save previous transaction
            if len(date_parts) == 3:
                save_transaction()
                current_date = parse_date_parts(date_parts[0], date_parts[1], date_parts[2])

            # If we found a payment type, it's a new transaction
            if payment_type:
                if current_payment_type and (current_paid_out or current_paid_in):
                    # Save previous transaction before starting new one
                    save_transaction()
                current_payment_type = payment_type

            # Accumulate description words
            if description_words and current_payment_type:
                current_description_parts.extend(description_words)

            # Accumulate amounts (they might come on continuation lines)
            if paid_out is not None:
                current_paid_out = paid_out
            if paid_in is not None:
                current_paid_in = paid_in
            if balance is not None:
                current_balance = balance

    # Don't forget the last transaction
    save_transaction()

    # Sort by date
    transactions.sort(key=lambda t: t.date)

    return transactions, errors


def extract_transactions(pages_text: list[str]) -> tuple[list[Transaction], Optional[StatementSummary], list[str]]:
    """
    Extract transactions from PDF page texts (fallback method).
    This is a simpler text-based extraction that may be less accurate.

    For better accuracy, use extract_transactions_from_words() with pdfplumber words.
    """
    # This is kept for compatibility but the words-based extraction is preferred
    transactions = []
    errors = ["Text-based extraction used - consider using word-level extraction for better accuracy"]

    full_text = '\n'.join(pages_text)
    summary = extract_summary(full_text)

    return transactions, summary, errors


def validate_transactions(transactions: list[Transaction], summary: StatementSummary) -> tuple[bool, list[str]]:
    """
    Validate extracted transactions against the statement summary.

    Returns:
        tuple: (is_valid, list of error messages)
    """
    errors = []

    if not transactions:
        errors.append("No transactions extracted")
        return False, errors

    if not summary:
        errors.append("Could not extract statement summary for validation")
        return True, errors

    total_in = sum(t.paid_in or 0 for t in transactions)
    total_out = sum(t.paid_out or 0 for t in transactions)

    # Allow small rounding differences (0.02)
    tolerance = 0.02

    if abs(total_in - summary.payments_in) > tolerance:
        errors.append(f"Payments In mismatch: extracted £{total_in:.2f}, expected £{summary.payments_in:.2f} (diff: £{abs(total_in - summary.payments_in):.2f})")

    if abs(total_out - summary.payments_out) > tolerance:
        errors.append(f"Payments Out mismatch: extracted £{total_out:.2f}, expected £{summary.payments_out:.2f} (diff: £{abs(total_out - summary.payments_out):.2f})")

    expected_closing = summary.opening_balance + total_in - total_out
    if abs(expected_closing - summary.closing_balance) > tolerance:
        errors.append(f"Balance calculation: £{summary.opening_balance:.2f} + £{total_in:.2f} - £{total_out:.2f} = £{expected_closing:.2f}, expected £{summary.closing_balance:.2f}")

    return len(errors) == 0, errors
