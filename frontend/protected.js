const BACKEND_URL = "http://127.0.0.1:8000";

// ---------- helpers ----------
function getToken() {
  return localStorage.getItem("access_token"); // from your login
}

function isPublicPage() {
  const page = (window.location.pathname.split("/").pop() || "").toLowerCase();
  return page === "login.html" || page === "signup.html" || page === "";
}

function redirectToLogin() {
  window.location.href = "login.html";
}

function extractDetail(data) {
  if (!data) return null;
  if (Array.isArray(data.detail)) return data.detail.map(x => x.msg).join(", ");
  return data.detail || data.message || null;
}

// Collect ratings in a generic way (won't break if ratings UI isn't there yet)
function collectRatingsFromUI() {
  // Looks for inputs named like: rating-<criterion>
  const inputs = Array.from(document.querySelectorAll('input[name^="rating-"]'));
  if (inputs.length === 0) return {};

  const criteria = new Set(inputs.map(i => i.name.replace("rating-", "")));
  const ratings = {};

  for (const c of criteria) {
    const selected = document.querySelector(`input[name="rating-${c}"]:checked`);
    if (!selected) {
      // If ratings exist in UI but missing selection, fail clearly
      throw new Error(`Missing rating for: ${c}`);
    }
    ratings[c] = Number(selected.value);
  }
  return ratings;
}

document.addEventListener("DOMContentLoaded", () => {
  // ---------- page protection ----------
  // Any page except login/signup requires auth
  if (!isPublicPage()) {
    const token = getToken();
    if (!token) {
      redirectToLogin();
      return;
    }
  }

  // ---------- LOGIN HANDLER (only if loginForm exists) ----------
  const form = document.getElementById("loginForm");
  if (form) {
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

    form.addEventListener("submit", async (e) => {
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
          // save token
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("role", data.role);
          localStorage.setItem("isLoggedIn", "true");
          localStorage.setItem("username", username);

          setMessage("Logged in successfully!", "success");

          setTimeout(() => {
            // Redirect to dashboard (change to index.html if that's your main page)
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

  // ---------- PEER REVIEW COMMENT (only if elements exist) ----------
  const teammateSelect = document.getElementById("teammateSelect");
  const commentBox = document.getElementById("commentBox");
  const commentCount = document.getElementById("commentCount");
  const submitReviewBtn = document.getElementById("submitReviewBtn");

  if (teammateSelect && commentBox && commentCount) {
    const commentsByTeammate = {};
    let currentTeammateId = null;

    function updateCommentCounter() {
      commentCount.textContent = `${commentBox.value.length}/500`;
    }

    function handleTeammateChange() {
      const newId = teammateSelect.value;

      // Save previous teammate comment
      if (currentTeammateId) {
        commentsByTeammate[currentTeammateId] = commentBox.value;
      }

      currentTeammateId = newId || null;

      // Load new teammate comment
      commentBox.value = (currentTeammateId && commentsByTeammate[currentTeammateId]) ? commentsByTeammate[currentTeammateId] : "";
      updateCommentCounter();
    }

    commentBox.addEventListener("input", updateCommentCounter);
    teammateSelect.addEventListener("change", handleTeammateChange);

    // Init
    currentTeammateId = teammateSelect.value || null;
    updateCommentCounter();
    if (currentTeammateId) handleTeammateChange();

    // Submit review (if button exists)
    if (submitReviewBtn) {
      submitReviewBtn.addEventListener("click", async () => {
        const token = getToken();
        if (!token) {
          alert("You are not logged in.");
          redirectToLogin();
          return;
        }

        const revieweeId = teammateSelect.value;
        if (!revieweeId) {
          alert("Please select a teammate.");
          return;
        }

        // Save current comment
        commentsByTeammate[revieweeId] = commentBox.value;

        let ratings = {};
        try {
          ratings = collectRatingsFromUI();
        } catch (e) {
          alert(e.message);
          return;
        }

        const payload = {
          reviewee_id: revieweeId,
          ratings: ratings,
          comment: (commentBox.value || "").trim(),
        };

        try {
          const res = await fetch(`${BACKEND_URL}/reviews`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Authorization": `Bearer ${token}`,
            },
            body: JSON.stringify(payload),
          });

          const ct = res.headers.get("content-type") || "";
          const data = ct.includes("application/json") ? await res.json() : null;

          if (res.ok) {
            alert("Review submitted!");
            return;
          }

          if (res.status === 401) {
            alert("Unauthorized. Please login again.");
            redirectToLogin();
            return;
          }

          const detail = extractDetail(data) || `Submit failed (HTTP ${res.status}).`;
          alert(detail);
        } catch (err) {
          alert("Network error: backend not reachable. Is it running?");
        }
      });
    }
  }
});
