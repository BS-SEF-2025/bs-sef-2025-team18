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
  const buttonText = btn.querySelector(".button-text");
  if (buttonText) {
    buttonText.textContent = isLoading ? "Signing up..." : "Sign up";
  } else {
    // Fallback if button-text element doesn't exist
    btn.textContent = isLoading ? "Signing up..." : "Sign up";
  }
}

function extractDetail(data) {
  if (!data) return null;
  if (Array.isArray(data.detail)) {
    return data.detail.map((x) => x.msg || x.message || String(x)).join(", ");
  }
  return data.detail || data.message || null;
}

// ✅ Single dashboard redirect
function redirectToDashboard() {
  window.location.replace("dashboard.html");
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
      console.log("Attempting signup for:", username);
      console.log("Backend URL:", BACKEND_URL);

      const signupUrl = `${BACKEND_URL}/auth/signup`;
      const res = await fetch(signupUrl, {
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

      console.log("Response received. Status:", res.status, res.statusText);

      const ct = res.headers.get("content-type") || "";
      let data = null;

      try {
        const responseText = await res.text();
        console.log("Response status:", res.status);
        console.log("Request URL was:", signupUrl);
        console.log("Response body (first 500 chars):", responseText.substring(0, 500));

        // Handle 404 Not Found immediately
        if (res.status === 404) {
          let errorMsg = `The endpoint ${signupUrl} was not found. `;
          errorMsg += "Please ensure the backend server is running. ";
          errorMsg +=
            "From the backend folder, run: python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000";
          setMessage(errorMsg, "error");
          setLoading(false);
          return;
        }

        if (ct.includes("application/json") || responseText.trim().startsWith("{")) {
          try {
            data = JSON.parse(responseText);
          } catch (jsonErr) {
            console.error("JSON parse error:", jsonErr);
            if (responseText.includes("Not Found") || responseText.includes('"detail":"Not Found"')) {
              setMessage(`The endpoint ${signupUrl} was not found. Please ensure the backend is running.`, "error");
            } else {
              setMessage("Failed to parse server response. Please check backend.", "error");
            }
            setLoading(false);
            return;
          }
        } else {
          console.error("Non-JSON response received. Full response:", responseText);
          let errorMsg = "Server returned non-JSON response. ";
          if (responseText.includes("404") || responseText.includes("Not Found")) {
            errorMsg += `The endpoint ${signupUrl} was not found. Is the backend running?`;
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

      // ✅ SIGNUP SUCCESS
      if (res.status === 201 || res.ok) {
        // Automatically log in the user after successful signup
        try {
          // Small delay to ensure user is fully created in database
          await new Promise((resolve) => setTimeout(resolve, 200));

          console.log("Attempting auto-login for:", username);

          const loginUrl = `${BACKEND_URL}/auth/login`;

          // Login endpoint expects JSON (same as regular login form)
          const loginRes = await fetch(loginUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password }),
          });

          const loginCt = loginRes.headers.get("content-type") || "";
          let loginData = null;

          try {
            const loginResponseText = await loginRes.text();
            console.log("Login response status:", loginRes.status);
            console.log("Login response text (first 500 chars):", loginResponseText.substring(0, 500));

            if (loginCt.includes("application/json") || loginResponseText.trim().startsWith("{")) {
              loginData = JSON.parse(loginResponseText);
            } else {
              console.error("Non-JSON login response:", loginResponseText);
            }
          } catch (parseErr) {
            console.error("Failed to parse login response:", parseErr);
          }

          if (loginRes.ok && loginData && loginData.access_token) {
            // Save auth data
            localStorage.setItem("access_token", loginData.access_token);
            localStorage.setItem("role", loginData.role || role);
            localStorage.setItem("isLoggedIn", "true");
            localStorage.setItem("username", username);

            // ✅ Redirect immediately into the app
            redirectToDashboard();
            return;
          }

          // If auto-login fails, still guide user
          console.error("Auto-login failed. Status:", loginRes.status, "Data:", loginData);
          setMessage("✓ Account created successfully! Please log in to continue.", "success");
          setLoading(false);

          setTimeout(() => {
            window.location.href = "login.html";
          }, 1200);
        } catch (loginErr) {
          console.error("Auto-login error:", loginErr);
          setMessage("✓ Account created successfully! Please log in to continue.", "success");
          setLoading(false);

          setTimeout(() => {
            window.location.href = "login.html";
          }, 1200);
        }
        return;
      }

      // Other errors
      if (res.status === 409) {
        const detail = extractDetail(data) || "Username or email already exists.";
        setMessage(detail, "error");
        setLoading(false);
        return;
      }

      const detail = extractDetail(data) || `Signup failed (HTTP ${res.status}).`;
      setMessage(detail, "error");
      setLoading(false);
    } catch (err) {
      console.error("Signup error:", err);
      console.error("Error name:", err.name);
      console.error("Error message:", err.message);

      if (
        err.message &&
        (err.message.includes("Failed to fetch") ||
          err.message.includes("NetworkError") ||
          err.message.includes("Load failed"))
      ) {
        setMessage(
          "Cannot connect to backend server. Please ensure the backend is running. From the backend folder, run: python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000",
          "error"
        );
      } else {
        setMessage("Connection error: " + (err.message || err.toString()), "error");
      }
      setLoading(false);
    }
  });
}
