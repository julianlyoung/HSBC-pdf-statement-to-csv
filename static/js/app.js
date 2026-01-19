// HSBC Statement PDF to CSV Converter - Frontend JavaScript

// Global variable for batch ID (used by download all)
let currentBatchId = null;

document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const fileList = document.getElementById('fileList');
    const processBtn = document.getElementById('processBtn');
    const progressSection = document.getElementById('progressSection');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    const logSection = document.getElementById('logSection');
    const logContainer = document.getElementById('logContainer');
    const resultsSection = document.getElementById('resultsSection');
    const resultsSummary = document.getElementById('resultsSummary');
    const resultsTable = document.getElementById('resultsTable');

    let selectedFiles = [];

    // Drag and Drop handlers
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        handleFiles(e.dataTransfer.files);
    });

    fileInput.addEventListener('change', (e) => {
        handleFiles(e.target.files);
    });

    function handleFiles(files) {
        for (const file of files) {
            if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
                if (!selectedFiles.some(f => f.name === file.name)) {
                    selectedFiles.push(file);
                }
            }
        }
        updateFileList();
    }

    function updateFileList() {
        fileList.innerHTML = '';

        selectedFiles.forEach((file, index) => {
            const item = document.createElement('div');
            item.className = 'file-item';
            item.innerHTML = `
                <span class="file-name">${file.name}</span>
                <span class="file-size">${formatFileSize(file.size)}</span>
                <button class="remove-btn" data-index="${index}">&times;</button>
            `;
            fileList.appendChild(item);
        });

        processBtn.disabled = selectedFiles.length === 0;

        // Add remove button handlers
        document.querySelectorAll('.remove-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const index = parseInt(e.target.dataset.index);
                selectedFiles.splice(index, 1);
                updateFileList();
            });
        });
    }

    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    // Process button click
    processBtn.addEventListener('click', async () => {
        if (selectedFiles.length === 0) return;

        // Show progress
        progressSection.classList.remove('hidden');
        logSection.classList.remove('hidden');
        resultsSection.classList.add('hidden');
        processBtn.disabled = true;

        progressFill.style.width = '5%';
        progressText.textContent = 'Uploading files...';
        logContainer.innerHTML = '';

        // Create form data
        const formData = new FormData();
        selectedFiles.forEach(file => {
            formData.append('files[]', file);
        });

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            // Handle Server-Sent Events stream
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process complete events in buffer
                const lines = buffer.split('\n\n');
                buffer = lines.pop(); // Keep incomplete event in buffer

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            handleStreamEvent(data);
                        } catch (e) {
                            console.error('Failed to parse event:', e);
                        }
                    }
                }
            }

            // Process any remaining data
            if (buffer.startsWith('data: ')) {
                try {
                    const data = JSON.parse(buffer.slice(6));
                    handleStreamEvent(data);
                } catch (e) {
                    // Ignore incomplete final chunk
                }
            }

        } catch (error) {
            progressText.textContent = 'Error: ' + error.message;
            addLog('Error: ' + error.message, 'error');
        }

        processBtn.disabled = false;
    });

    function handleStreamEvent(data) {
        switch (data.type) {
            case 'start':
                progressFill.style.width = '10%';
                progressText.textContent = `Starting: ${data.total_files} file(s)`;
                addLog(data.message, 'info');
                break;

            case 'progress':
                const percent = Math.max(10, Math.min(95, 10 + (data.percent * 0.85)));
                progressFill.style.width = `${percent}%`;
                progressText.textContent = `Processing ${data.current}/${data.total}: ${data.filename}`;
                break;

            case 'log':
                addLog(data.message, data.level, data.time);
                break;

            case 'file_complete':
                const statusIcon = data.status === 'success' ? '[OK]' :
                                   data.status === 'warning' ? '[WARN]' : '[FAIL]';
                addLog(`${statusIcon} ${data.filename} complete`, data.status === 'error' ? 'error' : 'info');
                break;

            case 'complete':
                progressFill.style.width = '100%';
                progressText.textContent = 'Complete!';
                displayResults(data);

                // Hide progress after a moment
                setTimeout(() => {
                    progressSection.classList.add('hidden');
                }, 1500);
                break;
        }
    }

    function displayLogs(logs) {
        logContainer.innerHTML = '';
        logs.forEach(log => {
            addLog(log.message, log.level, log.time);
        });
    }

    function addLog(message, level = 'info', time = null) {
        if (!time) {
            time = new Date().toLocaleTimeString('en-GB', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        }

        const entry = document.createElement('div');
        entry.className = `log-entry ${level}`;
        entry.innerHTML = `<span class="time">[${time}]</span>${escapeHtml(message)}`;
        logContainer.appendChild(entry);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    function displayResults(data) {
        resultsSection.classList.remove('hidden');

        // Store batch ID for download all
        currentBatchId = data.batch_id;

        const results = data.results;

        // Show Download All button if there are successful conversions
        const successfulFiles = results.filter(r => r.csv_file);
        const downloadAllBtn = document.getElementById('downloadAllBtn');
        if (successfulFiles.length > 0) {
            downloadAllBtn.classList.remove('hidden');
        } else {
            downloadAllBtn.classList.add('hidden');
        }
        const successCount = results.filter(r => r.status === 'success').length;
        const warningCount = results.filter(r => r.status === 'warning').length;
        const errorCount = results.filter(r => r.status === 'error').length;
        const totalTransactions = results.reduce((sum, r) => sum + (r.transactions || 0), 0);

        // Summary cards
        resultsSummary.innerHTML = `
            <div class="summary-card">
                <div class="value">${results.length}</div>
                <div class="label">Files Processed</div>
            </div>
            <div class="summary-card success">
                <div class="value">${successCount}</div>
                <div class="label">Successful</div>
            </div>
            <div class="summary-card warning">
                <div class="value">${warningCount}</div>
                <div class="label">With Warnings</div>
            </div>
            <div class="summary-card error">
                <div class="value">${errorCount}</div>
                <div class="label">Failed</div>
            </div>
            <div class="summary-card">
                <div class="value">${totalTransactions}</div>
                <div class="label">Total Transactions</div>
            </div>
        `;

        // Results table
        let tableHtml = `
            <table>
                <thead>
                    <tr>
                        <th>File</th>
                        <th>Status</th>
                        <th>Transactions</th>
                        <th>Total In</th>
                        <th>Total Out</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        results.forEach(result => {
            const statusClass = result.status;
            const statusText = result.status.charAt(0).toUpperCase() + result.status.slice(1);

            tableHtml += `
                <tr>
                    <td>${escapeHtml(result.filename)}</td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td>${result.transactions || '-'}</td>
                    <td>${result.total_in ? '£' + result.total_in.toFixed(2) : '-'}</td>
                    <td>${result.total_out ? '£' + result.total_out.toFixed(2) : '-'}</td>
                    <td>
                        ${result.csv_file ? `
                            <button class="btn btn-secondary action-btn" onclick="previewCSV('${result.csv_file}', '${escapeHtml(result.filename)}')">
                                Preview
                            </button>
                            <button class="btn btn-primary action-btn" onclick="downloadCSV('${result.csv_file}')">
                                Download
                            </button>
                        ` : '-'}
                    </td>
                </tr>
            `;

            if (result.warnings && result.warnings.length > 0) {
                tableHtml += `
                    <tr>
                        <td colspan="6" style="padding: 8px 15px; background: #fff3cd; font-size: 0.85rem;">
                            <strong>Warnings:</strong> ${escapeHtml(result.warnings.join('; '))}
                        </td>
                    </tr>
                `;
            }

            if (result.errors && result.errors.length > 0) {
                tableHtml += `
                    <tr>
                        <td colspan="6" style="padding: 8px 15px; background: #f8d7da; font-size: 0.85rem;">
                            <strong>Errors:</strong> ${escapeHtml(result.errors.join('; '))}
                        </td>
                    </tr>
                `;
            }
        });

        tableHtml += '</tbody></table>';
        resultsTable.innerHTML = tableHtml;

        // Clear selected files
        selectedFiles = [];
        updateFileList();
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});

// Global functions for button onclick handlers
async function previewCSV(filename, originalName) {
    const modal = document.getElementById('previewModal');
    const previewTitle = document.getElementById('previewTitle');
    const previewContent = document.getElementById('previewContent');
    const downloadBtn = document.getElementById('downloadPreviewBtn');

    previewTitle.textContent = `Preview: ${originalName.replace('.pdf', '.csv')}`;
    previewContent.innerHTML = 'Loading...';

    try {
        const response = await fetch(`/api/preview/${filename}`);
        const data = await response.json();

        if (data.error) {
            previewContent.innerHTML = `<p>Error: ${data.error}</p>`;
            return;
        }

        // Parse CSV and create table
        const headers = data.header.split(',');
        let tableHtml = '<table><thead><tr>';
        headers.forEach(h => {
            tableHtml += `<th>${escapeHtmlGlobal(h)}</th>`;
        });
        tableHtml += '</tr></thead><tbody>';

        data.rows.forEach(row => {
            if (row.trim()) {
                tableHtml += '<tr>';
                // Simple CSV parsing (doesn't handle all edge cases)
                const cells = parseCSVRow(row);
                cells.forEach(cell => {
                    tableHtml += `<td>${escapeHtmlGlobal(cell)}</td>`;
                });
                tableHtml += '</tr>';
            }
        });

        tableHtml += '</tbody></table>';

        if (data.total_rows > 20) {
            tableHtml += `<p style="margin-top: 15px; color: #666;">Showing 20 of ${data.total_rows} rows</p>`;
        }

        previewContent.innerHTML = tableHtml;
        downloadBtn.onclick = () => downloadCSV(filename);

    } catch (error) {
        previewContent.innerHTML = `<p>Error loading preview: ${error.message}</p>`;
    }

    modal.classList.remove('hidden');
}

function parseCSVRow(row) {
    const cells = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < row.length; i++) {
        const char = row[i];

        if (char === '"') {
            inQuotes = !inQuotes;
        } else if (char === ',' && !inQuotes) {
            cells.push(current.trim());
            current = '';
        } else {
            current += char;
        }
    }
    cells.push(current.trim());

    return cells;
}

function closePreview() {
    document.getElementById('previewModal').classList.add('hidden');
}

function downloadCSV(filename) {
    window.location.href = `/api/download/${filename}`;
}

function downloadAll() {
    if (currentBatchId) {
        window.location.href = `/api/download-all/${currentBatchId}`;
    }
}

function escapeHtmlGlobal(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modal on outside click
document.getElementById('previewModal').addEventListener('click', (e) => {
    if (e.target.id === 'previewModal') {
        closePreview();
    }
});
