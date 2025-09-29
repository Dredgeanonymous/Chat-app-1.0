// static/chat.js — compatible with current server & chat.html

(function () {
  const socket   = io();
  const form     = document.getElementById("sendForm");
  const msgInput = document.getElementById("msgInput");
  const list     = document.getElementById("messages");
  const usersBox = document.getElementById("users");
  const ROLE     = (window.ROLE || "user").toLowerCase();

  if (!form || !msgInput || !list || !usersBox) {
    console.error("Missing required DOM nodes; check chat.html IDs.");
  }

  // -------- DM helpers --------
  let pmTo = null;

  function startPM(username){
    pmTo = username;
    msgInput.placeholder = `DM to ${username}…`;
    msgInput.focus();
  }

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

  // -------- Emoji (safe init) --------
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
      emojiBtn.addEventListener("click", () => {
        msgInput.value += " 🙂";
        msgInput.focus();
      });
      console.warn("EmojiButton library not found; using fallback.");
    }
  } catch (err) {
    console.error("Emoji init failed:", err);
  }

  // -------- UI helpers --------
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

  // Accepts either ["alice","bob"] or [{username,role,gender}, ...]
  function renderUsers(roster){
    usersBox.innerHTML = "";
    (roster || []).forEach(u=>{
      const isObj = typeof u === "object" && u !== null;
      const username = isObj ? (u.username || u.user || "Anon") : u;
      const role     = isObj ? (u.role || "user") : "user";
      const gender   = isObj ? u.gender : "";
      const li = document.createElement("li");
      li.dataset.user = username;
      li.innerHTML = `<strong>${username}</strong>
        ${role === "mod" ? '<span class="badge-mod">MOD</span>' : ""}
        ${gender ? `<span class="g">${genderIcon(gender)} ${gender}</span>` : ""}`;
      li.addEventListener("click", ()=> startPM(username)); // quick DM
      usersBox.appendChild(li);
    });
  }

  // Server sends {id, user, text, ts?}
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

  // -------- submit --------
  form && form.addEventListener("submit", (e) => {
    e.preventDefault();
    const txt = (msgInput.value || "").trim();
    if (!txt) return;

    const w = parseWhisper(txt);
    if (w) {
      socket.emit("pm", w); // "/w user msg"
    } else if (pmTo) {
      socket.emit("pm", { to: pmTo, text: txt }); // active DM
    } else {
      socket.emit("chat", { text: txt }); // public
      // removed socket.emit("send_message") — server doesn't handle it
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

  // -------- listeners --------
  socket.on("online", renderUsers);

  socket.on("chat_history", (arr) => {
    list.innerHTML = "";
    (arr || []).forEach(renderMessage);
  });

  socket.on("chat", renderMessage);
  // removed socket.on("message") — server doesn't emit it

  socket.on("pm", (m) => {
    const li = document.createElement("li");
    li.className = "msg pm";
    li.textContent = `(DM) ${m.from} → ${m.to}: ${m.text}`;
    list.appendChild(li);
    list.scrollTop = list.scrollHeight;
  });

  // NEW: keep UI in sync with moderator deletions
  socket.on("message_deleted", ({ id }) => {
    const li = document.querySelector(`li[data-id="${id}"]`);
    if (li) li.remove();
  });

  // Debug hooks
  socket.on("connect", () => console.log("Socket connected", socket.id));
  socket.on("connect_error", (e) => console.error("connect_error", e));
  socket.on("disconnect", (r) => console.warn("disconnected", r));
})();
