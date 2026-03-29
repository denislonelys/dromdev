// ============================================================================
// IIStudio — Chat JS
// ============================================================================

"use strict";

let currentMode = 'text';
let currentModel = null;

// ── Инициализация ─────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', async () => {
  await loadModels(currentMode);
  updateHint();

  // Параметры из URL
  const params = new URLSearchParams(location.search);
  if (params.get('mode')) setMode(params.get('mode'));
  if (params.get('model')) {
    currentModel = params.get('model');
    document.getElementById('modelSelect').value = currentModel;
    updateHint();
  }
});

// ── Режим ─────────────────────────────────────────────────────────────────────

async function setMode(mode) {
  currentMode = mode;
  currentModel = null;

  // Обновить табы
  document.querySelectorAll('.mode-tab').forEach(t => {
    t.classList.toggle('active', t.dataset.mode === mode);
  });

  // Обновить выбор модели
  await loadModels(mode);
  updateHint();

  // Уведомить сервер
  try {
    await fetch('/api/chat/mode?mode=' + mode, { method: 'POST' });
  } catch(e) {}
}

async function setModel(modelId) {
  currentModel = modelId || null;
  updateHint();
  if (currentModel) {
    try {
      await fetch('/api/chat/model?model_id=' + encodeURIComponent(currentModel), { method: 'POST' });
    } catch(e) {}
  }
}

async function loadModels(mode) {
  const sel = document.getElementById('modelSelect');
  if (!sel) return;
  try {
    const data = await API.get('/models?mode=' + mode);
    sel.innerHTML = '<option value="">— по умолчанию —</option>';
    for (const m of data.models || []) {
      const opt = document.createElement('option');
      opt.value = m.id;
      opt.textContent = m.name + (m.is_default ? ' ★' : '');
      sel.appendChild(opt);
    }
  } catch(e) {
    console.error('Не удалось загрузить модели:', e);
  }
}

function updateHint() {
  const modeEl = document.getElementById('hintMode');
  const modelEl = document.getElementById('hintModel');
  if (modeEl) modeEl.textContent = currentMode;
  if (modelEl) modelEl.textContent = currentModel || 'по умолчанию';
}

// ── Отправка ──────────────────────────────────────────────────────────────────

function handleInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 200) + 'px';
}

async function sendMessage() {
  const input = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message) return;

  const useCache = document.getElementById('useCache')?.checked ?? true;
  const useStream = document.getElementById('useStream')?.checked ?? false;

  input.value = '';
  input.style.height = 'auto';

  appendMessage('user', message);
  removeWelcome();
  setLoading(true);

  try {
    if (useStream) {
      await sendStream(message, useCache);
    } else {
      await sendRegular(message, useCache);
    }
  } catch(e) {
    appendMessage('assistant', `**Ошибка:** ${e.message}`, 'Ошибка');
  } finally {
    setLoading(false);
  }
}

async function sendRegular(message, useCache) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      mode: currentMode,
      model_id: currentModel || null,
      use_cache: useCache,
      stream: false,
    }),
  });
  const data = await res.json();

  if (data.success) {
    const lat = data.latency_ms ? ` ${data.latency_ms.toFixed(0)}мс` : '';
    const cached = data.cached ? ' [кэш]' : '';
    appendMessage('assistant', data.response, (data.model || 'AI') + lat + cached);
  } else {
    appendMessage('assistant', `**Ошибка:** ${data.error || 'Неизвестная ошибка'}`, 'Ошибка');
  }
}

async function sendStream(message, useCache) {
  const params = new URLSearchParams({ message, mode: currentMode });
  if (currentModel) params.set('model_id', currentModel);

  const bubble = appendMessage('assistant', '', currentModel || 'AI', true);
  const textEl = bubble.querySelector('.message-text');
  textEl.classList.add('stream-cursor');

  const es = new EventSource('/api/chat/stream?' + params.toString());
  let fullText = '';

  await new Promise((resolve, reject) => {
    es.onmessage = (e) => {
      if (e.data === '[DONE]') {
        es.close();
        textEl.classList.remove('stream-cursor');
        resolve();
        return;
      }
      if (e.data.startsWith('[ERROR]')) {
        es.close();
        reject(new Error(e.data.replace('[ERROR] ', '')));
        return;
      }
      fullText += e.data.replace(/\\n/g, '\n');
      textEl.innerHTML = renderMarkdown(fullText);
      scrollToBottom();
    };
    es.onerror = () => { es.close(); resolve(); };
  });
}

async function sendQuickPrompt(text) {
  document.getElementById('chatInput').value = text;
  await sendMessage();
}

async function compareModels() {
  const input = document.getElementById('chatInput');
  const message = input.value.trim();
  if (!message) {
    alert('Введи сообщение для сравнения моделей');
    return;
  }
  input.value = '';
  removeWelcome();
  setLoading(true);

  try {
    const res = await fetch('/api/chat/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, mode: currentMode }),
    });
    const data = await res.json();
    appendCompare(message, data.results);
  } catch(e) {
    appendMessage('assistant', `**Ошибка:** ${e.message}`, 'Compare');
  } finally {
    setLoading(false);
  }
}

// ── DOM хелперы ───────────────────────────────────────────────────────────────

function appendMessage(role, text, meta = '', isStream = false) {
  const container = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = `message message-${role}`;

  const bubble = document.createElement('div');
  bubble.className = 'message-bubble';

  const textEl = document.createElement('div');
  textEl.className = 'message-text';
  textEl.innerHTML = text ? renderMarkdown(text) : '';
  bubble.appendChild(textEl);

  if (meta) {
    const metaEl = document.createElement('div');
    metaEl.className = 'message-meta';
    metaEl.textContent = meta;
    div.appendChild(bubble);
    div.appendChild(metaEl);
  } else {
    div.appendChild(bubble);
  }

  container.appendChild(div);
  scrollToBottom();
  return bubble;
}

function appendCompare(message, results) {
  const container = document.getElementById('chatMessages');

  // Вопрос пользователя
  appendMessage('user', message);

  // Карточки ответов
  const wrap = document.createElement('div');
  wrap.className = 'message message-assistant';
  wrap.style.width = '100%';

  const grid = document.createElement('div');
  grid.className = 'compare-grid';

  for (const [modelId, res] of Object.entries(results)) {
    const card = document.createElement('div');
    card.className = 'compare-card';
    const header = document.createElement('div');
    header.className = 'compare-card-header';
    header.textContent = res.model_name || modelId;
    const body = document.createElement('div');
    body.className = 'message-text';
    body.style.fontSize = '0.82rem';
    body.innerHTML = res.response ? renderMarkdown(res.response) : `<em style="color:var(--text3)">${res.error || 'Нет ответа'}</em>`;
    card.appendChild(header);
    card.appendChild(body);
    grid.appendChild(card);
  }

  wrap.appendChild(grid);
  container.appendChild(wrap);
  scrollToBottom();
}

function removeWelcome() {
  const w = document.querySelector('.welcome-message');
  if (w) w.remove();
}

function scrollToBottom() {
  const el = document.getElementById('chatMessages');
  if (el) el.scrollTop = el.scrollHeight;
}

async function clearHistory() {
  if (!confirm('Очистить историю диалога?')) return;
  try {
    await fetch('/api/chat/history', { method: 'DELETE' });
    document.getElementById('chatMessages').innerHTML = '';
    // Добавить welcome обратно
    const welcome = document.createElement('div');
    welcome.className = 'welcome-message';
    welcome.innerHTML = `
      <div class="welcome-icon">◈</div>
      <h2>IIStudio AI Orchestrator</h2>
      <p>История очищена. Введи новый запрос.</p>
    `;
    document.getElementById('chatMessages').appendChild(welcome);
  } catch(e) {
    console.error(e);
  }
}

function setLoading(loading) {
  const btn = document.getElementById('sendBtn');
  const txt = document.getElementById('sendBtnText');
  const ldr = document.getElementById('sendBtnLoader');
  if (!btn) return;
  btn.disabled = loading;
  txt?.classList.toggle('hidden', loading);
  ldr?.classList.toggle('hidden', !loading);
}
