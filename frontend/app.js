const API_BASE = "http://127.0.0.1:8000";

document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value.trim();
  const msg = document.getElementById("msg");
  msg.textContent = "";

  try {
    const res = await fetch(`${API_BASE}/login`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ username, password })
    });

    const data = await res.json();

    if (!res.ok) {
      msg.textContent = data.detail || "Login failed";
      return;
    }

    msg.style.color = "green";
    msg.textContent = `Logged in! Token: ${data.token}`;
  } catch (err) {
    msg.textContent = "Cannot connect to server. Is backend running?";
  }
});
