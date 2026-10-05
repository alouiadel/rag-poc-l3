// ===== DOM =====
const messagesEl = document.getElementById("messages");
const inputEl = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const logoutBtn = document.getElementById("logoutBtn");
const chatTitle = document.getElementById("chatTitle");

const chatOutput = document.createElement("div");
chatOutput.id = "chat-output";
messagesEl.appendChild(chatOutput);

const sidebarUserName = document.getElementById("sidebarUserName");
const sidebarAvatar = document.getElementById("sidebarAvatar");
const newChatBtn = document.getElementById("newChatBtn");
const adminBtn = document.getElementById("adminBtn");
const historyList = document.getElementById("historyList");

// ===== FILE UPLOAD SETUP =====
const fileUploadInput = document.createElement("input");
fileUploadInput.type = "file";
fileUploadInput.id = "fileUploadInput";
fileUploadInput.style.display = "none";
fileUploadInput.accept = ".txt,.md,.pdf,.docx";
document.body.appendChild(fileUploadInput);

const uploadBtn = document.querySelector('button[title="Joindre un fichier"]');

// ===== LocalStorage keys =====
// LS_TOKEN and LS_USER come from lib/ui.js
const LS_HISTORY = "sont_chat_history"; // base key, suffixée par username

// ===== State =====
let currentSessionId = null;
let currentChatId = null;
let chats = [];

// ===== Init =====
guardAuth();
initUserCard();
bindEvents();
initPersonaSelect();
loadHistory();

// =========================
//        EVENTS
// =========================
function bindEvents() {
  sendBtn.addEventListener("click", handleSend);

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSend();
    }
  });

  inputEl.addEventListener("input", updateSendState);
  updateSendState();
  inputEl.focus();

  if (newChatBtn) {
    newChatBtn.addEventListener("click", handleNewChat);
  }

  if (historyList) {
    historyList.addEventListener("click", (e) => {
      const deleteBtn = e.target.closest(".history-delete-btn");
      if (deleteBtn) {
        e.stopPropagation();
        deleteChat(deleteBtn.dataset.id);
        return;
      }

      const item = e.target.closest(".history-item");
      if (item && historyList.contains(item)) {
        loadChat(item.dataset.id);
      }
    });
  }

  if (uploadBtn) {
    uploadBtn.addEventListener("click", () => fileUploadInput.click());
  }

  if (fileUploadInput) {
    fileUploadInput.addEventListener("change", handleFileUpload);
  }

  if (adminBtn) {
    adminBtn.addEventListener("click", () => {
      window.location.href = "/admin";
    });
  }

  logoutBtn.addEventListener("click", () => logout());
}

// =========================
//        USER CARD
// =========================
function initUserCard() {
  const username = (localStorage.getItem(LS_USER) || "Utilisateur").trim();
  if (sidebarUserName) sidebarUserName.textContent = username;
  if (sidebarAvatar) sidebarAvatar.textContent = makeInitials(username);
  checkAdminRole();
}

function checkAdminRole() {
  const token = localStorage.getItem(LS_TOKEN);
  if (!token) return;

  try {
    const parts = token.split(".");
    if (parts.length !== 3) return;

    const payload = JSON.parse(atob(parts[1]));
    if (payload.role === "admin") {
      if (adminBtn) adminBtn.style.display = "block";
      const roleEl = document.getElementById("sidebarUserRole");
      if (roleEl) roleEl.textContent = "Administrateur";
    }
  } catch (e) {
    console.warn("Admin check failed:", e);
  }
}

// =========================
//     HISTORY SYSTEM
// =========================

// clé localStorage propre à l'utilisateur connecté
function getHistoryKey() {
  const username = (localStorage.getItem(LS_USER) || "anonymous")
    .trim()
    .toLowerCase();
  return `${LS_HISTORY}_${username}`;
}

async function loadHistory() {
  // IMPORTANT : on charge bien l'historique du user connecté
  const raw = localStorage.getItem(getHistoryKey());
  chats = raw ? JSON.parse(raw) : [];
  renderHistoryList();

  const token = localStorage.getItem(LS_TOKEN);
  if (!token) return;

  try {
    const response = await fetch(API_ENDPOINTS.sessions, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) return;

    const sessions = await response.json();

    // Garder uniquement les chats locaux appartenant aux sessions backend de CE user
    const backendSessionIds = new Set(sessions.map((s) => s.id));

    chats = chats.filter((chat) => {
      // On garde les chats pas encore persistés en DB (sessionId null)
      if (!chat.sessionId) return true;
      return backendSessionIds.has(chat.sessionId);
    });

    // Mettre à jour les titres depuis le backend
    for (const session of sessions) {
      const chat = chats.find((c) => c.sessionId === session.id);
      if (chat && session.title && session.title !== "New chat") {
        chat.title = session.title;
      }
    }

    saveHistory();
    renderHistoryList();
  } catch (e) {
    console.warn("Failed to sync sessions from backend:", e);
  }
}

function saveHistory() {
  localStorage.setItem(getHistoryKey(), JSON.stringify(chats));
}

function renderHistoryList() {
  if (!historyList) return;

  if (chats.length === 0) {
    historyList.innerHTML = `
      <div class="empty-history">
        <div class="empty-hint">
          Aucune discussion pour le moment.<br/>
          Clique sur <b>Nouveau chat</b> pour commencer.
        </div>
      </div>`;
    return;
  }

  const groups = groupByDate(chats);
  let html = "";

  for (const [label, items] of Object.entries(groups)) {
    if (items.length === 0) continue;

    html += `<div class="history-group-label">${label}</div>`;

    for (const chat of items) {
      const isActive = chat.id === currentChatId;
      html += `
        <div class="history-item ${isActive ? "active" : ""}" data-id="${chat.id}">
          <span class="history-item-title">${escapeHtml(chat.title)}</span>
          <button class="history-delete-btn" data-id="${chat.id}" title="Supprimer" aria-label="Supprimer la conversation"><svg class="icon" aria-hidden="true"><use href="/static/lib/icons.svg#i-trash"></use></svg></button>
        </div>`;
    }
  }

  historyList.innerHTML = html;
}

function groupByDate(chats) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  const sevenDays = new Date(today);
  sevenDays.setDate(sevenDays.getDate() - 7);

  const groups = {
    "Aujourd'hui": [],
    Hier: [],
    "7 derniers jours": [],
    "Plus ancien": [],
  };

  const sorted = [...chats].sort((a, b) => b.date - a.date);

  for (const chat of sorted) {
    const d = new Date(chat.date);
    d.setHours(0, 0, 0, 0);

    if (d >= today) groups["Aujourd'hui"].push(chat);
    else if (d >= yesterday) groups["Hier"].push(chat);
    else if (d >= sevenDays) groups["7 derniers jours"].push(chat);
    else groups["Plus ancien"].push(chat);
  }

  return groups;
}

function createNewChatEntry(firstMessage) {
  const id = "chat_" + Date.now();

  const initialTitle =
    firstMessage && firstMessage.trim()
      ? firstMessage.trim().slice(0, 40)
      : "Nouvelle conversation";

  const chat = {
    id,
    title: initialTitle,
    sessionId: null,
    date: Date.now(),
    messages: [],
  };

  chats.unshift(chat);
  saveHistory();
  renderHistoryList();
  return id;
}

function appendMessageToCurrentChat(role, text) {
  if (!currentChatId) return;

  const chat = chats.find((c) => c.id === currentChatId);
  if (!chat) return;

  chat.messages.push({ role, text, ts: Date.now() });
  chat.date = Date.now();

  saveHistory();
}

function loadChat(chatId) {
  const chat = chats.find((c) => c.id === chatId);
  if (!chat) return;

  currentChatId = chatId;
  currentSessionId = chat.sessionId || null;

  messagesEl.innerHTML = "";
  const chatOutputNew = document.createElement("div");
  chatOutputNew.id = "chat-output";
  messagesEl.appendChild(chatOutputNew);

  for (const msg of chat.messages) {
    addMessage(msg.text, msg.role);
  }

  if (chatTitle) chatTitle.textContent = chat.title;

  renderHistoryList();
  inputEl.focus();
}

async function deleteChat(chatId) {
  const chat = chats.find((c) => c.id === chatId);
  if (!chat) return;

  // Si la session existe côté backend, on la supprime aussi
  if (chat.sessionId) {
    const token = localStorage.getItem(LS_TOKEN);

    try {
      await fetch(`${API_BASE_URL}/chat/sessions/${chat.sessionId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    } catch (e) {
      console.warn("Failed to delete chat session from backend:", e);
    }
  }

  chats = chats.filter((c) => c.id !== chatId);
  saveHistory();

  if (currentChatId === chatId) {
    handleNewChat();
  } else {
    renderHistoryList();
  }
}

// =========================
//        CHAT LOGIC
function updateSendState() {
  if (sendBtn) sendBtn.disabled = inputEl.value.trim().length === 0;
}

// =========================
async function handleSend() {
  const text = inputEl.value.trim();
  if (!text) return;

  if (!currentChatId) {
    currentChatId = createNewChatEntry(text);
    if (chatTitle) chatTitle.textContent = "Nouvelle conversation";
  }

  addMessage(text, "user");
  appendMessageToCurrentChat("user", text);

  inputEl.value = "";
  inputEl.focus();
  updateSendState();

  const botBubble = addMessage("...", "bot", true);
  const token = localStorage.getItem(LS_TOKEN);

  try {
    const response = await fetch(API_ENDPOINTS.chat, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        message: text,
        session_id: currentSessionId,
        persona_prompt: getSelectedPersonaPrompt(),
      }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      botBubble.classList.remove("typing");
      const errorMsg = data.detail || `Erreur serveur (${response.status})`;

      renderMarkdown(botBubble, errorMsg);

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem(LS_TOKEN);
        localStorage.removeItem(LS_USER);
        setTimeout(() => {
          window.location.href = "/";
        }, 400);
      }
      return;
    }

    botBubble.classList.remove("typing");
    const answerText = data.answer || "No answer";

    renderMarkdown(botBubble, answerText);

    if (data.session_id) {
      currentSessionId = data.session_id;
      const chat = chats.find((c) => c.id === currentChatId);

      if (chat) {
        chat.sessionId = currentSessionId;

        if (data.title) {
          chat.title = data.title;
          if (chatTitle) chatTitle.textContent = data.title;
        }

        chat.date = Date.now();
        saveHistory();
        renderHistoryList();
      }
    }

    appendMessageToCurrentChat("bot", answerText);
  } catch (err) {
    botBubble.classList.remove("typing");
    botBubble.textContent = "Erreur de connexion au serveur";
  }
}

function handleNewChat() {
  currentChatId = null;
  currentSessionId = null;

  messagesEl.innerHTML = "";
  const chatOutputNew = document.createElement("div");
  chatOutputNew.id = "chat-output";
  messagesEl.appendChild(chatOutputNew);

  if (chatTitle) chatTitle.textContent = "Nouveau chat";
  inputEl.value = "";
  inputEl.focus();
  renderHistoryList();
}

// =========================
//      FILE UPLOAD
// =========================
async function handleFileUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const token = localStorage.getItem(LS_TOKEN);
  const formData = new FormData();
  formData.append("file", file);

  const loadingBubble = addMessage("", "bot", true);
  loadingBubble.innerHTML = `<span class="upload-spinner"></span> Analyse de <strong>${escapeHtml(file.name)}</strong> en cours...`;

  try {
    const response = await fetch(API_ENDPOINTS.upload, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });

    const data = await response.json();
    loadingBubble.classList.remove("typing");

    if (response.ok) {
      loadingBubble.innerHTML = `<strong>${escapeHtml(file.name)}</strong> importé avec succès !`;
    } else {
      loadingBubble.innerHTML = `Échec de l'import : ${escapeHtml(data.detail || "Erreur inconnue")}`;
    }
  } catch (err) {
    loadingBubble.classList.remove("typing");
    loadingBubble.innerHTML = `Erreur lors de l'import : ${escapeHtml(err.message)}`;
  }

  fileUploadInput.value = "";
}

// =========================
//        UI HELPERS
// =========================
function addMessage(text, role, isTyping = false) {
  const bubble = document.createElement("div");
  bubble.className = `message ${role}` + (isTyping ? " typing" : "");

  if (role === "user") {
    bubble.textContent = text;
  } else if (role === "bot") {
    renderMarkdown(bubble, text);
  }

  messagesEl.appendChild(bubble);
  scrollToBottom();
  return bubble;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// =========================
//   PERSONA SELECT SYNC
// =========================
let personas = [];
let selectedPersonaId = null;

function initPersonaSelect() {
  const trigger = document.getElementById("personaTrigger");
  const menu = document.getElementById("personaMenu");
  if (!trigger || !menu) return;

  trigger.addEventListener("click", (e) => {
    e.stopPropagation();
    togglePersonaMenu();
  });

  document.addEventListener("click", (e) => {
    if (!e.target.closest("#personaDropdown")) closePersonaMenu();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closePersonaMenu();
  });

  menu.addEventListener("click", (e) => {
    const option = e.target.closest(".persona-option");
    if (!option) return;
    selectPersona(option.dataset.id);
    closePersonaMenu();
  });

  populatePersonaSelect();
  window.addEventListener("focus", populatePersonaSelect);
}

function togglePersonaMenu() {
  const menu = document.getElementById("personaMenu");
  const trigger = document.getElementById("personaTrigger");
  if (!menu || !trigger) return;

  const willOpen = menu.hidden;
  menu.hidden = !willOpen;
  trigger.setAttribute("aria-expanded", String(willOpen));

  if (willOpen) {
    const active =
      menu.querySelector('[aria-selected="true"]') ||
      menu.querySelector(".persona-option");
    if (active) active.classList.add("active");
  } else {
    menu
      .querySelectorAll(".persona-option.active")
      .forEach((el) => el.classList.remove("active"));
  }
}

function closePersonaMenu() {
  const menu = document.getElementById("personaMenu");
  const trigger = document.getElementById("personaTrigger");
  if (menu) {
    menu.hidden = true;
    menu
      .querySelectorAll(".persona-option.active")
      .forEach((el) => el.classList.remove("active"));
  }
  if (trigger) trigger.setAttribute("aria-expanded", "false");
}

async function populatePersonaSelect() {
  const menu = document.getElementById("personaMenu");
  if (!menu) return;

  let list = [];
  try {
    const response = await fetch(API_ENDPOINTS.personas, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (response.ok) list = await response.json();
  } catch (e) {
    console.warn("Failed to load personas:", e);
  }

  personas = list;

  // Clear a selection that no longer exists.
  if (
    selectedPersonaId !== null &&
    !personas.some((p) => String(p.id) === String(selectedPersonaId))
  ) {
    selectedPersonaId = null;
  }

  menu.innerHTML = personas
    .map(
      (p) => `
      <li class="persona-option" role="option" data-id="${escapeHtml(p.id)}"
          aria-selected="${String(p.id) === String(selectedPersonaId)}">
        <svg class="icon" aria-hidden="true"><use href="/static/lib/icons.svg#i-sparkles"></use></svg>
        <span>${escapeHtml(p.name)}</span>
      </li>`,
    )
    .join("");

  updatePersonaLabel();
}

function selectPersona(id) {
  selectedPersonaId = id;
  const menu = document.getElementById("personaMenu");
  if (menu) {
    menu.querySelectorAll(".persona-option").forEach((el) => {
      el.setAttribute("aria-selected", String(el.dataset.id === String(id)));
    });
  }
  updatePersonaLabel();
}

function updatePersonaLabel() {
  const label = document.getElementById("personaLabel");
  if (!label) return;
  const persona = personas.find(
    (p) => String(p.id) === String(selectedPersonaId),
  );
  label.textContent = persona ? persona.name : "Aucune personnalité";
}

function getSelectedPersonaPrompt() {
  const persona = personas.find(
    (p) => String(p.id) === String(selectedPersonaId),
  );
  return persona ? persona.prompt : null;
}
