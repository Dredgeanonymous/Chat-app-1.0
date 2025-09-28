// Prefer WebSocket (paid Render supports it), fall back to polling if needed
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

  // show delete button for mods
  if (document.body.dataset.role === "mod") {
    const delBtn = el("button", { class: "mini danger", onclick: () => {
      socket.emit("mod_action", { action: "delete", message_id: m.id });
    }}, "✖");
    row.querySelector(".msg-head").appendChild(delBtn);
  }

  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// ---- socket events from server ----
socket.on("history", (history) => {
  messagesEl.innerHTML = "";
  (history || []).forEach(renderMessage);
});
socket.on("new_message", (m) => renderMessage(m));
socket.on("message_deleted", ({ id }) => {
  const li = document.getElementById(`m-${id}`);
  if (li) li.remove();
});

// support several event names for roster
socket.on("online", renderUsers);
socket.on("online_users", renderUsers);
socket.on("roster", renderUsers);

// also fetch once on load (covers missed early event)
fetch("/api/online").then(r => r.ok ? r.json() : []).then(renderUsers).catch(() => {});

// optional: quick diagnostic logs
socket.on("connect_error", (e) => console.log("connect_error:", e && e.message));
socket.on("reconnect_error", (e) => console.log("reconnect_error:", e && e.message));

// ---- outgoing ----
sendForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = msgInput.value.trim();
  if (!text) return;
  socket.emit("send_message", { text });
  msgInput.value = "";
});  socket.emit("send_message", { text });
  msgInput.value = "";
}
