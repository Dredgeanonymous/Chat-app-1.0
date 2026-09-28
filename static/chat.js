// static/chat.js
// HotSinglesChat real-time chat client

(function () {
  "use strict";

  // --------------------------------------------------
  // Elements
  // --------------------------------------------------

  const usersBox = document.getElementById("users");
  const messagesBox = document.getElementById("messages");
  const sendForm = document.getElementById("sendForm");
  const msgInput = document.getElementById("msgInput");
  const backToChat = document.getElementById("backToChat");
  const onlineCount = document.getElementById("onlineCount");

  const ROLE = document.body.dataset.role || window.ROLE || "user";
  const MY_USERNAME = window.USERNAME || "";

  let privateTarget = null;
  let socket = null;


  // --------------------------------------------------
  // Helpers
  // --------------------------------------------------

  function escapeHTML(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }


  function formatTime(ts) {
    if (!ts) return "";

    const date = new Date(ts);

    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return date.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit"
    });
  }


  function scrollMessages() {
    if (!messagesBox) return;

    messagesBox.scrollTop = messagesBox.scrollHeight;
  }


  function avatarHTML(url, username) {
    const safeName = escapeHTML(username || "?");

    if (!url) {
      const letter = safeName.charAt(0).toUpperCase();

      return `
        <div class="chat-avatar avatar-fallback"
             aria-hidden="true">
          ${letter}
        </div>
      `;
    }

    const safeURL = escapeHTML(url);

    return `
      <img
        class="chat-avatar"
        src="${safeURL}"
        alt=""
        loading="lazy"
        onerror="this.style.display='none';"
      >
    `;
  }


  function genderIcon(gender) {
    if (!gender) return "";

    const icons = {
      male: "♂",
      female: "♀",
      nonbinary: "⚧",
      trans: "⚧"
    };

    return icons[gender] || "";
  }


  function roleBadge(role) {
    if (role !== "mod") return "";

    return `
      <span class="mod-badge">
        MOD
      </span>
    `;
  }


  // --------------------------------------------------
  // Private messaging
  // --------------------------------------------------

  function startPM(username) {
    if (!username) return;

    if (username === MY_USERNAME) {
      return;
    }

    privateTarget = username;

    if (msgInput) {
      msgInput.placeholder = `Private message to ${username}…`;
      msgInput.focus();
    }

    if (backToChat) {
      backToChat.style.display = "block";
    }

    updateChatHeader(true, username);
  }


  function clearPM() {
    privateTarget = null;

    if (msgInput) {
      msgInput.placeholder = "Say something…";
      msgInput.focus();
    }

    if (backToChat) {
      backToChat.style.display = "none";
    }

    updateChatHeader(false);
  }


  function updateChatHeader(isPrivate, username) {
    const heading = document.querySelector("#chat-heading");

    if (!heading) return;

    if (isPrivate) {
      heading.textContent = `🔒 Private message with ${username}`;
    } else {
      heading.textContent = "💬 Public Chat";
    }
  }


  if (backToChat) {
    backToChat.addEventListener("click", clearPM);
  }


  // --------------------------------------------------
  // Online users
  // --------------------------------------------------

  function renderUsers(roster) {
    if (!usersBox) return;

    usersBox.innerHTML = "";

    const users = Array.isArray(roster) ? roster : [];

    if (onlineCount) {
      onlineCount.textContent = users.length;
    }

    if (users.length === 0) {
      usersBox.innerHTML = `
        <li class="user-empty">
          👋 You're the first one here!<br>
          Start the conversation.
        </li>
      `;

      return;
    }

    users.forEach(function (user) {
      const username = user.username || "Anonymous";

      const li = document.createElement("li");

      li.className = "chat-user";

      if (username === MY_USERNAME) {
        li.classList.add("current-user");
      }

      const gender = genderIcon(user.gender);
      const badge = roleBadge(user.role);

      li.innerHTML = `
        <div class="chat-user-main">
          ${avatarHTML(user.avatar, username)}

          <div class="chat-user-info">
            <div class="chat-user-name">
              ${escapeHTML(username)}
              ${badge}
            </div>

            <div class="chat-user-status">
              ${username === MY_USERNAME
                ? "You"
                : `Online ${gender}`}
            </div>
          </div>
        </div>

        ${
          username !== MY_USERNAME
            ? `
              <button
                type="button"
                class="user-message-btn"
                data-username="${escapeHTML(username)}"
                aria-label="Message ${escapeHTML(username)}"
              >
                Message
              </button>
            `
            : `
              <span class="you-badge">You</span>
            `
        }
      `;

      usersBox.appendChild(li);
    });


    // Message buttons
    usersBox
      .querySelectorAll(".user-message-btn")
      .forEach(function (button) {

        button.addEventListener("click", function (event) {
          event.stopPropagation();

          const username =
            button.getAttribute("data-username");

          startPM(username);
        });

      });
  }


  // --------------------------------------------------
  // Messages
  // --------------------------------------------------

  function renderMessage(message) {
    if (!messagesBox || !message) return;

    const li = document.createElement("li");

    li.className = "chat-message";

    const username = message.user || "Anonymous";
    const text = message.text || "";

    li.dataset.messageId = message.id || "";

    const isMe = username === MY_USERNAME;

    if (isMe) {
      li.classList.add("own-message");
    }

    li.innerHTML = `
      <div class="message-avatar">
        ${avatarHTML(message.avatar, username)}
      </div>

      <div class="message-content">

        <div class="message-meta">

          <strong>
            ${escapeHTML(username)}
          </strong>

          ${roleBadge(message.role)}

          <span class="message-time">
            ${escapeHTML(formatTime(message.ts))}
          </span>

        </div>

        <div class="message-text">
          ${escapeHTML(text)}
        </div>

        <div class="message-actions">

          <button
            type="button"
            class="reaction-btn"
            data-reaction="👍"
            aria-label="React with thumbs up"
          >
            👍
          </button>

          <button
            type="button"
            class="reaction-btn"
            data-reaction="❤️"
            aria-label="React with heart"
          >
            ❤️
          </button>

          <button
            type="button"
            class="reaction-btn"
            data-reaction="😂"
            aria-label="React with laughing"
          >
            😂
          </button>

          ${
            ROLE === "mod"
              ? `
                <button
                  type="button"
                  class="delete-message-btn"
                  aria-label="Delete message"
                >
                  Delete
                </button>
              `
              : ""
          }

        </div>

      </div>
    `;

    messagesBox.appendChild(li);

    attachMessageActions(li, message);

    scrollMessages();
  }


  function attachMessageActions(li, message) {

    li.querySelectorAll(".reaction-btn")
      .forEach(function (button) {

        button.addEventListener("click", function () {
  const reaction = button.dataset.reaction;

  if (!message.id) return;

  socket.emit("react", {
    id: message.id,
    reaction: reaction
  });
});


    const deleteButton =
      li.querySelector(".delete-message-btn");

    if (deleteButton) {

      deleteButton.addEventListener("click", function () {

        if (!message.id) return;

        socket.emit("delete_message", {
          id: message.id
        });

      });

    }
  }


  function renderHistory(history) {
    if (!messagesBox) return;

    messagesBox.innerHTML = "";

    if (!Array.isArray(history) || history.length === 0) {
      messagesBox.innerHTML = `
        <li class="chat-empty">
          <div>
            <strong>👋 Start the conversation!</strong>
            <p>
              Be the first person to say hello.
            </p>
          </div>
        </li>
      `;

      return;
    }

    history.forEach(renderMessage);

    scrollMessages();
  }


  // --------------------------------------------------
  // Socket.IO
  // --------------------------------------------------

  socket = io({
    transports: ["websocket", "polling"],
    upgrade: true
  });


  socket.on("connect", function () {

    console.log("Connected to HotSinglesChat");

    socket.emit("roster_request");

  });


  socket.on("disconnect", function () {

    console.log("Disconnected from HotSinglesChat");

  });


  socket.on("connect_error", function (error) {

    console.warn("Chat connection error:", error);

  });


  // --------------------------------------------------
  // Online roster
  // --------------------------------------------------

  socket.on("online", function (roster) {

    renderUsers(roster);

  });


  // --------------------------------------------------
  // Chat history
  // --------------------------------------------------

  socket.on("chat_history", function (history) {

    renderHistory(history);

  });


  // --------------------------------------------------
  // Public chat
  // --------------------------------------------------

  socket.on("chat", function (message) {

    renderMessage(message);

  });


  // --------------------------------------------------
  // Private messages
  // --------------------------------------------------

  socket.on("pm", function (message) {

    if (!messagesBox) return;

    const li = document.createElement("li");

    li.className = "chat-message private-message";

    const username =
      message.user || message.from || "Unknown";

    const text =
      message.text || "";

    li.innerHTML = `
      <div class="message-avatar">
        🔒
      </div>

      <div class="message-content">

        <div class="message-meta">
          <strong>
            ${escapeHTML(username)}
          </strong>

          <span class="pm-label">
            Private
          </span>

          <span class="message-time">
            ${escapeHTML(formatTime(message.ts))}
          </span>
        </div>

        <div class="message-text">
          ${escapeHTML(text)}
        </div>

      </div>
    `;

    messagesBox.appendChild(li);

    scrollMessages();

  });


  // --------------------------------------------------
  // Reactions
  // --------------------------------------------------

  socket.on("reaction_update", function (data) {
  if (!data || !data.id) return;

  const message = messagesBox?.querySelector(
    `[data-message-id="${CSS.escape(String(data.id))}"]`
  );

  if (!message) return;

  let reactionBox = message.querySelector(".reaction-counts");

  if (!reactionBox) {
    reactionBox = document.createElement("div");
    reactionBox.className = "reaction-counts";

    const actions = message.querySelector(".message-actions");

    if (actions) {
      actions.insertAdjacentElement("afterend", reactionBox);
    } else {
      message.querySelector(".message-content")?.appendChild(reactionBox);
    }
  }

  const counts = data.reactions || {};

  reactionBox.innerHTML = Object.entries(counts)
    .filter(([reaction, count]) => Number(count) > 0)
    .map(([reaction, count]) => {
      return `
        <span class="reaction-count">
          ${escapeHTML(reaction)} ${Number(count)}
        </span>
      `;
    })
    .join("");
});


  // --------------------------------------------------
  // Deleted messages
  // --------------------------------------------------

  socket.on("message_deleted", function (data) {

    if (!data || !data.id) return;

    const message =
      messagesBox?.querySelector(
        `[data-message-id="${CSS.escape(String(data.id))}"]`
      );

    if (message) {
      message.remove();
    }

  });


  // --------------------------------------------------
  // Typing indicator
  // --------------------------------------------------

  let typingTimeout = null;

  function sendTyping() {

    if (!socket.connected) return;

    socket.emit("typing", {
      typing: true
    });

    clearTimeout(typingTimeout);

    typingTimeout = setTimeout(function () {

      socket.emit("typing", {
        typing: false
      });

    }, 1000);
  }


  if (msgInput) {

    msgInput.addEventListener("input", function () {

      if (msgInput.value.trim()) {
        sendTyping();
      }

    });

  }


  socket.on("typing", function (data) {

    if (!data) return;

    const username =
      data.username || "";

    if (!username || username === MY_USERNAME) {
      return;
    }

    let indicator =
      document.getElementById("typingIndicator");

    if (!data.typing) {

      if (indicator) {
        indicator.remove();
      }

      return;
    }


    if (!indicator) {

      indicator =
        document.createElement("div");

      indicator.id =
        "typingIndicator";

      indicator.className =
        "typing-indicator";

      messagesBox?.parentElement
        ?.insertBefore(
          indicator,
          messagesBox
        );

    }

    indicator.textContent =
      `${username} is typing…`;

  });


  // --------------------------------------------------
  // Sending messages
  // --------------------------------------------------

  if (sendForm) {

    sendForm.addEventListener("submit", function (event) {

      event.preventDefault();

      if (!msgInput || !socket.connected) {
        return;
      }

      const text =
        msgInput.value.trim();

      if (!text) return;


      // Whisper shortcut:
      // /w username message
      if (text.startsWith("/w ")) {

        const parts =
          text.substring(3).trim().split(/\s+/);

        const target =
          parts.shift();

        const privateText =
          parts.join(" ").trim();

        if (target && privateText) {

          socket.emit("pm", {
            to: target,
            text: privateText
          });

          msgInput.value = "";

        }

        return;
      }


      // Private message mode
      if (privateTarget) {

        socket.emit("pm", {
          to: privateTarget,
          text: text
        });

      } else {

        socket.emit("chat", {
          text: text
        });

      }

      msgInput.value = "";

      msgInput.focus();

    });

  }


  // --------------------------------------------------
  // Reconnect
  // --------------------------------------------------

  socket.on("reconnect", function () {

    socket.emit("roster_request");

  });


})();