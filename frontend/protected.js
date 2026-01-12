const BACKEND_URL = "http://127.0.0.1:8000";

const form = document.getElementById("loginForm");
const msg = document.getElementById("msg");
const btn = document.getElementById("submitBtn");

function setMessage(text, type = "info") {
  msg.textContent = text;
  msg.className = `msg ${type}`;
}

function setLoading(isLoading) {
  btn.disabled = isLoading;
  btn.textContent = isLoading ? "Logging in..." : "Login";
}

function extractDetail(data) {
  if (!data) return null;
  if (Array.isArray(data.detail)) return data.detail.map(x => x.msg).join(", ");
  return data.detail || data.message || null;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;

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
      // save token
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("role", data.role);
      localStorage.setItem("isLoggedIn", "true");

      setMessage("Logged in successfully!", "success");

      // redirect based on role (optional)
      setTimeout(() => {
        window.location.href = "index.html"; // أو صفحة ثانية عندكم
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
