function formatTS(ts) {
  let d = new Date(ts);
  if (isNaN(d)) return "";
  return d.toLocaleString("en-US", {
   // pick one US timezone
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hour12: true
  });
}
// static/chat.js  — robust socket + roster + mod delete + gender icons

(function () {
  // ---------- Connection (stable) ----------
  const socket = io({
    transports: ["websocket", "polling"],
    upgrade: true
  });

  // Role detection (works whether window.ROLE or body dataset is set first)
  const BODY_ROLE = (document.body && document.body.dataset && document.body.dataset.role) || "";
  const ROLE = (String(window.ROLE || BODY_ROLE || "user")).toLowerCase(); // "mod" shows delete buttons

  const form     = document.getElementById("sendForm");
  const msgInput = document.getElementById("msgInput");
  const list     = document.getElementById("messages");
  const usersBox = document.getElementById("users");

  socket.on("connect", () => {
    console.log("SOCKET CONNECTED", socket.id);
    // Ask the server for the roster every (re)connect — prevents empty list after hiccups
    socket.emit("roster_request");
  });
  socket.on("reconnect", () => {
    console.log("SOCKET RECONNECTED");
    socket.emit("roster_request");
  });
  socket.on("connect_error", (e) => console.error("connect_error", e));
  socket.on("error", (e) => console.error("socket_error", e));
  socket.on("disconnect", (r) => console.warn("disconnected", r));

  // ---------- DM helpers ----------
  let pmTo = null;
  function startPM(username){
    pmTo = username;
    if (msgInput) {
      msgInput.placeholder = `DM to ${username}…`;
      msgInput.focus();
    }
  }
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

  // ---------- Emoji (optional) ----------
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
    }
  } catch (err) {
    console.error("Emoji init failed:", err);
  }

  // ---------- Icons/Badges ----------
  function genderIcon(g){
    switch((g || "").toLowerCase()){
      case "male":      return '<i class="fa-solid fa-mars" title="Male"></i>';
      case "female":    return '<i class="fa-solid fa-venus" title="Female"></i>';
      case "nonbinary": return '<i class="fa-solid fa-genderless" title="Non-binary"></i>';
      case "trans":     return '<i class="fa-solid fa-transgender" title="Trans"></i>';
      case "other":     return '<i class="fa-regular fa-circle-question" title="Other"></i>';
      default:          return "";
    }
  }
  function modBadge(role) {
    return (String(role).toLowerCase() === "mod")
      ? '<span class="badge-mod" title="Moderator">MOD</span>'
      : "";
  }

  // ---------- Message renderer ----------
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

  // ---------- Submit ----------
  form && form.addEventListener("submit", (e) => {
    e.preventDefault();
    const txt = (msgInput.value || "").trim();
    if (!txt) return;

    const w = parseWhisper(txt);
    if (w) {
      socket.emit("pm", w);
    } else if (pmTo) {
      socket.emit("pm", { to: pmTo, text: txt });
    } else {
      socket.emit("chat", { text: txt });
    }

    msgInput.value = "";
    msgInput.placeholder = pmTo ? `DM to ${pmTo}…` : "Type a message";
  });

  // ---------- Delete (mods) ----------
  list?.addEventListener("click", (e) => {
    const btn = e.target.closest(".msg-del");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (id) socket.emit("delete_message", { id });
  });

  // ---------- ONLINE roster (objects with role+gender) ----------
  socket.on("online", (roster) => {
    const usersEl = usersBox;
    if (!usersEl) return;

    if (!Array.isArray(roster)) {
      // If something odd came back, don't wipe the current UI; try again soon.
      setTimeout(() => socket.emit("roster_request"), 800);
      return;
    }

    usersEl.innerHTML = "";
    (roster || []).forEach((u) => {
      const isObj   = u && typeof u === "object";
      const name    = isObj ? (u.username || u.user || "Anon") : (u || "Anon");
      const role    = isObj ? (u.role || "user") : "user";
      const gender  = isObj ? (u.gender || "") : "";

      if (!name) return;

      const li = document.createElement("li");
      li.innerHTML = `
        <span class="user-name"><i class="fa-solid fa-circle-user"></i> ${name}</span>
        ${modBadge(role)}
        ${gender ? `<span class="g">${genderIcon(gender)} <small>${gender}</small></span>` : ""}
      `;
      li.addEventListener("click", () => startPM(name));
      usersEl.appendChild(li);
    });

    if (!roster.length) {
      const li = document.createElement("li");
      li.textContent = "No one online yet";
      usersEl.appendChild(li);
    }
  });

  // ---------- History & live messages ----------
  socket.on("chat_history", (arr) => {
    list.innerHTML = "";
    (arr || []).forEach(renderMessage);
  });
  socket.on("chat", renderMessage);

  // ---------- PMs ----------
  socket.on("pm", (m) => {
    const li = document.createElement("li");
    li.className = "msg pm";
    li.textContent = `(DM) ${m.from} → ${m.to}: ${m.text}`;
    list.appendChild(li);
    list.scrollTop = list.scrollHeight;
  });

  // ---------- Keep UI in sync with deletes ----------
  socket.on("message_deleted", ({ id }) => {
    const li = document.querySelector(`li[data-id="${id}"]`);
    if (li) li.remove();
  });
})();
