/**
 * Anchor Chat UI v2 — Clean UX: Kullanıcıya sadece nihai sonuç.
 * 
 * Prensip: LLM↔Anchor iletişimi kullanıcıya görünmez.
 * Sadece düzeltilmiş sonuç gösterilir.
 * Detaylar sadece istenirse (click) açılır — developer/audit için.
 */

const chatContainer = document.getElementById('chat-container');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const latencyEl = document.getElementById('latency');
const modifiedEl = document.getElementById('modified');
const confidenceEl = document.getElementById('confidence');

let isProcessing = false;

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isProcessing) return;

    addMessage(text, 'user');
    messageInput.value = '';

    isProcessing = true;
    sendBtn.disabled = true;
    const loadingId = addLoading();

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
    msg.innerHTML = '<span class="spinner"></span> Düzeltiliyor...';
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

    // === NİHAYİ CEVAP (tek şey kullanıcı görür) ===
    const corrected = document.createElement('div');
    corrected.className = 'final-text';
    corrected.textContent = data.corrected || data.raw;
    msg.appendChild(corrected);

    // === ALT BİLGİ BAR: Minimal, unobtrusive ===
    const meta = document.createElement('div');
    meta.className = 'meta-bar';

    // Düzeltme varsa küçük 🔧 indikator, yoksa hiçbir şey
    if (data.modified && data.corrections && data.corrections.length > 0) {
        const fixCount = data.corrections.length;
        const fixBtn = document.createElement('button');
        fixBtn.className = 'fix-toggle';
        fixBtn.textContent = `🔧 ${fixCount} düzeltme`;
        fixBtn.onclick = () => toggleDetails(msg, data);
        meta.appendChild(fixBtn);
    }

    // Sağ: latency (muted)
    const latency = document.createElement('span');
    latency.className = 'latency-muted';
    latency.textContent = `⏱ ${data.latency_ms.toFixed(1)}ms`;
    meta.appendChild(latency);

    msg.appendChild(meta);

    // === DETAY PANELİ: Başta gizli, istenirse açılır ===
    const detailsPanel = document.createElement('div');
    detailsPanel.className = 'details-panel hidden';
    detailsPanel.dataset.role = 'details';
    
    // Severity badge'leri (details içinde)
    if (data.corrections && data.corrections.length > 0) {
        const badgeRow = document.createElement('div');
        badgeRow.className = 'badge-row';
        data.corrections.forEach(c => {
            const badge = document.createElement('span');
            badge.className = `correction-badge ${c.severity.toLowerCase()}`;
            badge.textContent = c.severity;
            badgeRow.appendChild(badge);
        });
        detailsPanel.appendChild(badgeRow);
    }

    // Rapor (varsa)
    if (data.report) {
        const reportBox = document.createElement('pre');
        reportBox.className = 'report-text';
        reportBox.textContent = data.report;
        detailsPanel.appendChild(reportBox);
    }

    // Ham cevap (varsa, sadece details içinde)
    if (data.modified && data.raw && data.raw !== data.corrected) {
        const rawBox = document.createElement('div');
        rawBox.className = 'raw-box';
        rawBox.innerHTML = `<strong>🤖 LLM Ham Cevabı:</strong>`;
        const rawText = document.createElement('pre');
        rawText.className = 'raw-text';
        rawText.textContent = data.raw;
        rawBox.appendChild(rawText);
        detailsPanel.appendChild(rawBox);
    }

    msg.appendChild(detailsPanel);
    chatContainer.appendChild(msg);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function toggleDetails(msgEl, data) {
    const panel = msgEl.querySelector('[data-role="details"]');
    if (!panel) return;
    
    const isHidden = panel.classList.contains('hidden');
    if (isHidden) {
        panel.classList.remove('hidden');
        // Buton text güncelle
        const btn = msgEl.querySelector('.fix-toggle');
        if (btn) btn.textContent = '🔧 Detayları gizle';
    } else {
        panel.classList.add('hidden');
        const btn = msgEl.querySelector('.fix-toggle');
        if (btn) btn.textContent = `🔧 ${data.corrections.length} düzeltme`;
    }
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
