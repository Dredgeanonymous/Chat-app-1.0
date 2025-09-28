// static/chat.js

// ---- Socket connection ----
const socket = io({
  transports: ["websocket"],
  upgrade: false,
});

// ---- DOM refs (make sure these IDs exist in your HTML) ----
const form      = document.getElementById("chat-form");   // <form id="chat-form">
const msgInput  = document.getElementById("msg");         // <input id="msg">
const list      = document.getElementById("messages");    // <ul id="messages">
const onlineBox = document.getElementById("online");      // <ul id="online"> (optional)

// ---- helpers ----
function renderMessage(m) {
  // m is expected to look like: { id, text, username?, ts? }
  const li = document.createElement("li");
  li.dataset.id = m.id;

  const who = m.username || "Anon";
  li.textContent = `${who}: ${m.text}`;

  // delete button (if you allow it)
  const del = document.createElement("button");
  del.textContent = "✖";
  del.title = "Delete";
  del.className = "mini danger";
  del.addEventListener("click", () => {
    socket.emit("delete_message", { id: m.id });
  });

  li.appendChild(document.createTextNode(" "));
  li.appendChild(del);
  list.appendChild(li);
}

function removeMessageById(id) {
  const li = list.querySelector(`li[data-id="${id}"]`);
  if (li) li.remove();
}

// ---- incoming events from server ----

// Full history pushed on connect
socket.on("chat_history", (history) => {
  list.innerHTML = "";
  (history || []).forEach(renderMessage);
});

// New single message broadcast
socket.on("new_message", (m) => {
  renderMessage(m);
});

// Message deleted broadcast
socket.on("message_deleted", ({ id }) => {
  removeMessageById(id);
});

// Online roster (optional, your server emits "online")
socket.on("online", (roster) => {
  if (!onlineBox) return;
  onlineBox.innerHTML = "";
  (roster || []).forEach((name) => {
    const li = document.createElement("li");
    li.textContent = name;
    onlineBox.appendChild(li);
  });
});

// ---- submit handler (this is the part you asked about) ----
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = (msgInput.value || "").trim();
  if (!text) return;

  // Send to server; server will broadcast "new_message" to everyone
  socket.emit("send_message", { text });

  msgInput.value = "";
  msgInput.focus();
});

// (optional) debug
socket.on("connect", () => console.log("connected:", socket.id));
socket.on("disconnect", () => console.log("disconnected"));
