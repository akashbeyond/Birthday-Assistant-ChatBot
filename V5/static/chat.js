const chat = document.getElementById('chat');
const form = document.getElementById('chat-form');
const question = document.getElementById('question');
const trace = document.getElementById('trace');

function addMessage(text, role) {
  const row = document.createElement('div');
  row.className = `message ${role}`;
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop = chat.scrollHeight;
}

async function ask(text) {
  text = text.trim();
  if (!text) return;
  addMessage(text, 'user');
  question.value = '';
  question.disabled = true;
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: text})
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    addMessage(data.answer || 'No answer returned.', 'bot');
    speakAnswer(data.answer);
    trace.textContent = JSON.stringify({nlu_source: data.nlu_source, latency_ms: data.latency_ms, reply_source: data.reply_source, escalated: data.escalated, parsed: data.parsed, carried_from_context: data.carried_from_context, state: data.state}, null, 2) + '\n\nstatus: ' + (data.status || '');
  } catch (error) {
    addMessage(`Error: ${error.message}`, 'bot');
  } finally {
    question.disabled = false;
    question.focus();
  }
}

form.addEventListener('submit', e => {
  e.preventDefault();
  ask(question.value);
});

document.querySelectorAll('.chip[data-q]').forEach(button => {
  button.addEventListener('click', () => ask(button.dataset.q));
});

addMessage('Hello! I am Version 5. Type, or press Speak. Answers are always shown as text. Ask me about birthdays.', 'bot');

document.getElementById('reset').addEventListener('click', async () => {
  await fetch('/api/reset', {method: 'POST'});
  chat.innerHTML = '';
  trace.textContent = 'Conversation reset.';
  addMessage('Context cleared. Ask a new question.', 'bot');
});

// ---------- V5: voice channel (backend unchanged) ----------
const voiceStatus = document.getElementById('voice-status');
const speakBtn = document.getElementById('speak');
const speakBack = document.getElementById('speakBack');
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;

function speakAnswer(text) {
  if (!text || !speakBack.checked || !('speechSynthesis' in window)) return;
  const spoken = text.replace(/[•]/g, '').replace(/\n+/g, '. ');   // bullets read badly aloud
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(spoken);
  u.lang = 'en-IN';
  speechSynthesis.speak(u);
}

speakBtn.addEventListener('click', () => {
  if (!SR) { addMessage('Speech recognition is not supported in this browser. Use Chrome or Edge.', 'bot'); return; }
  speechSynthesis.cancel();
  const rec = new SR();
  rec.lang = 'en-IN';
  rec.interimResults = false;
  rec.maxAlternatives = 1;
  rec.onstart = () => { voiceStatus.textContent = '🎤 Listening…'; speakBtn.disabled = true; };
  rec.onresult = e => {
    const transcript = e.results[0][0].transcript;
    voiceStatus.textContent = `Heard: "${transcript}"`;   // check the transcript before blaming the NLU
    ask(transcript);
  };
  rec.onerror = e => { voiceStatus.textContent = `Voice error: ${e.error}`; };
  rec.onend = () => { speakBtn.disabled = false; if (voiceStatus.textContent.startsWith('🎤')) voiceStatus.textContent = 'No speech detected.'; };
  rec.start();
});
