// ============================================
// WORKFLOWS.JS - Workflow Management Functionality
// HR Intelligence Platform
// ============================================

// Approve a workflow request
async function approveRequest(requestId, evt) {
    // Show custom approve confirmation modal
    const confirmed = await _showApproveModal(requestId);
    if (!confirmed) return;

    // Find the card element first (before any async operations)
    const card = document.querySelector(`[data-request-id="${requestId}"]`) ||
                 (evt && evt.target ? evt.target.closest('.approval-card') : null);

    // Disable buttons during API call
    if (card) {
        const buttons = card.querySelectorAll('button');
        buttons.forEach(btn => { btn.disabled = true; btn.style.opacity = '0.5'; });
    }

    // Helper: check if this is a demo/static card ID (non-numeric)
    const isDemoId = isNaN(Number(requestId));

    // For demo IDs, handle locally without relying on API
    if (isDemoId) {
        showToast('Request approved successfully', 'success');
        if (typeof addNotificationEvent === 'function') {
            addNotificationEvent('Request Approved', `Approved request ${requestId}`);
        }
        _fadeOutCard(card, 'right');
        // Fire-and-forget API call for demo cards
        apiCall('/api/v2/workflows/approve', {
            method: 'POST',
            body: JSON.stringify({ request_id: requestId })
        }).catch(() => {});
        return;
    }

    try {
        const response = await apiCall('/api/v2/workflows/approve', {
            method: 'POST',
            body: JSON.stringify({ request_id: requestId })
        });

        const isApproved = (response && response.data && response.data.status === 'approved') ||
                           (response && response.success);

        if (isApproved) {
            showToast('Request approved successfully', 'success');
            if (typeof addNotificationEvent === 'function') {
                addNotificationEvent('Request Approved', `Approved request ${requestId}`);
            }
            _fadeOutCard(card, 'right');
        } else {
            showToast('Failed to approve request', 'error');
            _enableCardButtons(card);
        }
    } catch (error) {
        console.error('Error approving request:', error);
        showToast('Error approving request', 'error');
        _enableCardButtons(card);
    }
}

// Reject a workflow request
async function rejectRequest(requestId, evt) {
    // Use a custom modal for better UX
    const reason = await _showRejectModal(requestId);
    if (reason === null) return; // user cancelled

    // Find the card element first (before any async operations)
    const card = document.querySelector(`[data-request-id="${requestId}"]`) ||
                 (evt && evt.target ? evt.target.closest('.approval-card') : null);

    // Disable buttons during API call
    if (card) {
        const buttons = card.querySelectorAll('button');
        buttons.forEach(btn => { btn.disabled = true; btn.style.opacity = '0.5'; });
    }

    const isDemoId = isNaN(Number(requestId));

    // For demo IDs, handle locally without relying on API
    if (isDemoId) {
        showToast('Request rejected', 'info');
        if (typeof addNotificationEvent === 'function') {
            addNotificationEvent('Request Rejected', `Rejected request ${requestId}: ${reason || 'No reason provided'}`);
        }
        _fadeOutCard(card, 'left');
        // Fire-and-forget API call for demo cards
        apiCall('/api/v2/workflows/reject', {
            method: 'POST',
            body: JSON.stringify({ request_id: requestId, reason: reason })
        }).catch(() => {});
        return;
    }

    try {
        const response = await apiCall('/api/v2/workflows/reject', {
            method: 'POST',
            body: JSON.stringify({ request_id: requestId, reason: reason })
        });

        const isRejected = (response && response.data && response.data.status === 'rejected') ||
                           (response && response.success);

        if (isRejected) {
            showToast('Request rejected', 'info');
            if (typeof addNotificationEvent === 'function') {
                addNotificationEvent('Request Rejected', `Rejected request ${requestId}: ${reason || 'No reason provided'}`);
            }
            _fadeOutCard(card, 'left');
        } else {
            showToast('Failed to reject request', 'error');
            _enableCardButtons(card);
        }
    } catch (error) {
        console.error('Error rejecting request:', error);
        showToast('Error rejecting request', 'error');
        _enableCardButtons(card);
    }
}

// ============================================
// APPROVE CONFIRMATION MODAL
// ============================================

function _showApproveModal(requestId) {
    return new Promise((resolve) => {
        let modal = document.getElementById('approve-confirm-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'approve-confirm-modal';
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Approve Request</h3>
                        <button class="modal-close" id="approve-modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p style="margin:0;color:var(--text-secondary);font-size:14px;">
                            Are you sure you want to approve this request? This action cannot be undone.
                        </p>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" id="approve-modal-cancel">Cancel</button>
                        <button class="btn-primary" id="approve-modal-confirm">✓ Approve</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        modal.style.display = 'flex';

        function cleanup(result) {
            modal.style.display = 'none';
            document.getElementById('approve-modal-close').onclick = null;
            document.getElementById('approve-modal-cancel').onclick = null;
            document.getElementById('approve-modal-confirm').onclick = null;
            document.removeEventListener('keydown', escHandler);
            modal.onclick = null;
            resolve(result);
        }

        document.getElementById('approve-modal-close').onclick = () => cleanup(false);
        document.getElementById('approve-modal-cancel').onclick = () => cleanup(false);
        document.getElementById('approve-modal-confirm').onclick = () => cleanup(true);

        const escHandler = (e) => {
            if (e.key === 'Escape') cleanup(false);
        };
        document.addEventListener('keydown', escHandler);

        modal.onclick = (e) => { if (e.target === modal) cleanup(false); };
    });
}

// ============================================
// REJECT REASON MODAL
// ============================================

function _showRejectModal(requestId) {
    return new Promise((resolve) => {
        let modal = document.getElementById('reject-reason-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'reject-reason-modal';
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h3>Reject Request</h3>
                        <button class="modal-close" id="reject-modal-close">&times;</button>
                    </div>
                    <div class="modal-body">
                        <p style="margin:0 0 12px;color:var(--text-secondary);font-size:14px;">
                            Are you sure you want to reject this request? You may provide a reason below.
                        </p>
                        <textarea id="reject-reason-input" class="form-input" rows="3"
                            placeholder="Reason for rejection (optional)"
                            style="resize:vertical;width:100%;box-sizing:border-box;"></textarea>
                    </div>
                    <div class="modal-footer">
                        <button class="btn-secondary" id="reject-modal-cancel">Cancel</button>
                        <button class="btn-primary" id="reject-modal-confirm"
                            style="background:var(--danger, #E74C3C);color:white;">✗ Reject</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        const input = document.getElementById('reject-reason-input');
        input.value = '';
        modal.style.display = 'flex';
        setTimeout(() => input.focus(), 100);

        function cleanup(result) {
            modal.style.display = 'none';
            document.getElementById('reject-modal-close').onclick = null;
            document.getElementById('reject-modal-cancel').onclick = null;
            document.getElementById('reject-modal-confirm').onclick = null;
            document.removeEventListener('keydown', escHandler);
            modal.onclick = null;
            resolve(result);
        }

        document.getElementById('reject-modal-close').onclick = () => cleanup(null);
        document.getElementById('reject-modal-cancel').onclick = () => cleanup(null);
        document.getElementById('reject-modal-confirm').onclick = () => cleanup(input.value.trim());

        const escHandler = (e) => {
            if (e.key === 'Escape') cleanup(null);
        };
        document.addEventListener('keydown', escHandler);

        modal.onclick = (e) => { if (e.target === modal) cleanup(null); };
    });
}

// ============================================
// UI HELPERS
// ============================================

function _fadeOutCard(card, direction) {
    if (!card) return;
    const translate = direction === 'right' ? 'translateX(30px)' : 'translateX(-30px)';
    card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
    card.style.opacity = '0';
    card.style.transform = translate;
    setTimeout(() => {
        card.remove();
        updatePendingCount();
        // If no more approval cards, show an empty state
        const remaining = document.querySelectorAll('.approval-card');
        const container = document.getElementById('approval-cards-container');
        if (container && remaining.length === 0) {
            container.innerHTML = '<div class="empty-state" style="padding:32px;text-align:center;color:var(--text-secondary);"><p style="font-size:32px;margin-bottom:8px;">✅</p><p style="font-weight:600;">All caught up!</p><p style="font-size:13px;">No pending approvals at this time.</p></div>';
        }
    }, 400);
}

function _enableCardButtons(card) {
    if (!card) return;
    const buttons = card.querySelectorAll('button');
    buttons.forEach(btn => { btn.disabled = false; btn.style.opacity = '1'; });
}

// Load pending approvals from API
async function loadPendingApprovals() {
    const container = document.getElementById('approval-cards-container');
    try {
        const response = await apiCall('/api/v2/workflows/pending');
        if (response && response.data && response.data.pending) {
            renderPendingApprovals(response.data.pending);
        } else if (container) {
            container.innerHTML = '<div class="empty-state" style="padding:32px;text-align:center;color:var(--text-secondary);"><p style="font-size:32px;margin-bottom:8px;">&#10003;</p><p style="font-weight:600;">All caught up!</p><p style="font-size:13px;">No pending approvals at this time.</p></div>';
        }
    } catch (error) {
        console.error('Error loading pending approvals:', error);
        if (container) container.innerHTML = '<p style="padding:24px;text-align:center;color:var(--text-secondary);">Unable to load approvals.</p>';
    }
}

// Render pending approval cards
function renderPendingApprovals(pendingList) {
    const container = document.getElementById('approval-cards-container');
    if (!container) return;

    container.innerHTML = '';

    if (!pendingList || pendingList.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding:32px;text-align:center;color:var(--text-secondary);"><p style="font-size:32px;margin-bottom:8px;">&#10003;</p><p style="font-weight:600;">All caught up!</p><p style="font-size:13px;">No pending approvals at this time.</p></div>';
        return;
    }

    pendingList.forEach(item => {
        const priorityClass = item.priority === 'high' ? 'priority-high' :
                             item.priority === 'medium' ? 'priority-medium' :
                             'priority-low';
        const priorityLabel = (item.priority || 'normal').charAt(0).toUpperCase() + (item.priority || 'normal').slice(1) + ' Priority';

        const card = document.createElement('div');
        card.className = 'approval-card';
        card.dataset.requestId = item.request_id;
        card.innerHTML = `
            <div class="approval-header">
                <h4>${item.type} - ${item.requester}</h4>
                <span class="priority-badge ${priorityClass}">${priorityLabel}</span>
            </div>
            <p class="approval-detail">${item.detail}</p>
            <p class="approval-requested">Requested: ${formatDate(item.requested_date)}</p>
            <div class="approval-actions">
                <button class="btn-approve" onclick="approveRequest('${item.request_id}', event)">&#10003; Approve</button>
                <button class="btn-reject" onclick="rejectRequest('${item.request_id}', event)">&#10007; Reject</button>
            </div>
        `;
        container.appendChild(card);
    });
}

// Load active workflows from API (real DB data)
async function loadActiveWorkflows() {
    const container = document.getElementById('workflow-cards-container');
    if (!container) return;
    try {
        const response = await apiCall('/api/v2/workflows/active');
        if (response && response.data && response.data.length > 0) {
            renderActiveWorkflows(response.data);
        } else {
            container.innerHTML = '<div class="empty-state" style="padding:32px;text-align:center;color:var(--text-secondary);"><p style="font-size:32px;margin-bottom:8px;">&#128203;</p><p style="font-weight:600;">No workflows yet</p><p style="font-size:13px;">Workflows will appear here when leave requests are submitted.</p></div>';
        }
    } catch (error) {
        console.error('Error loading active workflows:', error);
        container.innerHTML = '<p style="padding:24px;text-align:center;color:var(--text-secondary);">Unable to load workflows.</p>';
    }
}

// Render active workflow cards with timeline
function renderActiveWorkflows(workflows) {
    const container = document.getElementById('workflow-cards-container');
    if (!container) return;
    container.innerHTML = '';

    workflows.forEach(wf => {
        const statusBadge = wf.status === 'completed' ? '<span class="priority-badge" style="background:#27ae6033;color:#27ae60;">Completed</span>' :
                           wf.status === 'rejected' ? '<span class="priority-badge" style="background:#e74c3c33;color:#e74c3c;">Rejected</span>' :
                           '<span class="priority-badge" style="background:#f39c1233;color:#f39c12;">In Progress</span>';

        const stepsHtml = (wf.steps || []).map(step => {
            const icon = step.status === 'completed' ? '&#10003;' :
                        step.status === 'in-progress' ? '&#9203;' :
                        step.status === 'rejected' ? '&#10007;' : '&#9675;';
            const lineClass = step.status === 'completed' ? 'color:#27ae60;' :
                             step.status === 'in-progress' ? 'color:#f39c12;' :
                             step.status === 'rejected' ? 'color:#e74c3c;' : 'color:var(--text-secondary);';
            return `<div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
                <span style="font-size:16px;${lineClass}">${icon}</span>
                <div>
                    <div style="font-weight:500;font-size:13px;">${step.title}</div>
                    <div style="font-size:11px;color:var(--text-secondary);">${step.date || ''}</div>
                </div>
            </div>`;
        }).join('');

        const card = document.createElement('div');
        card.className = 'approval-card';
        card.innerHTML = `
            <div class="approval-header">
                <h4>${wf.title}</h4>
                ${statusBadge}
            </div>
            <p class="approval-detail">${wf.detail || ''}</p>
            <div style="margin-top:12px;padding-top:8px;border-top:1px solid var(--border-color);">
                ${stepsHtml}
            </div>
        `;
        container.appendChild(card);
    });
}

// Update the pending approval count badge
function updatePendingCount() {
    const cards = document.querySelectorAll('.approval-card');
    const countEl = document.querySelector('.pending-count');
    if (countEl) {
        countEl.textContent = cards.length;
    }
}

// Initialize Workflows Page
document.addEventListener('DOMContentLoaded', () => {
    setActivePage('workflows');
    loadPendingApprovals().catch(() => {
        console.log('Pending approvals load failed');
    });
    loadActiveWorkflows().catch(() => {
        console.log('Active workflows load failed');
    });
    console.log('Workflows.js loaded successfully');
});

// Export functions for onclick handlers
window.approveRequest = approveRequest;
window.rejectRequest = rejectRequest;
window.loadPendingApprovals = loadPendingApprovals;
window.loadActiveWorkflows = loadActiveWorkflows;
