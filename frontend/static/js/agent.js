// ============================================
// AGENT.JS - Agent-Specific Utilities
// Additional functionality for agent features
// ============================================

/**
 * Export conversation with agent metadata
 */
function exportConversationWithMetadata() {
    if (!currentTopic || conversationHistory.length === 0) {
        alert('No conversation to export');
        return;
    }
    
    const exportData = {
        platform: 'Human Rights Education Platform',
        topic: {
            id: currentTopic.id,
            name: currentTopic.name
        },
        difficulty: currentDifficulty,
        agent_mode: useAgentMode,
        debug_mode: debugMode,
        exported_at: new Date().toISOString(),
        conversation: conversationHistory.map(msg => ({
            role: msg.role,
            content: msg.content,
            sources: msg.sources || [],
            metadata: msg.metadata || {},
            timestamp: msg.timestamp
        })),
        summary: {
            total_messages: conversationHistory.length,
            user_messages: conversationHistory.filter(m => m.role === 'user').length,
            ai_messages: conversationHistory.filter(m => m.role === 'assistant').length,
            unique_sources: getUniqueSources()
        }
    };
    
    const dataStr = JSON.stringify(exportData, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    
    const link = document.createElement('a');
    link.href = url;
    link.download = `conversation_${currentTopic.id}_${Date.now()}.json`;
    link.click();
    
    URL.revokeObjectURL(url);
    
    showNotification('✅ Exported', 'Conversation saved successfully');
}

/**
 * Get unique sources across conversation
 */
function getUniqueSources() {
    const sources = new Set();
    conversationHistory.forEach(msg => {
        if (msg.sources) {
            msg.sources.forEach(src => sources.add(src));
        }
    });
    return Array.from(sources);
}

/**
 * Analyze conversation statistics
 */
function analyzeConversation() {
    if (conversationHistory.length === 0) {
        return null;
    }
    
    const aiMessages = conversationHistory.filter(m => m.role === 'assistant' && m.metadata);
    
    const stats = {
        total_messages: conversationHistory.length,
        user_messages: conversationHistory.filter(m => m.role === 'user').length,
        ai_messages: aiMessages.length,
        avg_confidence: aiMessages.length > 0 
            ? aiMessages.reduce((sum, m) => sum + (m.metadata.confidence || 0), 0) / aiMessages.length 
            : 0,
        tools_usage: {},
        total_iterations: aiMessages.reduce((sum, m) => sum + (m.metadata.iterations || 0), 0)
    };
    
    // Count tool usage
    aiMessages.forEach(msg => {
        if (msg.metadata.tools_used) {
            msg.metadata.tools_used.forEach(tool => {
                stats.tools_usage[tool] = (stats.tools_usage[tool] || 0) + 1;
            });
        }
    });
    
    return stats;
}

/**
 * Display conversation statistics
 */
function showConversationStats() {
    const stats = analyzeConversation();
    
    if (!stats) {
        alert('No conversation data to analyze');
        return;
    }
    
    const modal = document.createElement('div');
    modal.className = 'reasoning-modal';
    
    const toolsUsageHTML = Object.entries(stats.tools_usage)
        .map(([tool, count]) => `
            <div style="display: flex; justify-content: space-between; padding: 5px 0;">
                <span>${tool}</span>
                <span style="font-weight: bold;">${count}x</span>
            </div>
        `).join('');
    
    modal.innerHTML = `
        <div class="modal-overlay" onclick="this.closest('.reasoning-modal').remove()"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h3>📊 Conversation Statistics</h3>
                <button class="modal-close" onclick="this.closest('.reasoning-modal').remove()">✕</button>
            </div>
            <div style="padding: 20px;">
                <div style="margin-bottom: 20px;">
                    <h4 style="margin-bottom: 10px;">Overview</h4>
                    <p>Total Messages: <strong>${stats.total_messages}</strong></p>
                    <p>User Messages: <strong>${stats.user_messages}</strong></p>
                    <p>AI Messages: <strong>${stats.ai_messages}</strong></p>
                    <p>Average Confidence: <strong>${(stats.avg_confidence * 100).toFixed(1)}%</strong></p>
                    <p>Total Iterations: <strong>${stats.total_iterations}</strong></p>
                </div>
                
                ${Object.keys(stats.tools_usage).length > 0 ? `
                    <div>
                        <h4 style="margin-bottom: 10px;">Tool Usage</h4>
                        ${toolsUsageHTML}
                    </div>
                ` : ''}
            </div>
            <button class="btn-primary" onclick="this.closest('.reasoning-modal').remove()">
                Close
            </button>
        </div>
    `;
    
    document.body.appendChild(modal);
}

/**
 * Compare agent mode vs RAG mode (educational)
 */
function explainAgentMode() {
    const modal = document.createElement('div');
    modal.className = 'reasoning-modal';
    modal.innerHTML = `
        <div class="modal-overlay" onclick="this.closest('.reasoning-modal').remove()"></div>
        <div class="modal-content">
            <div class="modal-header">
                <h3>🤖 What is Agent Mode?</h3>
                <button class="modal-close" onclick="this.closest('.reasoning-modal').remove()">✕</button>
            </div>
            <div style="padding: 20px; line-height: 1.6;">
                <h4>Agent Mode (Enabled)</h4>
                <p style="margin-bottom: 15px;">
                    The AI autonomously decides which specialized tools to use based on your question:
                </p>
                <ul style="margin-left: 20px; margin-bottom: 20px;">
                    <li><strong>RAG Search:</strong> Find information in documents</li>
                    <li><strong>Fact Verifier:</strong> Cross-check claims across sources</li>
                    <li><strong>Comparator:</strong> Compare different conventions</li>
                    <li><strong>Educational Planner:</strong> Create lesson plans & quizzes</li>
                </ul>
                
                <h4>Basic RAG Mode (Disabled)</h4>
                <p style="margin-bottom: 15px;">
                    Uses traditional retrieval-augmented generation:
                </p>
                <ul style="margin-left: 20px;">
                    <li>Simple query → retrieve → generate</li>
                    <li>Fixed pipeline, no decision-making</li>
                    <li>Faster but less sophisticated</li>
                </ul>
                
                <div style="margin-top: 20px; padding: 15px; background: #f0f4ff; border-radius: 10px;">
                    <strong>💡 Tip:</strong> Use Agent Mode for complex questions that might need 
                    multiple tools or comparison across documents.
                </div>
            </div>
            <button class="btn-primary" onclick="this.closest('.reasoning-modal').remove()">
                Got it!
            </button>
        </div>
    `;
    
    document.body.appendChild(modal);
}

/**
 * Keyboard shortcut to toggle agent mode
 */
document.addEventListener('keydown', (e) => {
    // Alt + A to toggle agent mode
    if (e.altKey && e.key === 'a') {
        e.preventDefault();
        const toggle = document.getElementById('agent-mode');
        if (toggle) {
            toggle.checked = !toggle.checked;
            toggle.dispatchEvent(new Event('change'));
        }
    }
    
    // Alt + D to toggle debug mode
    if (e.altKey && e.key === 'd') {
        e.preventDefault();
        const toggle = document.getElementById('debug-mode');
        if (toggle) {
            toggle.checked = !toggle.checked;
            toggle.dispatchEvent(new Event('change'));
        }
    }
    
    // Alt + E to export conversation
    if (e.altKey && e.key === 'e') {
        e.preventDefault();
        exportConversationWithMetadata();
    }
    
    // Alt + S to show stats
    if (e.altKey && e.key === 's') {
        e.preventDefault();
        showConversationStats();
    }
    
    // Alt + H to show help
    if (e.altKey && e.key === 'h') {
        e.preventDefault();
        explainAgentMode();
    }
});

/**
 * Add export button to chat header (optional)
 */
function addExportButton() {
    const chatHeader = document.querySelector('.chat-header');
    if (!chatHeader) return;
    
    const headerButtons = chatHeader.querySelector('.header-buttons');
    if (!headerButtons) return;
    
    const exportBtn = document.createElement('button');
    exportBtn.className = 'clear-btn';
    exportBtn.innerHTML = '📥 Export';
    exportBtn.onclick = exportConversationWithMetadata;
    
    headerButtons.appendChild(exportBtn);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        // Optionally add export button
        // addExportButton();
    });
} else {
    // DOM already loaded
    // addExportButton();
}
document.addEventListener('DOMContentLoaded', addExportButton);
console.log('Agent.js loaded - Keyboard shortcuts available:');
console.log('  Alt + A: Toggle Agent Mode');
console.log('  Alt + D: Toggle Debug Mode');
console.log('  Alt + E: Export Conversation');
console.log('  Alt + S: Show Statistics');
console.log('  Alt + H: Help (Explain Agent Mode)');