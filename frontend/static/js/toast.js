// ============================================
// TOAST.JS - Toast Notification System
// HR Intelligence Platform
// ============================================

(function() {
    'use strict';

    // Toast Icons Map
    const TOAST_ICONS = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };

    // Ensure toast container exists
    function ensureToastContainer() {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }
        return container;
    }

    // Create and show a toast notification
    window.showToast = function(message, type = 'info', duration = 4000) {
        const container = ensureToastContainer();
        
        // Validate type
        if (!['success', 'error', 'warning', 'info'].includes(type)) {
            type = 'info';
        }

        // Create toast element
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        
        const icon = TOAST_ICONS[type] || 'ℹ';
        
        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-message">${escapeHtml(message)}</div>
            <button class="toast-close" aria-label="Close notification">×</button>
        `;

        // Add close button handler
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => {
            removeToast(toast);
        });

        // Add to container
        container.appendChild(toast);

        // Auto-dismiss after duration
        const timeoutId = setTimeout(() => {
            removeToast(toast);
        }, duration);

        // Allow manual early dismissal
        toast.dataset.timeoutId = timeoutId;

        return toast;
    };

    // Remove toast with animation
    function removeToast(toast) {
        if (!toast || !toast.parentElement) return;

        // Clear timeout if exists
        if (toast.dataset.timeoutId) {
            clearTimeout(parseInt(toast.dataset.timeoutId));
        }

        // Add animation class
        toast.style.animation = 'slideOutRight 0.3s ease-out';
        
        // Remove after animation completes
        setTimeout(() => {
            if (toast.parentElement) {
                toast.parentElement.removeChild(toast);
            }
        }, 300);
    }

    // Utility function to escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Convenience methods
    window.showSuccessToast = function(message, duration = 4000) {
        return showToast(message, 'success', duration);
    };

    window.showErrorToast = function(message, duration = 4000) {
        return showToast(message, 'error', duration);
    };

    window.showWarningToast = function(message, duration = 4000) {
        return showToast(message, 'warning', duration);
    };

    window.showInfoToast = function(message, duration = 4000) {
        return showToast(message, 'info', duration);
    };

    console.log('Toast.js loaded successfully');
})();
