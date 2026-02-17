// ============================================
// SETTINGS.JS - Settings, Profile & Account Management
// HR Intelligence Platform
// ============================================

// Role definitions (for local display when API is unavailable)
const ROLES = {
    employee: {
        name: 'John Smith',
        title: 'Employee',
        badge: 'EMP',
        department: 'Engineering',
        email: 'john.smith@company.com',
        empId: 'EMP-2024-001',
    },
    manager: {
        name: 'Sarah Chen',
        title: 'Manager',
        badge: 'MGR',
        department: 'Engineering',
        email: 'sarah.chen@company.com',
        empId: 'MGR-2024-010',
    },
    hr_admin: {
        name: 'Emily Rodriguez',
        title: 'HR Administrator',
        badge: 'HR',
        department: 'Human Resources',
        email: 'emily.rodriguez@company.com',
        empId: 'HRA-2024-003',
    }
};

const ROLE_LABELS = {
    employee: 'Employee',
    manager: 'Manager',
    hr_admin: 'HR Admin'
};

// ============================================
// ROLE MANAGEMENT
// ============================================

function getCurrentRole() {
    return localStorage.getItem('hr_current_role') || 'employee';
}

function switchRole(role) {
    if (!ROLES[role]) return;

    localStorage.setItem('hr_current_role', role);
    localStorage.setItem('hr_user_name', ROLES[role].name);
    localStorage.setItem('hr_user_role', ROLES[role].title);
    localStorage.setItem('hr_role_badge', ROLES[role].badge);

    highlightActiveRole(role);
    updateHeaderRole(role);
    loadProfile();
    toggleAdminSection(role);

    // Sync with base.html global functions so full UI updates
    if (typeof applyRoleVisibility === 'function') applyRoleVisibility(role);
    if (typeof _highlightActiveAccount === 'function') _highlightActiveAccount(role);
    if (typeof _refreshProfileFromDB === 'function') _refreshProfileFromDB(role);

    // Close the account-switcher dropdown if open
    const panel = document.getElementById('account-switcher');
    if (panel) panel.classList.add('hidden');

    showToast(`Switched to ${ROLES[role].title} role`, 'success');
}

function highlightActiveRole(role) {
    document.querySelectorAll('.role-card').forEach(card => {
        card.classList.toggle('active', card.dataset.role === role);
    });
}

function updateHeaderRole(role) {
    const info = ROLES[role];
    if (!info) return;
    const userName = document.querySelector('.user-name');
    const userRole = document.querySelector('.user-role');
    const badgeText = document.querySelector('.badge-text');
    if (userName) userName.textContent = info.name;
    if (userRole) userRole.textContent = info.title;
    if (badgeText) badgeText.textContent = info.badge;
}

// ============================================
// ADMIN SECTION VISIBILITY
// ============================================

function toggleAdminSection(role) {
    const section = document.getElementById('admin-accounts-section');
    if (!section) return;

    if (role === 'hr_admin') {
        section.style.display = 'block';
        loadEmployeeList();
    } else {
        section.style.display = 'none';
    }
}

// ============================================
// PROFILE - LOAD FROM API
// ============================================

async function loadProfile() {
    const role = getCurrentRole();
    try {
        const result = await apiCall('/api/v2/profile');

        if (result && result.success && result.data) {
            const d = result.data;
            setValue('profile-first-name', d.first_name);
            setValue('profile-last-name', d.last_name);
            setValue('profile-email', d.email);
            setValue('profile-empid', d.hris_id);
            setValue('profile-role', ROLE_LABELS[d.role_level] || d.role_level);
            setSelectValue('profile-department', d.department);

            // ---- Persist DB data to localStorage & header so it survives role switches ----
            const dbFullName = `${d.first_name} ${d.last_name}`;
            localStorage.setItem('hr_user_name', dbFullName);
            const userName = document.querySelector('.user-name');
            if (userName) userName.textContent = dbFullName;
            // Also update the ROLES cache so quickSwitchRole in base.js uses real data
            if (ROLES[role]) {
                ROLES[role].name = dbFullName;
                ROLES[role].department = d.department;
            }
            return;
        }
    } catch (err) {
        console.warn('API unavailable, using local role data:', err);
    }

    // Fallback to local ROLES data
    const info = ROLES[role];
    if (info) {
        const parts = info.name.split(' ');
        setValue('profile-first-name', parts[0] || '');
        setValue('profile-last-name', parts.slice(1).join(' ') || '');
        setValue('profile-email', info.email);
        setValue('profile-empid', info.empId);
        setValue('profile-role', info.title);
        setSelectValue('profile-department', info.department);
    }
}

// ============================================
// PROFILE - SAVE TO API
// ============================================

async function saveProfile() {
    const btn = document.getElementById('btn-save-profile');
    const statusEl = document.getElementById('save-status');
    const role = getCurrentRole();

    const firstName = getVal('profile-first-name');
    const lastName = getVal('profile-last-name');
    const department = getVal('profile-department');

    if (!firstName || !lastName) {
        showToast('First name and last name are required', 'error');
        return;
    }

    // Disable button during save
    if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }
    if (statusEl) statusEl.textContent = '';

    try {
        const result = await apiCall('/api/v2/profile', {
            method: 'PUT',
            body: JSON.stringify({
                first_name: firstName,
                last_name: lastName,
                department: department,
            })
        });

        if (result && result.success) {
            if (statusEl) statusEl.textContent = 'Saved successfully!';
            showToast('Profile saved successfully', 'success');

            // Update header with new name
            const fullName = `${firstName} ${lastName}`;
            const userName = document.querySelector('.user-name');
            if (userName) userName.textContent = fullName;
            localStorage.setItem('hr_user_name', fullName);

            // Update ROLES cache so role switches keep the saved name
            if (ROLES[role]) {
                ROLES[role].name = fullName;
                ROLES[role].department = department;
            }
            // Update account switcher dropdown for this role
            if (typeof _roles !== 'undefined' && _roles[role]) {
                _roles[role].name = fullName;
            }
            const switcherName = document.querySelector(`.switcher-option[data-role="${role}"] .switcher-name`);
            if (switcherName) switcherName.textContent = fullName;

            addNotificationEvent('Profile updated', `${fullName} updated their profile settings.`);

            // Clear status after 3s
            setTimeout(() => { if (statusEl) statusEl.textContent = ''; }, 3000);
        } else {
            if (statusEl) { statusEl.textContent = 'Save failed'; statusEl.style.color = '#E74C3C'; }
            showToast(result.error || 'Failed to save profile', 'error');
        }
    } catch (err) {
        console.error('Save error:', err);
        if (statusEl) { statusEl.textContent = 'Save failed (server error)'; statusEl.style.color = '#E74C3C'; }
        showToast('Failed to save — server may be unreachable', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Save Changes'; }
    }
}

// ============================================
// ADMIN: EMPLOYEE LIST
// ============================================

async function loadEmployeeList() {
    const container = document.getElementById('employee-list-container');
    if (!container) return;

    container.innerHTML = '<div class="loading-text">Loading employee accounts...</div>';

    try {
        const result = await apiCall('/api/v2/employees');

        if (result && result.success && result.data) {
            renderEmployeeTable(result.data);
        } else {
            container.innerHTML = `<div class="loading-text" style="color:#E74C3C;">${(result && result.error) || 'Failed to load employees'}</div>`;
        }
    } catch (err) {
        console.error('Load employees error:', err);
        container.innerHTML = '<div class="loading-text" style="color:#E74C3C;">Failed to connect to server</div>';
    }
}

function renderEmployeeTable(employees) {
    const container = document.getElementById('employee-list-container');
    if (!container || !employees.length) {
        container.innerHTML = '<div class="loading-text">No employees found</div>';
        return;
    }

    let html = `
    <table class="employee-table">
        <thead>
            <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Department</th>
                <th>Role</th>
                <th>Status</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>`;

    employees.forEach(emp => {
        html += `
            <tr>
                <td><strong>${emp.first_name} ${emp.last_name}</strong><br><span style="font-size:12px;color:#6B7280;">${emp.hris_id}</span></td>
                <td>${emp.email}</td>
                <td>${emp.department}</td>
                <td><span class="settings-role-badge ${emp.role_level}">${ROLE_LABELS[emp.role_level] || emp.role_level}</span></td>
                <td><span class="status-badge ${emp.status}">${emp.status}</span></td>
                <td><button class="btn-edit" onclick='openEditModal(${JSON.stringify(emp)})'>Edit</button></td>
            </tr>`;
    });

    html += '</tbody></table>';
    container.innerHTML = html;
}

// ============================================
// ADMIN: EDIT EMPLOYEE MODAL
// ============================================

function openEditModal(emp) {
    document.getElementById('edit-emp-id').value = emp.id;
    document.getElementById('modal-title').textContent = `Edit: ${emp.first_name} ${emp.last_name}`;
    setValue('edit-first-name', emp.first_name);
    setValue('edit-last-name', emp.last_name);
    setValue('edit-email', emp.email);
    setSelectValue('edit-department', emp.department);
    setSelectValue('edit-role', emp.role_level);
    setSelectValue('edit-status', emp.status);

    document.getElementById('edit-employee-modal').style.display = 'flex';
}

function closeEditModal() {
    document.getElementById('edit-employee-modal').style.display = 'none';
}

async function saveEmployee() {
    const empId = document.getElementById('edit-emp-id').value;
    if (!empId) return;

    const saveBtn = document.querySelector('#edit-employee-modal .btn-primary');
    const data = {
        first_name: getVal('edit-first-name'),
        last_name: getVal('edit-last-name'),
        email: getVal('edit-email'),
        department: getVal('edit-department'),
        role_level: getVal('edit-role'),
        status: getVal('edit-status'),
    };

    // Disable button during save
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving...'; }

    try {
        const result = await apiCall(`/api/v2/employees/${empId}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });

        if (result && result.success) {
            // Show success state on the button briefly before closing
            if (saveBtn) { saveBtn.textContent = '✓ Saved!'; saveBtn.style.background = '#27AE60'; }
            showToast(`Employee ${data.first_name} ${data.last_name} updated successfully`, 'success');
            addNotificationEvent('Employee updated', `${data.first_name} ${data.last_name}'s account was modified by HR Admin.`);

            // Delay close so user sees the success state
            setTimeout(() => {
                closeEditModal();
                if (saveBtn) { saveBtn.textContent = 'Save Changes'; saveBtn.style.background = ''; saveBtn.disabled = false; }
                loadEmployeeList();
            }, 800);
        } else {
            if (saveBtn) { saveBtn.textContent = 'Save Changes'; saveBtn.disabled = false; }
            showToast(result.error || 'Failed to update employee', 'error');
        }
    } catch (err) {
        console.error('Save employee error:', err);
        if (saveBtn) { saveBtn.textContent = 'Save Changes'; saveBtn.disabled = false; }
        showToast('Failed to save — server may be unreachable', 'error');
    }
}

// Close modal on overlay click
document.addEventListener('click', (e) => {
    if (e.target.id === 'edit-employee-modal') closeEditModal();
});

// Close modal on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeEditModal();
});

// ============================================
// UTILITY HELPERS
// ============================================

function setValue(id, val) {
    const el = document.getElementById(id);
    if (el) el.value = val || '';
}

function getVal(id) {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
}

function setSelectValue(id, val) {
    const el = document.getElementById(id);
    if (!el || !val) return;
    for (let opt of el.options) {
        if (opt.value === val || opt.value.toLowerCase() === val.toLowerCase()) {
            el.value = opt.value;
            return;
        }
    }
}

// ============================================
// INITIALIZE
// ============================================

function initSettings() {
    const role = getCurrentRole();
    highlightActiveRole(role);
    updateHeaderRole(role);
    loadProfile();
    toggleAdminSection(role);
}

document.addEventListener('DOMContentLoaded', () => {
    setActivePage('settings');
    initSettings();
    loadNotifPrefs();
    console.log('Settings.js loaded successfully');
});

// ============================================
// NOTIFICATION PREFERENCES
// ============================================

function saveNotifPref(checkbox) {
    const prefs = JSON.parse(localStorage.getItem('hr_notif_prefs') || '{}');
    prefs[checkbox.id] = checkbox.checked;
    localStorage.setItem('hr_notif_prefs', JSON.stringify(prefs));
    if (typeof showToast === 'function') {
        showToast('Notification preference saved', 'success');
    }
}

function loadNotifPrefs() {
    const prefs = JSON.parse(localStorage.getItem('hr_notif_prefs') || '{}');
    Object.keys(prefs).forEach(id => {
        const el = document.getElementById(id);
        if (el) el.checked = prefs[id];
    });
}

// Called by quickSwitchRole in base.html when account switcher is used on settings page
function updateProfileForm(role) {
    loadProfile();
    toggleAdminSection(role);
}

// Expose to global for onclick handlers
window.switchRole = switchRole;
window.saveProfile = saveProfile;
window.loadEmployeeList = loadEmployeeList;
window.openEditModal = openEditModal;
window.closeEditModal = closeEditModal;
window.saveEmployee = saveEmployee;
window.updateProfileForm = updateProfileForm;
window.saveNotifPref = saveNotifPref;
window.loadNotifPrefs = loadNotifPrefs;