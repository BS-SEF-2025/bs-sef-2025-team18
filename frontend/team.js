(function() {
  'use strict';
  // Use global BACKEND_URL from window
  const BACKEND_URL = window.BACKEND_URL;

  document.addEventListener("DOMContentLoaded", async () => {
    // Check if user is an instructor - they don't have teammates
    const role = localStorage.getItem("role") || "student";
    if (role === "instructor") {
      // Instructors don't need team members, so skip loading
      return;
    }

    const container = document.getElementById("teamMembers");
    const teammateSelect = document.getElementById("teammateSelect");
    const errorEl = document.getElementById("teamError");

    const token = localStorage.getItem("access_token");
    const currentUsername = (localStorage.getItem("username") || "").toLowerCase();

    if (!token) {
      if (errorEl) errorEl.textContent = "Not logged in.";
      return;
    }

    // Fetch teammates from /peer-reviews/form
    let members = [];
    try {
      // Add timeout to prevent hanging if backend is not running
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
      
      const formRes = await fetch(`${BACKEND_URL}/peer-reviews/form`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
        },
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);

      if (!formRes.ok) {
        const text = await formRes.text().catch(() => "");
        throw new Error(`Failed to fetch teammates: HTTP ${formRes.status} ${text}`);
      }

      const formData = await formRes.json();
      members = formData.teammates || [];
      
      if (!Array.isArray(members)) {
        members = [];
      }
    } catch (e) {
      console.error("Failed to load teammates:", e);
      if (errorEl) {
        let errorMessage = e.message || "Check backend logs.";
        if (e.name === 'AbortError' || e.message.includes('Failed to fetch') || e.message.includes('NetworkError')) {
          errorMessage = `Backend server not responding. Please ensure the backend is running on ${BACKEND_URL}. Start it with: cd backend && uvicorn main:app --reload`;
        } else if (e.message.includes('401') || e.message.includes('Unauthorized')) {
          errorMessage = "Authentication failed. Please log in again.";
          setTimeout(() => {
            window.location.href = "login.html";
          }, 2000);
        } else if (e.message.includes('403') || e.message.includes('Forbidden')) {
          errorMessage = "Access denied. You may not have the required permissions.";
        }
        errorEl.textContent = `Failed to load team members: ${errorMessage}`;
        errorEl.className = "error";
      }
      return;
    }

    // Clear error
    if (errorEl) errorEl.textContent = "";

    // Populate #teamMembers (display cards)
    if (container) {
      container.innerHTML = "";

      if (members.length === 0) {
        container.innerHTML = `<p class="muted">No teammates found.</p>`;
      } else {
        members.forEach(m => {
          const card = document.createElement("div");
          card.className = "member-card";

          const displayName = m.name || m.username || "Unnamed";
          const displayEmail = m.email || "";

          card.innerHTML = `
            <div class="member-name">${escapeHtml(displayName)}</div>
            ${displayEmail ? `<div class="member-meta">${escapeHtml(displayEmail)}</div>` : ""}
          `;

          container.appendChild(card);
        });
      }
    }

    // Populate #teammateSelect (dropdown)
    if (teammateSelect) {
      // Clear existing options except the first placeholder
      teammateSelect.innerHTML = '<option value="">-- Select teammate --</option>';

      if (members.length > 0) {
        members.forEach(m => {
          const option = document.createElement("option");
          option.value = m.id;
          option.textContent = m.name || m.username || "Unnamed";
          teammateSelect.appendChild(option);
        });
      }
    }
  });

  // Helper to escape HTML
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }
})();
