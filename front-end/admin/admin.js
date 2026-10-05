// ============================================================
//  RAG PoC L3 – Admin Panel JS
//  Personnalités (server-side), utilisateurs et base de connaissances
// ============================================================

// LS_TOKEN and LS_USER come from lib/ui.js

const MAX = 5;

// ===== STATE =====
let personas = [];
let editingId = null;
let currentUser = "";
let kbBusy = false;

// ===== INIT =====
guardAuth("admin");
currentUser = (localStorage.getItem(LS_USER) || "").trim();
initUserCard();
bindEvents();
showSection("personas");

// ============================================================
//  USER CARD
// ============================================================
function initUserCard() {
  const username = (localStorage.getItem(LS_USER) || "Admin").trim();
  const nameEl = document.getElementById("adminName");
  const avatarEl = document.getElementById("adminAvatar");
  if (nameEl) nameEl.textContent = username;
  if (avatarEl) avatarEl.textContent = makeInitials(username);
}

// ============================================================
//  EVENTS
// ============================================================
function bindEvents() {
  document.getElementById("logoutBtn").addEventListener("click", () => logout());

  document.querySelectorAll(".nav-btn[data-section]").forEach((btn) => {
    btn.addEventListener("click", () => showSection(btn.dataset.section));
  });

  document.getElementById("modalClose").addEventListener("click", closeModal);
  document.getElementById("modalCancel").addEventListener("click", closeModal);
  document.getElementById("modalOverlay").addEventListener("click", (e) => {
    if (e.target === document.getElementById("modalOverlay")) closeModal();
  });
  document
    .getElementById("modalSave")
    .addEventListener("click", handleModalSave);
  document
    .getElementById("modalPrompt")
    .addEventListener("input", updateCharCount);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  document.getElementById("usersRefresh").addEventListener("click", loadUsers);
  document.getElementById("kbRefresh").addEventListener("click", loadKb);
  document.getElementById("kbIngest").addEventListener("click", ingestKbText);
  document.getElementById("kbReset").addEventListener("click", resetKb);
}

// ============================================================
//  NAVIGATION
// ============================================================
function showSection(name) {
  document.querySelectorAll(".admin-section").forEach((section) => {
    section.hidden = section.id !== `section-${name}`;
  });
  document.querySelectorAll(".nav-btn[data-section]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.section === name);
  });

  if (name === "personas") loadPersonas();
  else if (name === "users") loadUsers();
  else if (name === "kb") loadKb();
}

// ============================================================
//  API HELPER
// ============================================================
async function apiRequest(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getToken()}`,
      ...(options.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Erreur ${response.status}`);
  }
  return data;
}

// ============================================================
//  PERSONAS
// ============================================================
async function loadPersonas() {
  try {
    personas = await apiRequest(API_ENDPOINTS.personas);
  } catch (e) {
    personas = [];
    showToast(`Chargement impossible : ${e.message}`, "warning");
  }
  renderAll();
}

function renderAll() {
  const grid = document.getElementById("cardsGrid");
  grid.innerHTML = "";
  personas.forEach((p) => grid.appendChild(buildCard(p)));
  grid.appendChild(buildAddCard());
  updateBadge();
}

function updateBadge() {
  const badge = document.getElementById("countBadge");
  if (badge)
    badge.textContent = `${personas.length} / ${MAX} personnalité${personas.length !== 1 ? "s" : ""}`;
}

function buildCard(p) {
  const card = document.createElement("div");
  card.className = "card";
  card.dataset.id = p.id;
  card.innerHTML = `
    <div class="card-avatar">${escapeHtml(p.name[0].toUpperCase())}</div>
    <div class="card-name">${escapeHtml(p.name)}</div>
    <div class="card-prompt">${escapeHtml(p.prompt)}</div>
    <div class="card-actions">
      <button class="btn-edit">
        <svg class="icon" aria-hidden="true"><use href="/static/lib/icons.svg#i-pencil"></use></svg>
        Modifier
      </button>
      <button class="btn-delete" title="Supprimer" aria-label="Supprimer">
        <svg class="icon" aria-hidden="true"><use href="/static/lib/icons.svg#i-trash"></use></svg>
      </button>
    </div>
  `;
  card
    .querySelector(".btn-edit")
    .addEventListener("click", () => openModal(p.id));
  card
    .querySelector(".btn-delete")
    .addEventListener("click", () => deletePersona(p.id, card));
  return card;
}

function buildAddCard() {
  const maxReached = personas.length >= MAX;
  const card = document.createElement("div");
  card.className = "card-add" + (maxReached ? " disabled" : "");
  card.innerHTML = `
    <div class="add-plus">＋</div>
    <div class="add-label">Nouvelle personnalité</div>
    ${maxReached ? `<div class="add-max-hint">Maximum ${MAX} atteint</div>` : ""}
  `;
  if (!maxReached) card.addEventListener("click", () => openModal(null));
  return card;
}

// ============================================================
//  PERSONA MODAL
// ============================================================
function openModal(id) {
  editingId = id;
  const titleEl = document.getElementById("modalTitle");
  const nameInput = document.getElementById("modalName");
  const promptArea = document.getElementById("modalPrompt");

  if (id) {
    const p = personas.find((x) => x.id === id);
    titleEl.textContent = "Modifier la personnalité";
    nameInput.value = p.name;
    promptArea.value = p.prompt;
  } else {
    titleEl.textContent = "Nouvelle personnalité";
    nameInput.value = "";
    promptArea.value = "";
  }

  nameInput.classList.remove("error");
  promptArea.classList.remove("error");
  updateCharCount();
  document.getElementById("modalOverlay").classList.add("open");
  nameInput.focus();
}

function closeModal() {
  document.getElementById("modalOverlay").classList.remove("open");
  editingId = null;
}

function updateCharCount() {
  const len = document.getElementById("modalPrompt").value.length;
  document.getElementById("charCount").textContent = `${len} / 500`;
}

async function handleModalSave() {
  const nameInput = document.getElementById("modalName");
  const promptArea = document.getElementById("modalPrompt");
  const name = nameInput.value.trim();
  const prompt = promptArea.value.trim();

  nameInput.classList.remove("error");
  promptArea.classList.remove("error");
  let valid = true;

  if (!name) {
    nameInput.classList.add("error");
    nameInput.focus();
    valid = false;
  }
  if (!prompt) {
    promptArea.classList.add("error");
    if (valid) promptArea.focus();
    valid = false;
  }
  if (!valid) return;

  try {
    if (editingId) {
      const updated = await apiRequest(
        `${API_ENDPOINTS.personas}/${editingId}`,
        { method: "PUT", body: JSON.stringify({ name, prompt }) },
      );
      const idx = personas.findIndex((p) => p.id === editingId);
      if (idx !== -1) personas[idx] = updated;
      showToast(`"${name}" modifiée`, "success");
    } else {
      const created = await apiRequest(API_ENDPOINTS.personas, {
        method: "POST",
        body: JSON.stringify({ name, prompt }),
      });
      personas.push(created);
      showToast(`"${name}" ajoutée`, "success");
    }
    closeModal();
    renderAll();
  } catch (e) {
    showToast(`Erreur : ${e.message}`, "warning");
  }
}

async function deletePersona(id, cardEl) {
  const p = personas.find((x) => x.id === id);
  const ok = await confirmDialog({
    title: "Supprimer la personnalité",
    message: `Supprimer « ${p?.name} » ?\nElle sera retirée du chat immédiatement.`,
    confirmText: "Supprimer",
    danger: true,
  });
  if (!ok) return;

  try {
    await apiRequest(`${API_ENDPOINTS.personas}/${id}`, { method: "DELETE" });
  } catch (e) {
    showToast(`Erreur : ${e.message}`, "warning");
    return;
  }

  cardEl.classList.add("card-removing");
  setTimeout(() => {
    personas = personas.filter((x) => x.id !== id);
    renderAll();
    showToast(`"${p?.name}" supprimée`, "warning");
  }, 260);
}

// ============================================================
//  USERS
// ============================================================
async function loadUsers() {
  const tbody = document.getElementById("usersTableBody");
  tbody.innerHTML = `<tr><td colspan="4" class="table-empty">Chargement…</td></tr>`;

  let users = [];
  try {
    users = await apiRequest(API_ENDPOINTS.users);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" class="table-empty">Erreur : ${escapeHtml(e.message)}</td></tr>`;
    return;
  }

  if (!users.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="table-empty">Aucun utilisateur</td></tr>`;
    return;
  }

  tbody.innerHTML = "";
  users.forEach((u) => tbody.appendChild(buildUserRow(u)));
}

function buildUserRow(u) {
  const tr = document.createElement("tr");
  const isSelf = u.username === currentUser;

  tr.innerHTML = `
    <td>${escapeHtml(u.username)}${isSelf ? ' <span class="role-badge">vous</span>' : ""}</td>
    <td>${escapeHtml(u.full_name || "—")}</td>
    <td><span class="role-badge ${u.is_admin ? "admin" : ""}">${u.is_admin ? "Admin" : "Utilisateur"}</span></td>
    <td class="col-action">
      <button class="btn-row"${isSelf ? ' disabled title="Vous ne pouvez pas modifier votre propre rôle"' : ""}>
        <svg class="icon" aria-hidden="true"><use href="/static/lib/icons.svg#i-shield"></use></svg>
        ${u.is_admin ? "Retirer admin" : "Promouvoir"}
      </button>
    </td>
  `;

  const btn = tr.querySelector(".btn-row");
  if (!isSelf) btn.addEventListener("click", () => toggleUserRole(u, btn));
  return tr;
}

async function toggleUserRole(user, button) {
  button.disabled = true;
  try {
    await apiRequest(API_ENDPOINTS.updateUserAdmin, {
      method: "POST",
      body: JSON.stringify({
        target_username: user.username,
        is_admin: !user.is_admin,
      }),
    });
    showToast(`Rôle de "${user.username}" mis à jour`, "success");
    loadUsers();
  } catch (e) {
    showToast(`Erreur : ${e.message}`, "warning");
    button.disabled = false;
  }
}

// ============================================================
//  KNOWLEDGE BASE
// ============================================================
async function loadKb() {
  const vectorsEl = document.getElementById("kbVectors");
  const collectionEl = document.getElementById("kbCollection");
  vectorsEl.textContent = "…";
  collectionEl.textContent = "…";

  try {
    const data = await apiRequest(API_ENDPOINTS.collectionInfo);
    vectorsEl.textContent = data.points_count ?? 0;
    collectionEl.textContent = data.collection_name || "—";
  } catch (e) {
    vectorsEl.textContent = "—";
    collectionEl.textContent = "erreur";
    showToast(`Erreur : ${e.message}`, "warning");
  }
}

async function ingestKbText() {
  if (kbBusy) return;
  const area = document.getElementById("kbText");
  const text = area.value.trim();
  if (!text) {
    showToast("Le texte est vide", "warning");
    area.focus();
    return;
  }

  kbBusy = true;
  const button = document.getElementById("kbIngest");
  button.disabled = true;

  try {
    const result = await apiRequest(API_ENDPOINTS.ingest, {
      method: "POST",
      body: JSON.stringify({ documents: [text] }),
    });
    showToast(`${result.chunks_created} chunk(s) ingéré(s)`, "success");
    area.value = "";
    loadKb();
  } catch (e) {
    showToast(`Erreur : ${e.message}`, "warning");
  } finally {
    kbBusy = false;
    button.disabled = false;
  }
}

async function resetKb() {
  const ok = await confirmDialog({
    title: "Réinitialiser la base",
    message:
      "Tous les documents indexés (vecteurs Qdrant) seront définitivement supprimés.\nCette action est irréversible.",
    confirmText: "Réinitialiser",
    danger: true,
  });
  if (!ok) return;

  try {
    await apiRequest(API_ENDPOINTS.resetCollection, { method: "POST" });
    showToast("Base de connaissances réinitialisée", "warning");
    loadKb();
  } catch (e) {
    showToast(`Erreur : ${e.message}`, "warning");
  }
}

// ============================================================
//  TOAST
// ============================================================
let toastTimer = null;
function showToast(msg, type = "success") {
  const t = document.getElementById("toast");
  if (!t) return;
  clearTimeout(toastTimer);
  t.textContent = msg;
  t.className = `toast ${type} show`;
  toastTimer = setTimeout(() => t.classList.remove("show"), 2800);
}
