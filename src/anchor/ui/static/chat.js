/**
 * Anchor Chat UI — Frontend JavaScript
 */

const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const latencyEl = document.getElementById('latency');
const modifiedEl = document.getElementById('modified');
const confidenceEl = document.getElementById('confidence');

// State
let isProcessing = false;

// Event listeners
sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isProcessing) return;

    // Add user message
    addMessage(text, 'user');
    messageInput.value = '';

    // Show loading
    isProcessing = true;
    sendBtn.disabled = true;
    const loadingId = addLoading();

    // Send to backend
    fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text })
    })
    .then(res => res.json())
    .then(data => {
        removeLoading(loadingId);
        displayResult(data);
        updateStats(data);
    })
    .catch(err => {
        removeLoading(loadingId);
        addMessage(`Hata: ${err.message}`, 'bot');
    })
    .finally(() => {
        isProcessing = false;
        sendBtn.disabled = false;
    });
}

function addMessage(text, sender) {
    const msg = document.createElement('div');
    msg.className = `message ${sender}`;
    msg.textContent = text;
    chatContainer.appendChild(msg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return msg;
}

function addLoading() {
    const msg = document.createElement('div');
    msg.className = 'message bot';
    msg.id = 'loading-' + Date.now();
    msg.innerHTML = '<span class="spinner"></span> Düzeltme motoru çalışıyor...';
    chatContainer.appendChild(msg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return msg.id;
}

function removeLoading(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function displayResult(data) {
    const msg = document.createElement('div');
    msg.className = 'message bot';

    // Düzeltilmiş cevap
    const corrected = document.createElement('div');
    corrected.textContent = data.corrected || data.raw;
    msg.appendChild(corrected);

    // Meta bilgi
    const meta = document.createElement('div');
    meta.className = 'meta';

    const modText = data.modified ? '✅ Düzeltildi' : '❌ Değişmedi';
    meta.innerHTML = `
        <span>${modText}</span>
        <span>⏱ ${data.latency_ms.toFixed(1)}ms</span>
        <span>🎯 ${(data.confidence * 100).toFixed(0)}%</span>
    `;
    msg.appendChild(meta);

    // Düzeltme badge'leri
    if (data.corrections && data.corrections.length > 0) {
        const badgeContainer = document.createElement('div');
        badgeContainer.style.marginTop = '8px';
        data.corrections.forEach(c => {
            const badge = document.createElement('span');
            badge.className = `correction-badge ${c.severity.toLowerCase()}`;
            badge.textContent = c.severity;
            badgeContainer.appendChild(badge);
        });
        msg.appendChild(badgeContainer);
    }

    // Rapor paneli
    if (data.report) {
        const report = document.createElement('details');
        report.className = 'report-panel';
        report.innerHTML = `
            <summary>📋 Rapor</summary>
            <div class="details">${escapeHtml(data.report)}</div>
        `;
        msg.appendChild(report);
    }

    // Ham cevap (collapse)
    if (data.modified && data.raw !== data.corrected) {
        const rawPanel = document.createElement('details');
        rawPanel.className = 'report-panel';
        rawPanel.style.borderLeftColor = '#666';
        rawPanel.innerHTML = `
            <summary>🤖 LLM Ham Cevabı (değiştirildi)</summary>
            <div class="details">${escapeHtml(data.raw)}</div>
        `;
        msg.appendChild(rawPanel);
    }

    chatContainer.appendChild(msg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function updateStats(data) {
    if (data.latency_ms) latencyEl.textContent = data.latency_ms.toFixed(1) + 'ms';
    if (data.modified !== undefined) modifiedEl.textContent = data.modified ? 'Evet' : 'Hayır';
    if (data.confidence !== undefined) confidenceEl.textContent = (data.confidence * 100).toFixed(0) + '%';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
