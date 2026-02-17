// ============================================
// LEAVE.JS - Leave Management Functionality
// HR Intelligence Platform
// ============================================

let calendarPicker = null;

// Initialize Calendar Picker
function initializeCalendarPicker() {
    const container = document.getElementById('calendar-picker');
    if (!container) return;

    calendarPicker = initializeDateRangePicker({
        disablePastDates: true,
        disableWeekends: false,
        onSelectStart: (date) => {
            document.getElementById('start-date').value = date.toISOString().split('T')[0];
        },
        onSelectEnd: (date) => {
            document.getElementById('end-date').value = date.toISOString().split('T')[0];
        },
        onSelectRange: (startDate, endDate) => {
            document.getElementById('start-date').value = startDate.toISOString().split('T')[0];
            document.getElementById('end-date').value = endDate.toISOString().split('T')[0];
        }
    });

    // Initial render
    container.innerHTML = calendarPicker.render();
    window.datePickerInstance = calendarPicker;
}

// Update calendar options based on checkboxes
function updateCalendarOptions() {
    const disableWeekends = document.getElementById('disable-weekends').checked;
    if (calendarPicker) {
        calendarPicker.disableWeekends = disableWeekends;
        const container = document.getElementById('calendar-picker');
        if (container) {
            container.innerHTML = calendarPicker.render();
        }
    }
}

// Reset calendar selection
function resetCalendar() {
    if (calendarPicker) {
        calendarPicker.clearSelection();
        document.getElementById('start-date').value = '';
        document.getElementById('end-date').value = '';
        document.getElementById('calendar-picker').innerHTML = calendarPicker.render();
    }
}

// Load Leave Balance
async function loadLeaveBalance() {
    try {
        const response = await apiCall('/api/v2/leave/balance');
        if (response && response.data) {
            updateLeaveBalanceDisplay(response.data);
        }
    } catch (error) {
        console.error('Error loading leave balance:', error);
    }
}

// Update Leave Balance Display
function updateLeaveBalanceDisplay(data) {
    // API returns flat structure: data.vacation, data.sick, data.personal
    if (data.vacation) {
        updateLeaveCard(0, data.vacation);
    }
    if (data.sick) {
        updateLeaveCard(1, data.sick);
    }
    if (data.personal) {
        updateLeaveCard(2, data.personal);
    }
}

// Update Individual Leave Card
function updateLeaveCard(cardIndex, leaveData) {
    const cards = document.querySelectorAll('.leave-card');
    if (cardIndex >= cards.length) return;

    const card = cards[cardIndex];
    const used = leaveData.used || 0;
    const available = leaveData.available || 0;
    const pending = leaveData.pending || 0;
    const total = used + available;
    const remaining = available;
    const percentage = total > 0 ? (used / total) * 100 : 0;

    // Update bar
    const bar = card.querySelector('.leave-used');
    if (bar) {
        bar.style.width = percentage + '%';
    }

    // Update text
    const infoDiv = card.querySelector('.leave-info');
    if (infoDiv) {
        infoDiv.innerHTML = `
            <span class="leave-used-text">${used} used</span>
            <span class="leave-remaining-text">${remaining} remaining</span>
        `;
    }
}

// Load Leave History
async function loadLeaveHistory() {
    try {
        const response = await apiCall('/api/v2/leave/history');
        if (response && response.data) {
            populateLeaveHistory(response.data.history || []);
        }
    } catch (error) {
        console.error('Error loading leave history:', error);
    }
}

// Populate Leave History Table
function populateLeaveHistory(history) {
    const tbody = document.getElementById('leave-history-tbody');
    if (!tbody) return;

    // Clear all existing rows before rendering API data
    tbody.innerHTML = '';

    if (history.length === 0) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `<td colspan="6" style="text-align:center; color:var(--text-secondary); padding:24px;">No leave history found. Submit a request to get started.</td>`;
        tbody.appendChild(emptyRow);
        return;
    }

    history.forEach(leave => {
        const row = document.createElement('tr');

        const startDate = new Date(leave.start_date);
        const endDate = new Date(leave.end_date);
        const days = Math.ceil((endDate - startDate) / (1000 * 60 * 60 * 24)) + 1;

        const statusClass = leave.status === 'Approved' ? 'status-approved' :
                           leave.status === 'Pending' ? 'status-pending' :
                           'status-rejected';

        row.innerHTML = `
            <td>${leave.type}</td>
            <td>${formatDate(leave.start_date)}</td>
            <td>${formatDate(leave.end_date)}</td>
            <td>${days}</td>
            <td><span class="status-badge ${statusClass}">${leave.status}</span></td>
            <td>${formatDate(leave.requested_date)}</td>
        `;

        tbody.appendChild(row);
    });
}

// Leave balance limits per type (business days)
const LEAVE_LIMITS = {
    'Vacation': { max: 15, label: 'Vacation' },
    'Sick Leave': { max: 10, label: 'Sick Leave' },
    'Personal': { max: 5, label: 'Personal' },
    'Bereavement': { max: 5, label: 'Bereavement' },
    'Parental': { max: 60, label: 'Parental' },
};

// Calculate business days between two dates
function calculateBusinessDays(start, end) {
    let count = 0;
    const cur = new Date(start);
    const endDate = new Date(end);
    while (cur <= endDate) {
        const day = cur.getDay();
        if (day !== 0 && day !== 6) count++;
        cur.setDate(cur.getDate() + 1);
    }
    return count;
}

// Show leave confirmation modal
function _showLeaveConfirmModal(leaveType, startDate, endDate, days, reason) {
    return new Promise((resolve) => {
        let modal = document.getElementById('leave-confirm-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'leave-confirm-modal';
            modal.className = 'modal-overlay';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);';
            modal.innerHTML = `
                <div style="background:var(--bg-card,#fff);border-radius:12px;width:460px;max-width:90vw;box-shadow:0 8px 24px rgba(0,0,0,0.15);border:1px solid var(--border-color,#e8e8e8);">
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:20px 24px;border-bottom:1px solid var(--border-color,#e8e8e8);">
                        <h3 style="margin:0;font-size:18px;font-weight:700;color:var(--text-primary,#333);">Confirm Leave Request</h3>
                        <button id="leave-modal-close" style="background:none;border:none;font-size:24px;color:var(--text-tertiary,#999);cursor:pointer;padding:0;line-height:1;">&times;</button>
                    </div>
                    <div id="leave-modal-body" style="padding:24px;"></div>
                    <div style="display:flex;justify-content:flex-end;gap:12px;padding:16px 24px;border-top:1px solid var(--border-color,#e8e8e8);">
                        <button class="btn-secondary" id="leave-modal-cancel">Cancel</button>
                        <button class="btn-primary" id="leave-modal-confirm">Submit Request</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }

        const body = document.getElementById('leave-modal-body');
        const reasonHtml = reason ? `<div style="padding:8px 12px;background:var(--bg-light,#f5f5f5);border-radius:6px;">
            <span style="color:var(--text-secondary,#666);font-size:13px;">Reason:</span>
            <p style="margin:4px 0 0;font-size:13px;">${reason}</p>
        </div>` : '';

        body.innerHTML = `
            <div style="display:grid;gap:12px;">
                <div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--bg-light,#f5f5f5);border-radius:6px;">
                    <span style="color:var(--text-secondary,#666);font-size:13px;">Type</span>
                    <strong style="font-size:13px;">${leaveType}</strong>
                </div>
                <div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--bg-light,#f5f5f5);border-radius:6px;">
                    <span style="color:var(--text-secondary,#666);font-size:13px;">Dates</span>
                    <strong style="font-size:13px;">${startDate} to ${endDate}</strong>
                </div>
                <div style="display:flex;justify-content:space-between;padding:8px 12px;background:var(--bg-light,#f5f5f5);border-radius:6px;">
                    <span style="color:var(--text-secondary,#666);font-size:13px;">Business Days</span>
                    <strong style="font-size:13px;">${days} day${days > 1 ? 's' : ''}</strong>
                </div>
                ${reasonHtml}
            </div>
            <p style="margin:16px 0 0;color:var(--text-secondary,#666);font-size:12px;">This request will be sent to your manager for approval.</p>
        `;

        modal.style.display = 'flex';

        function cleanup(result) {
            modal.style.display = 'none';
            document.getElementById('leave-modal-close').onclick = null;
            document.getElementById('leave-modal-cancel').onclick = null;
            document.getElementById('leave-modal-confirm').onclick = null;
            document.removeEventListener('keydown', escHandler);
            modal.onclick = null;
            resolve(result);
        }

        document.getElementById('leave-modal-close').onclick = () => cleanup(false);
        document.getElementById('leave-modal-cancel').onclick = () => cleanup(false);
        document.getElementById('leave-modal-confirm').onclick = () => cleanup(true);

        const escHandler = (e) => { if (e.key === 'Escape') cleanup(false); };
        document.addEventListener('keydown', escHandler);
        modal.onclick = (e) => { if (e.target === modal) cleanup(false); };
    });
}

// Submit Leave Request
async function submitLeaveRequest(event) {
    event.preventDefault();

    const leaveType = document.getElementById('leave-type').value;
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    const reason = document.getElementById('reason').value;

    // Validation
    if (!leaveType || !startDate || !endDate) {
        showToast('Please fill in all required fields', 'error');
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        showToast('Start date must be before end date', 'error');
        return;
    }

    // Calculate requested days
    const requestedDays = calculateBusinessDays(startDate, endDate);

    if (requestedDays <= 0) {
        showToast('Selected dates contain no business days', 'error');
        return;
    }

    // Check against leave limits
    const limit = LEAVE_LIMITS[leaveType];
    if (limit && requestedDays > limit.max) {
        showToast(`${limit.label} requests cannot exceed ${limit.max} days. You requested ${requestedDays} days.`, 'error');
        return;
    }

    // Show confirmation modal
    const confirmed = await _showLeaveConfirmModal(leaveType, startDate, endDate, requestedDays, reason);
    if (!confirmed) return;

    const requestData = {
        leave_type: leaveType,
        start_date: startDate,
        end_date: endDate,
        reason: reason
    };

    try {
        const response = await apiCall('/api/v2/leave/request', {
            method: 'POST',
            body: JSON.stringify(requestData)
        });

        if (response && response.data) {
            showToast('Leave request submitted successfully', 'success');
            if (typeof addNotificationEvent === 'function') {
                addNotificationEvent('Leave Request Submitted', `${leaveType}: ${requestedDays} day(s) from ${startDate} to ${endDate}`);
            }
            document.getElementById('leave-form').reset();
            resetCalendar();
            loadLeaveHistory();
            loadLeaveBalance();
        } else {
            showToast('Failed to submit leave request', 'error');
        }
    } catch (error) {
        console.error('Error submitting leave request:', error);
        showToast('Error submitting leave request', 'error');
    }
}

// Initialize Leave Page
document.addEventListener('DOMContentLoaded', () => {
    setActivePage('leave');
    loadLeaveBalance();
    loadLeaveHistory();
    initializeCalendarPicker();

    const form = document.getElementById('leave-form');
    if (form) {
        form.addEventListener('submit', submitLeaveRequest);
    }

    console.log('✅ Leave.js loaded successfully');
});

// Export functions
window.loadLeaveBalance = loadLeaveBalance;
window.loadLeaveHistory = loadLeaveHistory;
window.submitLeaveRequest = submitLeaveRequest;
window.initializeCalendarPicker = initializeCalendarPicker;
window.updateCalendarOptions = updateCalendarOptions;
window.resetCalendar = resetCalendar;
