// ============================================
// ANALYTICS.JS - Analytics Page Functionality
// HR Intelligence Platform
// ============================================

// Chart instances
let headcountChart = null;
let queryVolumeChart = null;
let leaveChart = null;
let agentChart = null;

// Load Analytics Data
async function loadAnalytics() {
    try {
        const dateFrom = document.getElementById('date-from')?.value;
        const dateTo = document.getElementById('date-to')?.value;
        const department = document.getElementById('department-filter')?.value;

        const queryParams = new URLSearchParams();
        if (dateFrom) queryParams.append('date_from', dateFrom);
        if (dateTo) queryParams.append('date_to', dateTo);
        if (department) queryParams.append('department', department);

        const endpoint = `/api/v2/metrics?${queryParams.toString()}`;
        const response = await apiCall(endpoint);

        if (response && response.data) {
            initCharts(response.data);
        } else {
            // Fallback: render charts with defaults
            initCharts({});
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
        showToast('Failed to load analytics data', 'error');
        // Still render charts with defaults on error
        initCharts({});
    }
}

// Initialize Charts
function initCharts(data) {
    initHeadcountChart(data.department_headcount || {});
    initQueryVolumeChart(data.query_volume_trend || []);
    initLeaveChart(data.leave_utilization || {});
    initAgentChart(data.agent_performance || {});

    // Update summary statistics from live API data
    const headcountEl = document.getElementById('stat-headcount');
    if (headcountEl) headcountEl.textContent = formatNumber(data.total_employees || 0);
    const queriesTodayEl = document.getElementById('stat-queries-today');
    if (queriesTodayEl) queriesTodayEl.textContent = formatNumber(data.queries_today || 0);
    const avgLeaveEl = document.getElementById('stat-avg-leave');
    if (avgLeaveEl) avgLeaveEl.textContent = data.avg_leave_days_used || 0;
    const avgConfEl = document.getElementById('stat-avg-confidence');
    if (avgConfEl) {
        const conf = data.avg_confidence || 0;
        avgConfEl.textContent = conf > 0 ? (conf * 100).toFixed(0) + '%' : '–';
    }
}

// Headcount by Department Chart
function initHeadcountChart(deptData) {
    const ctx = document.getElementById('headcountChart');
    if (!ctx) return;

    const departments = Object.keys(deptData).length > 0 ? Object.keys(deptData) : ['Engineering', 'Sales', 'HR', 'Finance', 'Operations'];
    const counts = Object.keys(deptData).length > 0 ? Object.values(deptData) : [45, 38, 22, 28, 35];

    if (headcountChart) {
        headcountChart.data.labels = departments;
        headcountChart.data.datasets[0].data = counts;
        headcountChart.update();
    } else {
        headcountChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: departments,
                datasets: [{
                    label: 'Employee Count',
                    data: counts,
                    backgroundColor: [
                        '#73C41D',
                        '#4CAF50',
                        '#2196F3',
                        '#FF9800',
                        '#9C27B0'
                    ],
                    borderRadius: 6,
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
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// Query Volume Trend Chart (live from DB)
function initQueryVolumeChart(volumeData) {
    const ctx = document.getElementById('queryVolumeChart');
    if (!ctx) return;

    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const volume = volumeData.length > 0 ? volumeData : [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

    if (queryVolumeChart) {
        queryVolumeChart.data.labels = months;
        queryVolumeChart.data.datasets[0].data = volume;
        queryVolumeChart.update();
    } else {
        queryVolumeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: months,
                datasets: [{
                    label: 'Queries',
                    data: volume,
                    borderColor: '#73C41D',
                    backgroundColor: 'rgba(115, 196, 29, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#73C41D',
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
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// Leave Utilization Pie Chart
function initLeaveChart(leaveData) {
    const ctx = document.getElementById('leaveChart');
    if (!ctx) return;

    const labels = Object.keys(leaveData).length > 0 ? Object.keys(leaveData) : ['Vacation', 'Sick Leave', 'Personal Days'];
    const data = Object.keys(leaveData).length > 0 ? Object.values(leaveData) : [0, 0, 0];

    if (leaveChart) {
        leaveChart.data.labels = labels;
        leaveChart.data.datasets[0].data = data;
        leaveChart.update();
    } else {
        leaveChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: [
                        '#73C41D',
                        '#4CAF50',
                        '#FF9800'
                    ],
                    borderColor: '#fff',
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
}

// Agent Performance Chart
function initAgentChart(agentData) {
    const ctx = document.getElementById('agentChart');
    if (!ctx) return;

    const agents = Object.keys(agentData).length > 0 ? Object.keys(agentData) : [];
    const queryCounts = Object.keys(agentData).length > 0 ? Object.values(agentData) : [];

    if (agentChart) {
        agentChart.data.labels = agents;
        agentChart.data.datasets[0].data = queryCounts;
        agentChart.update();
    } else {
        agentChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: agents,
                datasets: [{
                    label: 'Query Count',
                    data: queryCounts,
                    backgroundColor: '#73C41D',
                    borderRadius: 6,
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
                        beginAtZero: true
                    }
                }
            }
        });
    }
}

// Export Analytics Data to CSV
async function exportAnalytics() {
    try {
        const dateFrom = document.getElementById('date-from')?.value;
        const dateTo = document.getElementById('date-to')?.value;
        const department = document.getElementById('department-filter')?.value;

        const queryParams = new URLSearchParams();
        if (dateFrom) queryParams.append('date_from', dateFrom);
        if (dateTo) queryParams.append('date_to', dateTo);
        if (department) queryParams.append('department', department);

        // Use fetch with auth headers instead of direct navigation
        const token = localStorage.getItem('auth_token');
        const currentRole = localStorage.getItem('hr_current_role') || 'employee';
        const response = await fetch(`/api/v2/metrics/export?${queryParams.toString()}`, {
            headers: {
                'Authorization': token ? `Bearer ${token}` : '',
                'X-User-Role': currentRole
            }
        });

        if (response.ok) {
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `analytics_${department || 'all'}_${dateFrom || 'start'}_to_${dateTo || 'end'}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('Analytics data exported successfully', 'success');
        } else {
            // Fallback: generate CSV client-side from current chart data
            const csv = generateClientCSV();
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `analytics_${department || 'all'}_export.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('Analytics data exported (client-side)', 'success');
        }
    } catch (error) {
        console.error('Error exporting analytics:', error);
        // Fallback: generate CSV client-side
        try {
            const csv = generateClientCSV();
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'analytics_export.csv';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('Analytics data exported (client-side)', 'success');
        } catch (e2) {
            showToast('Failed to export analytics data', 'error');
        }
    }
}

// Generate CSV from current chart data
function generateClientCSV() {
    let csv = 'Category,Metric,Value\n';
    // Headcount data from chart
    if (headcountChart) {
        const labels = headcountChart.data.labels || [];
        const data = headcountChart.data.datasets[0]?.data || [];
        labels.forEach((d, i) => { csv += `Headcount,${d},${data[i] || 0}\n`; });
    }
    // Query volume data from chart
    if (queryVolumeChart) {
        const labels = queryVolumeChart.data.labels || [];
        const data = queryVolumeChart.data.datasets[0]?.data || [];
        labels.forEach((m, i) => { csv += `Query Volume,${m},${data[i] || 0}\n`; });
    }
    // Key metrics from DOM
    const headcount = document.getElementById('stat-headcount')?.textContent || '0';
    const queries = document.getElementById('stat-queries-today')?.textContent || '0';
    const avgLeave = document.getElementById('stat-avg-leave')?.textContent || '0';
    const avgConf = document.getElementById('stat-avg-confidence')?.textContent || '0';
    csv += `Key Metric,Total Headcount,${headcount}\n`;
    csv += `Key Metric,Queries Today,${queries}\n`;
    csv += `Key Metric,Avg Leave Days Used,${avgLeave}\n`;
    csv += `Key Metric,Avg Agent Confidence,${avgConf}\n`;
    return csv;
}

// Update Analytics on filter change
function updateAnalytics() {
    loadAnalytics();
}

// Initialize Analytics Page
document.addEventListener('DOMContentLoaded', () => {
    setActivePage('analytics');

    // Set default dates
    const today = new Date();
    const oneYearAgo = new Date(today.getFullYear() - 1, today.getMonth(), today.getDate());

    const dateFromInput = document.getElementById('date-from');
    const dateToInput = document.getElementById('date-to');

    if (dateFromInput) {
        dateFromInput.valueAsDate = oneYearAgo;
    }
    if (dateToInput) {
        dateToInput.valueAsDate = today;
    }

    loadAnalytics();

    console.log('✅ Analytics.js loaded successfully');
});

// Export Analytics to PDF
async function exportAnalyticsPDF() {
    const btn = document.querySelector('[onclick="exportAnalyticsPDF()"]');
    if (btn) { btn.disabled = true; btn.textContent = 'Generating...'; }

    try {
        const dept = document.getElementById('department-filter')?.value || 'All Departments';
        const dateFrom = document.getElementById('date-from')?.value || '';
        const dateTo = document.getElementById('date-to')?.value || '';
        const queryParams = new URLSearchParams();
        if (dateFrom) queryParams.append('date_from', dateFrom);
        if (dateTo) queryParams.append('date_to', dateTo);
        if (dept && dept !== 'All Departments') queryParams.append('department', dept);

        const token = localStorage.getItem('auth_token');
        const currentRole = localStorage.getItem('hr_current_role') || 'employee';

        // Prefer server-side export so PDF works even when CDN libs fail to load.
        const serverResp = await fetch(`/api/v2/metrics/export/pdf?${queryParams.toString()}`, {
            headers: {
                'Authorization': token ? `Bearer ${token}` : '',
                'X-User-Role': currentRole
            }
        });

        if (serverResp.ok) {
            const blob = await serverResp.blob();
            const contentType = (serverResp.headers.get('content-type') || '').toLowerCase();
            if (blob.size > 0 && contentType.includes('application/pdf')) {
                const disposition = serverResp.headers.get('content-disposition') || '';
                const match = disposition.match(/filename\*?=(?:UTF-8''|\"?)([^\";]+)/i);
                const filename = match ? decodeURIComponent(match[1].replace(/\"/g, '')) : `HR_Analytics_Report_${new Date().toISOString().slice(0, 10)}.pdf`;
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = filename;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                showToast('PDF report exported successfully', 'success');
                return;
            }
        }

        // Fallback to client-side jsPDF generation if available.
        if (typeof window.jspdf !== 'undefined') {
            const { jsPDF } = window.jspdf;
            const pdf = new jsPDF('landscape', 'mm', 'a4');
            const pageWidth = pdf.internal.pageSize.getWidth();
            const pageHeight = pdf.internal.pageSize.getHeight();

            pdf.setFontSize(20);
            pdf.setTextColor(115, 196, 29);
            pdf.text('HR Analytics Report', 14, 18);
            pdf.setFontSize(10);
            pdf.setTextColor(100);
            pdf.text(`Department: ${dept}  |  Period: ${dateFrom || 'Start'} to ${dateTo || 'End'}  |  Generated: ${new Date().toLocaleDateString()}`, 14, 25);
            pdf.setDrawColor(200);
            pdf.line(14, 28, pageWidth - 14, 28);

            const chartIds = ['headcountChart', 'queryVolumeChart', 'leaveChart', 'agentChart'];
            const chartTitles = ['Headcount by Department', 'Query Volume Trend', 'Leave Days Used', 'Queries by Agent'];
            const y = 34;
            const chartW = (pageWidth - 42) / 2;
            const chartH = 70;

            for (let i = 0; i < chartIds.length; i++) {
                const canvas = document.getElementById(chartIds[i]);
                if (!canvas) continue;
                const col = i % 2;
                const row = Math.floor(i / 2);
                const x = 14 + col * (chartW + 14);
                const yPos = y + row * (chartH + 18);
                pdf.setFontSize(11);
                pdf.setTextColor(50);
                pdf.text(chartTitles[i], x, yPos);
                const imgData = canvas.toDataURL('image/png', 1.0);
                pdf.addImage(imgData, 'PNG', x, yPos + 3, chartW, chartH);
            }

            pdf.setFontSize(8);
            pdf.setTextColor(150);
            pdf.text('HR Multi-Agent Intelligence Platform — Confidential', pageWidth / 2, pageHeight - 6, { align: 'center' });
            pdf.save(`HR_Analytics_Report_${new Date().toISOString().slice(0, 10)}.pdf`);
            showToast('PDF report exported successfully', 'success');
            return;
        }

        showToast('PDF export fallback: opening print dialog', 'info');
        window.print();
    } catch (error) {
        console.error('PDF export error:', error);
        showToast('Using print dialog as fallback...', 'info');
        window.print();
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '📄 Export PDF'; }
    }
}

// Export functions
window.loadAnalytics = loadAnalytics;
window.updateAnalytics = updateAnalytics;
window.exportAnalytics = exportAnalytics;
window.exportAnalyticsPDF = exportAnalyticsPDF;
window.initCharts = initCharts;
