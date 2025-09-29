const socket = io();
socket.on("connect", () => console.log("Socket connected", socket.id));
socket.on("connect_error", (e) => console.error("connect_error", e));
socket.on("disconnect", (r) => console.warn("disconnected", r));

// ---- DOM refs (match your chat.html) ----
const form     = document.getElementById("sendForm");   // form id="sendForm"
const msgInput = document.getElementById("msgInput");  // input id="msgInput"
const list     = document.getElementById("messages");  // ul id="messages"
const usersBox = document.getElementById("users");     // ul id="users"

let pmTo = null;

function startPM(username){
  pmTo = username;
  msgInput.placeholder = `DM to ${username}…`;
  msgInput.focus();
}

// parse "/w user msg"
function parseWhisper(s){
  const m = s.match(/^\/w\s+(\S+)\s+([\s\S]+)/i);
  return m ? {to:m[1], text:m[2]} : null;
}

form.addEventListener('submit', (e)=>{
  e.preventDefault();
  let txt = msgInput.value.trim();
  if(!txt) return;

  // whisper by command
  const w = parseWhisper(txt);
  if (w){
    socket.emit('pm', w);
  } else if (pmTo){
    socket.emit('pm', {to: pmTo, text: txt});
  } else {
    socket.emit('chat', {text: txt});
  }
  msgInput.value = '';
  msgInput.placeholder = pmTo ? `DM to ${pmTo}…` : 'Type a message';
});

// render PMs differently
socket.on('pm', m=>{
  const li = document.createElement('li');
  li.className = 'msg pm';
  li.textContent = `(DM) ${m.from} → ${m.to}: ${m.text}`;
  list.appendChild(li);
  list.scrollTop = list.scrollHeight;
});

// clear DM target with Escape
document.addEventListener('keydown', e=>{
  if (e.key === 'Escape'){
    pmTo = null;
    msgInput.placeholder = 'Type a message';
  }
});
function genderIcon(g){
  switch(g){
    case 'male': return '<i class="fa-solid fa-mars"></i>';
    case 'female': return '<i class="fa-solid fa-venus"></i>';
    case 'nonbinary': return '<i class="fa-solid fa-genderless"></i>';
    case 'trans': return '<i class="fa-solid fa-transgender"></i>';
    case 'other': return '<i class="fa-regular fa-circle-question"></i>';
    default: return '';
  }
}

function renderUsers(roster){
  usersBox.innerHTML = '';
  roster.forEach(u=>{
    const li = document.createElement('li');
    li.dataset.user = u.username;
    li.innerHTML = `<strong>${u.username}</strong>
      ${u.role === 'mod' ? '<span class="badge-mod">MOD</span>' : ''}
      <span class="g">${genderIcon(u.gender)} ${u.gender || ''}</span>`;
    // click to prepare PM
    li.addEventListener('click', ()=> startPM(u.username));
    usersBox.appendChild(li);
  });
}
// Emoji picker (optional)
let picker;
const emojiBtn = document.createElement('button');
emojiBtn.type = 'button';
emojiBtn.className = 'emoji-btn';
emojiBtn.title = 'Insert emoji';
emojiBtn.innerHTML = '😊';
document.getElementById('sendForm').prepend(emojiBtn);

emojiBtn.addEventListener('click', () => {
  if (!picker) {
    picker = new EmojiButton({ position: 'top-start', autoHide: true });
    picker.on('emoji', emoji => {
      msgInput.value += emoji;
      msgInput.focus();
    });
  }
  picker.togglePicker(emojiBtn);
});
// ---- helpers ----

function renderMessage(m) {
  const li = document.createElement("li");
  li.dataset.id = m.id;

  // Gender icon
  const g = m.gender ? `<span class="g">${genderIcon(m.gender)}</span>` : '';
  const who = m.username || "Anon";

  // Base content
  li.innerHTML = `<strong>${who}</strong> ${g}: ${m.text}`;

  // Add delete button if moderator
  if (window.ROLE === "mod") {
    const del = document.createElement("button");
    del.textContent = "✖";
    del.title = "Delete";
    del.className = "mini danger";
    del.addEventListener("click", () => {
      socket.emit("delete_message", { id: m.id });
    });

    li.appendChild(document.createTextNode(" "));
    li.appendChild(del);
  }

  list.appendChild(li);
    }

// ---- form submission ----
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = (msgInput.value || "").trim();
  if (!text) return;

  socket.emit("send_message", { text });
  msgInput.value = "";
  msgInput.focus();
});

// Debug
socket.on("connect", () => console.log("connected:", socket.id));
socket.on("disconnect", () => console.log("disconnected"));
