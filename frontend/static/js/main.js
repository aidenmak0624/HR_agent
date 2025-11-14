// ============================================
// MAIN.JS - FIXED VERSION
// Human Rights Education Platform
// ============================================

// API Configuration
const API_BASE = 'http://localhost:5050';

// State Management
let currentTopic = null;
let currentDifficulty = 'intermediate';
let conversationHistory = [];
let useAgentMode = true;  // Default to agent mode
let debugMode = false;

// DOM Elements - Will be initialized after DOM loads
let topicSelection, chatSection, topicsGrid, chatContainer;
let userInput, sendBtn, backBtn, currentTopicEl;

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize DOM elements
    topicSelection = document.getElementById('topic-selection');
    chatSection = document.getElementById('chat-section');
    topicsGrid = document.getElementById('topics-grid');
    chatContainer = document.getElementById('chat-container');
    userInput = document.getElementById('user-input');
    sendBtn = document.getElementById('send-btn');
    backBtn = document.getElementById('back-btn');
    currentTopicEl = document.getElementById('current-topic');
    
    loadTopics();
    setupEventListeners();
    setupAgentControls();
});

// ============================================
// AGENT CONTROLS SETUP
// ============================================

function setupAgentControls() {
    const agentToggle = document.getElementById('agent-mode');
    const debugToggle = document.getElementById('debug-mode');
    
    if (agentToggle) {
        agentToggle.addEventListener('change', (e) => {
            useAgentMode = e.target.checked;
            console.log('Agent mode:', useAgentMode ? 'ON' : 'OFF');
            
            showNotification(
                useAgentMode 
                    ? '🤖 Agent mode enabled - Autonomous tool selection active' 
                    : '📝 Agent mode disabled - Using basic RAG only',
                'info'
            );
        });
    }
    
    if (debugToggle) {
        debugToggle.addEventListener('change', (e) => {
            debugMode = e.target.checked;
            console.log('Debug mode:', debugMode ? 'ON' : 'OFF');
            
            if (debugMode) {
                showNotification('🔍 Debug mode enabled - Reasoning traces will be shown', 'info');
            }
        });
    }
}

// ============================================
// TOPICS
// ============================================

async function loadTopics() {
    topicsGrid.innerHTML = '<p>Loading topics…</p>';

    try {
        const response = await fetch(`${API_BASE}/api/topics`, {
            method: 'GET',
            headers: {
                'Accept': 'application/json'
            }
        });

        if (!response.ok) {
            console.error(`HTTP error! ${response.status} - ${response.statusText}`);
            topicsGrid.innerHTML = `<p>Failed to load topics (${response.status}). Please refresh.</p>`;
            return;
        }

        const data = await response.json();

        if (!data || !Array.isArray(data.topics)) {
            console.error('Invalid response format:', data);
            topicsGrid.innerHTML = '<p>Server returned invalid data. Contact support.</p>';
            return;
        }

        topicsGrid.innerHTML = '';

        if (data.topics.length === 0) {
            topicsGrid.innerHTML = '<p>No topics available.</p>';
            return;
        }

        data.topics.forEach(topic => {
            const card = createTopicCard(topic);
            topicsGrid.appendChild(card);
        });

    } catch (err) {
        console.error('Error loading topics:', err);
        topicsGrid.innerHTML = '<p>Unexpected error occurred. Please check your connection.</p>';
    }
}

function createTopicCard(topic) {
    const card = document.createElement('div');
    card.className = 'topic-card';
    card.innerHTML = `
        <div class="icon">${topic.icon}</div>
        <h3>${topic.name}</h3>
        <p>${topic.description}</p>
    `;
    
    card.addEventListener('click', () => selectTopic(topic));
    
    return card;
}

function selectTopic(topic) {
    currentTopic = topic;
    currentTopicEl.textContent = topic.name;
    
    topicSelection.classList.add('hidden');
    chatSection.classList.remove('hidden');
    
    chatContainer.innerHTML = '';
    conversationHistory = [];
    
    const welcomeDiv = document.createElement('div');
    welcomeDiv.className = 'message ai-message';
    welcomeDiv.innerHTML = `
        <div class="message-content">
            <p>Welcome! I'm your AI assistant ${useAgentMode ? 'with autonomous agent capabilities' : ''}.</p>
            <p>Ask me anything about <strong>${topic.name}</strong>.</p>
            ${useAgentMode ? '<p><em>Agent mode is active - I can use multiple specialized tools to give you comprehensive answers.</em></p>' : ''}
        </div>
        <div class="message-time">${getCurrentTime()}</div>
    `;
    chatContainer.appendChild(welcomeDiv);
    
    userInput.focus();
}

// ============================================
// EVENT LISTENERS
// ============================================

function setupEventListeners() {
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }
    
    if (userInput) {
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        
        // Enable/disable send button based on input
        userInput.addEventListener('input', () => {
            sendBtn.disabled = !userInput.value.trim();
        });
    }
    
    if (backBtn) {
        backBtn.addEventListener('click', () => {
            topicSelection.classList.remove('hidden');
            chatSection.classList.add('hidden');
            currentTopic = null;
            conversationHistory = [];
        });
    }
}

// ============================================
// DIFFICULTY MANAGEMENT
// ============================================

function updateDifficulty(level) {
    currentDifficulty = level;
    
    const hints = {
        'beginner': 'Simple explanations with examples',
        'intermediate': 'Balanced detail and accessibility',
        'advanced': 'Comprehensive legal analysis'
    };
    
    const hintElement = document.getElementById('difficulty-hint');
    if (hintElement) {
        hintElement.textContent = hints[level];
    }
    
    console.log('Difficulty updated to:', level);
}

// ============================================
// MESSAGING - FIXED VERSION
// ============================================

async function sendMessage() {
    const message = userInput.value.trim();
    
    if (!message || !currentTopic) {
        console.warn('Cannot send: empty message or no topic selected');
        return;
    }
    
    // Disable send button to prevent double-send
    sendBtn.disabled = true;
    
    // Add user message to chat
    addUserMessage(message);
    
    // Clear input
    userInput.value = '';
    
    // Show typing indicator
    const typingIndicator = showTypingIndicator();
    
    try {
        // Choose endpoint based on mode
        const endpoint = useAgentMode ? '/api/agent/chat' : '/api/chat';
        
        console.log(`Sending to ${endpoint}:`, {
            query: message,
            topic: currentTopic.id,
            difficulty: currentDifficulty
        });
        
        const response = await fetch(`${API_BASE}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({
                query: message,
                topic: currentTopic.id,
                difficulty: currentDifficulty
            })
        });
        
        // Remove typing indicator
        typingIndicator.remove();
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('Server error:', response.status, errorText);
            addErrorMessage(`Server error (${response.status}). Please try again.`);
            return;
        }
        
        const data = await response.json();
        console.log('Response received:', data);
        
        // Add AI response
        addAIMessage(data);
        
    } catch (error) {
        console.error('Error sending message:', error);
        typingIndicator.remove();
        addErrorMessage('Failed to connect to server. Please check if the server is running.');
    } finally {
        // Re-enable send button
        sendBtn.disabled = false;
        userInput.focus();
    }
}

function addUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    messageDiv.innerHTML = `
        <div class="message-content">
            <p>${escapeHtml(message)}</p>
        </div>
        <div class="message-time">${getCurrentTime()}</div>
    `;
    
    chatContainer.appendChild(messageDiv);
    conversationHistory.push({ role: 'user', content: message });
    scrollToBottom();
}

function addAIMessage(data) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message ai-message';
    
    // Store metadata for debugging
    if (data.reasoning_trace) {
        messageDiv.dataset.reasoning = JSON.stringify(data.reasoning_trace);
    }
    
    // Format the answer
    const formattedAnswer = formatAnswer(data.answer || 'No response generated.');
    
    // Create sources HTML
    const sourcesHTML = createSourcesHTML(data.sources || []);
    
    // Create metadata badges (for agent mode)
    let metadataHTML = '';
    if (useAgentMode && data.tools_used) {
        const confidence = Math.round((data.confidence || 0) * 100);
        metadataHTML = `
            <div class="message-metadata">
                <span class="metadata-badge">
                    <span class="icon">🔧</span> 
                    ${data.tools_used.join(' → ')}
                </span>
                <span class="metadata-badge">
                    <span class="icon">📊</span> 
                    Confidence: ${confidence}%
                </span>
            </div>
        `;
    }
    
    messageDiv.innerHTML = `
        <div class="message-content">
            ${formattedAnswer}
            ${sourcesHTML}
            ${metadataHTML}
        </div>
        <div class="message-actions">
            <button onclick="copyToClipboard(this)" class="action-btn" title="Copy to clipboard">
                <span class="icon">📋</span> Copy
            </button>
            ${data.reasoning_trace && data.reasoning_trace.length > 0 ? `
                <button onclick="showReasoning(this)" class="action-btn" title="View reasoning">
                    <span class="icon">🧠</span> Reasoning
                </button>
            ` : ''}
        </div>
        <div class="message-time">${getCurrentTime()}</div>
    `;
    
    chatContainer.appendChild(messageDiv);
    conversationHistory.push({ 
        role: 'assistant', 
        content: data.answer,
        sources: data.sources,
        metadata: {
            tools_used: data.tools_used,
            confidence: data.confidence,
            reasoning_trace: data.reasoning_trace
        }
    });
    scrollToBottom();
}

function addErrorMessage(errorText) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message error-message';
    messageDiv.innerHTML = `
        <div class="message-content">
            <p>❌ ${escapeHtml(errorText)}</p>
        </div>
        <div class="message-time">${getCurrentTime()}</div>
    `;
    
    chatContainer.appendChild(messageDiv);
    scrollToBottom();
}

function showTypingIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'message ai-message typing-indicator';
    indicator.innerHTML = `
        <div class="message-content">
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    chatContainer.appendChild(indicator);
    scrollToBottom();
    return indicator;
}

// ============================================
// SOURCE DISPLAY
// ============================================

function createSourcesHTML(sources) {
    if (!sources || sources.length === 0) {
        return '';
    }
    
    const sourceBadges = sources.map(source => {
        return `
            <span class="source-badge">
                <span class="source-icon">📄</span>
                <span class="source-name">${escapeHtml(source)}</span>
            </span>
        `;
    }).join('');
    
    return `
        <div class="sources-section">
            <div class="sources-header">
                <span class="sources-icon">📚</span>
                <strong>Sources</strong>
            </div>
            <div class="sources-list">
                ${sourceBadges}
            </div>
        </div>
    `;
}

// ============================================
// REASONING MODAL
// ============================================

function showReasoning(button) {
    const messageDiv = button.closest('.ai-message');
    const reasoning = JSON.parse(messageDiv.dataset.reasoning || '[]');
    
    if (!reasoning || reasoning.length === 0) {
        alert('No reasoning trace available');
        return;
    }
    
    const modal = document.createElement('div');
    modal.className = 'reasoning-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="this.closest('.reasoning-modal').remove()"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h3>🧠 Agent Reasoning Process</h3>
                <button class="modal-close" onclick="this.closest('.reasoning-modal').remove()">✕</button>
            </div>
            <div class="reasoning-steps">
                ${reasoning.map((step, i) => {
                    const icon = step.includes('PLAN') ? '📋' :
                                step.includes('DECISION') ? '🎯' :
                                step.includes('EXECUTED') ? '⚙️' :
                                step.includes('REFLECTION') ? '🤔' :
                                '📍';
                    
                    return `
                        <div class="reasoning-step">
                            <span class="step-number">${i + 1}</span>
                            <span class="step-icon">${icon}</span>
                            <span class="step-text">${escapeHtml(step)}</span>
                        </div>
                    `;
                }).join('')}
            </div>
            <button class="btn-primary" onclick="this.closest('.reasoning-modal').remove()">
                Close
            </button>
        </div>
    `;
    
    document.body.appendChild(modal);
}

// ============================================
// COPY FUNCTIONALITY
// ============================================

function copyToClipboard(button) {
    const messageDiv = button.closest('.ai-message');
    const contentDiv = messageDiv.querySelector('.message-content');
    const text = contentDiv.innerText;
    
    navigator.clipboard.writeText(text).then(() => {
        const originalHTML = button.innerHTML;
        button.innerHTML = '<span class="icon">✅</span> Copied!';
        button.classList.add('copied');
        
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('copied');
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy to clipboard');
    });
}

// ============================================
// CONVERSATION MANAGEMENT
// ============================================

function clearConversation() {
    if (confirm('Clear conversation history?')) {
        conversationHistory = [];
        chatContainer.innerHTML = `
            <div class="message ai-message">
                <div class="message-content">
                    <p>Conversation cleared. Ask me anything about ${currentTopic.name}!</p>
                </div>
                <div class="message-time">${getCurrentTime()}</div>
            </div>
        `;
    }
}

// ============================================
// UTILITY FUNCTIONS
// ============================================

function scrollToBottom() {
    chatContainer.scrollTo({
        top: chatContainer.scrollHeight,
        behavior: 'smooth'
    });
}

function getCurrentTime() {
    const now = new Date();
    return now.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatAnswer(answer) {
    // Convert markdown-style bold to HTML
    answer = answer.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    
    // Convert newlines to paragraphs
    return answer
        .split('\n\n')
        .map(p => p.trim())
        .filter(p => p.length > 0)
        .map(p => `<p>${p.replace(/\n/g, '<br>')}</p>`)
        .join('');
}

function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'info' ? '#667eea' : '#f44336'};
        color: white;
        border-radius: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================
// EXPORT FUNCTIONS (for inline handlers)
// ============================================

window.copyToClipboard = copyToClipboard;
window.clearConversation = clearConversation;
window.updateDifficulty = updateDifficulty;
window.showReasoning = showReasoning;

console.log('✅ Main.js loaded successfully');