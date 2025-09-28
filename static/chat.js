// static/chat.js

// Force polling so it works on Render free tier (no websocket upgrade)
const socket = io({
  transports: ["polling"],
  upgrade: false,
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
  const li = el("li", { id: `m-${m.id}`, class: "message" });

  const header = el("div", { class: "row" },
    el("span", { class: "when" }, new Date(m.ts).toLocaleTimeString()),
    el("span", { class: "who"  }, `${m.username}${m.role === "mod" ? " (mod)" : ""}`)
  );

  const text = el("div", { class: "text" }, m.text);

  li.appendChild(header);
  li.appendChild(text);

  // show delete button only for moderators
  if (document.body.dataset.role === "mod") {
    const delBtn = el(
      "button",
      { class: "mini danger", onclick: () => deleteMsg(m.id), title: "Delete message" },
      "✖"
    );
    li.querySelector(".row").appendChild(delBtn);
  }

  messagesEl.appendChild(li);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function deleteMsg(id) {
  // server expects: event 'mod_action' with { action:'delete', message_id: id }
  socket.emit("mod_action", { action: "delete", message_id: id });
}

// ---- socket events from server ----

// initial backlog (server emits "history")
socket.on("history", (history) => {
  messagesEl.innerHTML = "";
  (history || []).forEach(renderMessage);
});

// new message
socket.on("new_message", (m) => renderMessage(m));

// message deleted
socket.on("message_deleted", ({ id }) => {
  const li = document.getElementById(`m-${id}`);
  if (li) li.remove();
});

// live user roster (support a few names just in case)
socket.on("online", renderUsers);
socket.on("online_users", renderUsers);
socket.on("roster", renderUsers);

// also fetch once on load (ok if 404; we ignore errors)
fetch("/api/online").then(r => r.ok ? r.json() : []).then(renderUsers).catch(() => {});

// ---- outgoing ----
sendForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = msgInput.value.trim();
  if (!text) return;
  socket.emit("send_message", { text });
  msgInput.value = "";
}
