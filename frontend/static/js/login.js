// ============================================
// LOGIN.JS - Authentication Logic
// HR Intelligence Platform
// ============================================

const API_BASE = 'http://localhost:5050';

// Tab switching
function switchTab(tab) {
    // 'signin' or 'signup'
    // Show/hide the appropriate form
    // Update tab button active states
    // Clear error messages
    document.querySelectorAll('.tab').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tab);
    });
    const signinDiv = document.getElementById('signin');
    const signupDiv = document.getElementById('signup');
    if (signinDiv) signinDiv.classList.toggle('active', tab === 'signin');
    if (signupDiv) signupDiv.classList.toggle('active', tab === 'signup');
    clearError();
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.add('show');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
}

function clearError() {
    const errorDiv = document.getElementById('errorMessage');
    if (errorDiv) {
        errorDiv.textContent = '';
        errorDiv.classList.remove('show');
    }
}

function setLoading(buttonId, loading) {
    const btn = document.getElementById(buttonId);
    if (btn) {
        btn.disabled = loading;
        if (loading) {
            btn.innerHTML = '<span class="btn-loading"><span class="spinner"></span>Loading...</span>';
        } else {
            btn.textContent = buttonId === 'signinBtn' ? 'Sign In' : 'Create Account';
        }
    }
}

// Sign In
async function signIn(event) {
    event.preventDefault();
    clearError();

    const email = document.getElementById('signinEmail').value.trim();
    const password = document.getElementById('signinPassword').value;

    if (!email || !password) {
        showError('Please enter both email and password');
        return;
    }

    setLoading('signinBtn', true);

    try {
        const response = await fetch(`${API_BASE}/api/v2/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const result = await response.json();

        if (result.success && result.data) {
            // Store JWT tokens and user info
            localStorage.setItem('auth_token', result.data.access_token);
            if (result.data.refresh_token) {
                localStorage.setItem('refresh_token', result.data.refresh_token);
            }
            localStorage.setItem('hr_current_role', result.data.user.role);
            localStorage.setItem('hr_user_name', result.data.user.name);
            localStorage.setItem('hr_user_role', result.data.user.title);
            localStorage.setItem('hr_role_badge', result.data.user.badge);
            localStorage.setItem('hr_user_email', result.data.user.email);

            // Redirect to dashboard
            window.location.href = '/dashboard';
        } else {
            showError(result.error || 'Invalid email or password');
        }
    } catch (error) {
        console.error('Sign in error:', error);
        showError('Unable to connect to server. Please try again.');
    } finally {
        setLoading('signinBtn', false);
    }
}

// Create Account
async function createAccount(event) {
    event.preventDefault();
    clearError();

    const firstName = document.getElementById('firstName').value.trim();
    const lastName = document.getElementById('lastName').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value;
    const department = document.getElementById('department').value;

    if (!firstName || !lastName || !email || !password || !department) {
        showError('Please fill in all fields');
        return;
    }

    if (password.length < 6) {
        showError('Password must be at least 6 characters');
        return;
    }

    setLoading('signupBtn', true);

    try {
        const response = await fetch(`${API_BASE}/api/v2/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                first_name: firstName,
                last_name: lastName,
                email,
                password,
                department
            })
        });

        const result = await response.json();

        if (result.success && result.data) {
            // Store JWT tokens and user info
            localStorage.setItem('auth_token', result.data.access_token);
            if (result.data.refresh_token) {
                localStorage.setItem('refresh_token', result.data.refresh_token);
            }
            localStorage.setItem('hr_current_role', result.data.user.role);
            localStorage.setItem('hr_user_name', result.data.user.name);
            localStorage.setItem('hr_user_role', result.data.user.title);
            localStorage.setItem('hr_role_badge', result.data.user.badge);
            localStorage.setItem('hr_user_email', result.data.user.email);

            // Redirect to dashboard
            window.location.href = '/dashboard';
        } else {
            showError(result.error || 'Registration failed. Please try again.');
        }
    } catch (error) {
        console.error('Registration error:', error);
        showError('Unable to connect to server. Please try again.');
    } finally {
        setLoading('signupBtn', false);
    }
}

// Demo quick-login buttons (optional convenience)
async function demoLogin(role) {
    const demoAccounts = {
        employee: { email: 'john.smith@company.com', password: 'demo123' },
        manager: { email: 'sarah.chen@company.com', password: 'demo123' },
        hr_admin: { email: 'emily.rodriguez@company.com', password: 'demo123' },
    };

    const account = demoAccounts[role];
    if (!account) return;

    document.getElementById('signinEmail').value = account.email;
    document.getElementById('signinPassword').value = account.password;

    // Trigger sign in
    signIn(new Event('submit'));
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Default to sign in tab
    switchTab('signin');

    // Set data-label on buttons for loading state restoration
    const signinBtn = document.getElementById('signinBtn');
    const signupBtn = document.getElementById('signupBtn');
    if (signinBtn) signinBtn.dataset.label = signinBtn.textContent;
    if (signupBtn) signupBtn.dataset.label = signupBtn.textContent;

    // If already logged in, redirect
    if (localStorage.getItem('auth_token')) {
        window.location.href = '/dashboard';
    }

    console.log('Login.js loaded successfully');
});