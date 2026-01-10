(function () {
  const isLoggedIn = localStorage.getItem("isLoggedIn") === "true";
  if (!isLoggedIn) {
    window.location.href = "login.html";
  }
})();
fetch("http://127.0.0.1:8000/auth/login", {
  method: "POST",
  headers: {
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    username,
    password
  })
})
.then(res => res.json())
.then(data => {
  localStorage.setItem("isLoggedIn", "true");   // 🔑 مهم
  localStorage.setItem("token", data.access_token); // 🔑 مهم
  window.location.href = "dashboard.html";
});
