// ============================================
// DIRECTORY.JS - Employee Directory Functionality
// HR Intelligence Platform
// ============================================

let allEmployees = [];
let currentView = 'grid';

// Load all employees
async function loadEmployees() {
    try {
        const response = await apiCall('/api/v2/employees');
        if (response && response.data && response.data.employees) {
            allEmployees = response.data.employees;
            renderEmployees();
        }
    } catch (error) {
        console.error('Error loading employees:', error);
        showToast('Failed to load employee directory', 'error');
    }
}

// Filter employees based on search input
function filterEmployees() {
    const searchTerm = document.getElementById('directory-search').value.toLowerCase();
    
    const filtered = allEmployees.filter(emp => {
        const name = (emp.first_name + ' ' + emp.last_name).toLowerCase();
        const department = (emp.department || '').toLowerCase();
        const role = (emp.role || '').toLowerCase();
        const email = (emp.email || '').toLowerCase();
        
        return name.includes(searchTerm) || 
               department.includes(searchTerm) || 
               role.includes(searchTerm) ||
               email.includes(searchTerm);
    });

    if (currentView === 'grid') {
        renderGridView(filtered);
    } else if (currentView === 'list') {
        renderListView(filtered);
    } else if (currentView === 'org') {
        renderOrgChart(filtered);
    }
}

// Switch between views
function switchView(view) {
    currentView = view;
    
    // Update button states
    document.getElementById('grid-view-btn').classList.toggle('active', view === 'grid');
    document.getElementById('list-view-btn').classList.toggle('active', view === 'list');
    document.getElementById('org-chart-btn').classList.toggle('active', view === 'org');

    // Hide all sections
    document.getElementById('grid-view').style.display = 'none';
    document.getElementById('list-view').style.display = 'none';
    document.getElementById('org-view').style.display = 'none';

    // Show selected section
    if (view === 'grid') {
        document.getElementById('grid-view').style.display = 'block';
        renderGridView(allEmployees);
    } else if (view === 'list') {
        document.getElementById('list-view').style.display = 'block';
        renderListView(allEmployees);
    } else if (view === 'org') {
        document.getElementById('org-view').style.display = 'block';
        renderOrgChart(allEmployees);
    }
}

// Render employees in grid view
function renderGridView(employees) {
    const grid = document.getElementById('employees-grid');
    
    if (!employees || employees.length === 0) {
        grid.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-state-icon">👥</div>
                <p class="empty-state-text">No employees found</p>
            </div>
        `;
        return;
    }

    grid.innerHTML = employees.map(emp => {
        const initials = (emp.first_name.charAt(0) + emp.last_name.charAt(0)).toUpperCase();
        const fullName = emp.first_name + ' ' + emp.last_name;
        const email = emp.email || 'N/A';
        const role = emp.role || 'N/A';
        const department = emp.department || 'N/A';

        return `
            <div class="employee-card">
                <div class="employee-avatar">${initials}</div>
                <div class="employee-name">${fullName}</div>
                <div class="employee-role">${role}</div>
                <div class="employee-department">${department}</div>
                <div class="employee-email">${email}</div>
                <div class="employee-actions">
                    <button class="action-btn" onclick="copyToClipboard('${email}')">📧 Email</button>
                    <button class="action-btn" onclick="viewEmployeeDetails(${emp.id})">👁️ View</button>
                </div>
            </div>
        `;
    }).join('');
}

// Render employees in list view
function renderListView(employees) {
    const tbody = document.getElementById('directory-table-body');
    
    if (!employees || employees.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 40px 16px; color: var(--text-secondary);">
                    No employees found
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = employees.map(emp => {
        const initials = (emp.first_name.charAt(0) + emp.last_name.charAt(0)).toUpperCase();
        const fullName = emp.first_name + ' ' + emp.last_name;
        const email = emp.email || 'N/A';
        const role = emp.role || 'N/A';
        const department = emp.department || 'N/A';

        return `
            <tr>
                <td>
                    <div class="employee-name-cell">
                        <div class="table-avatar">${initials}</div>
                        <div>
                            <strong>${fullName}</strong><br>
                            <span style="color: var(--text-secondary); font-size: 11px;">${email}</span>
                        </div>
                    </div>
                </td>
                <td>${department}</td>
                <td>${role}</td>
                <td><a href="mailto:${email}" style="color: var(--accent); text-decoration: none;">${email}</a></td>
                <td>
                    <button class="action-link" onclick="viewEmployeeDetails(${emp.id})">View</button>
                </td>
            </tr>
        `;
    }).join('');
}

// Render organizational chart
function renderOrgChart(employees) {
    const chartContainer = document.getElementById('org-chart');
    
    if (!employees || employees.length === 0) {
        chartContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🏢</div>
                <p class="empty-state-text">No employees found</p>
            </div>
        `;
        return;
    }

    // Group by department and role hierarchy
    const ceo = employees.find(e => e.role && e.role.toLowerCase().includes('ceo'));
    const managers = employees.filter(e => e.role && e.role.toLowerCase().includes('manager'));
    const others = employees.filter(e => !e.role || (!e.role.toLowerCase().includes('ceo') && !e.role.toLowerCase().includes('manager')));

    let html = '';

    // CEO Level
    if (ceo) {
        html += `
            <div class="org-level">
                <div class="org-level-title">Executive</div>
                <div class="org-level-items">
                    <div class="org-node ceo">
                        <div class="org-node-name">${ceo.first_name} ${ceo.last_name}</div>
                        <div class="org-node-title">${ceo.role}</div>
                        <div class="org-node-dept">${ceo.department || 'N/A'}</div>
                    </div>
                </div>
            </div>
        `;
    }

    // Department Structure
    const departments = [...new Set(employees.map(e => e.department).filter(Boolean))];
    
    departments.forEach(dept => {
        const deptEmployees = employees.filter(e => e.department === dept);
        
        if (deptEmployees.length > 0) {
            html += `
                <div class="org-level">
                    <div class="org-level-title">${dept}</div>
                    <div class="org-level-items">
                        ${deptEmployees.map(emp => `
                            <div class="org-node">
                                <div class="org-node-name">${emp.first_name} ${emp.last_name}</div>
                                <div class="org-node-title">${emp.role || 'N/A'}</div>
                                <div class="org-node-dept">${emp.department || 'N/A'}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
    });

    chartContainer.innerHTML = html;
}

// Render based on current view
function renderEmployees() {
    if (currentView === 'grid') {
        renderGridView(allEmployees);
    } else if (currentView === 'list') {
        renderListView(allEmployees);
    } else if (currentView === 'org') {
        renderOrgChart(allEmployees);
    }
}

// Copy email to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Email copied to clipboard', 'success');
    }).catch(() => {
        showToast('Failed to copy email', 'error');
    });
}

// View employee details (placeholder)
function viewEmployeeDetails(empId) {
    const emp = allEmployees.find(e => e.id === empId);
    if (emp) {
        const fullName = emp.first_name + ' ' + emp.last_name;
        showToast(`Viewing ${fullName}'s profile`, 'info');
        // Could be extended to open a modal or navigate to a detail page
    }
}

// Initialize Directory Page
document.addEventListener('DOMContentLoaded', () => {
    loadEmployees();
    console.log('✅ Directory.js loaded successfully');
});

// Export functions
window.loadEmployees = loadEmployees;
window.filterEmployees = filterEmployees;
window.switchView = switchView;
window.copyToClipboard = copyToClipboard;
window.viewEmployeeDetails = viewEmployeeDetails;
