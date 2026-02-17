// ============================================
// CHAT_V2.JS - Chat Interface Functionality
// HR Intelligence Platform
// ============================================

// State Management
let conversationHistory = [];
let isWaitingForResponse = false;
let conversations = [];  // Array of {id, title, messages, createdAt}
let activeConversationId = null;
let currentChatRole = null;  // tracks which role owns the loaded conversations

// Get a role-specific storage key so each account has its own chat history
function _chatStorageKey() {
    const role = localStorage.getItem('hr_current_role') || 'employee';
    return 'hr_conversations_' + role;
}

// ============================================
// CONVERSATION SIDEBAR MANAGEMENT
// ============================================

function initConversations() {
    currentChatRole = localStorage.getItem('hr_current_role') || 'employee';

    // Load saved conversations for THIS role only
    const saved = localStorage.getItem(_chatStorageKey());
    if (saved) {
        try {
            conversations = JSON.parse(saved);
        } catch (e) {
            conversations = [];
        }
    } else {
        conversations = [];
    }

    // If no conversations exist for this role, create one
    if (conversations.length === 0) {
        const firstConv = createConversationObject('New Conversation');
        conversations.push(firstConv);
        activeConversationId = firstConv.id;
    } else {
        activeConversationId = conversations[0].id;
    }

    // Restore active conversation messages
    const activeConv = conversations.find(c => c.id === activeConversationId);
    if (activeConv && activeConv.messages.length > 0) {
        const container = document.getElementById('messages-container');
        if (container) {
            container.innerHTML = '';
            activeConv.messages.forEach(msg => {
                if (msg.role === 'user') renderUserMessage(msg.content, false);
                else if (msg.role === 'agent') renderAgentMessage(msg, false);
            });
            conversationHistory = [...activeConv.messages];
            hideSuggestedQuestions();
        }
    } else {
        conversationHistory = [];
    }

    renderConversationSidebar();
    saveConversations();
}

function createConversationObject(title) {
    return {
        id: 'conv_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5),
        title: title || 'New Conversation',
        messages: [],
        createdAt: new Date().toISOString(),
    };
}

function renderConversationSidebar() {
    const list = document.getElementById('conversation-list');
    if (!list) return;

    list.innerHTML = '';

    conversations.forEach(conv => {
        const item = document.createElement('div');
        item.className = 'conversation-item' + (conv.id === activeConversationId ? ' active' : '');
        item.dataset.convId = conv.id;
        item.onclick = () => switchConversation(conv.id);

        // Calculate relative time
        const timeStr = getRelativeTime(conv.createdAt);

        item.innerHTML = `
            <span class="conv-title">${escapeHtml(conv.title)}</span>
            <span class="conv-time">${timeStr}</span>
        `;
        list.appendChild(item);
    });
}

function switchConversation(convId) {
    if (convId === activeConversationId) return;

    // Save current conversation messages
    saveCurrentConversationMessages();

    // Switch active
    activeConversationId = convId;
    const conv = conversations.find(c => c.id === convId);

    // Clear and reload messages
    const container = document.getElementById('messages-container');
    if (!container) return;

    if (conv && conv.messages.length > 0) {
        // Replay saved messages
        container.innerHTML = '';
        conv.messages.forEach(msg => {
            if (msg.role === 'user') {
                renderUserMessage(msg.content, false);
            } else if (msg.role === 'agent') {
                renderAgentMessage(msg, false);
            }
        });
        conversationHistory = [...conv.messages];
        hideSuggestedQuestions();
    } else {
        // Empty conversation — show welcome
        showWelcomeMessage();
        conversationHistory = [];
        showSuggestedQuestions();
    }

    // Update sessionStorage conversation_id
    sessionStorage.setItem('conversation_id', convId);

    renderConversationSidebar();
    saveConversations();
}

function saveCurrentConversationMessages() {
    const conv = conversations.find(c => c.id === activeConversationId);
    if (conv) {
        conv.messages = [...conversationHistory];
    }
    saveConversations();
}

function saveConversations() {
    try {
        localStorage.setItem(_chatStorageKey(), JSON.stringify(conversations));
    } catch (e) {
        console.warn('Failed to save conversations:', e);
    }
}

function updateConversationTitle(message) {
    const conv = conversations.find(c => c.id === activeConversationId);
    if (conv && conv.title === 'New Conversation') {
        // Use the first user message as title (truncated)
        conv.title = message.length > 35 ? message.substring(0, 35) + '...' : message;
        renderConversationSidebar();
        saveConversations();
    }
}

function getRelativeTime(isoDate) {
    const now = new Date();
    const date = new Date(isoDate);
    const diffMs = now - date;
    const diffMin = Math.floor(diffMs / 60000);
    const diffHr = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHr < 24) return `${diffHr}h ago`;
    if (diffDay === 1) return 'Yesterday';
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

// ============================================
// CHAT INPUT & MESSAGING
// ============================================

function setupChatListeners() {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }
}

async function sendMessage() {
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');

    if (!chatInput || !chatInput.value.trim()) {
        return;
    }

    if (isWaitingForResponse) return;

    const message = chatInput.value.trim();
    chatInput.value = '';
    isWaitingForResponse = true;

    // Disable send button
    if (sendBtn) {
        sendBtn.disabled = true;
    }

    // Update conversation title if this is the first message
    updateConversationTitle(message);

    // Add user message to chat
    renderUserMessage(message);

    // Add to conversation history
    conversationHistory.push({ role: 'user', content: message });

    // Show typing indicator
    const typingId = showTypingIndicator();

    try {
        // Include user context so the chatbot can personalize responses
        const userRole = localStorage.getItem('hr_current_role') || 'employee';
        const userName = localStorage.getItem('hr_user_name') || 'User';

        const response = await apiCall('/api/v2/query', {
            method: 'POST',
            body: JSON.stringify({
                query: message,
                conversation_id: activeConversationId,
                conversation_history: conversationHistory.slice(-10), // send last 10 for context
                user_name: userName,
                user_role: userRole
            })
        });

        removeTypingIndicator(typingId);

        if (response && response.success && response.data) {
            const agentData = response.data;
            renderAgentMessage(agentData);
            conversationHistory.push({
                role: 'agent',
                content: agentData.answer,
                answer: agentData.answer,
                agent_type: agentData.agent_type,
                confidence: agentData.confidence,
                reasoning_trace: agentData.reasoning_trace
            });
        } else {
            showErrorMessage('Failed to get response from agent. Please try again.');
        }
    } catch (error) {
        console.error('Error sending message:', error);
        removeTypingIndicator(typingId);
        showErrorMessage('Error communicating with server. Please check your connection.');
    } finally {
        isWaitingForResponse = false;
        if (sendBtn) {
            sendBtn.disabled = false;
        }
        chatInput.focus();
        hideSuggestedQuestions();
        saveCurrentConversationMessages();
    }
}

// ============================================
// MESSAGE RENDERING
// ============================================

function renderUserMessage(message, scroll = true) {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper user-message-wrapper';

    const msg = document.createElement('div');
    msg.className = 'user-message';
    msg.innerHTML = `<p>${escapeHtml(message)}</p>`;

    const time = document.createElement('span');
    time.className = 'message-time';
    time.textContent = getCurrentTime();

    wrapper.appendChild(msg);
    wrapper.appendChild(time);
    container.appendChild(wrapper);

    if (scroll) scrollToBottom();
}

function renderAgentMessage(response, scroll = true) {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper agent-message-wrapper';

    const msg = document.createElement('div');
    msg.className = 'agent-message';

    const answerText = response.answer || response.content || '';
    let html = formatAgentResponse(answerText);

    // Add agent badge
    if (response.agent_type) {
        html += `<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(0,0,0,0.1);">`;
        html += renderAgentBadge(response.agent_type);

        if (response.confidence !== undefined) {
            html += renderConfidenceIndicator(response.confidence);
        }

        if (response.reasoning_trace && response.reasoning_trace.length > 0) {
            const traceId = 'trace_' + Date.now();
            html += `<button class="reasoning-btn" onclick="toggleReasoningTrace('${traceId}')" style="margin-left: 12px; padding: 4px 8px; background: #F5F7FA; border: 1px solid #E0E6F2; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: 600;">View Reasoning</button>`;
            html += `<div id="${traceId}" class="reasoning-trace hidden" style="margin-top: 12px; padding: 12px; background: #F5F7FA; border-radius: 4px; font-size: 12px;">`;
            response.reasoning_trace.forEach((step, i) => {
                html += `<p style="margin: 4px 0;"><strong>Step ${i + 1}:</strong> ${escapeHtml(step)}</p>`;
            });
            html += `</div>`;
        }

        html += `</div>`;
    }

    // Wrap content in agent-message-body with avatar so all messages are consistent
    msg.innerHTML = `<div class="agent-avatar">🤖</div><div class="agent-message-body">${html}</div>`;

    const time = document.createElement('span');
    time.className = 'message-time';
    time.textContent = getCurrentTime();

    wrapper.appendChild(msg);
    wrapper.appendChild(time);
    container.appendChild(wrapper);

    if (scroll) scrollToBottom();
}

function renderAgentBadge(agentType) {
    const colors = {
        'hr_agent': '#2E86AB',
        'benefits_agent': '#27AE60',
        'payroll_agent': '#F39C12',
        'leave_agent': '#9B59B6',
        'onboarding_agent': '#E67E22',
        'policy_agent': '#3498DB',
        'employee_info_agent': '#E74C3C'
    };

    const color = colors[agentType] || '#7F8C8D';
    const label = agentType.replace(/_/g, ' ').toUpperCase();
    return `<span style="display: inline-block; padding: 4px 8px; background: ${color}; color: white; border-radius: 4px; font-size: 11px; font-weight: 600;">${label}</span>`;
}

function renderConfidenceIndicator(confidence) {
    const percentage = Math.round(confidence * 100);
    let color = '#27AE60';
    if (percentage < 50) color = '#E74C3C';
    else if (percentage < 75) color = '#F39C12';

    return `<span style="margin-left: 12px; display: inline-block; font-size: 11px; color: ${color}; font-weight: 600;">Confidence: ${percentage}%</span>`;
}

// ============================================
// TYPING INDICATOR & ERRORS
// ============================================

function showTypingIndicator() {
    const container = document.getElementById('messages-container');
    if (!container) return null;

    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper agent-message-wrapper';
    wrapper.id = 'typing-indicator-' + Date.now();

    const msg = document.createElement('div');
    msg.className = 'agent-message';
    msg.innerHTML = '<div style="display: flex; gap: 4px; padding: 8px 0;"><span style="width: 8px; height: 8px; background: #999; border-radius: 50%; animation: bounce 1.4s infinite;"></span><span style="width: 8px; height: 8px; background: #999; border-radius: 50%; animation: bounce 1.4s infinite; animation-delay: 0.2s;"></span><span style="width: 8px; height: 8px; background: #999; border-radius: 50%; animation: bounce 1.4s infinite; animation-delay: 0.4s;"></span></div>';

    wrapper.appendChild(msg);
    container.appendChild(wrapper);
    scrollToBottom();

    return wrapper.id;
}

function removeTypingIndicator(id) {
    if (id) {
        const element = document.getElementById(id);
        if (element) element.remove();
    }
}

function showErrorMessage(errorText) {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper agent-message-wrapper';

    const msg = document.createElement('div');
    msg.className = 'agent-message';
    msg.style.background = '#FFE5E5';
    msg.style.color = '#C92A2A';
    msg.innerHTML = `<p>${escapeHtml(errorText)}</p>`;

    wrapper.appendChild(msg);
    container.appendChild(wrapper);
    scrollToBottom();
}

// ============================================
// ACTIONS
// ============================================

function askQuestion(question) {
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.value = question;
        chatInput.focus();
        sendMessage();
    }
}

function startNewChat() {
    // Save current conversation
    saveCurrentConversationMessages();

    // Create new conversation
    const newConv = createConversationObject('New Conversation');
    conversations.unshift(newConv); // Add to top
    activeConversationId = newConv.id;
    conversationHistory = [];

    // Update sessionStorage conversation_id
    sessionStorage.setItem('conversation_id', newConv.id);

    // Show welcome message
    showWelcomeMessage();
    showSuggestedQuestions();
    renderConversationSidebar();
    saveConversations();

    // Focus input
    const chatInput = document.getElementById('chat-input');
    if (chatInput) chatInput.focus();
}

function showWelcomeMessage() {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const userName = localStorage.getItem('hr_user_name') || 'there';
    const firstName = userName.split(' ')[0];
    const userRole = localStorage.getItem('hr_current_role') || 'employee';
    const roleLabelMap = { employee: 'Employee', manager: 'Manager', hr_admin: 'HR Admin' };
    const roleLabel = roleLabelMap[userRole] || 'Employee';

    container.innerHTML = `
        <div class="message-wrapper agent-message-wrapper">
            <div class="agent-message">
                <div class="agent-avatar">🤖</div>
                <div class="agent-message-body">
                    <p>Hello, <strong>${escapeHtml(firstName)}</strong>! 👋 I see you're signed in as <strong>${roleLabel}</strong>.</p>
                    <p>I'm your HR Intelligence Assistant. I can help you with:</p>
                    <ul class="chat-list">
                        <li>Leave and attendance questions</li>
                        <li>Benefits and compensation inquiries</li>
                        <li>Policy information</li>
                        <li>Workflow and approval status</li>
                        <li>Document generation</li>
                    </ul>
                    <p>What can I help you with today?</p>
                </div>
            </div>
            <span class="message-time">Just now</span>
        </div>
    `;
}

function toggleReasoningTrace(traceId) {
    const trace = document.getElementById(traceId);
    if (trace) {
        const isHidden = trace.classList.contains('hidden');
        trace.classList.toggle('hidden');
        // Find the button that triggered this
        const btn = trace.previousElementSibling;
        if (btn && btn.classList.contains('reasoning-btn')) {
            btn.textContent = isHidden ? 'Hide Reasoning' : 'View Reasoning';
        }
    }
}

// ============================================
// UTILITIES
// ============================================

function showSuggestedQuestions() {
    const suggestedDiv = document.getElementById('suggested-questions');
    if (suggestedDiv) suggestedDiv.style.display = 'flex';
}

function hideSuggestedQuestions() {
    const suggestedDiv = document.getElementById('suggested-questions');
    if (suggestedDiv) suggestedDiv.style.display = 'none';
}

function scrollToBottom() {
    const container = document.getElementById('messages-container');
    if (container) {
        setTimeout(() => { container.scrollTop = container.scrollHeight; }, 100);
    }
}

function getCurrentTime() {
    return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Parse agent response text into richly formatted HTML.
 * Handles: section headers, key-value cards, bullet lists, numbered lists,
 * **bold**, tables, and structured data visualization.
 */
function formatAgentResponse(text) {
    if (!text) return '';

    // First escape HTML entities
    let html = escapeHtml(text);

    // Convert **bold** to <strong>
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Split into lines
    const lines = html.split('\n');
    let result = '';
    let inList = false;
    let listType = null; // 'ul' or 'ol'
    let kvItems = []; // key-value pair accumulator

    // Helper: flush accumulated key-value items as styled cards
    function flushKVCards() {
        if (kvItems.length === 0) return;
        result += '<div class="chat-kv-grid">';
        kvItems.forEach(item => {
            const iconMap = {
                'vacation': '🏖️', 'sick': '🤒', 'personal': '👤', 'carryover': '🔄',
                'tenure': '⭐', 'salary': '💰', 'bonus': '🎁', 'benefit': '🛡️',
                'health': '❤️', 'dental': '🦷', 'vision': '👁️', '401k': '📈',
                'pto': '🌴', 'leave': '📅', 'days': '📅', 'hours': '⏰',
                'remote': '🏠', 'insurance': '🛡️', 'pay': '💵', 'time': '⏰'
            };
            let icon = '📋';
            const keyLower = item.key.toLowerCase();
            for (const [keyword, emoji] of Object.entries(iconMap)) {
                if (keyLower.includes(keyword)) { icon = emoji; break; }
            }
            result += `<div class="chat-kv-card">
                <div class="chat-kv-icon">${icon}</div>
                <div class="chat-kv-label">${item.key}</div>
                <div class="chat-kv-value">${item.value}</div>
            </div>`;
        });
        result += '</div>';
        kvItems = [];
    }

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmed = line.trim();

        // Detect bullet list items (•, -, *) with possible key: value pattern
        const bulletMatch = trimmed.match(/^([•\-\*])\s+(.+)/);
        // Detect sub-numbered items like 1.1, 1.2, 2.1 — treat as bullets
        const subNumberedMatch = trimmed.match(/^(\d+\.\d+)[.)]?\s+(.+)/);
        // Detect numbered list items (1., 2., etc.) — but NOT sub-numbers
        const numberedMatch = !subNumberedMatch && trimmed.match(/^(\d+)[.)]\s+(.+)/);

        // Merge sub-numbered items (1.1, 2.3, etc.) into bullet handling
        const effectiveBullet = bulletMatch || subNumberedMatch;

        if (effectiveBullet) {
            // Close any non-ul list
            if (inList && listType !== 'ul') {
                result += '</ol>';
                inList = false;
                listType = null;
            }

            const bulletContent = effectiveBullet[2];
            // Check for "Key: Value" pattern (structured data)
            const kvMatch = bulletContent.match(/^(.+?):\s+(.+)/);
            if (kvMatch && kvMatch[1].length < 40) {
                // Accumulate as key-value card
                if (inList) {
                    result += '</ul>';
                    inList = false;
                    listType = null;
                }
                kvItems.push({ key: kvMatch[1], value: kvMatch[2] });
            } else {
                // Regular bullet - flush any pending KV cards first
                flushKVCards();
                if (!inList || listType !== 'ul') {
                    if (inList) result += listType === 'ol' ? '</ol>' : '</ul>';
                    result += '<ul class="chat-list">';
                    inList = true;
                    listType = 'ul';
                }
                result += `<li>${bulletContent}</li>`;
            }
        } else if (numberedMatch) {
            flushKVCards();
            if (!inList || listType !== 'ol') {
                if (inList) result += listType === 'ol' ? '</ol>' : '</ul>';
                result += '<ol class="chat-list">';
                inList = true;
                listType = 'ol';
            }
            result += `<li>${numberedMatch[2]}</li>`;
        } else {
            // Flush any accumulated KV cards
            flushKVCards();

            // When inside an ordered list, keep continuation text inside the last <li>
            // and skip blank lines — don't close the list until we hit a section header or end
            if (inList && listType === 'ol') {
                if (trimmed === '') {
                    // Blank line inside numbered list — just add spacing, don't close
                    continue;
                }
                // Check if upcoming lines have another numbered item (look ahead)
                let hasMoreNumbered = false;
                for (let j = i + 1; j < lines.length && j <= i + 5; j++) {
                    const fut = lines[j].trim();
                    if (fut.match(/^\d+[.)]\s+/)) { hasMoreNumbered = true; break; }
                    if (fut.match(/^[•\-\*]\s+/) || (fut.endsWith(':') && fut.length < 60)) break;
                }
                if (hasMoreNumbered || trimmed.length > 0) {
                    // Continuation text — append to current list item
                    result += `<li style="list-style:none;margin-left:-20px;margin-top:-4px;"><span style="font-size:13px;">${trimmed}</span></li>`;
                    continue;
                }
            }

            // Close any open list
            if (inList) {
                result += listType === 'ol' ? '</ol>' : '</ul>';
                inList = false;
                listType = null;
            }

            if (trimmed === '') {
                result += '<br>';
            } else if (trimmed.endsWith(':') && trimmed.length < 60) {
                // Section header (e.g., "TechNova PTO Policy:")
                result += `<div class="chat-section-header">${trimmed.slice(0, -1)}</div>`;
            } else if (trimmed.match(/^(Contact|Note|Important|Tip|Submit|For more):/i)) {
                // Info callout
                result += `<div class="chat-info-callout">${trimmed}</div>`;
            } else {
                result += `<p>${trimmed}</p>`;
            }
        }
    }

    // Flush any remaining KV cards
    flushKVCards();

    // Close trailing list
    if (inList) {
        result += listType === 'ol' ? '</ol>' : '</ul>';
    }

    return result;
}

function getConversationId() {
    return activeConversationId || sessionStorage.getItem('conversation_id') || 'conv_' + Date.now();
}

// Bounce animation
const chatStyle = document.createElement('style');
chatStyle.textContent = `
    @keyframes bounce {
        0%, 80%, 100% { transform: scale(0); opacity: 0.5; }
        40% { transform: scale(1); opacity: 1; }
    }
    .hidden { display: none !important; }
`;
document.head.appendChild(chatStyle);

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    setActivePage('chat');
    setupChatListeners();
    initConversations();

    // Ensure welcome message is shown if no messages are loaded
    const container = document.getElementById('messages-container');
    if (container && container.children.length === 0) {
        showWelcomeMessage();
        showSuggestedQuestions();
    }

    console.log('Chat_v2.js loaded successfully');
});

// Export functions
window.sendMessage = sendMessage;
window.askQuestion = askQuestion;
window.startNewChat = startNewChat;
window.toggleReasoningTrace = toggleReasoningTrace;
window.setupChatListeners = setupChatListeners;
window.switchConversation = switchConversation;

// ============================================
// CHAT HISTORY PERSISTENCE & SESSIONS
// ============================================

// Session tracking (30 min gap = new session)
const SESSION_TIMEOUT = 30 * 60 * 1000; // 30 minutes

function getSessionGap() {
    const activeConv = conversations.find(c => c.id === activeConversationId);
    if (!activeConv || activeConv.messages.length === 0) return 0;
    
    const lastMsg = activeConv.messages[activeConv.messages.length - 1];
    const lastTime = new Date(lastMsg.timestamp || activeConv.createdAt).getTime();
    return Date.now() - lastTime;
}

function isNewSession() {
    return getSessionGap() > SESSION_TIMEOUT;
}

function addSessionDivider(sessionNumber) {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const divider = document.createElement('div');
    divider.className = 'session-divider';
    divider.innerHTML = `
        <div class="session-divider-line"></div>
        <div class="session-divider-text">Session ${sessionNumber}</div>
        <div class="session-divider-line"></div>
    `;
    container.appendChild(divider);
}

// Enhanced message rendering with timestamp
function renderUserMessageWithTimestamp(content, timestamp) {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper user-message-wrapper';

    const time = timestamp ? new Date(timestamp).toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    }) : 'Just now';

    wrapper.innerHTML = `
        <div class="user-message">
            <p>${escapeHtml(content)}</p>
        </div>
        <span class="message-time">${time}</span>
    `;

    container.appendChild(wrapper);
}

function renderAgentMessageWithTimestamp(content, timestamp) {
    const container = document.getElementById('messages-container');
    if (!container) return;

    const wrapper = document.createElement('div');
    wrapper.className = 'message-wrapper agent-message-wrapper';

    const time = timestamp ? new Date(timestamp).toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    }) : 'Just now';

    wrapper.innerHTML = `
        <div class="agent-message">
            <p>${content}</p>
        </div>
        <span class="message-time">${time}</span>
    `;

    container.appendChild(wrapper);
}

// Save conversations to both localStorage and server
async function saveConversationsToServer() {
    if (!activeConversationId) return;

    const activeConv = conversations.find(c => c.id === activeConversationId);
    if (!activeConv) return;

    try {
        const response = await apiCall('/api/v2/chat/history', {
            method: 'POST',
            body: JSON.stringify({
                conversation_id: activeConv.id,
                messages: activeConv.messages,
                title: activeConv.title,
                created_at: activeConv.createdAt
            })
        });

        if (response && response.success) {
            // Server saved successfully
            return true;
        }
    } catch (error) {
        console.warn('Failed to save chat history to server (will use localStorage):', error);
    }
    return false;
}

// Load chat history from server
async function loadConversationsFromServer() {
    try {
        const response = await apiCall('/api/v2/chat/history', {
            method: 'GET'
        });

        if (response && response.data && response.data.conversations) {
            // Merge server conversations with local ones
            const serverConvs = response.data.conversations;
            conversations = serverConvs.length > 0 ? serverConvs : conversations;
            return true;
        }
    } catch (error) {
        console.warn('Failed to load chat history from server (using localStorage):', error);
    }
    return false;
}

// Add clear history button functionality
function clearChatHistory() {
    if (!confirm('Are you sure you want to clear all chat history? This cannot be undone.')) {
        return;
    }

    conversations = [createConversationObject('New Conversation')];
    activeConversationId = conversations[0].id;
    conversationHistory = [];

    const container = document.getElementById('messages-container');
    if (container) {
        container.innerHTML = '';
        showWelcomeMessage();
        showSuggestedQuestions();
    }

    saveConversations();
    renderConversationSidebar();
    showToast('Chat history cleared', 'success');
}

// Add clear button to conversation header
function addClearHistoryButton() {
    const header = document.querySelector('.sidebar-header');
    if (!header) return;

    // Check if button already exists
    if (header.querySelector('.clear-history-btn')) return;

    const clearBtn = document.createElement('button');
    clearBtn.className = 'clear-history-btn';
    clearBtn.title = 'Clear chat history';
    clearBtn.innerHTML = '🗑️';
    clearBtn.onclick = (e) => {
        e.stopPropagation();
        clearChatHistory();
    };
    clearBtn.style.cssText = `
        position: absolute;
        right: 12px;
        top: 16px;
        background: rgba(255,255,255,0.2);
        border: none;
        border-radius: 4px;
        padding: 4px 8px;
        cursor: pointer;
        font-size: 14px;
        transition: background 0.2s;
    `;
    clearBtn.onmouseover = () => clearBtn.style.background = 'rgba(255,255,255,0.3)';
    clearBtn.onmouseout = () => clearBtn.style.background = 'rgba(255,255,255,0.2)';

    header.appendChild(clearBtn);
}

// Initialize server sync
async function initChatServerSync() {
    // Try to load from server first, fall back to localStorage
    const serverLoaded = await loadConversationsFromServer();
    
    if (!serverLoaded) {
        // Use localStorage as fallback
        initConversations();
    } else {
        // Render with server data
        if (conversations.length === 0) {
            conversations = [createConversationObject('New Conversation')];
        }
        activeConversationId = conversations[0].id;
        renderConversationSidebar();
    }

    // Add clear button
    addClearHistoryButton();

    // Auto-save every 10 seconds
    setInterval(() => {
        if (conversationHistory.length > 0) {
            saveConversations();
            saveConversationsToServer().catch(() => {});
        }
    }, 10000);
}

// Export new functions
window.clearChatHistory = clearChatHistory;
window.initChatServerSync = initChatServerSync;
window.saveConversationsToServer = saveConversationsToServer;
window.loadConversationsFromServer = loadConversationsFromServer;

// Add CSS for session dividers
const chatStyles = document.createElement('style');
chatStyles.textContent = `
.session-divider {
    display: flex;
    align-items: center;
    margin: 24px 0 16px;
    gap: 12px;
    color: var(--text-secondary);
    font-size: 12px;
}

.session-divider-line {
    flex: 1;
    height: 1px;
    background: linear-gradient(to right, transparent, var(--border-color), transparent);
}

.session-divider-text {
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.clear-history-btn {
    opacity: 0.8;
}

.clear-history-btn:hover {
    opacity: 1;
}
`;
document.head.appendChild(chatStyles);
