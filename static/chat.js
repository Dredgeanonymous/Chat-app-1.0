// Prefer WebSocket on paid Render, fall back to polling if needed
const socket = io({
  transports: ["websocket", "polling"],
  upgrade: true,
});

// ---- DOM refs ----
const usersEl    = document.getElementById("users");
const messagesEl = document.getElementById("messages");
const sendForm   = document.getElementById("sendForm");
const msgInput   = document.getElementById("msgInput");

// ---- tiny helper ----
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

// ---- renderers ----
function renderUsers(list) {
  usersEl.innerHTML = "";
  if (!list || !list.length) {
    usersEl.appendChild(el("li", { class: "muted" }, "Nobody online yet"));
    return;
  }
  list.forEach(u => {
    usersEl.appendChild(
      el("li", { class: "user" },
        el("span", { class: "name" }, u.username),
        u.role === "mod" ? el("span", { class: "badge small" }, "MOD") : ""
      )
    );
  });
}

function renderMessage(m) {
  const row = el("li", { id: `m-${m.id}`, class: "message" },
    el("div", { class: "msg-head" },
      el("span", { class: "who" }, `${m.username}${m.role === "mod" ? " (mod)" : ""}`),
      el("span", { class: "when" }, new Date(m.ts).toLocaleTimeString())
    ),
    el("div", { class: "msg-text" }, m.text)
  );

  // add delete button if logged-in role is mod
  if (window.ROLE === "mod") {
    const delBtn = el("button", { class: "mini danger", onclick: () => {
      socket.emit("delete_message", { id: m.id });
    }}, "✖");
    row.querySelector(".msg-head").appendChild(delBtn);
  }

  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ---- socket events ----
socket.on("chat_history", (history) => {
  messagesEl.innerHTML = "";
  (history || []).forEach(renderMessage);
});

socket.on("new_message", (m) => renderMessage(m));

socket.on("message_deleted", ({ id }) => {
  const li = document.getElementById(`m-${id}`);
  if (li) li.remove();
});

socket.on("online", renderUsers);
socket.on("online_users", renderUsers);
socket.on("roster", renderUsers);

// fetch once on load in case any socket event is missed
fetch("/api/online").then(r => r.ok ? r.json() : []).then(renderUsers).catch(() => {});

// ---- outgoing ----
sendForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = msgInput.value.trim();
  if (!text) return;
  socket.emit("send_message", { text });
  msgInput.value = "";
});

// debug logs (optional)
socket.on("connect_error", (e) => console.log("connect_error:", e.message));
socket.on("reconnect_error", (e) => console.log("reconnect_error:", e.message));
