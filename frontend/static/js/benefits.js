// ============================================
// BENEFITS.JS - Benefits Enrollment UI
// ============================================

const BENEFITS_API_BASE =
    typeof API_BASE !== 'undefined' && API_BASE
        ? API_BASE
        : (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
            ? 'http://localhost:5050'
            : window.location.origin);

const COVERAGE_OPTIONS = [
    { value: 'employee', label: 'Employee Only' },
    { value: 'employee_spouse', label: 'Employee + Spouse' },
    { value: 'employee_children', label: 'Employee + Children' },
    { value: 'family', label: 'Family' },
];

const benefitsState = {
    plans: [],
    enrollments: [],
    lastSynced: null,
    enrollingPlanIds: new Set(),
    planSource: '',
    enrollmentSource: '',
    integration: {
        mcp: { status: 'loading', tools: 0, protocol_version: '' },
        hris: {
            requested_provider: '',
            active_provider: '',
            using_fallback: false,
            fallback_reason: '',
            healthy: null,
        },
    },
};

document.addEventListener('DOMContentLoaded', () => {
    initializeBenefitsPage();
});

function initializeBenefitsPage() {
    const refreshButton = document.getElementById('benefits-refresh-btn');
    if (refreshButton) {
        refreshButton.addEventListener('click', async () => {
            await Promise.all([loadIntegrationStatus(), loadBenefitsData(true)]);
        });
    }

    const plansContainer = document.getElementById('benefits-plans');
    if (plansContainer) {
        plansContainer.addEventListener('click', (event) => {
            const button = event.target.closest('[data-action="enroll-plan"]');
            if (!button) return;
            const planId = Number(button.getAttribute('data-plan-id'));
            if (!Number.isFinite(planId)) return;
            enrollInPlan(planId);
        });
    }

    Promise.all([loadIntegrationStatus(), loadBenefitsData(false)]);
}

async function loadBenefitsData(showRefreshToast) {
    setLoadingState();
    toggleRefreshButton(true);

    try {
        const [plansResponse, enrollmentsResponse] = await Promise.all([
            benefitsFetch('/api/v2/benefits/plans'),
            benefitsFetch('/api/v2/benefits/enrollments'),
        ]);

        if (!plansResponse.success) {
            throw new Error(plansResponse.error || 'Unable to load benefits plans.');
        }
        if (!enrollmentsResponse.success) {
            throw new Error(enrollmentsResponse.error || 'Unable to load current enrollments.');
        }

        benefitsState.plans = Array.isArray(plansResponse.data) ? plansResponse.data : [];
        benefitsState.enrollments = Array.isArray(enrollmentsResponse.data)
            ? enrollmentsResponse.data
            : [];
        benefitsState.planSource = plansResponse.metadata && plansResponse.metadata.source
            ? String(plansResponse.metadata.source)
            : '';
        benefitsState.enrollmentSource =
            enrollmentsResponse.metadata && enrollmentsResponse.metadata.source
                ? String(enrollmentsResponse.metadata.source)
                : '';
        benefitsState.lastSynced = new Date();

        renderEnrollments();
        renderPlans();
        updateLastSynced();
        renderIntegrationStatus();

        if (showRefreshToast && typeof showToast === 'function') {
            showToast('Benefits data refreshed.', 'success', 2200);
        }
    } catch (error) {
        console.error('Benefits load error:', error);
        const message = error && error.message ? error.message : 'Unable to load benefits data.';
        renderErrorState(message);
        if (typeof showToast === 'function') {
            showToast(message, 'error');
        }
    } finally {
        toggleRefreshButton(false);
    }
}

async function loadIntegrationStatus() {
    const statusResponse = await benefitsFetch('/api/v2/integrations/mcp/status?check=1');
    if (!statusResponse.success || !statusResponse.data) {
        benefitsState.integration = {
            mcp: { status: 'error', tools: 0, protocol_version: '' },
            hris: {
                requested_provider: '',
                active_provider: '',
                using_fallback: true,
                fallback_reason: statusResponse.error || 'Unable to load integration status.',
                healthy: false,
            },
        };
        renderIntegrationStatus();
        return;
    }

    benefitsState.integration = {
        mcp: statusResponse.data.mcp || { status: 'error', tools: 0, protocol_version: '' },
        hris: statusResponse.data.hris || {
            requested_provider: '',
            active_provider: '',
            using_fallback: true,
            fallback_reason: 'HRIS status unavailable',
            healthy: false,
        },
    };
    renderIntegrationStatus();
}

async function enrollInPlan(planId) {
    if (benefitsState.enrollingPlanIds.has(planId)) {
        return;
    }

    const coverageSelect = document.getElementById(`coverage-level-${planId}`);
    const coverageLevel = coverageSelect ? coverageSelect.value : 'employee';

    benefitsState.enrollingPlanIds.add(planId);
    renderPlans();

    try {
        const response = await benefitsFetch('/api/v2/benefits/enroll', {
            method: 'POST',
            body: JSON.stringify({
                plan_id: planId,
                coverage_level: coverageLevel,
            }),
        });

        if (!response.success) {
            throw new Error(response.error || 'Enrollment request failed.');
        }

        if (typeof showToast === 'function') {
            const message =
                response.data && response.data.message
                    ? response.data.message
                    : 'Benefits enrollment updated.';
            showToast(message, 'success');
        }

        await loadBenefitsData(false);
        await loadIntegrationStatus();
    } catch (error) {
        console.error('Benefits enrollment error:', error);
        if (typeof showToast === 'function') {
            const message =
                error && error.message
                    ? error.message
                    : 'Could not complete enrollment. Please try again.';
            showToast(message, 'error');
        }
    } finally {
        benefitsState.enrollingPlanIds.delete(planId);
        renderPlans();
    }
}

async function benefitsFetch(endpoint, options = {}) {
    const role = localStorage.getItem('hr_current_role') || 'employee';
    const token = localStorage.getItem('auth_token');
    const headers = {
        'Content-Type': 'application/json',
        'X-User-Role': role,
        ...(options.headers || {}),
    };

    if (token) {
        headers.Authorization = `Bearer ${token}`;
    }

    try {
        const response = await fetch(`${BENEFITS_API_BASE}${endpoint}`, {
            ...options,
            headers,
        });

        let payload = null;
        try {
            payload = await response.json();
        } catch (parseError) {
            payload = null;
        }

        if (response.status === 401) {
            window.location.href = '/login';
            return { success: false, error: 'Session expired. Please sign in again.' };
        }

        if (!response.ok) {
            return {
                success: false,
                error:
                    (payload && payload.error) ||
                    `Request failed (${response.status} ${response.statusText})`,
            };
        }

        if (payload && typeof payload.success === 'boolean') {
            return payload;
        }

        return { success: true, data: payload };
    } catch (error) {
        return { success: false, error: error.message || 'Network request failed.' };
    }
}

function renderEnrollments() {
    const container = document.getElementById('current-enrollments');
    if (!container) return;

    const enrollments = Array.isArray(benefitsState.enrollments) ? benefitsState.enrollments : [];
    if (enrollments.length === 0) {
        container.innerHTML =
            '<div class="empty-state">No current enrollments found. Select a plan below to enroll.</div>';
        return;
    }

    const sortedEnrollments = [...enrollments].sort((a, b) => {
        if ((a.status || '').toLowerCase() === 'active' && (b.status || '').toLowerCase() !== 'active')
            return -1;
        if ((b.status || '').toLowerCase() === 'active' && (a.status || '').toLowerCase() !== 'active')
            return 1;
        return new Date(b.enrolled_at || 0) - new Date(a.enrolled_at || 0);
    });

    container.innerHTML = sortedEnrollments
        .map((enrollment) => {
            const status = String(enrollment.status || 'unknown').toLowerCase();
            const statusClass =
                status === 'active'
                    ? 'status-active'
                    : status === 'terminated'
                        ? 'status-terminated'
                        : 'status-waived';
            const enrolledDate = enrollment.enrolled_at
                ? formatDateTimeLocal(enrollment.enrolled_at)
                : '--';
            return `
                <article class="enrollment-item" data-testid="enrollment-item">
                    <div>
                        <p class="enrollment-title">${escapeHtml(enrollment.plan_name || 'Unknown Plan')}</p>
                        <p class="enrollment-meta">
                            ${escapeHtml(toTitleCase(enrollment.plan_type || 'unknown'))} | Coverage: ${escapeHtml(formatCoverageLevel(enrollment.coverage_level))}<br/>
                            Enrolled: ${escapeHtml(enrolledDate)}
                        </p>
                    </div>
                    <span class="status-badge ${statusClass}">${escapeHtml(status)}</span>
                </article>
            `;
        })
        .join('');
}

function renderPlans() {
    const container = document.getElementById('benefits-plans');
    if (!container) return;

    const plans = Array.isArray(benefitsState.plans) ? benefitsState.plans : [];
    if (plans.length === 0) {
        container.innerHTML =
            '<div class="empty-state">No active benefits plans are currently available.</div>';
        return;
    }

    const activeByPlanType = new Map();
    benefitsState.enrollments.forEach((enrollment) => {
        if (String(enrollment.status || '').toLowerCase() !== 'active') return;
        const planType = normalizePlanType(enrollment.plan_type);
        if (!activeByPlanType.has(planType)) {
            activeByPlanType.set(planType, enrollment);
        }
    });

    container.innerHTML = plans
        .map((plan) => {
            const planId = Number(plan.id);
            const planTypeKey = normalizePlanType(plan.plan_type);
            const activeEnrollment = activeByPlanType.get(planTypeKey);
            const isCurrentPlan = activeEnrollment && Number(activeEnrollment.plan_id) === planId;
            const isEnrolling = benefitsState.enrollingPlanIds.has(planId);
            const selectedCoverage = activeEnrollment
                ? activeEnrollment.coverage_level || 'employee'
                : 'employee';
            const details = normalizeCoverageDetails(plan.coverage_details);
            const buttonText = isEnrolling
                ? 'Enrolling...'
                : isCurrentPlan
                    ? 'Current Plan'
                    : activeEnrollment
                        ? 'Switch Plan'
                        : 'Enroll Now';
            const detailsHtml =
                details.length === 0
                    ? '<li>Coverage details available at enrollment.</li>'
                    : details.map((item) => `<li>${escapeHtml(item)}</li>`).join('');

            return `
                <article class="benefit-plan-card" data-testid="benefit-plan-card" data-plan-id="${planId}">
                    <div class="plan-head">
                        <div>
                            <h4 class="plan-name">${escapeHtml(plan.name || 'Unnamed Plan')}</h4>
                            <p class="plan-provider">${escapeHtml(plan.provider || 'Provider not listed')}</p>
                        </div>
                        <span class="plan-tag">${escapeHtml(toTitleCase(plan.plan_type || 'plan'))}</span>
                    </div>
                    <p class="plan-cost"><strong>$${formatCurrency(plan.premium_monthly)}</strong> per month</p>
                    <ul class="plan-details">
                        ${detailsHtml}
                    </ul>
                    <div class="plan-actions">
                        <select id="coverage-level-${planId}" class="form-input coverage-select" aria-label="Coverage level for ${escapeHtml(plan.name || 'plan')}">
                            ${renderCoverageOptions(selectedCoverage)}
                        </select>
                        <button
                            class="enroll-btn"
                            data-action="enroll-plan"
                            data-plan-id="${planId}"
                            ${isCurrentPlan || isEnrolling ? 'disabled' : ''}
                        >
                            ${escapeHtml(buttonText)}
                        </button>
                    </div>
                    ${
                        isCurrentPlan
                            ? '<p class="plan-current-note">You are currently enrolled in this plan.</p>'
                            : ''
                    }
                </article>
            `;
        })
        .join('');
}

function renderCoverageOptions(selectedCoverage) {
    return COVERAGE_OPTIONS.map((option) => {
        const isSelected = option.value === selectedCoverage ? 'selected' : '';
        return `<option value="${option.value}" ${isSelected}>${option.label}</option>`;
    }).join('');
}

function normalizeCoverageDetails(rawDetails) {
    if (!rawDetails) {
        return [];
    }
    if (Array.isArray(rawDetails)) {
        return rawDetails.map((item) => String(item));
    }
    if (typeof rawDetails === 'string') {
        return [rawDetails];
    }
    if (typeof rawDetails === 'object') {
        return Object.entries(rawDetails).map(([key, value]) => {
            if (value === null || value === undefined || value === '') {
                return toTitleCase(key.replace(/_/g, ' '));
            }
            const normalizedValue =
                typeof value === 'object' ? JSON.stringify(value) : String(value);
            return `${toTitleCase(key.replace(/_/g, ' '))}: ${normalizedValue}`;
        });
    }
    return [String(rawDetails)];
}

function setLoadingState() {
    const enrollmentsContainer = document.getElementById('current-enrollments');
    const plansContainer = document.getElementById('benefits-plans');

    if (enrollmentsContainer) {
        enrollmentsContainer.innerHTML =
            '<div class="loading-state">Loading current enrollments...</div>';
    }
    if (plansContainer) {
        plansContainer.innerHTML = '<div class="loading-state">Loading available plans...</div>';
    }
}

function renderErrorState(message) {
    const enrollmentsContainer = document.getElementById('current-enrollments');
    const plansContainer = document.getElementById('benefits-plans');
    const safeMessage = escapeHtml(message || 'An unexpected error occurred.');

    if (enrollmentsContainer) {
        enrollmentsContainer.innerHTML = `<div class="error-state">${safeMessage}</div>`;
    }
    if (plansContainer) {
        plansContainer.innerHTML = `<div class="error-state">${safeMessage}</div>`;
    }
}

function renderIntegrationStatus() {
    const mcp = benefitsState.integration.mcp || {};
    const hris = benefitsState.integration.hris || {};

    const mcpHealthy = String(mcp.status || '').toLowerCase() === 'ok';
    const mcpText = mcpHealthy
        ? `Live (${Number(mcp.tools || 0)} tools)`
        : 'Unavailable';
    setIntegrationPill(
        'mcp-status-pill',
        'mcp-status-text',
        mcpHealthy ? 'status-live' : 'status-offline',
        mcpText
    );

    let hrisClass = 'status-loading';
    let hrisText = 'Checking...';
    const requestedProvider = String(hris.requested_provider || '').toLowerCase();
    const activeProvider = String(hris.active_provider || '').toLowerCase();
    const healthy = hris.healthy === true;

    if (activeProvider === 'bamboohr' && !hris.using_fallback && healthy) {
        hrisClass = 'status-live';
        hrisText = 'BambooHR Live';
    } else if (hris.using_fallback) {
        hrisClass = 'status-warning';
        hrisText = `Fallback (${activeProvider || 'local'})`;
    } else if (activeProvider) {
        hrisClass = healthy ? 'status-live' : 'status-warning';
        hrisText = `${toTitleCase(activeProvider)} ${healthy ? 'Live' : 'Degraded'}`;
    }

    setIntegrationPill('hris-status-pill', 'hris-status-text', hrisClass, hrisText);

    const detailParts = [];
    if (mcpHealthy) {
        detailParts.push(
            `MCP protocol ${mcp.protocol_version || '--'}`
        );
    } else {
        detailParts.push('MCP endpoint not healthy');
    }

    if (requestedProvider === 'bamboohr' && activeProvider === 'bamboohr' && healthy) {
        detailParts.push('Serving HRIS data from BambooHR');
    } else if (hris.using_fallback) {
        detailParts.push(
            hris.fallback_reason
                ? String(hris.fallback_reason)
                : 'Using local HRIS fallback'
        );
    }

    const sourceBits = [];
    if (benefitsState.planSource) {
        sourceBits.push(`plans:${benefitsState.planSource}`);
    }
    if (benefitsState.enrollmentSource) {
        sourceBits.push(`enrollments:${benefitsState.enrollmentSource}`);
    }
    if (sourceBits.length) {
        detailParts.push(`data source ${sourceBits.join(', ')}`);
    }

    const detailLabel = document.getElementById('integration-status-detail');
    if (detailLabel) {
        detailLabel.textContent = detailParts.join(' | ') || 'Integration status unavailable';
    }
}

function setIntegrationPill(containerId, textId, statusClass, text) {
    const pill = document.getElementById(containerId);
    const label = document.getElementById(textId);
    if (!pill || !label) return;

    pill.classList.remove('status-live', 'status-warning', 'status-offline', 'status-loading');
    pill.classList.add(statusClass || 'status-loading');
    label.textContent = text || '--';
}

function toggleRefreshButton(disabled) {
    const refreshButton = document.getElementById('benefits-refresh-btn');
    if (!refreshButton) return;
    refreshButton.disabled = disabled;
    refreshButton.textContent = disabled ? 'Refreshing...' : 'Refresh Data';
}

function updateLastSynced() {
    const label = document.getElementById('benefits-last-synced');
    if (!label) return;

    if (!benefitsState.lastSynced) {
        label.textContent = '--';
        return;
    }

    label.textContent = benefitsState.lastSynced.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function normalizePlanType(planType) {
    return String(planType || '').trim().toLowerCase();
}

function formatCoverageLevel(coverageLevel) {
    const found = COVERAGE_OPTIONS.find((option) => option.value === coverageLevel);
    if (found) {
        return found.label;
    }
    return toTitleCase(String(coverageLevel || 'employee').replace(/_/g, ' '));
}

function formatCurrency(value) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) {
        return '0.00';
    }
    return numericValue.toFixed(2);
}

function formatDateTimeLocal(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return '--';
    }
    return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function toTitleCase(text) {
    return String(text || '')
        .split(' ')
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
        .join(' ');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text || '');
    return div.innerHTML;
}
