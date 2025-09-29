// Ensure the CDN for Socket.IO is loaded before this file.
// EmojiButton (optional) is loaded by chat.html before this file.

(function () {
  const socket = io({
    // If you want to force polling on some hosts:
    // transports: ["websocket", "polling"],
    // upgrade: true
  });

  const messagesEl = document.getElementById("messages");
  const usersEl = document.getElementById("users");
  const formEl = document.getElementById("sendForm");
  const inputEl = document.getElementById("msgInput");

  const ROLE = (window.ROLE || "user").toLowerCase();

  function el(html) {
    const tmp = document.createElement("template");
    tmp.innerHTML = html.trim();
    return tmp.content.firstElementChild;
  }

  function addMessage(msg) {
    // msg = {id, user, text, ts}
    const safeText = String(msg.text || "");
    const li = el(`
      <li class="msg" data-id="${msg.id}">
        <div class="msg-row">
          <span class="msg-user"><i class="fa-solid fa-user"></i> ${msg.user}</span>
          <span class="msg-time">${msg.ts || ""}</span>
          ${ROLE === "mod"
            ? `<button class="msg-del" title="Delete" data-id="${msg.id}" style="margin-left:8px;">
                 <i class="fa-solid fa-trash"></i>
               </button>`
            : ""}
        </div>
        <div class="msg-text">${safeText}</div>
      </li>
    `);
    messagesEl.appendChild(li);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // Submit handler
  formEl?.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const txt = (inputEl.value || "").trim();
    if (!txt) return;
    socket.emit("chat", { text: txt });
    inputEl.value = "";
  });

  // Click handler for delete (mods only)
  messagesEl?.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".msg-del");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (!id) return;
    socket.emit("delete_message", { id });
  });

  // Online list
  socket.on("online", (list) => {
    usersEl.innerHTML = "";
    (list || []).forEach((u) => {
      usersEl.appendChild(el(`<li><i class="fa-solid fa-circle-user"></i> ${u}</li>`));
    });
  });

  // History and live chat
  socket.on("chat_history", (msgs) => {
    messagesEl.innerHTML = "";
    (msgs || []).forEach(addMessage);
  });

  socket.on("chat", (msg) => {
    addMessage(msg);
  });

  // Private messages (optional UI - you can build inputs for this)
  socket.on("pm", (payload) => {
    // For now, show PM inline with a prefix
    addMessage({
      id: `pm_${Date.now()}`,
      user: `${payload.from} ➜ ${payload.to} (PM)`,
      text: payload.text,
      ts: payload.ts
    });
  });

  // NEW: react to deletions
  socket.on("message_deleted", ({ id }) => {
    const li = document.querySelector(`li[data-id="${id}"]`);
    if (li) li.remove();
  });

  // Optional: Emoji picker hookup (requires a trigger/button in your HTML if desired)
  // Example minimal wiring (if you add a button with id="emojiBtn"):
  const emojiBtn = document.getElementById("emojiBtn");
  if (window.EmojiButton && emojiBtn) {
    const picker = new EmojiButton();
    picker.on("emoji", emoji => {
      inputEl.value += emoji;
      inputEl.focus();
    });
    emojiBtn.addEventListener("click", () => picker.togglePicker(emojiBtn));
  }
})();
