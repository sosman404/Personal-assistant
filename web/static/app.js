'use strict';

// ── WebSocket ──────────────────────────────────────────────────────────────
const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
let ws = null;
let wsReady = false;

function connectWS() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => { wsReady = true; };
  ws.onclose = () => { wsReady = false; setTimeout(connectWS, 3000); };
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'response') handleAIResponse(data.message);
    if (data.type === 'reminder') showReminderPopup(data.title);
  };
}
connectWS();

// ── Panel navigation ───────────────────────────────────────────────────────
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const panel = btn.dataset.panel;
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById(`panel-${panel}`).classList.add('active');
    if (panel === 'events') loadEvents();
    if (panel === 'tasks') loadTasks();
    if (panel === 'reminders') loadReminders();
    if (panel === 'emails') loadEmails();
  });
});

// ── Status refresh ─────────────────────────────────────────────────────────
async function refreshStatus() {
  try {
    const r = await fetch('/api/status');
    const s = await r.json();
    document.getElementById('statEvents').textContent = s.upcoming_events ?? '—';
    document.getElementById('statTasks').textContent = s.active_tasks ?? '—';
    document.getElementById('statReminders').textContent = s.pending_reminders ?? '—';
    if (s.next_event) {
      const card = document.getElementById('nextEventCard');
      card.style.display = 'block';
      document.getElementById('nextEventTitle').textContent = s.next_event.title;
      document.getElementById('nextEventTime').textContent = fmtDateTime(s.next_event.start);
    }
  } catch (_) {}
}
refreshStatus();
setInterval(refreshStatus, 60000);

// ── Chat ───────────────────────────────────────────────────────────────────
const chatMessages = document.getElementById('chatMessages');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');

function fmtTime(d) {
  return new Date(d || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function addMessage(text, role) {
  const msg = document.createElement('div');
  msg.className = `message ${role}`;
  const initial = role === 'assistant' ? 'A' : 'U';
  msg.innerHTML = `
    <div class="message-avatar">${initial}</div>
    <div class="message-body">
      <div class="message-text">${escHtml(text)}</div>
      <div class="message-time">${fmtTime()}</div>
    </div>`;
  chatMessages.appendChild(msg);
  chatMessages.scrollTop = chatMessages.scrollHeight;
  return msg;
}

function addTypingIndicator() {
  const msg = document.createElement('div');
  msg.className = 'message assistant';
  msg.id = 'typing';
  msg.innerHTML = `
    <div class="message-avatar">A</div>
    <div class="message-body">
      <div class="typing-indicator"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div>
    </div>`;
  chatMessages.appendChild(msg);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTypingIndicator() {
  const el = document.getElementById('typing');
  if (el) el.remove();
}

function handleAIResponse(text) {
  removeTypingIndicator();
  addMessage(text, 'assistant');
  sendBtn.disabled = false;
  refreshStatus();
}

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text) return;
  chatInput.value = '';
  chatInput.style.height = 'auto';
  addMessage(text, 'user');
  sendBtn.disabled = true;
  addTypingIndicator();

  if (wsReady) {
    ws.send(JSON.stringify({ type: 'chat', message: text }));
  } else {
    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      const d = await r.json();
      handleAIResponse(d.response);
    } catch (err) {
      removeTypingIndicator();
      addMessage('Connection error. Please try again.', 'assistant');
      sendBtn.disabled = false;
    }
  }
}

sendBtn.addEventListener('click', sendMessage);
chatInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
chatInput.addEventListener('input', () => {
  chatInput.style.height = 'auto';
  chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + 'px';
});

document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => { chatInput.value = chip.dataset.msg; sendMessage(); });
});

document.getElementById('clearHistory').addEventListener('click', async () => {
  await fetch('/api/chat/clear', { method: 'POST' });
  chatMessages.innerHTML = '';
  addMessage("Conversation cleared. How can I help you?", 'assistant');
});

// ── Voice input (browser Web Speech API) ──────────────────────────────────
const voiceBtn = document.getElementById('voiceBtn');
let recognition = null;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SR();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  recognition.onresult = (e) => {
    const transcript = e.results[0][0].transcript;
    chatInput.value = transcript;
    voiceBtn.classList.remove('listening');
    sendMessage();
  };
  recognition.onend = () => voiceBtn.classList.remove('listening');
  recognition.onerror = () => voiceBtn.classList.remove('listening');

  voiceBtn.addEventListener('click', () => {
    if (voiceBtn.classList.contains('listening')) {
      recognition.stop();
      voiceBtn.classList.remove('listening');
    } else {
      recognition.start();
      voiceBtn.classList.add('listening');
    }
  });
} else {
  voiceBtn.title = 'Voice input not supported in this browser';
  voiceBtn.style.opacity = '0.4';
}

// ── Events panel ───────────────────────────────────────────────────────────
async function loadEvents() {
  const list = document.getElementById('eventsList');
  list.innerHTML = '<div class="loading">Loading events…</div>';
  try {
    const r = await fetch('/api/events?days=30');
    const events = await r.json();
    if (!events.length) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📅</div><div class="empty-state-text">No upcoming events</div></div>';
      return;
    }
    list.innerHTML = '';
    events.forEach(ev => {
      const d = new Date(ev.start);
      const card = document.createElement('div');
      card.className = 'event-card';
      card.innerHTML = `
        <div class="event-date-block">
          <div class="event-day">${d.getDate()}</div>
          <div class="event-month">${d.toLocaleString('default',{month:'short'})}</div>
        </div>
        <div class="card-content">
          <div class="card-title">${escHtml(ev.title)}</div>
          <div class="card-meta">
            ${fmtDateTime(ev.start)}${ev.end ? ' – ' + fmtTime(ev.end) : ''}
            ${ev.location ? ' · ' + escHtml(ev.location) : ''}
          </div>
          ${ev.source !== 'local' ? `<span class="badge badge-source">${ev.source}</span>` : ''}
        </div>
        <div class="card-actions">
          ${typeof ev.id === 'number' ? `<button class="icon-btn" title="Delete" onclick="deleteEvent(${ev.id})">🗑</button>` : ''}
        </div>`;
      list.appendChild(card);
    });
  } catch (e) {
    list.innerHTML = `<div class="loading">Failed to load events: ${e.message}</div>`;
  }
}

async function deleteEvent(id) {
  if (!confirm('Delete this event?')) return;
  await fetch(`/api/events/${id}`, { method: 'DELETE' });
  loadEvents(); refreshStatus();
}

document.getElementById('addEventBtn').addEventListener('click', () => {
  document.getElementById('addEventModal').style.display = 'flex';
});

document.getElementById('addEventForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  if (!body.end_time) delete body.end_time;
  await fetch('/api/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  closeModal('addEventModal');
  e.target.reset();
  loadEvents(); refreshStatus();
  showToast('Event created!');
});

// ── Tasks panel ────────────────────────────────────────────────────────────
let currentTaskStatus = '';

document.querySelectorAll('.filter-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    currentTaskStatus = chip.dataset.status;
    loadTasks();
  });
});

async function loadTasks() {
  const list = document.getElementById('tasksList');
  list.innerHTML = '<div class="loading">Loading tasks…</div>';
  try {
    const url = currentTaskStatus ? `/api/tasks?status=${currentTaskStatus}` : '/api/tasks';
    const r = await fetch(url);
    const tasks = await r.json();
    if (!tasks.length) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">✅</div><div class="empty-state-text">No tasks</div></div>';
      return;
    }
    list.innerHTML = '';
    tasks.forEach(t => {
      const card = document.createElement('div');
      card.className = 'task-card';
      const done = t.status === 'completed';
      card.innerHTML = `
        <button class="task-check" title="Mark complete" onclick="completeTask(${t.id})" ${done ? 'disabled style="opacity:0.4"' : ''}>
          ${done ? '✓' : ''}
        </button>
        <div class="card-content">
          <div class="card-title" style="${done ? 'text-decoration:line-through;opacity:0.5' : ''}">${escHtml(t.title)}</div>
          <div class="card-meta">
            <span class="badge badge-${t.priority}">${t.priority}</span>
            ${t.due_date ? ' · Due ' + fmtDate(t.due_date) : ''}
            ${t.category ? ' · ' + escHtml(t.category) : ''}
          </div>
        </div>
        <div class="card-actions">
          <button class="icon-btn" title="Delete" onclick="deleteTask(${t.id})">🗑</button>
        </div>`;
      list.appendChild(card);
    });
  } catch (e) {
    list.innerHTML = `<div class="loading">Failed to load tasks</div>`;
  }
}

async function completeTask(id) {
  await fetch(`/api/tasks/${id}/complete`, { method: 'PATCH' });
  loadTasks(); refreshStatus(); showToast('Task completed! ✓');
}
async function deleteTask(id) {
  if (!confirm('Delete this task?')) return;
  await fetch(`/api/tasks/${id}`, { method: 'DELETE' });
  loadTasks(); refreshStatus();
}

document.getElementById('addTaskBtn').addEventListener('click', () => {
  document.getElementById('addTaskModal').style.display = 'flex';
});

document.getElementById('addTaskForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  if (!body.due_date) delete body.due_date;
  if (!body.category) delete body.category;
  await fetch('/api/tasks', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  closeModal('addTaskModal');
  e.target.reset();
  loadTasks(); refreshStatus(); showToast('Task created!');
});

// ── Reminders panel ────────────────────────────────────────────────────────
async function loadReminders() {
  const list = document.getElementById('remindersList');
  list.innerHTML = '<div class="loading">Loading reminders…</div>';
  try {
    const r = await fetch('/api/reminders');
    const reminders = await r.json();
    if (!reminders.length) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔔</div><div class="empty-state-text">No reminders set</div></div>';
      return;
    }
    list.innerHTML = '';
    reminders.forEach(rem => {
      const card = document.createElement('div');
      card.className = 'reminder-card';
      card.innerHTML = `
        <div class="card-content">
          <div class="card-title">${escHtml(rem.title)}</div>
          <div class="card-meta">
            <span class="badge badge-${rem.type}">${rem.type}</span>
            · ${fmtDateTime(rem.trigger_time)}
            ${rem.repeat && rem.repeat !== 'none' ? ' · repeats ' + rem.repeat : ''}
          </div>
          ${rem.description ? `<div class="card-meta" style="margin-top:4px">${escHtml(rem.description)}</div>` : ''}
        </div>
        <div class="card-actions">
          <button class="icon-btn" title="Cancel" onclick="cancelReminder(${rem.id})">🗑</button>
        </div>`;
      list.appendChild(card);
    });
  } catch (e) {
    list.innerHTML = '<div class="loading">Failed to load reminders</div>';
  }
}

async function cancelReminder(id) {
  if (!confirm('Cancel this reminder?')) return;
  await fetch(`/api/reminders/${id}`, { method: 'DELETE' });
  loadReminders(); refreshStatus();
}

document.getElementById('addReminderBtn').addEventListener('click', () => {
  document.getElementById('addReminderModal').style.display = 'flex';
});

document.getElementById('addReminderForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = Object.fromEntries(fd.entries());
  await fetch('/api/reminders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  closeModal('addReminderModal');
  e.target.reset();
  loadReminders(); refreshStatus(); showToast('Reminder set! 🔔');
});

// ── Emails panel ───────────────────────────────────────────────────────────
async function loadEmails() {
  const list = document.getElementById('emailsList');
  list.innerHTML = '<div class="loading">Loading emails…</div>';
  try {
    const r = await fetch('/api/emails');
    const emails = await r.json();
    if (!emails.length) {
      list.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📧</div><div class="empty-state-text">No emails or Outlook not configured</div></div>';
      return;
    }
    list.innerHTML = '';
    emails.forEach(em => {
      const card = document.createElement('div');
      card.className = `email-card ${!em.is_read ? 'email-unread' : ''}`;
      card.innerHTML = `
        ${!em.is_read ? '<div class="email-dot"></div>' : '<div style="width:8px"></div>'}
        <div class="card-content">
          <div class="card-title">${escHtml(em.subject)}</div>
          <div class="card-meta">${escHtml(em.sender)} · ${fmtDateTime(em.received)}</div>
          ${em.preview ? `<div class="card-meta" style="margin-top:4px;-webkit-line-clamp:2;overflow:hidden;display:-webkit-box;-webkit-box-orient:vertical">${escHtml(em.preview)}</div>` : ''}
        </div>`;
      list.appendChild(card);
    });
  } catch (e) {
    list.innerHTML = '<div class="loading">Failed to load emails</div>';
  }
}

document.getElementById('composeBtn').addEventListener('click', () => {
  document.getElementById('composeModal').style.display = 'flex';
});

document.getElementById('composeForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const raw = Object.fromEntries(fd.entries());
  const body = {
    to: raw.to.split(',').map(s => s.trim()).filter(Boolean),
    cc: raw.cc ? raw.cc.split(',').map(s => s.trim()).filter(Boolean) : [],
    subject: raw.subject,
    body: raw.body,
  };
  const r = await fetch('/api/emails/send', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  const result = await r.json();
  closeModal('composeModal');
  e.target.reset();
  showToast(result.success ? 'Email sent! ✉' : `Failed: ${result.error || 'unknown error'}`);
});

// ── Helpers ────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
}

function fmtDateTime(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function closeModal(id) {
  document.getElementById(id).style.display = 'none';
}

function showToast(msg, duration = 3000) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, duration);
}

function showReminderPopup(title) {
  document.getElementById('reminderPopupText').textContent = title;
  document.getElementById('reminderPopup').style.display = 'flex';
  // Browser notification
  if (Notification.permission === 'granted') {
    new Notification('ARIA Reminder', { body: title, icon: '/static/icon.png' });
  }
}

// Request notification permission on load
if (Notification.permission === 'default') {
  Notification.requestPermission();
}

// Close modals on backdrop click
document.querySelectorAll('.modal').forEach(m => {
  m.addEventListener('click', (e) => { if (e.target === m) m.style.display = 'none'; });
});
