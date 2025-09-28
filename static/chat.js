// Connect using polling so it works with the eventlet setup on Android
const socket = io({
  transports: ["polling"],
  upgrade: false,
});

// DOM refs
const usersEl = document.getElementById("users");
const messagesEl = document.getElementById("messages");
const sendForm = document.getElementById("sendForm");
const msgInput = document.getElementById("msgInput");

// ---- helpers ----
function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => {
    if (k === "class") e.className = v;
    else if (k === "dataset") Object.assign(e.dataset, v);
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  });
  children.flat().forEach(c => e.appendChild(typeof c === "string" ? document.createTextNode(c) : c));
  return e;
}

function renderUsers(list) {
  usersEl.innerHTML = "";
  list.forEach(u => {
    const isMod = u.role === "mod";
    usersEl.appendChild(
      el("li", { class: "user" },
        el("span", { class: "name" }, u.username),
        isMod ? el("span", { class: "badge small" }, "MOD") : ""
      )
    );
  });
}

function renderMessage(m) {
  // <li> [time] user: text [X] (X only visible to mods)
  const li = el("li", { id: `m-${m.id}`, class: "message" });

  const header = el("div", { class: "row" },
    el("span", { class: "meta" }, new Date(m.ts).toLocaleTimeString()),
    el("span", { class: "user" }, m.username),
  );

  const text = el("div", { class: "text" }, m.text);

  li.appendChild(header);
  li.appendChild(text);

  if (window.ROLE === "mod") {
    const del = el(
      "button",
      { class: "mini danger", onclick: () => deleteMsg(m.id), title: "Delete message" },
      "✖"
    );
    li.appendChild(del);
  }

  messagesEl.appendChild(li);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function deleteMsg(id) {
  // moderator-only endpoint
  socket.emit("delete_message", { id });
}

// ---- events from server ----

// on first join the server may send the backlog
socket.on("chat_history", (history) => {
  messagesEl.innerHTML = "";
  history.forEach(renderMessage);
});

// when any new message arrives
socket.on("new_message", (m) => {
  renderMessage(m);
});

// when a message was deleted by a mod
socket.on("message_deleted", ({ id }) => {
  const li = document.getElementById(`m-${id}`);
  if (li) li.remove();
});

// live user list
socket.on("user_list", (users) => {
  renderUsers(users);
});

// ---- outgoing ----

// send message
sendForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = msgInput.value.trim();
  if (!text) return;
  socket.emit("send_message", { text });
  msgInput.value = "";
});
