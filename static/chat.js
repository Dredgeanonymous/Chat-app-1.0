function reactionStripHTML(m){
  // render reaction buttons + counts
  const rx = m.reactions || {};
  const parts = REACTION_SET.map(em => {
    const count = (rx[em] && rx[em].length) || 0;
    const badge = count ? `<span class="rx-count">${count}</span>` : "";
    return `<button class="rx-btn" data-id="${m.id}" data-em="${em}" title="React ${em}">${em}${badge}</button>`;
  });
  return `<div class="reactions">${parts.join("")}</div>`;
}

function renderMessage(m){
  const atBottom = shouldAutoScroll(list);

  const id   = m.id;
  const who  = m.user || m.username || "Anon";
  const text = linkify(m.text || "");
  const ts   = formatTS(m.ts);

  const li = document.createElement("li");
  li.dataset.id = id;
  li.innerHTML = `
    <div class="msg-row">
      ${renderAvatar(m.avatar, who)}
      <strong>${who}</strong>
      <span class="msg-time" title="${m.ts}">${ts}</span>
      ${ROLE === "mod" ? `
        <button class="mini danger msg-del" title="Delete" data-id="${id}">✖</button>
      ` : ""}
    </div>
    <div class="msg-text">${text}</div>
    ${reactionStripHTML(m)}
  `;

  // copy on double-click
  li.addEventListener("dblclick", () => {
    navigator.clipboard?.writeText(m.text || "").catch(()=>{});
  });

  list.appendChild(li);
  if (atBottom) doScroll(list);
      }

function hashColor(name) {
  // tiny stable color from name
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  const hue = h % 360;
  return `hsl(${hue} 70% 45%)`;
}
function renderAvatar(avatarUrl, username) {
  const initial = (username || "A").trim().charAt(0).toUpperCase();
  if (avatarUrl) {
    return `<img class="avatar" src="${avatarUrl}" alt="${username || ""}" onerror="this.remove()">`;
  }
  return `<span class="avatar avatar-fallback" style="background:${hashColor(username||"A")}">${initial}</span>`;
}

// static/chat.js — polished UI/UX + stable socket + gender icons + MOD delete

(function () {
  // ---------- Helpers (UX polish) ----------
  function formatTS(ts) {
    let d = new Date(ts);
    if (isNaN(d)) return "";
    return d.toLocaleString("en-US", {
      timeZone: "America/New_York", // lock to Eastern Time
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit", second: "2-digit",
      hour12: true
    });
  }
  function linkify(text) {
    const urlRe = /\b(https?:\/\/[^\s]+)\b/gi;
    return (text || "").replace(urlRe, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>');
  }
  function shouldAutoScroll(container) {
    const threshold = 60; // px from bottom
    return container.scrollHeight - container.scrollTop - container.clientHeight < threshold;
  }
  function doScroll(container) {
    container.scrollTop = container.scrollHeight;
  }

  // ---------- Connection (stable) ----------
  const REACTION_SET = ["👍","😂","😍","😮","🙏"];
  const socket = io({ transports: ["websocket", "polling"], upgrade: true });

  // Role detection (works if set on body or window)
  const BODY_ROLE = (document.body && document.body.dataset && document.body.dataset.role) || "";
  const ROLE = (String(window.ROLE || BODY_ROLE || "user")).toLowerCase(); // "mod" shows delete buttons

  // DOM references
  const form     = document.getElementById("sendForm");
  const msgInput = document.getElementById("msgInput");
  const list     = document.getElementById("messages");
  const usersBox = document.getElementById("users");

  socket.on("connect", () => {
    console.log("SOCKET CONNECTED", socket.id);
    socket.emit("roster_request"); // fetch who’s online right away
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

  // ---------- Typing indicator (polish) ----------
  const typingEl = document.createElement("div");
  typingEl.style.cssText = "padding:6px 12px;color:#94a3b8;font-size:12px;";
  document.querySelector(".panel:last-of-type")?.appendChild(typingEl);

  let othersTyping = new Set();
  let typingTimer = null;

  function updateTyping() {
    if (othersTyping.size) {
      typingEl.textContent = `${Array.from(othersTyping).slice(0,3).join(", ")} typing…`;
    } else {
      typingEl.textContent = "";
    }
  }

  msgInput?.addEventListener("input", () => {
    socket.emit("typing", { typing: !!msgInput.value.trim() });
  });

  socket.on("typing", ({ user, typing }) => {
    if (!user) return;
    if (typing) othersTyping.add(user); else othersTyping.delete(user);
    clearTimeout(typingTimer);
    typingTimer = setTimeout(() => { othersTyping.clear(); updateTyping(); }, 3000);
    updateTyping();
  });

  // ---------- Message renderer (polished)
  function renderMessage(m){
    const atBottom = shouldAutoScroll(list);

    const id   = m.id;
    const who  = m.user || m.username || "Anon";
    const text = linkify(m.text || "");
    const ts   = formatTS(m.ts);

    const li = document.createElement("li");
    li.dataset.id = id;
    li.innerHTML = `
      <div class="msg-row">
        <strong>${who}</strong>
        <span class="msg-time" title="${m.ts}">${ts}</span>
        ${ROLE === "mod" ? `
          <button class="mini danger msg-del" title="Delete" data-id="${id}">✖</button>
        ` : ""}
      </div>
      <div class="msg-text">${text}</div>
    `;
    // copy on double-click
    li.addEventListener("dblclick", () => {
      navigator.clipboard?.writeText(m.text || "").catch(()=>{});
    });

    list.appendChild(li);
    if (atBottom) doScroll(list);
  }

  // ---------- Safer submit (debounce + disable)
  const submitBtn = form?.querySelector('button[type="submit"]');
  let sending = false;

  form && form.addEventListener("submit", (e) => {
    e.preventDefault();
    if (sending) return;

    const txt = (msgInput.value || "").trim();
    if (!txt) return;

    sending = true;
    submitBtn && (submitBtn.disabled = true);

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

    setTimeout(() => {
      sending = false;
      submitBtn && (submitBtn.disabled = false);
      msgInput?.focus();
    }, 180);
  });

  // ---------- Delete (mods)
  // Click-to-react / toggle
list?.addEventListener("click", (e) => {
  const btn = e.target.closest(".rx-btn");
  if (!btn) return;
  const id = btn.getAttribute("data-id");
  const em = btn.getAttribute("data-em");
  if (id && em) socket.emit("react", { id, emoji: em });
});

// Server broadcasts minimal updates
socket.on("reaction_update", ({ id, emoji, count }) => {
  const li = document.querySelector(`li[data-id="${id}"]`);
  if (!li) return;
  const btn = li.querySelector(`.rx-btn[data-em="${emoji}"]`);
  if (!btn) return;

  let badge = btn.querySelector(".rx-count");
  if (!badge && count) {
    badge = document.createElement("span");
    badge.className = "rx-count";
    btn.appendChild(badge);
  }
  if (badge) {
    if (count) badge.textContent = count;
    else badge.remove();
  }
});
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
      // if odd payload, don't wipe; try again
      setTimeout(() => socket.emit("roster_request"), 800);
      return;
    }

    usersEl.innerHTML = "";
    (roster || []).forEach((u) => {
      const isObj   = u && typeof u === "object";
      const name    = isObj ? (u.username || u.user || "Anon") : (u || "Anon");
      const role    = isObj ? (u.role || "user") : "user";
      const gender  = isObj ? (u.gender || "") : "";
      const avatar = isObj ? (u.avatar || "") : "";
      if (!name) return;

      const li = document.createElement("li");
      li.innerHTML = `
     ${renderAvatar(avatar, name)}
     <span class="user-name">${name}</span>
     ${modBadge(role)}
     ${gender ? `<span class="g">${genderIcon(gender)} <small>${gender}</small></span>` : ""}
`;





      li.addEventListener("click", () => startPM(name));
      usersEl.appendChild(li);
    });

    // show count in heading
    const h2 = document.querySelector('.panel h2');
    if (h2) h2.textContent = `Online (${(roster || []).length})`;

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
    const atBottom = shouldAutoScroll(list);
    const li = document.createElement("li");
    li.className = "msg pm";
    li.innerHTML = `
      <div class="msg-row">
        <strong>(DM) ${m.from} → ${m.to}</strong>
        <span class="msg-time">${formatTS(m.ts)}</span>
      </div>
      <div class="msg-text">${linkify(m.text || "")}</div>
    `;
    list.appendChild(li);
    if (atBottom) doScroll(list);
  });

  // ---------- Keep UI in sync with deletes ----------
  socket.on("message_deleted", ({ id }) => {
    document.querySelector(`li[data-id="${id}"]`)?.remove();
  });
})();
