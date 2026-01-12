// Use global BACKEND_URL from window
const BACKEND_URL = window.BACKEND_URL;

// ---------- Helper Functions ----------
function getToken() {
  return localStorage.getItem("access_token");
}

function isPublicPage() {
  const page = (window.location.pathname.split("/").pop() || "").toLowerCase();
  return page === "login.html" || page === "signup.html" || page === "" || page === "index.html";
}

function redirectToLogin() {
  window.location.href = "login.html";
}

function extractDetail(data) {
  if (!data) return null;
  if (Array.isArray(data.detail)) {
    return data.detail.map((x) => x.msg || x.message || String(x)).join(", ");
  }
  return data.detail || data.message || null;
}

// ---------- Page Protection ----------
document.addEventListener("DOMContentLoaded", () => {
  // Protect pages except login/signup
  if (!isPublicPage()) {
    const token = getToken();
    if (!token) {
      redirectToLogin();
      return;
    }
  }

  // ---------- Login Handler ----------
  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    const msg = document.getElementById("msg");
    const btn = document.getElementById("submitBtn");

    function setMessage(text, type = "info") {
      if (!msg) return;
      msg.textContent = text;
      msg.className = `msg ${type}`;
    }

    function setLoading(isLoading) {
      if (!btn) return;
      btn.disabled = isLoading;
      btn.textContent = isLoading ? "Logging in..." : "Login";
    }

    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();

      const usernameEl = document.getElementById("username");
      const passwordEl = document.getElementById("password");

      const username = (usernameEl?.value || "").trim();
      const password = passwordEl?.value || "";

      if (!username || !password) {
        setMessage("Please fill in all fields.", "error");
        return;
      }

      setLoading(true);
      setMessage("");

      try {
        const res = await fetch(`${BACKEND_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });

        const ct = res.headers.get("content-type") || "";
        const data = ct.includes("application/json") ? await res.json() : null;

        if (res.ok) {
          // Save auth data
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("role", data.role);
          localStorage.setItem("isLoggedIn", "true");
          localStorage.setItem("username", username);

          setMessage("Logged in successfully!", "success");

          setTimeout(() => {
            window.location.href = "dashboard.html";
          }, 600);
          return;
        }

        const detail = extractDetail(data) || `Login failed (HTTP ${res.status}).`;
        setMessage(detail, "error");
      } catch (err) {
        setMessage("Network error: backend not reachable. Is it running?", "error");
      } finally {
        setLoading(false);
      }
    });
  }
});
