// ============================================================================
// IIStudio — Глобальный JS
// ============================================================================

"use strict";

// ── API утилиты ──────────────────────────────────────────────────────────────

const API = {
  async get(path) {
    const r = await fetch('/api' + path);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch('/api' + path, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  },
};

// ── Загрузка статуса прокси ──────────────────────────────────────────────────

async function loadProxyStatus() {
  const el = document.getElementById('proxyStatus');
  if (!el) return;
  try {
    const data = await API.get('/proxy');
    const alive = data.alive;
    const total = data.total;
    const current = data.proxies?.find(p => p.alive);
    if (current) {
      el.innerHTML = `<span style="color:var(--green)">✅ ${current.host}</span><br><small>${current.type} | ${current.latency_ms ? current.latency_ms.toFixed(0) + 'мс' : '—'}</small>`;
    } else {
      el.textContent = `Нет живых прокси (${alive}/${total})`;
    }
  } catch(e) {
    el.textContent = 'Ошибка загрузки';
  }
}

// ── Markdown рендер (простой) ────────────────────────────────────────────────

function renderMarkdown(text) {
  // Блоки кода
  text = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang}">${escHtml(code.trim())}</code></pre>`
  );
  // Инлайн-код
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Жирный
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  // Курсив
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // Заголовки
  text = text.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  text = text.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  text = text.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  // Цитаты
  text = text.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>');
  // Списки
  text = text.replace(/^- (.+)$/gm, '<li>$1</li>');
  text = text.replace(/(<li>.*<\/li>\n?)+/g, s => `<ul>${s}</ul>`);
  // Параграфы
  text = text.replace(/\n\n/g, '</p><p>');
  text = `<p>${text}</p>`;
  // Убрать пустые параграфы
  text = text.replace(/<p><\/p>/g, '');
  return text;
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Init ─────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadProxyStatus();
  // Обновлять статус прокси каждые 60 сек
  setInterval(loadProxyStatus, 60000);
});
