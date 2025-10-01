// static/chat.js — robust chat client for Flask-SocketIO
// Works with templates/chat.html that define:
//   #users, #messages, #sendForm, #msgInput, #backToChat
// Expects server events: 'chat_history', 'chat', 'pm', 'online',
// 'message_deleted', 'typing', and accepts 'chat', 'pm', 'delete_message'.

(function () {
  "use strict";

  // ---------------- Shortcuts ----------------
  const $  = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

  // Role (for mod-only actions)
  const ROLE = String(window.ROLE || document.body.dataset.role || "user").toLowerCase();

  // DOM
  const usersBox = $("#users");
  const list     = $("#messages");
  const form     = $("#sendForm");
  const msgInput = $("#msgInput");
  const backBtn  = $("#backToChat");

  // Socket
  const socket = io({ transports: ["websocket", "polling"], upgrade: true });

  // ---------------- Utilities ----------------
  function nowISO () { return new Date().toISOString(); }

  function formatTS(ts) {
    const d = new Date(ts || Date.now());
    if (isNaN(d)) return "";
    return d.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit"
    });
  }

  function linkify(text) {
    const re = /\b(https?:\/\/[^\s<]+)\b/gi;
    return (text || "").replace(re, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  }

  function atBottom(el, threshold = 60) {
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }
  function scrollToBottom(el) { el.scrollTop = el.scrollHeight; }

  // Avatars & accents
  function hashColor(name) {
    let h = 0;
    for (let i = 0; i < (name || "").length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    return `hsl(${h % 360} 70% 45%)`;
  }
  function avatarHTML(url, username) {
    const initial = (username || "?").charAt(0).toUpperCase();
    if (url) return `<img class="avatar" src="${url}" alt="${username || ""}" onerror="this.remove()">`;
    return `<span class="avatar avatar-fallback" style="background:${hashColor(username)}">${initial}</span>`;
  }
  function genderIcon(g) {
    switch ((g || "").toLowerCase()) {
      case "male":      return '<i class="fa-solid fa-mars" title="Male"></i>';
      case "female":    return '<i class="fa-solid fa-venus" title="Female"></i>';
      case "nonbinary": return '<i class="fa-solid fa-genderless" title="Non-binary"></i>';
      case "trans":     return '<i class="fa-solid fa-transgender" title="Trans"></i>';
      default:          return "";
    }
  }
  function modBadge(role) {
    return String(role).toLowerCase() === "mod"
      ? '<span class="badge-mod" title="Moderator">MOD</span>'
      : "";
  }

  // ---------------- Typing indicator ----------------
  const typingEl = document.createElement("div");
  typingEl.className = "typing";
  typingEl.setAttribute("aria-live", "polite");
  typingEl.style.display = "none";
  typingEl.innerHTML = `
    <span class="who"></span>
    <span class="dots" aria-hidden="true">
      <span class="dot"></span><span class="dot"></span><span class="dot"></span>
    </span>`;
  // attach under right panel or near form
  (document.querySelector(".panel:last-of-type") || form?.parentElement || document.body)
    .appendChild(typingEl);

  let othersTyping = new Set();
  let typingTimer = null;

  function renderTyping() {
    const who = typingEl.querySelector(".who");
    if (!who) return;
    if (othersTyping.size === 0) {
      typingEl.style.display = "none";
      return;
    }
    const names = Array.from(othersTyping);
    const label = names.length === 1
      ? `${names[0]} is typing`
      : `${names.slice(0,3).join(", ")}${names.length > 3 ? " and others" : ""} are typing`;
    who.textContent = label + " ";
    typingEl.style.display = "flex";
  }

  // When others type
  socket.on("typing", ({ user, typing }) => {
    if (!user) return;
    if (typing) othersTyping.add(user); else othersTyping.delete(user);
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => { othersTyping.clear(); renderTyping(); }, 3000);
    renderTyping();
  });

  // Send our typing signals (debounced)
  let lastTyped = 0, sentTyping = false;
  msgInput?.addEventListener("input", () => {
    const now = Date.now();
    if (now - lastTyped > 250) {
      socket.emit("typing", { typing: true });
      sentTyping = true;
      lastTyped = now;
      setTimeout(() => {
        if (sentTyping) socket.emit("typing", { typing: false });
        sentTyping = false;
      }, 1200);
    }
  });

  // ---------------- DM mode ----------------
  let pmTo = null; // username string or null

  function startPM(username) {
    pmTo = username;
    if (msgInput) {
      msgInput.placeholder = `DM to ${username}…`;
      msgInput.focus();
    }
    if (backBtn) backBtn.style.display = "inline-block";
  }
  function clearPM() {
    pmTo = null;
    if (msgInput) msgInput.placeholder = "Type a message";
    if (backBtn) backBtn.style.display = "none";
  }
  backBtn?.addEventListener("click", clearPM);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") clearPM(); });

  // /w <user> <message>
  function parseWhisper(s) {
    const m = (s || "").match(/^\/w\s+(\S+)\s+([\s\S]+)/i);
    return m ? { to: m[1], text: m[2] } : null;
  }

  // ---------------- Online roster ----------------
  socket.on("online", (roster) => {
    if (!usersBox) return;
    usersBox.innerHTML = "";

    (roster || []).forEach((u) => {
      const isObj  = u && typeof u === "object";
      const name   = isObj ? (u.username || u.user || "Anon") : (u || "Anon");
      const role   = isObj ? (u.role || "user") : "user";
      const gender = isObj ? (u.gender || "") : "";
      const avatar = isObj ? (u.avatar || "") : "";

      const li = document.createElement("li");
      li.innerHTML = `
        ${avatarHTML(avatar, name)}
        <span class="user-name">${name}</span>
        ${modBadge(role)}
        ${gender ? `<span class="g">${genderIcon(gender)} <small>${gender}</small></span>` : ""}
      `;
      li.addEventListener("click", () => startPM(name));
      usersBox.appendChild(li);
    });

    if (!roster || roster.length === 0) {
      const li = document.createElement("li");
      li.textContent = "No one online yet";
      usersBox.appendChild(li);
    }
  });

  // ---------------- Reactions (client-side only; server optional) ----------------
  const REACTIONS = ["👍", "❤️", "😂"];
  function reactionsBarHTML(id) {
    // If you later hook server events for reactions, you can add counts here
    return `
      <div class="reactions" data-for="${id}">
        ${REACTIONS.map(e => `<button class="rx-btn" data-emoji="${e}" data-id="${id}" type="button">${e}</button>`).join("")}
      </div>
    `;
  }
  function handleReactionClick(e) {
    const btn = e.target.closest(".rx-btn");
    if (!btn) return;
    const emoji = btn.getAttribute("data-emoji");
    const id    = btn.getAttribute("data-id");
    // If you implement reactions server-side, emit here:
    // socket.emit("react", { id, emoji });
    // For now we do a playful local bump effect:
    btn.style.transform = "scale(1.15)";
    setTimeout(() => (btn.style.transform = ""), 120);
  }
  list?.addEventListener("click", handleReactionClick);

  // ---------------- Messages ----------------
  function renderMessage(m) {
    if (!list) return;
    const keepDown = atBottom(list);

    const id   = m.id || `m-${Math.random().toString(36).slice(2)}`;
    const who  = m.user || m.username || "Anon";
    const ts   = formatTS(m.ts);
    const isPM = !!m.to && !!m.from;

    const li = document.createElement("li");
    if (isPM) li.classList.add("pm");
    li.dataset.id = id;

    li.innerHTML = `
      <div class="msg-row">
        ${avatarHTML(m.avatar, who)}
        <strong>${who}</strong>
        <span class="msg-time" title="${m.ts || ""}">${ts}</span>
        ${ROLE === "mod" ? `<button class="mini danger msg-del" data-id="${id}" title="Delete">✖</button>` : ""}
      </div>
      <div class="msg-text">${linkify(m.text || "")}</div>
      ${reactionsBarHTML(id)}
    `;
    list.appendChild(li);

    if (keepDown) scrollToBottom(list);
  }

  socket.on("chat_history", (arr) => {
    if (!list) return;
    list.innerHTML = "";
    (arr || []).forEach(renderMessage);
    scrollToBottom(list);
  });

  socket.on("chat", renderMessage);

  // Private messages (server echoes to sender + recipient)
  socket.on("pm", (payload) => {
    const msg = {
      id: payload.id || `pm-${Math.random().toString(36).slice(2)}`,
      user: payload.from,
      text: payload.text,
      ts: payload.ts || nowISO(),
      to: payload.to,
      from: payload.from,
      avatar: payload.avatar || ""
    };
    renderMessage(msg);
  });

  // Delete (mods)
  list?.addEventListener("click", (e) => {
    const btn = e.target.closest(".msg-del");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (id) socket.emit("delete_message", { id });
  });
  socket.on("message_deleted", ({ id }) => {
    document.querySelector(`li[data-id="${id}"]`)?.remove();
  });

  // ---------------- Send + offline outbox ----------------
  const outbox = [];
  function emitOrQueue(event, payload) {
    if (socket.connected) socket.emit(event, payload);
    else outbox.push({ event, payload });
  }
  function flushQueue() {
    while (socket.connected && outbox.length) {
      const item = outbox.shift();
      socket.emit(item.event, item.payload);
    }
  }
  function sendChatOrPM(txt) {
    const m = parseWhisper(txt);
    if (m) emitOrQueue("pm", m);
    else if (pmTo) emitOrQueue("pm", { to: pmTo, text: txt });
    else emitOrQueue("chat", { text: txt });
  }

  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const txt = (msgInput.value || "").trim();
    if (!txt) return;
    sendChatOrPM(txt);
    msgInput.value = "";
    msgInput.focus();
  });

  socket.on("connect", () => {
    socket.emit("roster_request");
    flushQueue();
  });
  socket.on("reconnect", () => socket.emit("roster_request"));

  // ---------------- Optional Emoji Picker ----------------
  // If you included Emoji Button via <script> on the page, this will attach automatically.
  try {
    if (window.EmojiButton && form && msgInput) {
      const picker = new EmojiButton({ position: "top-start" });
      let trigger = $("#emojiBtn");
      if (!trigger) {
        // Add a trigger button if the page doesn't have one
        trigger = document.createElement("button");
        trigger.type = "button";
        trigger.id = "emojiBtn";
        trigger.className = "emoji-btn";
        trigger.innerHTML = "😊";
        form.insertBefore(trigger, form.lastElementChild);
      }
      trigger.addEventListener("click", () => picker.togglePicker(trigger));
      picker.on("emoji", selection => {
        msgInput.value += selection.emoji;
        msgInput.focus();
      });
    }
  } catch (_) { /* ignore */ }

  // ---------------- Hash PM shortcut ----------------
  // Visiting /chat#@Alice auto starts a DM to Alice
  window.addEventListener("load", () => {
    const tag = decodeURIComponent(location.hash || "");
    if (tag.startsWith("#@") && tag.length > 2) {
      startPM(tag.slice(2));
    }
  });
})();
