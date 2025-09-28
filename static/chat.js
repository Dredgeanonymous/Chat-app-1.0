// static/chat.js

const socket = io({
  transports: ["websocket"],
  upgrade: false,
});

// ---- DOM refs (match your chat.html) ----
const form     = document.getElementById("sendForm");   // form id="sendForm"
const msgInput = document.getElementById("msgInput");  // input id="msgInput"
const list     = document.getElementById("messages");  // ul id="messages"
const usersBox = document.getElementById("users");     // ul id="users"

// ---- helpers ----
function renderMessage(m) {
  const li = document.createElement("li");
  li.dataset.id = m.id;

  const who = m.username || "Anon";
  li.textContent = `${who}: ${m.text}`;

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

function removeMessageById(id) {
  const li = list.querySelector(`li[data-id="${id}"]`);
  if (li) li.remove();
}

// ---- incoming events ----
socket.on("chat_history", (history) => {
  list.innerHTML = "";
  (history || []).forEach(renderMessage);
});

socket.on("new_message", (m) => {
  renderMessage(m);
});

socket.on("message_deleted", ({ id }) => {
  removeMessageById(id);
});

socket.on("online", (roster) => {
  usersBox.innerHTML = "";
  (roster || []).forEach((user) => {
    const li = document.createElement("li");
    li.textContent = user.role === "mod" ? `${user.username} (mod)` : user.username;
    usersBox.appendChild(li);
  });
});

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
