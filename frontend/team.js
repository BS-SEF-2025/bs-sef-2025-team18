(function() {
  'use strict';
  // Use global BACKEND_URL from window
  const BACKEND_URL = window.BACKEND_URL;

  document.addEventListener("DOMContentLoaded", async () => {
    const role = localStorage.getItem("role") || "student";
    const container = document.getElementById("teamMembers");
    const teammateSelect = document.getElementById("teammateSelect");
    const errorEl = document.getElementById("teamError");

    const token = localStorage.getItem("access_token");
    const currentUsername = (localStorage.getItem("username") || "").toLowerCase();

    if (!token) {
      if (errorEl) errorEl.textContent = "Not logged in.";
      return;
    }

    // Fetch teammates - instructors get all students, students get teammates
    let members = [];
    try {
      // Add timeout to prevent hanging if backend is not running
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout
      
      // Instructors fetch all students, students fetch from peer-reviews/form
      const endpoint = role === "instructor" 
        ? `${BACKEND_URL}/instructor/students`
        : `${BACKEND_URL}/peer-reviews/form`;
      
      const formRes = await fetch(endpoint, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
        },
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);

      if (!formRes.ok) {
        const text = await formRes.text().catch(() => "");
        throw new Error(`Failed to fetch team members: HTTP ${formRes.status} ${text}`);
      }

      const formData = await formRes.json();
      // Instructors get { students: [...] }, students get { teammates: [...] }
      members = formData.students || formData.teammates || [];
      
      if (!Array.isArray(members)) {
        members = [];
      }
    } catch (e) {
      console.error("Failed to load team members:", e);
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
        container.innerHTML = `<p class="muted">No team members found.</p>`;
      } else {
        members.forEach((m, index) => {
          const card = document.createElement("div");
          card.className = "member-card";

          const displayName = m.name || m.username || "Unnamed";
          const displayEmail = m.email || "";
          const initials = getInitials(displayName);
          const avatarColor = getAvatarColor(index);

          card.innerHTML = `
            <div class="member-avatar" style="background: ${avatarColor};">
              ${initials}
            </div>
            <div class="member-info">
              <div class="member-name">${escapeHtml(displayName)}</div>
              ${displayEmail ? `<div class="member-meta">${escapeHtml(displayEmail)}</div>` : `<div class="member-meta">Student</div>`}
            </div>
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

  // Get initials from name
  function getInitials(name) {
    return name
      .split(' ')
      .map(word => word.charAt(0).toUpperCase())
      .slice(0, 2)
      .join('');
  }

  // Get avatar color based on index
  function getAvatarColor(index) {
    const colors = [
      'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
      'linear-gradient(135deg, #3b82f6 0%, #6366f1 100%)',
      'linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%)',
      'linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%)',
      'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
      'linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)',
      'linear-gradient(135deg, #ec4899 0%, #8b5cf6 100%)',
      'linear-gradient(135deg, #14b8a6 0%, #10b981 100%)',
    ];
    return colors[index % colors.length];
  }
})();
