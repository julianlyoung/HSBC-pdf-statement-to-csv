# HSBC Statement PDF to CSV Converter

A Python web application that converts HSBC UK bank statement PDFs into CSV format. Features a user-friendly drag-and-drop interface, batch processing, real-time progress updates, and automatic validation.

## Features

- **Drag & Drop Upload** - Easy file upload with support for multiple PDFs
- **Batch Processing** - Convert multiple statements at once
- **Real-time Progress** - Live progress bar and log updates as files are processed
- **Automatic Validation** - Verifies extracted totals match statement summary
- **CSV Preview** - View converted data before downloading
- **Download All** - Export all converted files as a single ZIP

## Screenshot

```
┌─────────────────────────────────────────────────────────────┐
│           HSBC Statement PDF to CSV Converter               │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │         Drag & drop PDF files here                    │  │
│  │            or click to select files                   │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  [Process Files]                                            │
├─────────────────────────────────────────────────────────────┤
│  Processing Log:                                            │
│  [12:30:45] Processing: 2024-01-28_Statement.pdf            │
│  [12:30:46] Extracted 48 transactions                       │
│  [12:30:46] Total In: £2,392.07, Total Out: £1,894.42       │
├─────────────────────────────────────────────────────────────┤
│  Results:                              [Download All (ZIP)] │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ File          │ Status  │ Transactions │ Actions       ││
│  │ Jan-2024.pdf  │ Success │ 48          │ Preview | DL   ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

## Installation

### Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/hsbc-statementpdftocsv.git
   cd hsbc-statementpdftocsv
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**

   Windows:
   ```bash
   venv\Scripts\activate
   ```

   macOS/Linux:
   ```bash
   source venv/bin/activate
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running the Application

**Windows:**
```bash
# Double-click run.bat
# OR
venv\Scripts\activate
python app.py
```

**macOS/Linux:**
```bash
source venv/bin/activate
python app.py
```

Then open your browser to: **http://localhost:5000**

### Converting Statements

1. Drag and drop your HSBC statement PDF(s) onto the upload area, or click to select files
2. Click **Process Files**
3. Watch the real-time progress and log output
4. Preview results and download individual CSVs or use **Download All (ZIP)**

### CSV Output Format

The generated CSV files have the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| Date | Transaction date (DD/MM/YYYY) | 29/12/2024 |
| Bank | Always "hsbc" | hsbc |
| Description | Transaction description | PAYPAL PAYMENT |
| Income | Money received (with £ symbol) | £500.00 |
| Expenses | Money spent (negative, with £ symbol) | -£125.00 |

## Supported Statement Types

This tool is designed for **HSBC UK personal bank account statements** in PDF format. It parses:

- Current account statements
- Monthly statements with transaction listings

### Payment Types Recognized

| Code | Type |
|------|------|
| DD | Direct Debit |
| VIS | Visa Card Payment |
| BP | Bank Payment |
| CR | Credit/Transfer |
| SO | Standing Order |
| ))) | Contactless Payment |
| DR | Debit |
| OBP | Online Bank Payment |
| ATM | Cash Machine |
| CHQ | Cheque |

## Project Structure

```
hsbc-statementpdftocsv/
├── app.py                 # Flask web application
├── run.bat                # Windows startup script
├── requirements.txt       # Python dependencies
├── parser/
│   ├── __init__.py
│   ├── pdf_parser.py      # PDF text extraction
│   ├── transaction_extractor.py  # Transaction parsing
│   └── csv_generator.py   # CSV output generation
├── static/
│   ├── css/style.css      # Application styles
│   └── js/app.js          # Frontend JavaScript
├── templates/
│   └── index.html         # Web interface
└── tests/
    └── test_parser.py     # Automated tests
```

## Running Tests

```bash
# Activate virtual environment first
python -m pytest tests/ -v
```

## How It Works

1. **PDF Parsing**: Uses `pdfplumber` to extract text with position data
2. **Column Detection**: Identifies transaction columns by x-coordinate positions
3. **Transaction Extraction**: Parses dates, payment types, descriptions, and amounts
4. **Validation**: Compares extracted totals against the statement's summary section
5. **CSV Generation**: Outputs formatted CSV matching the expected structure

## Troubleshooting

### "No transactions extracted"
- Ensure the PDF is a genuine HSBC UK statement
- Check that the PDF isn't password-protected or scanned (needs to be text-based)

### Amounts don't match expected totals
- Some statements may have different layouts
- Check the warnings in the processing log for details

### Application won't start
- Ensure Python 3.10+ is installed
- Verify the virtual environment is activated
- Run `pip install -r requirements.txt` again

## Privacy & Security

- **All processing is local** - Your PDFs never leave your computer
- **No data is stored permanently** - Uploaded files are deleted after processing
- **No external connections** - The app works completely offline

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
