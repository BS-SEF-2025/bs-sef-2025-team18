const BACKEND_URL = "http://127.0.0.1:8000";

document.addEventListener("DOMContentLoaded", async () => {
  const container = document.getElementById("teamMembers");
  const errorEl = document.getElementById("teamError");

  const token = localStorage.getItem("access_token");
  const currentUsername = (localStorage.getItem("username") || "").toLowerCase();

  if (!token) {
    errorEl.textContent = "Not logged in.";
    return;
  }

  const MEMBERS_ENDPOINT = `${BACKEND_URL}/team/members`; // عدّل إذا لازم

  try {
    const res = await fetch(MEMBERS_ENDPOINT, {
      method: "GET",
      headers: {
        "Authorization": `Bearer ${token}`,
      },
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status} ${text}`);
    }

    const members = await res.json();

    const filtered = members.filter(m => {
      const u = (m.username || "").toLowerCase();
      // إذا backend ما برجع username، ما نستثني (بس ما نخرب)
      if (!u) return true;
      return u !== currentUsername;
    });

    container.innerHTML = "";

    if (!Array.isArray(filtered) || filtered.length === 0) {
      container.innerHTML = `<p class="muted">No teammates found.</p>`;
      return;
    }

    filtered.forEach(m => {
      const card = document.createElement("div");
      card.className = "member-card";

      const displayName = m.name || m.username || "Unnamed";
      const displayEmail = m.email || "";

      card.innerHTML = `
        <div class="member-name">${displayName}</div>
        ${displayEmail ? `<div class="member-meta">${displayEmail}</div>` : ""}
      `;

      container.appendChild(card);
    });

  } catch (e) {
    console.error(e);
    errorEl.textContent = "Failed to load team members. Check /team/members and backend logs.";
  }
});
