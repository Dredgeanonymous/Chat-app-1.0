// static/chat.js

// -------------------- socket --------------------
const socket = io();
socket.on("connect", () => console.log("Socket connected", socket.id));
socket.on("connect_error", (e) => console.error("connect_error", e));
socket.on("disconnect", (r) => console.warn("disconnected", r));

// -------------------- DOM --------------------
const form     = document.getElementById("sendForm");
const msgInput = document.getElementById("msgInput");
const list     = document.getElementById("messages");
const usersBox = document.getElementById("users");

// If any critical node is missing, stop cleanly (no crashes)
if (!form || !msgInput || !list || !usersBox) {
  console.error("Missing required DOM nodes; check chat.html IDs.");
}

// -------------------- DM helpers --------------------
let pmTo = null;

function startPM(username){
  pmTo = username;
  msgInput.placeholder = `DM to ${username}…`;
  msgInput.focus();
}

// Parse "/w username message"
function parseWhisper(s){
  const m = s.match(/^\/w\s+(\S+)\s+([\s\S]+)/i);
  return m ? { to: m[1], text: m[2] } : null;
}

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape"){
    pmTo = null;
    msgInput.placeholder = "Type a message";
  }
});

// -------------------- Emoji (safe init) --------------------
try {
  const emojiBtn = document.createElement("button");
  emojiBtn.type = "button";
  emojiBtn.className = "emoji-btn";
  emojiBtn.title = "Insert emoji";
  emojiBtn.textContent = "😊";
  form && form.prepend(emojiBtn);

  if (window.EmojiButton) {
    const picker = new EmojiButton({ position: "top-start", autoHide: true });
    emojiBtn.addEventListener("click", () => picker.togglePicker(emojiBtn));
    picker.on("emoji", (emoji) => {
      msgInput.value += emoji;
      msgInput.focus();
    });
  } else {
    // graceful fallback
    emojiBtn.addEventListener("click", () => {
      msgInput.value += " 🙂";
      msgInput.focus();
    });
    console.warn("EmojiButton library not found; using fallback.");
  }
} catch (err) {
  console.error("Emoji init failed:", err);
}

// -------------------- UI helpers --------------------
function genderIcon(g){
  switch(g){
    case "male":      return '<i class="fa-solid fa-mars"></i>';
    case "female":    return '<i class="fa-solid fa-venus"></i>';
    case "nonbinary": return '<i class="fa-solid fa-genderless"></i>';
    case "trans":     return '<i class="fa-solid fa-transgender"></i>';
    case "other":     return '<i class="fa-regular fa-circle-question"></i>';
    default:          return "";
  }
}

function renderUsers(roster){
  usersBox.innerHTML = "";
  (roster || []).forEach(u=>{
    const li = document.createElement("li");
    li.dataset.user = u.username;
    li.innerHTML = `<strong>${u.username}</strong>
      ${u.role === "mod" ? '<span class="badge-mod">MOD</span>' : ""}
      <span class="g">${genderIcon(u.gender)} ${u.gender || ""}</span>`;
    li.addEventListener("click", ()=> startPM(u.username)); // quick DM
    usersBox.appendChild(li);
  });
}

function renderMessage(m){
  const li = document.createElement("li");
  li.dataset.id = m.id;
  const who = m.username || "Anon";
  const g   = m.gender ? `<span class="g">${genderIcon(m.gender)}</span>` : "";
  li.innerHTML = `<strong>${who}</strong> ${g}: ${m.text}`;

  // add delete button if moderator
  if (window.ROLE === "mod") {
    const del = document.createElement("button");
    del.textContent = "✖";
    del.title = "Delete";
    del.className = "mini danger";
    del.addEventListener("click", () => socket.emit("delete_message", { id: m.id }));
    li.appendChild(document.createTextNode(" "));
    li.appendChild(del);
  }

  list.appendChild(li);
  list.scrollTop = list.scrollHeight;
}

// -------------------- submit --------------------
form && form.addEventListener("submit", (e) => {
  e.preventDefault();
  const txt = (msgInput.value || "").trim();
  if (!txt) return;

  // 1) "/w user msg"
  const w = parseWhisper(txt);
  if (w) {
    socket.emit("pm", w);
  // 2) Active DM target
  } else if (pmTo) {
    socket.emit("pm", { to: pmTo, text: txt });
  // 3) Public message — emit BOTH names to cover server variants
  } else {
    socket.emit("chat", { text: txt });
    socket.emit("send_message", { text: txt });
  }

  msgInput.value = "";
  msgInput.placeholder = pmTo ? `DM to ${pmTo}…` : "Type a message";
});

// -------------------- listeners --------------------
// roster
socket.on("online", renderUsers);

// history
socket.on("chat_history", (arr) => {
  list.innerHTML = "";
  (arr || []).forEach(renderMessage);
});

// public message (support both)
socket.on("chat", renderMessage);
socket.on("message", renderMessage);

// private
socket.on("pm", (m) => {
  const li = document.createElement("li");
  li.className = "msg pm";
  li.textContent = `(DM) ${m.from} → ${m.to}: ${m.text}`;
  list.appendChild(li);
  list.scrollTop = list.scrollHeight;
});
