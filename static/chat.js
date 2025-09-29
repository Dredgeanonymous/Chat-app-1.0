// static/chat.js

(function () {
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
  const ROLE     = (window.ROLE || "user").toLowerCase();

  if (!form || !msgInput || !list || !usersBox) {
    console.error("Missing required DOM nodes; check chat.html IDs.");
  }

  // -------------------- DM helpers --------------------
  let pmTo = null;

  function startPM(username){
    pmTo = username;
    if (msgInput) {
      msgInput.placeholder = `DM to ${username}…`;
      msgInput.focus();
    }
  }

  // Parse "/w username message"
  function parseWhisper(s){
    const m = s.match(/^\/w\s+(\S+)\s+([\s\S]+)/i);
    return m ? { to: m[1], text: m[2] } : null;
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape"){
      pmTo = null;
      if (msgInput) msgInput.placeholder = "Type a message";
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

  // Message renderer that accepts either {user,...} or {username,...}
  function renderMessage(m){
    const id   = m.id;
    const who  = m.user || m.username || "Anon";
    const text = m.text || "";
    const ts   = m.ts || "";

    const li = document.createElement("li");
    li.dataset.id = id;
    li.innerHTML = `
      <div class="msg-row">
        <strong>${who}</strong>
        <span class="msg-time">${ts}</span>
        ${ROLE === "mod" ? `
          <button class="mini danger msg-del" title="Delete" data-id="${id}">✖</button>
        ` : ""}
      </div>
      <div class="msg-text">${text}</div>
    `;

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
    // 3) Public message
    } else {
      socket.emit("chat", { text: txt });
      // removed: socket.emit("send_message") — server doesn't handle it
    }

    msgInput.value = "";
    msgInput.placeholder = pmTo ? `DM to ${pmTo}…` : "Type a message";
  });

  // Click-to-delete (mods)
  list?.addEventListener("click", (e) => {
    const btn = e.target.closest(".msg-del");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (id) socket.emit("delete_message", { id });
  });

  // -------------------- listeners --------------------
  // ✅ Your flexible ONLINE handler (accepts strings or objects)
  socket.on("online", (roster) => {
    const usersEl = document.getElementById("users");
    if (!usersEl) return;
    usersEl.innerHTML = "";

    (roster || []).forEach((item) => {
      // Accept either "Alice" or {username:"Alice", ...}
      const name =
        typeof item === "string"
          ? item
          : (item && (item.username || item.user)) || "Anon";

      if (!name) return;

      const li = document.createElement("li");
      li.textContent = name;
      li.addEventListener("click", () => {
        const input = document.getElementById("msgInput");
        if (input) {
          input.placeholder = `DM to ${name}…`;
          input.focus();
        }
        pmTo = name;
      });
      usersEl.appendChild(li);
    });
  });

  // History + live chat
  socket.on("chat_history", (arr) => {
    list.innerHTML = "";
    (arr || []).forEach(renderMessage);
  });
  socket.on("chat", renderMessage);

  // Private messages
  socket.on("pm", (m) => {
    const li = document.createElement("li");
    li.className = "msg pm";
    li.textContent = `(DM) ${m.from} → ${m.to}: ${m.text}`;
    list.appendChild(li);
    list.scrollTop = list.scrollHeight;
  });

  // Keep UI in sync with moderator deletions
  socket.on("message_deleted", ({ id }) => {
    const li = document.querySelector(`li[data-id="${id}"]`);
    if (li) li.remove();
  });
})();
