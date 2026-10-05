// Shared UI helpers and auth utilities for all pages.
// Must be loaded after config.js and before page scripts.

const LS_TOKEN = "access_token";
const LS_USER = "username";

function getToken() {
  return localStorage.getItem(LS_TOKEN);
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function makeInitials(name) {
  const clean = String(name || "")
    .replace(/\s+/g, " ")
    .trim();
  if (!clean) return "UA";
  const parts = clean.split(" ");
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function renderMarkdown(el, text) {
  const value = text == null ? "" : String(text);
  const markedLib = window.marked || (typeof marked !== "undefined" ? marked : null);
  const purify = window.DOMPurify;
  if (markedLib && typeof markedLib.parse === "function" && purify) {
    try {
      el.innerHTML = purify.sanitize(markedLib.parse(value));
      return;
    } catch (e) {
      // fall through to plain text
    }
  }
  // Safe fallback: never inject unsanitized HTML.
  el.textContent = value;
}

function guardAuth(requiredRole) {
  const token = getToken();
  if (!token) {
    window.location.href = "/";
    return false;
  }
  if (!requiredRole) return true;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    if (payload.role !== requiredRole) {
      window.location.href = "/chat";
      return false;
    }
  } catch (e) {
    window.location.href = "/";
    return false;
  }
  return true;
}

async function logout(redirectTo = "/") {
  const token = getToken();
  if (token) {
    try {
      await fetch(API_ENDPOINTS.logout, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
    } catch (e) {
      console.warn("Logout API failed:", e);
    }
  }
  localStorage.removeItem(LS_TOKEN);
  localStorage.removeItem(LS_USER);
  window.location.href = redirectTo;
}

// ---------------------------------------------------------------------------
// App dialog — replaces native alert()/confirm()/prompt() with our own modal.
// ---------------------------------------------------------------------------
function openDialog({
  title = "",
  message = "",
  confirmText = "Confirmer",
  cancelText = "Annuler",
  danger = false,
  showCancel = true,
} = {}) {
  return new Promise((resolve) => {
    const overlay = document.createElement("div");
    overlay.className = "dialog-overlay";
    overlay.innerHTML = `
      <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="dialogTitle">
        <div class="dialog-header">
          <h2 class="dialog-title" id="dialogTitle"></h2>
          <button type="button" class="dialog-close" aria-label="Fermer">
            <svg class="icon" aria-hidden="true"><use href="/static/lib/icons.svg#i-x"></use></svg>
          </button>
        </div>
        <p class="dialog-message"></p>
        <div class="dialog-actions">
          ${showCancel ? '<button type="button" class="dialog-cancel"></button>' : ""}
          <button type="button" class="dialog-confirm"></button>
        </div>
      </div>`;

    overlay.querySelector(".dialog-title").textContent = title;
    overlay.querySelector(".dialog-message").textContent = message;

    const confirmBtn = overlay.querySelector(".dialog-confirm");
    const cancelBtn = overlay.querySelector(".dialog-cancel");
    confirmBtn.textContent = confirmText;
    if (danger) confirmBtn.classList.add("danger");
    if (cancelBtn) cancelBtn.textContent = cancelText;

    let closed = false;
    const close = (result) => {
      if (closed) return;
      closed = true;
      document.removeEventListener("keydown", onKey);
      overlay.classList.remove("open");
      setTimeout(() => overlay.remove(), 160);
      resolve(result);
    };
    const onKey = (e) => {
      if (e.key === "Escape") close(false);
      else if (e.key === "Enter") close(true);
    };

    confirmBtn.addEventListener("click", () => close(true));
    if (cancelBtn) cancelBtn.addEventListener("click", () => close(false));
    overlay
      .querySelector(".dialog-close")
      .addEventListener("click", () => close(false));
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) close(false);
    });
    document.addEventListener("keydown", onKey);

    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add("open"));
    confirmBtn.focus();
  });
}

function confirmDialog(options) {
  return openDialog({ showCancel: true, ...options });
}

function alertDialog(options) {
  return openDialog({ showCancel: false, confirmText: "OK", ...options });
}
