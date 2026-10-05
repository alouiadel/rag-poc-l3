const form = document.getElementById("loginForm");
const usernameInput = document.getElementById("username");
const passwordInput = document.getElementById("password");
const loginButton = document.getElementById("loginBtn");
const errorMessage = document.getElementById("errorMessage");
const togglePassword = document.getElementById("togglePassword");

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.style.display = "block";
}

function hideError() {
  errorMessage.textContent = "";
  errorMessage.style.display = "none";
}

togglePassword.addEventListener("click", () => {
  const showing = passwordInput.type === "text";
  passwordInput.type = showing ? "password" : "text";
  togglePassword.textContent = showing ? "Afficher" : "Masquer";
  togglePassword.setAttribute("aria-pressed", String(!showing));
  togglePassword.setAttribute(
    "aria-label",
    showing ? "Afficher le mot de passe" : "Masquer le mot de passe",
  );
  passwordInput.focus();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const username = usernameInput.value.trim();
  const password = passwordInput.value.trim();

  if (username === "" || password === "") {
    showError("Veuillez remplir tous les champs !");
    (username ? passwordInput : usernameInput).focus();
    return;
  }

  hideError();
  loginButton.disabled = true;
  const originalLabel = loginButton.textContent;
  loginButton.textContent = "Connexion…";

  try {
    const response = await fetch(API_ENDPOINTS.login, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    const data = await response.json().catch(() => ({}));

    if (response.ok) {
      localStorage.setItem(LS_TOKEN, data.access_token);
      localStorage.setItem(LS_USER, username);
      window.location.href = "/chat";
      return;
    }

    showError(data.detail || "Login failed");
  } catch (error) {
    showError("Erreur de connexion au serveur");
  } finally {
    loginButton.disabled = false;
    loginButton.textContent = originalLabel;
  }
});
