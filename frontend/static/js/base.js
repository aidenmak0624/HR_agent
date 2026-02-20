// ============================================
// BASE.JS - Base Navigation and Utilities
// HR Intelligence Platform
// ============================================

// API Configuration - use current origin in production, localhost in dev
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:5050'
    : window.location.origin;

// ============================================
// DARK MODE TOGGLE
// ============================================

function initTheme() {
    const savedTheme = localStorage.getItem('hr_theme') || 'light';
    setTheme(savedTheme);
    updateThemeIcon(savedTheme);
}

function setTheme(theme) {
    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('hr_theme', 'dark');
    } else {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('hr_theme', 'light');
    }
}

function toggleTheme() {
    const currentTheme = localStorage.getItem('hr_theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    updateThemeIcon(newTheme);
    
    // Show toast
    if (typeof showToast === 'function') {
        const message = newTheme === 'light' ? 'Switched to Light Mode' : 'Switched to Dark Mode';
        showToast(message, 'info', 2000);
    }
}

function updateThemeIcon(theme) {
    const icon = document.getElementById('theme-icon');
    if (icon) {
        icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
}

// ============================================
// SKELETON LOADING
// ============================================

function showSkeletons(container) {
    if (typeof container === 'string') {
        container = document.getElementById(container);
    }
    if (!container) return;

    container.innerHTML = '';
    container.classList.add('skeleton-loading');

    // Create skeleton elements
    const skeletonCount = 4;
    for (let i = 0; i < skeletonCount; i++) {
        const skeletonCard = document.createElement('div');
        skeletonCard.className = 'skeleton skeleton-card';
        container.appendChild(skeletonCard);
    }
}

function hideSkeletons(container) {
    if (typeof container === 'string') {
        container = document.getElementById(container);
    }
    if (!container) return;

    container.classList.remove('skeleton-loading');
}

function showChartSkeletons(container) {
    if (typeof container === 'string') {
        container = document.getElementById(container);
    }
    if (!container) return;

    const skeleton = document.createElement('div');
    skeleton.className = 'skeleton skeleton-chart';
    container.innerHTML = '';
    container.appendChild(skeleton);
}

// ============================================
// COMMAND PALETTE / KEYBOARD SHORTCUTS
// ============================================

const COMMANDS = [
    { id: 'dashboard', title: 'Go to Dashboard', description: 'View main dashboard', icon: '📊', action: () => navigateTo('/dashboard') },
    { id: 'chat', title: 'Go to Chat', description: 'Open chat interface', icon: '💬', action: () => navigateTo('/chat') },
    { id: 'leave', title: 'Go to Leave', description: 'Manage leave requests', icon: '🏖️', action: () => navigateTo('/leave') },
    { id: 'benefits', title: 'Go to Benefits', description: 'Enroll in benefit plans', icon: '💳', action: () => navigateTo('/benefits') },
    { id: 'workflows', title: 'Go to Workflows', description: 'View workflows', icon: '📋', action: () => navigateTo('/workflows') },
    { id: 'documents', title: 'Go to Documents', description: 'View documents', icon: '📄', action: () => navigateTo('/documents') },
    { id: 'analytics', title: 'Go to Analytics', description: 'View analytics', icon: '📈', action: () => navigateTo('/analytics') },
    { id: 'settings', title: 'Go to Settings', description: 'Account settings', icon: '⚙️', action: () => navigateTo('/settings') },
    { id: 'theme', title: 'Toggle Dark Mode', description: 'Switch between light and dark theme', icon: '🌙', action: toggleTheme }
];

let commandPaletteOpen = false;
let selectedCommandIndex = -1;

function initCommandPalette() {
    // Keyboard shortcut: Ctrl+K or Cmd+K
    document.addEventListener('keydown', (e) => {
        // Ctrl+K or Cmd+K
        if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
            e.preventDefault();
            toggleCommandPalette();
        }
        // Escape to close
        if (e.key === 'Escape' && commandPaletteOpen) {
            closeCommandPalette();
        }
        // Navigation in open palette
        if (commandPaletteOpen) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectNextCommand();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectPrevCommand();
            } else if (e.key === 'Enter') {
                e.preventDefault();
                executeSelectedCommand();
            }
        }
    });

    // Search input handler
    const searchInput = document.getElementById('command-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            filterAndDisplayCommands(e.target.value);
        });
    }
}

function toggleCommandPalette() {
    if (commandPaletteOpen) {
        closeCommandPalette();
    } else {
        openCommandPalette();
    }
}

function openCommandPalette() {
    const overlay = document.getElementById('command-palette-overlay');
    if (!overlay) return;

    commandPaletteOpen = true;
    // Keep both classes for CSS compatibility across versions.
    overlay.classList.add('active', 'show');
    selectedCommandIndex = -1;

    // Focus search input and populate all commands
    const searchInput = document.getElementById('command-search');
    if (searchInput) {
        setTimeout(() => searchInput.focus(), 100);
        searchInput.value = '';
    }

    displayCommands(COMMANDS);
}

function closeCommandPalette(event) {
    if (event && event.target.id !== 'command-palette-overlay') {
        return;
    }

    const overlay = document.getElementById('command-palette-overlay');
    if (overlay) {
        overlay.classList.remove('active', 'show');
    }
    commandPaletteOpen = false;
    selectedCommandIndex = -1;
}

function displayCommands(commands) {
    const list = document.getElementById('command-list');
    if (!list) return;

    list.innerHTML = '';

    if (commands.length === 0) {
        list.innerHTML = '<div style="padding:32px 16px; text-align:center; color:var(--text-secondary);">No commands found</div>';
        return;
    }

    commands.forEach((cmd, index) => {
        const item = document.createElement('div');
        item.className = 'command-item';
        item.innerHTML = `
            <div class="command-item-icon">${cmd.icon}</div>
            <div class="command-item-content">
                <div class="command-item-title">${escapeHtml(cmd.title)}</div>
                <div class="command-item-desc">${escapeHtml(cmd.description)}</div>
            </div>
            <div class="command-shortcut">Enter</div>
        `;

        item.addEventListener('click', () => {
            executeCommand(cmd);
        });

        item.addEventListener('mouseenter', () => {
            selectedCommandIndex = index;
            updateCommandSelection();
        });

        list.appendChild(item);
    });
}

function filterAndDisplayCommands(query) {
    if (!query.trim()) {
        displayCommands(COMMANDS);
        return;
    }

    const filtered = COMMANDS.filter(cmd => 
        cmd.title.toLowerCase().includes(query.toLowerCase()) ||
        cmd.description.toLowerCase().includes(query.toLowerCase())
    );

    displayCommands(filtered);
    selectedCommandIndex = -1;
}

function selectNextCommand() {
    const list = document.getElementById('command-list');
    if (!list) return;

    const items = list.querySelectorAll('.command-item');
    selectedCommandIndex = Math.min(selectedCommandIndex + 1, items.length - 1);
    updateCommandSelection();
}

function selectPrevCommand() {
    selectedCommandIndex = Math.max(selectedCommandIndex - 1, -1);
    updateCommandSelection();
}

function updateCommandSelection() {
    const list = document.getElementById('command-list');
    if (!list) return;

    const items = list.querySelectorAll('.command-item');
    items.forEach((item, index) => {
        item.classList.toggle('selected', index === selectedCommandIndex);
    });

    // Scroll selected item into view
    if (selectedCommandIndex >= 0 && items[selectedCommandIndex]) {
        items[selectedCommandIndex].scrollIntoView({ block: 'nearest' });
    }
}

function executeSelectedCommand() {
    const list = document.getElementById('command-list');
    if (!list || selectedCommandIndex < 0) return;

    const items = list.querySelectorAll('.command-item');
    if (items[selectedCommandIndex]) {
        items[selectedCommandIndex].click();
    }
}

function executeCommand(cmd) {
    closeCommandPalette();
    if (cmd.action && typeof cmd.action === 'function') {
        cmd.action();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================
// MOBILE SIDEBAR TOGGLE
// ============================================

function toggleMobileSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) sidebar.classList.toggle('mobile-open');
    if (overlay) overlay.classList.toggle('active');
}

// Close sidebar when a nav link is clicked (mobile)
document.addEventListener('click', (e) => {
    if (e.target.closest('.nav-item') && window.innerWidth <= 768) {
        const sidebar = document.querySelector('.sidebar');
        const overlay = document.getElementById('sidebar-overlay');
        if (sidebar) sidebar.classList.remove('mobile-open');
        if (overlay) overlay.classList.remove('active');
    }
});

// ============================================
// NAVIGATION MANAGEMENT
// ============================================

function setupNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            navItems.forEach(i => i.classList.remove('active'));
            item.classList.add('active');
        });
    });
}

function navigateTo(path) {
    window.location.href = path;
}

function setActivePage(pageName) {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.classList.remove('active');
        if (item.dataset.page === pageName) {
            item.classList.add('active');
        }
    });
}

// ============================================
// NOTIFICATION MANAGEMENT
// ============================================

function toggleNotifications() {
    const panel = document.getElementById('notification-panel');
    if (panel) {
        panel.classList.toggle('hidden');
    }
}

function closeNotifications() {
    const panel = document.getElementById('notification-panel');
    if (panel) {
        panel.classList.add('hidden');
    }
}

// Click outside to close notifications
document.addEventListener('click', (e) => {
    const panel = document.getElementById('notification-panel');
    const bellBtn = document.querySelector('.bell-btn');
    if (panel && bellBtn && !panel.contains(e.target) && !bellBtn.contains(e.target)) {
        closeNotifications();
    }
});

// ============================================
// TOKEN MANAGEMENT (JWT)
// ============================================

function getAuthToken() {
    return localStorage.getItem('auth_token') || null;
}

function setAuthToken(token) {
    localStorage.setItem('auth_token', token);
}

function removeAuthToken() {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('refresh_token');
}

// Attempt to refresh the JWT access token using the stored refresh token
async function refreshAuthToken() {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;
    try {
        const resp = await fetch(`${API_BASE}/api/v2/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken })
        });
        const result = await resp.json();
        if (result.success && result.data && result.data.access_token) {
            setAuthToken(result.data.access_token);
            return true;
        }
    } catch (e) { /* refresh failed */ }
    return false;
}

// ============================================
// API HELPER
// ============================================

async function apiCall(endpoint, options = {}) {
    const token = getAuthToken();
    const currentRole = localStorage.getItem('hr_current_role') || 'employee';
    const headers = {
        'Content-Type': 'application/json',
        'X-User-Role': currentRole,
        ...options.headers
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    try {
        const response = await fetch(`${API_BASE}${endpoint}`, {
            ...options,
            headers
        });

        if (response.status === 401) {
            // Attempt silent token refresh before giving up
            const refreshed = await refreshAuthToken();
            if (refreshed) {
                // Retry the original request with the new token
                headers['Authorization'] = `Bearer ${getAuthToken()}`;
                const retryResp = await fetch(`${API_BASE}${endpoint}`, { ...options, headers });
                if (retryResp.ok) return await retryResp.json();
            }
            removeAuthToken();
            window.location.href = '/login';
            return null;
        }

        if (!response.ok) {
            console.error(`API Error: ${response.status} ${response.statusText}`);
            return null;
        }

        return await response.json();
    } catch (error) {
        console.error('API Call Error:', error);
        return null;
    }
}

// ============================================
// DATE FORMATTING
// ============================================

function formatDate(date) {
    if (typeof date === 'string') {
        date = new Date(date);
    }
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatDateTime(date) {
    if (typeof date === 'string') {
        date = new Date(date);
    }
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// ============================================
// NUMBER FORMATTING
// ============================================

function formatNumber(num) {
    return num.toLocaleString('en-US');
}

function formatPercentage(num, decimals = 1) {
    return (num * 100).toFixed(decimals) + '%';
}

// ============================================
// NOTIFICATION SYSTEM
// ============================================

const NOTIFICATION_KEY = 'hr_notifications';
const MAX_NOTIFICATIONS = 20;

function getNotifications() {
    try {
        return JSON.parse(localStorage.getItem(NOTIFICATION_KEY) || '[]');
    } catch { return []; }
}

function saveNotifications(list) {
    localStorage.setItem(NOTIFICATION_KEY, JSON.stringify(list.slice(0, MAX_NOTIFICATIONS)));
}

// Add a notification event (call from any page)
function addNotificationEvent(title, detail) {
    const list = getNotifications();
    list.unshift({
        id: Date.now(),
        title: title,
        detail: detail || '',
        time: new Date().toISOString(),
        read: false
    });
    saveNotifications(list);
    updateNotificationBadge();
}

// Update the badge count on the bell icon
function updateNotificationBadge() {
    const badge = document.querySelector('.notification-badge, .bell-badge');
    const list = getNotifications();
    const unread = list.filter(n => !n.read).length;

    if (badge) {
        badge.textContent = unread > 0 ? unread : '';
        badge.style.display = unread > 0 ? 'flex' : 'none';
    }
}

// Populate the notification dropdown panel
function populateNotificationPanel() {
    const panel = document.getElementById('notification-panel');
    if (!panel) return;

    const list = getNotifications();
    const container = panel.querySelector('.notification-list') || panel;

    if (list.length === 0) {
        container.innerHTML = '<p style="padding:16px; text-align:center; color:var(--text-secondary);">No notifications yet</p>';
        return;
    }

    container.innerHTML = '';
    list.slice(0, 8).forEach(n => {
        const item = document.createElement('div');
        item.className = 'notification-item' + (n.read ? '' : ' unread');
        item.style.cssText = 'padding:10px 16px; border-bottom:1px solid var(--border-color); cursor:pointer;';
        item.innerHTML = `
            <strong style="font-size:13px;">${n.title}</strong>
            <p style="font-size:12px; color:var(--text-secondary); margin:2px 0 0;">${n.detail}</p>
            <span style="font-size:11px; color:var(--text-secondary);">${formatTimeAgo(n.time)}</span>
        `;
        item.addEventListener('click', () => {
            n.read = true;
            saveNotifications(list);
            updateNotificationBadge();
            item.classList.remove('unread');
        });
        container.appendChild(item);
    });

    // Mark all as read on open
    list.forEach(n => n.read = true);
    saveNotifications(list);
    setTimeout(updateNotificationBadge, 300);
}

function formatTimeAgo(isoStr) {
    const diff = (Date.now() - new Date(isoStr).getTime()) / 1000;
    if (diff < 60) return 'Just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
}

// Override toggleNotifications to also populate
const _origToggle = toggleNotifications;
function toggleNotifications() {
    const panel = document.getElementById('notification-panel');
    if (panel) {
        const wasHidden = panel.classList.contains('hidden');
        panel.classList.toggle('hidden');
        if (wasHidden) populateNotificationPanel();
    }
}

// ============================================
// LOADING STATE UTILITIES
// ============================================

function showLoadingState(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.dataset.prevContent = el.innerHTML;
    el.innerHTML = '<div class="loading-skeleton"><div class="skeleton-pulse" style="height:20px;margin:8px 0;border-radius:4px;"></div><div class="skeleton-pulse" style="height:20px;width:70%;margin:8px 0;border-radius:4px;"></div><div class="skeleton-pulse" style="height:20px;width:50%;margin:8px 0;border-radius:4px;"></div></div>';
}

function hideLoadingState(containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (el.dataset.prevContent && el.querySelector('.loading-skeleton')) {
        el.innerHTML = el.dataset.prevContent;
    }
}

function showEmptyState(containerId, message) {
    const el = document.getElementById(containerId);
    if (!el) return;
    el.innerHTML = `<div class="empty-state"><p>${message}</p></div>`;
}

// ============================================
// SSE REAL-TIME NOTIFICATION STREAM
// ============================================

let _sseSource = null;

function connectNotificationStream() {
    const token = getAuthToken();
    if (!token) return;

    // Close existing connection if any
    if (_sseSource) {
        _sseSource.close();
        _sseSource = null;
    }

    // EventSource doesn't support custom headers, so pass token as query param
    const url = `${API_BASE}/api/v2/notifications/stream?token=${encodeURIComponent(token)}`;
    _sseSource = new EventSource(url);

    _sseSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'notification' && data.payload) {
                // Push into local notification store
                addNotificationEvent(data.payload.title, data.payload.detail);
                // Show a toast for the new notification
                if (typeof showToast === 'function') {
                    showToast(data.payload.title, 'info', 4000);
                }
            }
        } catch (e) {
            // Heartbeat or parse error — ignore
        }
    };

    _sseSource.onerror = function() {
        // SSE connection lost — close and rely on polling fallback
        if (_sseSource) {
            _sseSource.close();
            _sseSource = null;
        }
        // Attempt reconnect after 10 seconds
        setTimeout(connectNotificationStream, 10000);
    };
}

// Poll-based fallback to fetch notifications every 30s
let _pollInterval = null;

function startNotificationPolling() {
    if (_pollInterval) return;
    _pollInterval = setInterval(async () => {
        const token = getAuthToken();
        if (!token) return;
        try {
            const result = await apiCall('/api/v2/notifications');
            if (result && result.success && result.data && result.data.notifications) {
                const serverNotifs = result.data.notifications;
                const localList = getNotifications();
                const localIds = new Set(localList.map(n => n.id));
                let added = 0;
                serverNotifs.forEach(sn => {
                    if (!localIds.has(sn.id)) {
                        localList.unshift(sn);
                        added++;
                    }
                });
                if (added > 0) {
                    saveNotifications(localList);
                    updateNotificationBadge();
                }
            }
        } catch (e) { /* polling failed, will retry */ }
    }, 30000);
}

// ============================================
// INITIALIZE
// ============================================

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize theme
    initTheme();

    // Setup navigation
    setupNavigation();

    // Initialize command palette
    initCommandPalette();

    // Update notification badge
    updateNotificationBadge();

    // Start real-time notification stream if authenticated
    if (getAuthToken()) {
        connectNotificationStream();
        startNotificationPolling();
    }

    console.log('Base.js loaded successfully');
});

// Export functions globally
window.toggleTheme = toggleTheme;
window.showSkeletons = showSkeletons;
window.hideSkeletons = hideSkeletons;
window.showChartSkeletons = showChartSkeletons;
window.toggleCommandPalette = toggleCommandPalette;
window.closeCommandPalette = closeCommandPalette;
window.addNotificationEvent = addNotificationEvent;
window.updateNotificationBadge = updateNotificationBadge;
window.showLoadingState = showLoadingState;
window.hideLoadingState = hideLoadingState;
window.showEmptyState = showEmptyState;
window.toggleNotifications = toggleNotifications;
window.connectNotificationStream = connectNotificationStream;
window.toggleMobileSidebar = toggleMobileSidebar;
window.navigateTo = navigateTo;
