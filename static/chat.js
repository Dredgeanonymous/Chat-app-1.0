// static/chat.js — DM toggle + avatar/gender/mod in Online + basic chat rendering

(function () {
  // ---------- Utilities ----------
  function formatTS(ts) {
    const d = new Date(ts);
    if (isNaN(d)) return "";
    return d.toLocaleString("en-US", {
      timeZone: "America/New_York",
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hour12: true
    });
  }
  function linkify(text) {
    const urlRe = /\b(https?:\/\/[^\s]+)\b/gi;
    return (text || "").replace(urlRe, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  }
  function atBottom(el) {
    const threshold = 60;
    return el.scrollHeight - el.scrollTop - el.clientHeight < threshold;
  }
  function scrollToBottom(el) { el.scrollTop = el.scrollHeight; }

  // ---------- Small UI helpers ----------
  function hashColor(name) {
    let h = 0;
    for (let i = 0; i < (name || "").length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    return `hsl(${h % 360} 70% 45%)`;
  }
  function renderAvatar(avatarUrl, username) {
    const initial = (username || "A").charAt(0).toUpperCase();
    if (avatarUrl) {
      return `<img class="avatar" src="${avatarUrl}" alt="${username || ""}" onerror="this.remove()">`;
    }
    return `<span class="avatar avatar-fallback" style="background:${hashColor(username)}">${initial}</span>`;
  }
  function genderIcon(g) {
    switch ((g || "").toLowerCase()) {
      case "male":      return '<i class="fa-solid fa-mars" title="Male"></i>';
      case "female":    return '<i class="fa-solid fa-venus" title="Female"></i>';
      case "nonbinary": return '<i class="fa-solid fa-genderless" title="Non-binary"></i>';
      case "trans":     return '<i class="fa-solid fa-transgender" title="Trans"></i>';
      case "other":     return '<i class="fa-regular fa-circle-question" title="Other"></i>';
      default:          return "";
    }
  }
  function modBadge(role) {
    return String(role).toLowerCase() === "mod"
      ? '<span class="badge-mod" title="Moderator">MOD</span>'
      : "";
  }

  // ---------- Socket connection ----------
  const socket   = io({ transports: ["websocket", "polling"], upgrade: true });
  const ROLE     = (String(window.ROLE || (document.body.dataset.role || "user"))).toLowerCase();

  // DOM
  const form     = document.getElementById("sendForm");
  const msgInput = document.getElementById("msgInput");
  const list     = document.getElementById("messages");
  const usersBox = document.getElementById("users");
  const backBtn  = document.getElementById("backToChat");
  // ---------- Typing indicator (animated) ----------
  const typingEl = document.createElement("div");
typingEl.className = "typing";
typingEl.setAttribute("aria-live", "polite");
typingEl.style.display = "none";
typingEl.innerHTML = `
  <span class="who"></span>
  <span class="dots" aria-hidden="true">
    <span class="dot"></span><span class="dot"></span><span class="dot"></span>
  </span>
`;

// attach to the messages panel, or fallback below the form
const attachTarget =
  document.querySelector(".panel:last-of-type") ||
  document.getElementById("sendForm")?.parentElement ||
  document.body;
attachTarget.appendChild(typingEl);

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

// update when OTHERS type
socket.on("typing", ({ user, typing }) => {
  if (!user) return;
  if (typing) othersTyping.add(user); else othersTyping.delete(user);

  clearTimeout(typingTimer);
  typingTimer = setTimeout(() => { othersTyping.clear(); renderTyping(); }, 3000);

  renderTyping();
});
  socket.on("connect", () => socket.emit("roster_request"));
  socket.on("reconnect", () => socket.emit("roster_request"));

  // ---------- DM helpers (your requested toggle) ----------
  let pmTo = null;

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

  function parseWhisper(s) {
    const m = s.match(/^\/w\s+(\S+)\s+([\s\S]+)/i);
    return m ? { to: m[1], text: m[2] } : null;
  }

  // ---------- Submit ----------
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const txt = (msgInput.value || "").trim();
    if (!txt) return;

    const m = parseWhisper(txt);
    if (m) {
      socket.emit("pm", m);
    } else if (pmTo) {
      socket.emit("pm", { to: pmTo, text: txt });
    } else {
      socket.emit("chat", { text: txt });
    }
    msgInput.value = "";
    msgInput.focus();
  });

  // ---------- Online roster (INCLUDES YOUR SNIPPET) ----------
  socket.on("online", (roster) => {
    if (!usersBox) return;
    usersBox.innerHTML = "";

    (roster || []).forEach((u) => {
      const isObj  = u && typeof u === "object";
      const name   = isObj ? (u.username || u.user || "Anon") : (u || "Anon");
      const role   = isObj ? (u.role || "user") : "user";
      const gender = isObj ? (u.gender || "") : "";
      const avatar = isObj ? (u.avatar || "") : "";

      if (!name) return;

      const li = document.createElement("li");
      // >>> Your requested snippet, integrated <<<
      li.innerHTML = `
        ${renderAvatar(avatar, name)}
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

  // ---------- Messages ----------
  function renderMessage(m) {
    if (!list) return;
    const keepDown = atBottom(list);

    const id  = m.id;
    const who = m.user || m.username || "Anon";
    const ts  = formatTS(m.ts);
    const li  = document.createElement("li");
    li.dataset.id = id || "";

    li.innerHTML = `
      <div class="msg-row">
        ${renderAvatar(m.avatar, who)}
        <strong>${who}</strong>
        <span class="msg-time" title="${m.ts || ""}">${ts}</span>
        ${ROLE === "mod" ? `<button class="mini danger msg-del" data-id="${id || ""}" title="Delete">✖</button>` : ""}
      </div>
      <div class="msg-text">${linkify(m.text || "")}</div>
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

  // delete (mod)
  list?.addEventListener("click", (e) => {
    const btn = e.target.closest(".msg-del");
    if (!btn) return;
    const id = btn.getAttribute("data-id");
    if (id) socket.emit("delete_message", { id });
  });

  socket.on("message_deleted", ({ id }) => {
    document.querySelector(`li[data-id="${id}"]`)?.remove();
  });
})();
