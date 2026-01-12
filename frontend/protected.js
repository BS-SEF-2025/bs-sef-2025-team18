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
      const buttonText = btn.querySelector(".button-text");
      if (buttonText) {
        buttonText.textContent = isLoading ? "Logging in..." : "Log In";
      } else {
        // Fallback if button-text element doesn't exist
        btn.textContent = isLoading ? "Logging in..." : "Log In";
      }
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
        console.log("Attempting login for:", username);
        console.log("Backend URL:", BACKEND_URL);
        const res = await fetch(`${BACKEND_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });

        console.log("Response received. Status:", res.status, res.statusText);

        const ct = res.headers.get("content-type") || "";
        let data = null;
        
        try {
          const responseText = await res.text();
          console.log("Response status:", res.status);
          console.log("Response headers:", Object.fromEntries(res.headers.entries()));
          console.log("Response body (first 500 chars):", responseText.substring(0, 500));
          console.log("Request URL was:", `${BACKEND_URL}/auth/login`);
          
          if (ct.includes("application/json") || responseText.trim().startsWith("{")) {
            data = JSON.parse(responseText);
          } else {
            console.error("Non-JSON response received. Full response:", responseText);
            // Show more helpful error message
            let errorMsg = "Server returned non-JSON response. ";
            if (responseText.includes("404") || responseText.includes("Not Found")) {
              errorMsg += `The endpoint ${BACKEND_URL}/auth/login was not found. Is the backend running?`;
            } else if (responseText.includes("<!DOCTYPE") || responseText.includes("<html")) {
              errorMsg += "Received HTML instead of JSON. The backend might not be running or the URL is incorrect.";
            } else {
              errorMsg += `Response: ${responseText.substring(0, 200)}`;
            }
            setMessage(errorMsg, "error");
            setLoading(false);
            return;
          }
        } catch (parseErr) {
          console.error("Failed to parse response:", parseErr);
          setMessage("Failed to parse server response. Please check backend.", "error");
          setLoading(false);
          return;
        }

        if (res.ok && data && data.access_token) {
          // Save auth data
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("role", data.role || "student");
          localStorage.setItem("isLoggedIn", "true");
          localStorage.setItem("username", username);

          setMessage("Logged in successfully! Redirecting...", "success");
          setLoading(false);

          // Redirect immediately
          window.location.href = "dashboard.html";
          return;
        }
        
        // If we get here, the response was ok but missing required data
        if (res.ok && (!data || !data.access_token)) {
          console.error("Missing access_token in response:", data);
          setMessage("Login response missing token. Please try again.", "error");
          setLoading(false);
          return;
        }

        // Handle error response
        const detail = extractDetail(data) || `Login failed (HTTP ${res.status}).`;
        setMessage(detail, "error");
        setLoading(false);
      } catch (err) {
        console.error("Login error:", err);
        console.error("Error name:", err.name);
        console.error("Error message:", err.message);
        
        if (err.message && (err.message.includes("Failed to fetch") || err.message.includes("NetworkError") || err.message.includes("Load failed"))) {
          setMessage("Cannot connect to backend server. Please ensure the backend is running. From the backend folder, run: python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000", "error");
        } else {
          setMessage("Connection error: " + (err.message || err.toString()), "error");
        }
        setLoading(false);
      }
    });
  }
});
