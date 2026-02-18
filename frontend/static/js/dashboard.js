// ============================================
// DASHBOARD.JS - Dashboard Page Functionality
// HR Intelligence Platform
// ============================================

let departmentChart = null;
let queryTrendChart = null;

// Fetch metrics and update dashboard
async function fetchMetrics() {
    // Show loading skeletons
    showKPISkeletons();
    try {
        const response = await apiCall('/api/v2/metrics');
        const data = (response && response.data) ? response.data : (response || {});
        updateKPICards(data);
        updateKPILabels(data.role || localStorage.getItem('hr_current_role') || 'employee');
        initializeCharts(data);
    } catch (error) {
        console.error('Error fetching metrics:', error);
        // Use defaults on error
        updateKPICards({});
    }
}

// Show pulsing skeleton placeholders for KPI cards
function showKPISkeletons() {
    const ids = ['kpi-employees', 'kpi-leave-requests', 'kpi-approvals', 'kpi-queries'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = '<span class="skeleton-pulse">&nbsp;&nbsp;&nbsp;&nbsp;</span>';
        }
    });
}

// Update KPI Cards (use ?? instead of || so that 0 is not treated as falsy)
function updateKPICards(data) {
    const kpiElements = {
        'kpi-employees': data.total_employees ?? 0,
        'kpi-leave-requests': data.open_leave_requests ?? 0,
        'kpi-approvals': data.pending_approvals ?? 0,
        'kpi-queries': data.queries_today ?? 0
    };

    for (const [id, value] of Object.entries(kpiElements)) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = formatNumber(value);
        }
    }
}

// Update KPI labels and subtexts based on user role
function updateKPILabels(role) {
    const labels = {
        hr_admin: {
            employees: { label: 'Total Employees', sub: 'Company-wide' },
            leave:     { label: 'Open Leave Requests', sub: 'All departments' },
            approvals: { label: 'Pending Approvals', sub: 'Action required' },
            queries:   { label: 'Agent Queries Today', sub: 'Last 24 hours' }
        },
        manager: {
            employees: { label: 'Team Headcount', sub: 'Your department' },
            leave:     { label: 'Team Leave Requests', sub: 'Your team' },
            approvals: { label: 'Pending Approvals', sub: 'Needs your review' },
            queries:   { label: 'Agent Queries Today', sub: 'Last 24 hours' }
        },
        employee: {
            employees: { label: 'Dept. Headcount', sub: 'Your department' },
            leave:     { label: 'My Leave Requests', sub: 'Open / pending' },
            approvals: { label: 'Pending Approvals', sub: 'N/A for your role' },
            queries:   { label: 'My Queries Today', sub: 'Last 24 hours' }
        }
    };

    const config = labels[role] || labels.employee;

    // Update label text for each KPI card
    const kpiCards = document.querySelectorAll('.kpi-card');
    const keys = ['employees', 'leave', 'approvals', 'queries'];
    kpiCards.forEach((card, i) => {
        const key = keys[i];
        if (key && config[key]) {
            const labelEl = card.querySelector('.kpi-label');
            const changeEl = card.querySelector('.kpi-change');
            if (labelEl) labelEl.textContent = config[key].label;
            if (changeEl) changeEl.textContent = config[key].sub;
        }
    });
}

// Initialize Charts
function initializeCharts(data) {
    initDepartmentChart(data.department_headcount || {});
    initQueryTrendChart(data.monthly_queries || []);
}

// Department Headcount Chart
function initDepartmentChart(deptData) {
    const ctx = document.getElementById('departmentChart');
    if (!ctx) return;

    // Prepare data
    const departments = Object.keys(deptData);
    const counts = Object.values(deptData);

    if (departmentChart) {
        departmentChart.data.labels = departments;
        departmentChart.data.datasets[0].data = counts;
        departmentChart.update();
    } else {
        departmentChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: departments.length > 0 ? departments : [],
                datasets: [{
                    label: 'Employee Count',
                    data: counts.length > 0 ? counts : [],
                    backgroundColor: [
                        '#2E86AB',
                        '#A23B72',
                        '#F18F01',
                        '#C73E1D',
                        '#6A994E'
                    ],
                    borderRadius: 4,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 10
                        }
                    }
                }
            }
        });
    }
}

// Query Trend Chart
function initQueryTrendChart(queryData) {
    const ctx = document.getElementById('queryTrendChart');
    if (!ctx) return;

    // Prepare data
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
    const queries = queryData.length > 0 ? queryData : [0, 0, 0, 0, 0, 0];

    if (queryTrendChart) {
        queryTrendChart.data.labels = months;
        queryTrendChart.data.datasets[0].data = queries;
        queryTrendChart.update();
    } else {
        queryTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: months,
                datasets: [{
                    label: 'Agent Queries',
                    data: queries,
                    borderColor: '#2E86AB',
                    backgroundColor: 'rgba(46, 134, 171, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#2E86AB',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 5,
                    pointHoverRadius: 7
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        display: false
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 10
                        }
                    }
                }
            }
        });
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    setActivePage('dashboard');

    console.log('Dashboard.js loaded successfully');
});

// Export for debugging
window.fetchMetrics = fetchMetrics;
window.initializeCharts = initializeCharts;
