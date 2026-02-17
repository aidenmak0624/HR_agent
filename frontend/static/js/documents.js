// ============================================
// DOCUMENTS.JS - Document Management Functionality
// HR Intelligence Platform
// ============================================

let uploadedFiles = [];

// Handle drag and drop
function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    const uploadZone = document.getElementById('upload-zone');
    if (uploadZone) {
        uploadZone.classList.add('drag-over');
    }
}

function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    const uploadZone = document.getElementById('upload-zone');
    if (uploadZone) {
        uploadZone.classList.remove('drag-over');
    }
}

function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    const uploadZone = document.getElementById('upload-zone');
    if (uploadZone) {
        uploadZone.classList.remove('drag-over');
    }

    const files = event.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

function handleFileSelect(event) {
    const files = event.target.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

// Upload file to server
async function uploadFile(file) {
    // Validation
    const MAX_SIZE = 10 * 1024 * 1024; // 10MB
    const ALLOWED_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'image/jpeg', 'image/png', 'image/gif', 'image/jpg'];

    if (file.size > MAX_SIZE) {
        showUploadMessage(`File exceeds 10MB limit`, 'error');
        return;
    }

    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'jpg', 'jpeg', 'png', 'gif'].includes(ext)) {
        showUploadMessage(`File type .${ext} not allowed`, 'error');
        return;
    }

    // Show progress
    const progressContainer = document.getElementById('upload-progress-container');
    if (progressContainer) {
        progressContainer.style.display = 'block';
        document.getElementById('progress-filename').textContent = file.name;
        document.getElementById('progress-fill').style.width = '0%';
        document.getElementById('progress-percent').textContent = '0%';
    }

    // Prepare form data
    const formData = new FormData();
    formData.append('file', file);

    try {
        // Simulate progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress = Math.min(progress + Math.random() * 30, 90);
            updateProgress(progress);
        }, 200);

        const response = await apiCall('/api/v2/documents/upload', {
            method: 'POST',
            body: formData,
            headers: {} // Remove Content-Type to let browser set it with boundary
        });

        clearInterval(progressInterval);
        updateProgress(100);

        if (response && response.success) {
            uploadedFiles.push(response.data);
            showUploadMessage(`✅ File uploaded successfully: ${file.name}`, 'success');
            
            setTimeout(() => {
                loadUploadedFiles();
                document.getElementById('file-input').value = '';
                if (progressContainer) {
                    progressContainer.style.display = 'none';
                }
            }, 1000);
        } else {
            showUploadMessage(`❌ Upload failed: ${response?.error || 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Upload error:', error);
        showUploadMessage(`Error uploading file: ${error.message || 'Unknown error'}`, 'error');
    }
}

// Update progress bar
function updateProgress(percent) {
    const fill = document.getElementById('progress-fill');
    const percentText = document.getElementById('progress-percent');
    if (fill) {
        fill.style.width = Math.round(percent) + '%';
    }
    if (percentText) {
        percentText.textContent = Math.round(percent) + '%';
    }
}

// Show upload message
function showUploadMessage(message, type) {
    const container = document.getElementById('upload-messages');
    if (!container) return;

    const msgEl = document.createElement('div');
    msgEl.className = `upload-message ${type}`;
    msgEl.innerHTML = `<span>${message}</span>`;
    container.appendChild(msgEl);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        msgEl.remove();
    }, 5000);
}

// Load uploaded files
async function loadUploadedFiles() {
    // For now, show demo files
    // In a full implementation, this would load from the server
    renderUploadedFiles(uploadedFiles);
}

// Render uploaded files
function renderUploadedFiles(files) {
    const container = document.getElementById('uploaded-files-container');
    if (!container) return;

    if (!files || files.length === 0) {
        container.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 20px; grid-column: 1 / -1;">No documents uploaded yet</p>';
        return;
    }

    container.innerHTML = files.map(file => {
        const ext = file.original_name.split('.').pop().toLowerCase();
        const icons = {
            'pdf': '📄',
            'docx': '📝',
            'jpg': '🖼️',
            'jpeg': '🖼️',
            'png': '🖼️',
            'gif': '🖼️'
        };
        const icon = icons[ext] || '📎';

        const uploadedDate = new Date(file.uploaded_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });

        const sizeKB = Math.round(file.size / 1024);

        return `
            <div class="uploaded-file-card">
                <div class="file-icon">${icon}</div>
                <div class="file-name">${file.original_name}</div>
                <div class="file-meta">
                    <div>${sizeKB} KB</div>
                    <div>${uploadedDate}</div>
                </div>
                <div class="file-actions">
                    <button class="file-action-btn" onclick="downloadFile('${file.filename}', '${file.original_name}')">
                        ⬇️ Download
                    </button>
                    <button class="file-action-btn" onclick="deleteFile('${file.filename}')">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

// Download file
function downloadFile(filename, displayName) {
    showToast(`Downloading ${displayName}`, 'info');
    // In a real implementation, this would trigger a server download
    // For now, just show a message
    setTimeout(() => {
        showToast(`${displayName} downloaded`, 'success');
    }, 1500);
}

// Delete file
function deleteFile(filename) {
    if (!confirm(`Are you sure you want to delete this file?`)) {
        return;
    }

    uploadedFiles = uploadedFiles.filter(f => f.filename !== filename);
    renderUploadedFiles(uploadedFiles);
    showToast('File deleted', 'success');
}

// Template Selection
function selectTemplate(templateId) {
    document.getElementById('selected-template').value = templateId;
    const section = document.getElementById('generate-form-section');
    if (section) {
        section.style.display = 'block';
        section.scrollIntoView({ behavior: 'smooth' });
    }
}

// Cancel template generation
function cancelGenerate() {
    const section = document.getElementById('generate-form-section');
    if (section) {
        section.style.display = 'none';
    }
    document.getElementById('generate-form').reset();
}

// Generate document
async function generateDocument(event) {
    event.preventDefault();

    const templateSlug = document.getElementById('selected-template').value;
    const employeeSlug = document.getElementById('employee-select').value;
    const variables = document.getElementById('doc-variables').value;

    if (!templateSlug || !employeeSlug) {
        showToast('Please select template and employee', 'error');
        return;
    }

    // Map slug names to API template IDs
    const templateIdMap = {
        'employment-cert': 't4',
        'offer-letter': 't1',
        'promotion-letter': 't5',
        'separation-letter': 't3',
        'experience-letter': 't6',
        'salary-slip': 't7',
    };

    const templateId = templateIdMap[templateSlug] || templateSlug;

    // Get employee display name from the dropdown selection
    const employeeSelect = document.getElementById('employee-select');
    const employeeName = employeeSelect.options[employeeSelect.selectedIndex]?.text || employeeSlug;

    const submitBtn = event.target.querySelector('button[type="submit"]');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Generating...'; }

    try {
        const response = await apiCall('/api/v2/documents/generate', {
            method: 'POST',
            body: JSON.stringify({
                template_id: templateId,
                employee_id: employeeSlug,
                parameters: { variables: variables, employee_name: employeeName }
            })
        });

        if (response && response.success && response.data) {
            showToast(`Document generated successfully for ${employeeName}`, 'success');
            if (typeof addNotificationEvent === 'function') {
                const templateLabel = templateSlug.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                addNotificationEvent('Document Generated', `${templateLabel} created for ${employeeName}`);
            }
            cancelGenerate();
            // Refresh the recent documents table
            loadRecentDocuments();
        } else {
            showToast(response?.error || 'Failed to generate document', 'error');
        }
    } catch (error) {
        console.error('Error generating document:', error);
        showToast('Error generating document — check server connection', 'error');
    } finally {
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Generate Document'; }
    }
}

// Download document — generates a PDF from the demo data in the table
function downloadDocument(docId) {
    // Map demo doc IDs to metadata from the table
    const docMeta = {
        'emp-cert-001': { name: 'Employment_Certificate_John_Smith.pdf', employee: 'John Smith', type: 'Employment Certificate' },
        'offer-001':    { name: 'Offer_Letter_Alice_Johnson.pdf', employee: 'Alice Johnson', type: 'Offer Letter' },
        'promo-001':    { name: 'Promotion_Letter_Bob_Williams.pdf', employee: 'Bob Williams', type: 'Promotion Letter' },
        'exp-001':      { name: 'Experience_Letter_Carol_White.pdf', employee: 'Carol White', type: 'Experience Letter' },
    };

    const meta = docMeta[docId];
    if (!meta) {
        showToast('Document not found', 'error');
        return;
    }

    showToast(`Preparing ${meta.name}...`, 'info');

    // Generate a styled HTML document and download it
    const lines = _getDocumentBody(meta.type, meta.employee);
    const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    const bodyHtml = lines.map(line => {
        if (line === '') return '<br>';
        return `<p style="margin:0 0 6px 0;line-height:1.6;">${line.replace(/^- /, '&bull; ')}</p>`;
    }).join('\n');

    const htmlContent = `<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>${meta.type} - ${meta.employee}</title>
<style>
@media print { body { margin: 0; } .no-print { display: none; } }
body { font-family: 'Segoe UI', Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 40px; color: #333; }
.header { border-bottom: 3px solid #73C41D; padding-bottom: 12px; margin-bottom: 24px; }
.header h1 { color: #73C41D; font-size: 14px; margin: 0; letter-spacing: 1px; }
.title { font-size: 26px; color: #333; margin: 0 0 8px 0; font-weight: 700; }
.date { color: #888; font-size: 13px; margin-bottom: 32px; }
.body { font-size: 14px; color: #444; }
.footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid #ddd; font-size: 11px; color: #999; }
.print-btn { background: #73C41D; color: white; border: none; padding: 10px 24px; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; margin-bottom: 24px; }
.print-btn:hover { background: #65AD19; }
</style></head><body>
<button class="print-btn no-print" onclick="window.print()">Print / Save as PDF</button>
<div class="header"><h1>HR INTELLIGENCE PLATFORM</h1></div>
<div class="title">${meta.type}</div>
<div class="date">Date: ${today}</div>
<div class="body">${bodyHtml}</div>
<div class="footer">Generated by HR Intelligence Platform</div>
</body></html>`;

    const blob = new Blob([htmlContent], { type: 'text/html' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = meta.name.replace('.pdf', '.html');
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(a.href);
    showToast(`${meta.name.replace('.pdf', '.html')} downloaded — use Print to save as PDF`, 'success');
}

// Generate document body text for demo PDFs
function _getDocumentBody(type, employee) {
    const companyName = 'TechNova Solutions Inc.';
    const today = new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });

    const bodies = {
        'Employment Certificate': [
            'TO WHOM IT MAY CONCERN',
            '',
            `This is to certify that ${employee} has been employed with ${companyName} ` +
            `since January 15, 2021 and continues to be employed as of ${today}.`,
            '',
            `During their tenure, ${employee} has served in the Engineering department ` +
            `and has consistently demonstrated professionalism, dedication, and technical expertise.`,
            '',
            `Current Position: Software Engineer`,
            `Department: Engineering`,
            `Employment Status: Full-time`,
            '',
            `This certificate is issued upon request of the employee for whatever legal purpose it may serve.`,
            '',
            '',
            'Sincerely,',
            'Emily Rodriguez',
            'HR Director',
            companyName,
        ],
        'Offer Letter': [
            `Dear ${employee},`,
            '',
            `We are pleased to extend an offer of employment for the position of Senior Software Engineer ` +
            `at ${companyName}.`,
            '',
            `Start Date: April 1, 2024`,
            `Salary: $125,000 per annum`,
            `Department: Engineering`,
            `Reports to: Sarah Chen, Engineering Manager`,
            '',
            `Benefits include health, dental, and vision insurance, 401(k) with company match, ` +
            `15 days PTO, and professional development allowance.`,
            '',
            `Please confirm your acceptance by signing and returning this letter by March 25, 2024.`,
            '',
            '',
            'Warm regards,',
            'Emily Rodriguez',
            'HR Director',
            companyName,
        ],
        'Promotion Letter': [
            `Dear ${employee},`,
            '',
            `We are delighted to inform you of your promotion, effective April 1, 2024.`,
            '',
            `Previous Position: Software Engineer`,
            `New Position: Senior Software Engineer`,
            `New Salary: $135,000 per annum (increase of 12%)`,
            '',
            `This promotion reflects your outstanding contributions to the team and your ` +
            `consistent performance over the past year. Your leadership on the Platform ` +
            `Modernization project was instrumental in its success.`,
            '',
            `Congratulations on this well-deserved achievement!`,
            '',
            '',
            'Best regards,',
            'Sarah Chen, Engineering Manager',
            'Emily Rodriguez, HR Director',
            companyName,
        ],
        'Experience Letter': [
            'TO WHOM IT MAY CONCERN',
            '',
            `This letter serves as confirmation that ${employee} was employed with ` +
            `${companyName} from March 2020 to February 2024.`,
            '',
            `During their employment, ${employee} held the position of Software Engineer ` +
            `in the Engineering department. Key responsibilities included:`,
            '',
            `- Designing and developing scalable web applications`,
            `- Collaborating with cross-functional teams on product features`,
            `- Mentoring junior developers and conducting code reviews`,
            `- Contributing to system architecture decisions`,
            '',
            `${employee} was a valued member of our team and we wish them the very best ` +
            `in their future endeavors.`,
            '',
            '',
            'Sincerely,',
            'Emily Rodriguez',
            'HR Director',
            companyName,
        ],
    };

    return bodies[type] || [`${type} for ${employee}`, '', `Generated on ${today} by ${companyName}.`];
}

// Initialize Documents Page
document.addEventListener('DOMContentLoaded', () => {
    setActivePage('documents');
    loadUploadedFiles();
    loadRecentDocuments();
    loadEmployeeDropdown();
    console.log('✅ Documents.js loaded successfully');
});

// Load recent documents from DB
async function loadRecentDocuments() {
    const tbody = document.getElementById('recent-docs-tbody');
    if (!tbody) return;
    try {
        const response = await apiCall('/api/v2/documents/recent');
        if (response && response.data && response.data.length > 0) {
            tbody.innerHTML = '';
            response.data.forEach(doc => {
                const dateStr = doc.created_at ? new Date(doc.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—';
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${doc.file_name}</td>
                    <td>${doc.employee_name}</td>
                    <td>${doc.template_name}</td>
                    <td>${dateStr}</td>
                    <td><button class="action-link" onclick="downloadDocument('doc-${doc.id}')">⬇️ Download</button></td>
                `;
                tbody.appendChild(tr);
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-secondary);">No documents generated yet</td></tr>';
        }
    } catch (error) {
        console.error('Error loading recent documents:', error);
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-secondary);">Unable to load documents</td></tr>';
    }
}

// Load employees into dropdown from API
async function loadEmployeeDropdown() {
    const select = document.getElementById('employee-select');
    if (!select) return;
    try {
        const response = await apiCall('/api/v2/employees/names');
        if (response && response.data && response.data.length > 0) {
            select.innerHTML = '<option value="">Select an employee</option>';
            response.data.forEach(emp => {
                const slug = `${emp.first_name}-${emp.last_name}`.toLowerCase().replace(/\s+/g, '-');
                const opt = document.createElement('option');
                opt.value = slug;
                opt.textContent = `${emp.first_name} ${emp.last_name}`;
                select.appendChild(opt);
            });
        } else {
            select.innerHTML = '<option value="">Select an employee</option>';
        }
    } catch (error) {
        console.error('Error loading employees:', error);
        select.innerHTML = '<option value="">Select an employee</option>';
    }
}

// Export functions
window.handleDragOver = handleDragOver;
window.handleDragLeave = handleDragLeave;
window.handleDrop = handleDrop;
window.handleFileSelect = handleFileSelect;
window.uploadFile = uploadFile;
window.loadUploadedFiles = loadUploadedFiles;
window.selectTemplate = selectTemplate;
window.cancelGenerate = cancelGenerate;
window.generateDocument = generateDocument;
window.downloadDocument = downloadDocument;
window.downloadFile = downloadFile;
window.deleteFile = deleteFile;
window.loadRecentDocuments = loadRecentDocuments;
window.loadEmployeeDropdown = loadEmployeeDropdown;
