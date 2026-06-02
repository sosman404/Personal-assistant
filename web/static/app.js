'use strict';

// ── WebSocket ─────────────────────────────────────────────────
const WS = `${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`;
let ws=null, wsOk=false;
function connectWS(){
  ws=new WebSocket(WS);
  ws.onopen=()=>{wsOk=true;};
  ws.onclose=()=>{wsOk=false;setTimeout(connectWS,3000);};
  ws.onmessage=e=>{
    const d=JSON.parse(e.data);
    if(d.type==='response') handleReply(d.message);
    if(d.type==='reminder') fireAlert(d.title);
  };
}
connectWS();

// ── Status clock ──────────────────────────────────────────────
function tickClock(){
  const t=new Date();
  document.getElementById('statusTime').textContent=
    t.getHours().toString().padStart(2,'0')+':'+t.getMinutes().toString().padStart(2,'0');
}
tickClock(); setInterval(tickClock,30000);

// ── Greeting date ─────────────────────────────────────────────
document.getElementById('greetingDate').textContent=
  new Date().toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'});

// ── Tab navigation ─────────────────────────────────────────────
const TABS=['home','chat','calendar','tasks','more'];
function switchTab(tab){
  TABS.forEach(t=>{
    document.getElementById(`screen-${t}`).classList.toggle('active',t===tab);
    document.querySelector(`.nav-item[data-tab="${t}"]`).classList.toggle('active',t===tab);
  });
  if(tab==='calendar') loadEvents();
  if(tab==='tasks')    loadTasks();
  if(tab==='more')     loadMore();
  if(tab==='home')     loadHome();
}
document.querySelectorAll('.nav-item').forEach(b=>{
  b.addEventListener('click',()=>switchTab(b.dataset.tab));
});
window.switchTab=switchTab;

// ── Status refresh (home widgets) ────────────────────────────
async function loadHome(){
  try{
    const[evRes,tkRes,rmRes]=await Promise.all([
      fetch('/api/events?days=3'),fetch('/api/tasks'),fetch('/api/reminders')
    ]);
    const events=await evRes.json();
    const tasks =await tkRes.json();
    const rems  =await rmRes.json();

    // reminder count
    document.getElementById('reminderNum').textContent=rems.length;
    document.getElementById('taskBadge').textContent=tasks.length;

    // schedule preview (next 2 events)
    const sp=document.getElementById('schedulePreview');
    if(events.length===0){
      sp.innerHTML='<div class="sched-empty">No upcoming events</div>';
    } else {
      sp.innerHTML=events.slice(0,2).map(e=>`
        <div class="sched-item">
          <div class="sched-time">${fmtTime(e.start)}</div>
          <div class="sched-title">${esc(e.title)}</div>
        </div>`).join('');
    }

    // tasks preview (top 3)
    const tp=document.getElementById('tasksHomePreview');
    if(tasks.length===0){
      tp.innerHTML='<div class="preview-empty">All caught up! 🎉</div>';
    } else {
      tp.innerHTML=tasks.slice(0,3).map(t=>`
        <div class="task-row">
          <div class="task-check-circle"></div>
          <div class="task-row-title">${esc(t.title)}</div>
          <span class="task-row-pri pri-${t.priority}">${t.priority}</span>
        </div>`).join('');
    }
  } catch(_){}
}
loadHome();
setInterval(loadHome, 60000);

// ── CHAT ──────────────────────────────────────────────────────
const msgs=document.getElementById('chatMessages');
const inp =document.getElementById('chatInput');
const send=document.getElementById('sendBtn');

function scrollBottom(){ msgs.scrollTop=msgs.scrollHeight; }

function appendMsg(text,role){
  const row=document.createElement('div');
  row.className=`msg-row ${role==='user'?'user':'ai'}`;
  if(role==='user'){
    row.innerHTML=`
      <div class="msg-group">
        <div class="bubble user">${esc(text)}</div>
        <div class="msg-ts">${fmtTimestamp()}</div>
      </div>`;
  } else {
    row.innerHTML=`
      <div class="msg-av">A</div>
      <div class="msg-group">
        <div class="bubble ai">${esc(text)}</div>
        <div class="msg-ts">${fmtTimestamp()}</div>
      </div>`;
  }
  msgs.appendChild(row);
  scrollBottom();
}

function showTyping(){
  const el=document.createElement('div');
  el.className='msg-row ai'; el.id='typing';
  el.innerHTML=`<div class="msg-av">A</div><div class="msg-group"><div class="typing-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>`;
  msgs.appendChild(el); scrollBottom();
}
function hideTyping(){ document.getElementById('typing')?.remove(); }

function handleReply(text){
  hideTyping();
  appendMsg(text,'ai');
  send.disabled=false;
  loadHome();
}

async function sendMessage(){
  const text=inp.value.trim(); if(!text) return;
  inp.value=''; inp.style.height='auto';
  appendMsg(text,'user');
  send.disabled=true;
  showTyping();
  if(wsOk){
    ws.send(JSON.stringify({type:'chat',message:text}));
  } else {
    try{
      const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
      const d=await r.json();
      handleReply(d.response);
    } catch(e){
      hideTyping();
      appendMsg('Connection error. Please retry.','ai');
      send.disabled=false;
    }
  }
}

send.addEventListener('click',sendMessage);
inp.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();}});
inp.addEventListener('input',()=>{ inp.style.height='auto'; inp.style.height=Math.min(inp.scrollHeight,110)+'px'; });

document.querySelectorAll('.chip').forEach(c=>{
  c.addEventListener('click',()=>{ inp.value=c.dataset.msg; sendMessage(); });
});
document.getElementById('clearChatBtn').addEventListener('click',async()=>{
  await fetch('/api/chat/clear',{method:'POST'});
  msgs.innerHTML='<div class="chat-date-sep">Today</div>';
  appendMsg('Conversation cleared. How can I help you? 👋','ai');
});

// ── VOICE (Web Speech API) ────────────────────────────────────
const voiceBtn    = document.getElementById('voiceBtn');
const homeVoiceBtn= document.getElementById('homeVoiceBtn');
const navMicBtn   = document.getElementById('navMicBtn');
const orbWrap     = document.getElementById('orbWrap');
const orbLabel    = document.getElementById('orbLabel');
const homeTranscript = document.getElementById('homeTranscript');
const homeVoiceResponse = document.getElementById('homeVoiceResponse');
const homeVoiceText = document.getElementById('homeVoiceText');

let recog=null, homeRecog=null;

// Shared: send a voice command from home and show response on home
async function sendVoiceCommand(text){
  homeTranscript.textContent = `"${text}"`;
  homeVoiceResponse.style.display='none';
  orbLabel.textContent='Thinking…';
  try{
    const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text})});
    const d=await r.json();
    homeVoiceText.textContent=d.response;
    homeVoiceResponse.style.display='flex';
    orbLabel.textContent='Tap & speak to ARIA';
    // Also speak the response aloud
    if('speechSynthesis' in window){
      const utt=new SpeechSynthesisUtterance(d.response);
      utt.rate=1; utt.pitch=1;
      window.speechSynthesis.speak(utt);
    }
    loadHome();
  }catch(_){
    orbLabel.textContent='Tap & speak to ARIA';
  }
}

function startHomeListening(){
  if(!homeRecog) return;
  orbWrap.classList.add('listening');
  homeVoiceBtn.classList.add('listening');
  navMicBtn.classList.add('listening');
  orbLabel.textContent='Listening…';
  homeTranscript.textContent='';
  homeRecog.start();
}
function stopHomeListening(){
  orbWrap.classList.remove('listening');
  homeVoiceBtn.classList.remove('listening');
  navMicBtn.classList.remove('listening');
  orbLabel.textContent='Tap & speak to ARIA';
  try{ homeRecog.stop(); }catch(_){}
}

if('webkitSpeechRecognition' in window||'SpeechRecognition' in window){
  const SR=window.SpeechRecognition||window.webkitSpeechRecognition;

  // Home / nav mic recognition
  homeRecog=new SR();
  homeRecog.lang='en-US';homeRecog.continuous=false;homeRecog.interimResults=true;
  homeRecog.onresult=e=>{
    const isFinal=e.results[e.results.length-1].isFinal;
    const txt=e.results[e.results.length-1][0].transcript;
    homeTranscript.textContent=`"${txt}"`;
    if(isFinal){ stopHomeListening(); sendVoiceCommand(txt); }
  };
  homeRecog.onend=()=>stopHomeListening();
  homeRecog.onerror=()=>stopHomeListening();

  // Home orb button
  homeVoiceBtn.addEventListener('click',()=>{
    if(orbWrap.classList.contains('listening')) stopHomeListening();
    else startHomeListening();
  });

  // Nav mic FAB (works from any screen)
  navMicBtn.addEventListener('click',()=>{
    switchTab('home');
    setTimeout(()=>{
      if(orbWrap.classList.contains('listening')) stopHomeListening();
      else startHomeListening();
    },100);
  });

  // Chat screen mic (sends to chat)
  recog=new SR(); recog.lang='en-US'; recog.continuous=false; recog.interimResults=false;
  recog.onresult=e=>{ inp.value=e.results[0][0].transcript; voiceBtn.classList.remove('listening'); sendMessage(); };
  recog.onend=()=>voiceBtn.classList.remove('listening');
  recog.onerror=()=>voiceBtn.classList.remove('listening');
  voiceBtn.addEventListener('click',()=>{
    if(voiceBtn.classList.contains('listening')){ recog.stop(); voiceBtn.classList.remove('listening'); }
    else { recog.start(); voiceBtn.classList.add('listening'); }
  });
} else { voiceBtn.style.opacity='.3'; voiceBtn.title='Voice not supported'; }

// ── EVENTS ────────────────────────────────────────────────────
async function loadEvents(){
  const el=document.getElementById('eventsList');
  el.innerHTML='<div class="list-placeholder">Loading events…</div>';
  try{
    const r=await fetch('/api/events?days=30');
    const events=await r.json();
    if(!events.length){
      el.innerHTML=`<div class="empty-block"><div class="empty-ico">📅</div><div class="empty-txt">No upcoming events.<br>Add one or ask ARIA to schedule for you.</div></div>`;
      return;
    }
    // Group by day
    const grouped={};
    events.forEach(e=>{
      const d=new Date(e.start);
      const key=d.toDateString();
      if(!grouped[key]) grouped[key]=[];
      grouped[key].push(e);
    });
    el.innerHTML='';
    Object.entries(grouped).forEach(([day,evs])=>{
      const lbl=document.createElement('div');
      lbl.className='list-section-label';
      const d=new Date(day);
      lbl.textContent=d.toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long'});
      el.appendChild(lbl);
      evs.forEach(e=>{
        const d2=new Date(e.start);
        const item=document.createElement('div');
        item.className='ev-item';
        item.innerHTML=`
          <div class="ev-date-block">
            <div class="ev-day">${d2.getDate()}</div>
            <div class="ev-mon">${d2.toLocaleString('default',{month:'short'})}</div>
          </div>
          <div class="ev-info">
            <div class="ev-title">${esc(e.title)}</div>
            <div class="ev-meta">${fmtTime(e.start)}${e.end?' – '+fmtTime(e.end):''}${e.location?' · '+esc(e.location):''}</div>
          </div>
          ${typeof e.id==='number'?`<button class="ev-del" onclick="delEvent(${e.id},event)">🗑</button>`:''}`;
        el.appendChild(item);
      });
    });
  }catch(err){el.innerHTML=`<div class="list-placeholder">Failed to load: ${err.message}</div>`;}
}
window.delEvent=async(id,e)=>{
  e.stopPropagation();
  if(!confirm('Delete this event?')) return;
  await fetch(`/api/events/${id}`,{method:'DELETE'});
  loadEvents(); loadHome(); toast('Event deleted');
};

document.getElementById('addEventBtn').addEventListener('click',()=>openSheet('sheetEvent'));
document.getElementById('formEvent').addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target), b=Object.fromEntries(fd.entries());
  if(!b.end_time) delete b.end_time;
  if(!b.location) delete b.location;
  await fetch('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
  closeSheet('sheetEvent'); e.target.reset();
  loadEvents(); loadHome(); toast('Event created! 📅');
});

// ── TASKS ─────────────────────────────────────────────────────
let taskStatus='';
document.querySelectorAll('.fpill').forEach(p=>{
  p.addEventListener('click',()=>{
    document.querySelectorAll('.fpill').forEach(x=>x.classList.remove('active'));
    p.classList.add('active');
    taskStatus=p.dataset.status;
    loadTasks();
  });
});
async function loadTasks(){
  const el=document.getElementById('tasksList');
  el.innerHTML='<div class="list-placeholder">Loading…</div>';
  try{
    const url=taskStatus?`/api/tasks?status=${taskStatus}`:'/api/tasks';
    const tasks=await(await fetch(url)).json();
    if(!tasks.length){
      el.innerHTML=`<div class="empty-block"><div class="empty-ico">✅</div><div class="empty-txt">No tasks here.</div></div>`;
      return;
    }
    el.innerHTML='';
    tasks.forEach(t=>{
      const done=t.status==='completed';
      const item=document.createElement('div');
      item.className='task-item';
      item.innerHTML=`
        <button class="task-cb ${done?'done':''}" onclick="doneTask(${t.id})" ${done?'disabled':''}>✓</button>
        <div class="task-info">
          <div class="task-title ${done?'done-text':''}">${esc(t.title)}</div>
          <div class="task-meta">
            <span class="pri-badge pri-${t.priority}">${t.priority}</span>
            ${t.due_date?' · Due '+fmtDate(t.due_date):''}${t.category?' · '+esc(t.category):''}
          </div>
        </div>
        <button class="task-del" onclick="delTask(${t.id},event)">🗑</button>`;
      el.appendChild(item);
    });
  }catch(_){el.innerHTML='<div class="list-placeholder">Failed to load tasks</div>';}
}
window.doneTask=async id=>{
  await fetch(`/api/tasks/${id}/complete`,{method:'PATCH'});
  loadTasks(); loadHome(); toast('Task done! ✓');
};
window.delTask=async(id,e)=>{
  e.stopPropagation();
  if(!confirm('Delete this task?')) return;
  await fetch(`/api/tasks/${id}`,{method:'DELETE'});
  loadTasks(); loadHome(); toast('Task deleted');
};
document.getElementById('addTaskBtn').addEventListener('click',()=>openSheet('sheetTask'));
document.getElementById('formTask').addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target), b=Object.fromEntries(fd.entries());
  if(!b.due_date) delete b.due_date;
  if(!b.category) delete b.category;
  await fetch('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
  closeSheet('sheetTask'); e.target.reset();
  loadTasks(); loadHome(); toast('Task created! ✅');
});

// ── MORE (reminders + emails) ─────────────────────────────────
async function loadMore(){
  loadReminders(); loadEmails();
}
async function loadReminders(){
  const el=document.getElementById('remindersList');
  try{
    const rems=await(await fetch('/api/reminders')).json();
    if(!rems.length){
      el.innerHTML=`<div class="empty-block"><div class="empty-ico">🔔</div><div class="empty-txt">No reminders set.</div></div>`;
      return;
    }
    el.innerHTML='';
    rems.forEach(r=>{
      const item=document.createElement('div');
      item.className='rem-item';
      item.innerHTML=`
        <div class="rem-icon-box ${r.type}">${r.type==='alarm'?'⏰':'🔔'}</div>
        <div class="rem-info">
          <div class="rem-title">${esc(r.title)}</div>
          <div class="rem-time">${fmtDateTime(r.trigger_time)}${r.repeat&&r.repeat!=='none'?' · repeats '+r.repeat:''}</div>
        </div>
        <button class="rem-del" onclick="delReminder(${r.id},event)">🗑</button>`;
      el.appendChild(item);
    });
  }catch(_){el.innerHTML='<div class="list-placeholder">Failed to load</div>';}
}
async function loadEmails(){
  const el=document.getElementById('emailsList');
  try{
    const emails=await(await fetch('/api/emails')).json();
    if(!emails.length){
      el.innerHTML=`<div class="empty-block"><div class="empty-ico">📧</div><div class="empty-txt">No emails, or Outlook not configured.</div></div>`;
      return;
    }
    el.innerHTML='';
    emails.forEach(em=>{
      const item=document.createElement('div');
      item.className='email-item';
      item.innerHTML=`
        ${!em.is_read?'<div class="email-unread-dot"></div>':'<div style="width:8px"></div>'}
        <div class="email-info">
          <div class="email-subject">${esc(em.subject)}</div>
          <div class="email-from">${esc(em.sender)}</div>
          ${em.preview?`<div class="email-preview">${esc(em.preview)}</div>`:''}
        </div>
        <div class="email-time">${fmtTime(em.received)}</div>`;
      el.appendChild(item);
    });
  }catch(_){el.innerHTML='<div class="list-placeholder">Failed to load</div>';}
}
window.delReminder=async(id,e)=>{
  e.stopPropagation();
  if(!confirm('Cancel this reminder?')) return;
  await fetch(`/api/reminders/${id}`,{method:'DELETE'});
  loadReminders(); loadHome(); toast('Reminder cancelled');
};
document.getElementById('addReminderBtn').addEventListener('click',()=>openSheet('sheetReminder'));
document.getElementById('formReminder').addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target), b=Object.fromEntries(fd.entries());
  await fetch('/api/reminders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
  closeSheet('sheetReminder'); e.target.reset();
  loadReminders(); loadHome(); toast('Reminder set! 🔔');
});
document.getElementById('composeBtn').addEventListener('click',()=>openSheet('sheetEmail'));
document.getElementById('formEmail').addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target), raw=Object.fromEntries(fd.entries());
  const b={
    to:raw.to.split(',').map(s=>s.trim()).filter(Boolean),
    cc:raw.cc?raw.cc.split(',').map(s=>s.trim()).filter(Boolean):[],
    subject:raw.subject,body:raw.body,
  };
  const r=await fetch('/api/emails/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
  const res=await r.json();
  closeSheet('sheetEmail'); e.target.reset();
  toast(res.success?'Email sent! ✉':'Failed: '+(res.error||'unknown'));
});

// ── Sheet helpers ─────────────────────────────────────────────
const overlay=document.getElementById('sheetOverlay');
function openSheet(id){
  document.getElementById(id).classList.add('open');
  overlay.classList.add('open');
}
function closeSheet(id){
  document.getElementById(id).classList.remove('open');
  overlay.classList.remove('open');
}
overlay.addEventListener('click',()=>{
  document.querySelectorAll('.sheet.open').forEach(s=>s.classList.remove('open'));
  overlay.classList.remove('open');
});

// ── Toast ─────────────────────────────────────────────────────
function toast(msg,ms=2800){
  const el=document.getElementById('toast');
  el.textContent=msg; el.classList.add('show');
  setTimeout(()=>el.classList.remove('show'),ms);
}

// ── Reminder alert ─────────────────────────────────────────────
function fireAlert(title){
  document.getElementById('alertText').textContent=title;
  document.getElementById('alertPill').style.display='flex';
  setTimeout(()=>document.getElementById('alertPill').style.display='none',8000);
  if(Notification.permission==='granted') new Notification('ARIA Reminder',{body:title});
}

// ── Notification permission ────────────────────────────────────
if(Notification.permission==='default') Notification.requestPermission();

// ── Util ──────────────────────────────────────────────────────
function esc(s){
  if(!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function fmtTime(iso){
  if(!iso) return '';
  return new Date(iso).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
}
function fmtDate(iso){
  if(!iso) return '';
  return new Date(iso).toLocaleDateString([],{month:'short',day:'numeric'});
}
function fmtDateTime(iso){
  if(!iso) return '';
  return new Date(iso).toLocaleString([],{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
}
function fmtTimestamp(){
  return new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'});
}
