const BACKEND_URL = "http://127.0.0.1:8000";

const form = document.getElementById("signupForm");
const msg = document.getElementById("msg");
const btn = document.getElementById("submitBtn");

function setMessage(text, type = "info") {
  msg.textContent = text;
  msg.className = `msg ${type}`;
}

function setLoading(isLoading) {
  btn.disabled = isLoading;
  btn.textContent = isLoading ? "Signing up..." : "Sign Up";
}

function extractDetail(data) {
  // FastAPI sometimes returns detail as array for 422 validation errors
  if (!data) return null;

  if (Array.isArray(data.detail)) {
    // [{loc:..., msg:..., type:...}, ...]
    return data.detail.map((x) => x.msg).join(", ");
  }
  return data.detail || data.message || null;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const confirmPassword = document.getElementById("confirmPassword").value;

  // role is optional in the HTML; default to student if missing
  const roleEl = document.getElementById("role");
  const role = roleEl ? roleEl.value : "student";

  if (!username || !password || !confirmPassword) {
    setMessage("Please fill in all fields.", "error");
    return;
  }

  if (password !== confirmPassword) {
    setMessage("Passwords do not match.", "error");
    return;
  }

  setLoading(true);
  setMessage("");

  try {
    const res = await fetch(`${BACKEND_URL}/auth/signup`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username,
        password,
        confirm_password: confirmPassword, // IMPORTANT: backend expects this exact name
        role, // "student" or "instructor"
      }),
    });

    const ct = res.headers.get("content-type") || "";
    const data = ct.includes("application/json") ? await res.json() : null;

    if (res.status === 201 || res.ok) {
      setMessage("Account created! Redirecting to login...", "success");
      setTimeout(() => {
        window.location.href = "login.html";
      }, 900);
      return;
    }

    if (res.status === 409) {
      setMessage("Username already exists. Choose another.", "error");
      return;
    }

    const detail = extractDetail(data) || `Signup failed (HTTP ${res.status}).`;
    setMessage(detail, "error");
  } catch (err) {
    setMessage("Network error: backend not reachable. Is it running?", "error");
  } finally {
    setLoading(false);
  }
});
