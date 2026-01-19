"""Flask web application for HSBC Statement PDF to CSV converter."""

import os
import io
import uuid
import zipfile
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename

from parser import HSBCStatementParser, generate_csv, generate_combined_csv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max
app.config['UPLOAD_FOLDER'] = Path('uploads')
app.config['OUTPUT_FOLDER'] = Path('output')
app.config['LOGS_FOLDER'] = Path('logs')

# Create folders
for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER'], app.config['LOGS_FOLDER']]:
    folder.mkdir(exist_ok=True)

# Store processing results in memory (for demo purposes)
# In production, use a database
processing_results = {}


def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'


@app.route('/')
def index():
    """Main page."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Handle PDF file uploads and process them with streaming progress."""
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files[]')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected'}), 400

    # Save files first (can't access them in generator after request ends)
    batch_id = str(uuid.uuid4())[:8]
    saved_files = []

    for file in files:
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = app.config['UPLOAD_FOLDER'] / f"{batch_id}_{filename}"
            file.save(upload_path)
            saved_files.append((filename, upload_path))

    def generate():
        import json

        results = []
        log_entries = []
        parser = HSBCStatementParser()
        total_files = len(saved_files)

        def send_event(event_type, data):
            return f"data: {json.dumps({'type': event_type, **data})}\n\n"

        def log(message, level='info'):
            timestamp = datetime.now().strftime('%H:%M:%S')
            log_entries.append({'time': timestamp, 'level': level, 'message': message})
            logger.log(getattr(logging, level.upper()), message)

        yield send_event('start', {
            'batch_id': batch_id,
            'total_files': total_files,
            'message': f'Starting batch {batch_id} with {total_files} file(s)'
        })

        for idx, (filename, upload_path) in enumerate(saved_files):
            progress = int(((idx) / total_files) * 100)
            yield send_event('progress', {
                'current': idx + 1,
                'total': total_files,
                'percent': progress,
                'filename': filename
            })

            yield send_event('log', {
                'time': datetime.now().strftime('%H:%M:%S'),
                'level': 'info',
                'message': f'Processing: {filename}'
            })

            try:
                # Parse PDF
                result = parser.parse(upload_path)

                if result.success:
                    # Generate CSV
                    csv_filename = filename.replace('.pdf', '.csv').replace('.PDF', '.csv')
                    csv_path = app.config['OUTPUT_FOLDER'] / f"{batch_id}_{csv_filename}"
                    csv_content = generate_csv(result.transactions, csv_path)

                    total_in = sum(t.paid_in or 0 for t in result.transactions)
                    total_out = sum(t.paid_out or 0 for t in result.transactions)

                    yield send_event('log', {
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'level': 'info',
                        'message': f'  Extracted {len(result.transactions)} transactions'
                    })

                    yield send_event('log', {
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'level': 'info',
                        'message': f'  Total In: {total_in:.2f}, Total Out: {total_out:.2f}'
                    })

                    if result.warnings:
                        for warning in result.warnings:
                            yield send_event('log', {
                                'time': datetime.now().strftime('%H:%M:%S'),
                                'level': 'warning',
                                'message': f'  Warning: {warning}'
                            })

                    results.append({
                        'filename': filename,
                        'status': 'success' if not result.warnings else 'warning',
                        'transactions': len(result.transactions),
                        'total_in': total_in,
                        'total_out': total_out,
                        'csv_file': f"{batch_id}_{csv_filename}",
                        'warnings': result.warnings,
                        'summary': {
                            'opening': result.summary.opening_balance if result.summary else 0,
                            'closing': result.summary.closing_balance if result.summary else 0,
                            'expected_in': result.summary.payments_in if result.summary else 0,
                            'expected_out': result.summary.payments_out if result.summary else 0,
                        }
                    })

                    yield send_event('file_complete', {
                        'filename': filename,
                        'status': 'success' if not result.warnings else 'warning',
                        'transactions': len(result.transactions)
                    })
                else:
                    yield send_event('log', {
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'level': 'error',
                        'message': f'  Failed: {result.errors}'
                    })
                    results.append({
                        'filename': filename,
                        'status': 'error',
                        'errors': result.errors,
                    })
                    yield send_event('file_complete', {
                        'filename': filename,
                        'status': 'error'
                    })

            except Exception as e:
                yield send_event('log', {
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'level': 'error',
                    'message': f'  Error processing {filename}: {str(e)}'
                })
                results.append({
                    'filename': filename,
                    'status': 'error',
                    'errors': [str(e)],
                })

            finally:
                # Clean up uploaded file
                if upload_path.exists():
                    upload_path.unlink()

        # Store results for later retrieval
        processing_results[batch_id] = {
            'results': results,
            'logs': log_entries,
            'timestamp': datetime.now().isoformat(),
        }

        yield send_event('log', {
            'time': datetime.now().strftime('%H:%M:%S'),
            'level': 'info',
            'message': f'Batch {batch_id} complete: {len(results)} file(s) processed'
        })

        yield send_event('complete', {
            'batch_id': batch_id,
            'results': results
        })

    return Response(generate(), mimetype='text/event-stream')


@app.route('/api/download/<filename>')
def download_file(filename):
    """Download a generated CSV file."""
    file_path = app.config['OUTPUT_FOLDER'] / secure_filename(filename)
    if file_path.exists():
        return send_file(
            file_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename.split('_', 1)[1] if '_' in filename else filename
        )
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/preview/<filename>')
def preview_file(filename):
    """Preview CSV content."""
    file_path = app.config['OUTPUT_FOLDER'] / secure_filename(filename)
    if file_path.exists():
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
        return jsonify({
            'header': lines[0] if lines else '',
            'rows': lines[1:21],  # First 20 data rows
            'total_rows': len(lines) - 1,
        })
    return jsonify({'error': 'File not found'}), 404


@app.route('/api/results/<batch_id>')
def get_results(batch_id):
    """Get processing results for a batch."""
    if batch_id in processing_results:
        return jsonify(processing_results[batch_id])
    return jsonify({'error': 'Batch not found'}), 404


@app.route('/api/download-all/<batch_id>')
def download_all(batch_id):
    """Download all CSV files from a batch as a ZIP."""
    if batch_id not in processing_results:
        return jsonify({'error': 'Batch not found'}), 404

    results = processing_results[batch_id]['results']
    csv_files = [r['csv_file'] for r in results if r.get('csv_file')]

    if not csv_files:
        return jsonify({'error': 'No CSV files to download'}), 404

    # Create ZIP in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for csv_filename in csv_files:
            file_path = app.config['OUTPUT_FOLDER'] / secure_filename(csv_filename)
            if file_path.exists():
                # Use original filename (without batch prefix) in the ZIP
                original_name = csv_filename.split('_', 1)[1] if '_' in csv_filename else csv_filename
                zip_file.write(file_path, original_name)

    zip_buffer.seek(0)

    # Generate ZIP filename with date
    date_str = datetime.now().strftime('%Y-%m-%d')
    zip_filename = f'hsbc_statements_{date_str}.zip'

    return send_file(
        zip_buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )


if __name__ == '__main__':
    print("\n" + "="*60)
    print("HSBC Statement PDF to CSV Converter")
    print("="*60)
    print("\nStarting server at http://localhost:5000")
    print("Press Ctrl+C to stop\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
