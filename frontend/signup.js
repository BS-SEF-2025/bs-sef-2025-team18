// Use global BACKEND_URL from window
const BACKEND_URL = window.BACKEND_URL;

const form = document.getElementById("signupForm");
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
  btn.textContent = isLoading ? "Signing up..." : "Sign Up";
}

function extractDetail(data) {
  if (!data) return null;
  if (Array.isArray(data.detail)) {
    return data.detail.map((x) => x.msg || x.message || String(x)).join(", ");
  }
  return data.detail || data.message || null;
}

if (form) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const email = document.getElementById("email").value.trim();
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const confirmPassword = document.getElementById("confirmPassword").value;
    const role = document.getElementById("role").value;

    if (!email || !username || !password || !confirmPassword || !role) {
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
          email,
          username,
          password,
          confirm_password: confirmPassword,
          role,
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
        const detail = extractDetail(data) || "Username or email already exists.";
        setMessage(detail, "error");
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
}
