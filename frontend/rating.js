const BACKEND_URL = "http://127.0.0.1:8000";

// مؤقتاً (لو 1.2 مش جاهز) — استبدله ببيانات من API لاحقاً
const CRITERIA = [
  { id: "c1", title: "Contribution" },
  { id: "c2", title: "Communication" },
  { id: "c3", title: "Reliability" },
];

function createRatingGroup(teammateUsername, criterionId) {
  const wrapper = document.createElement("div");
  wrapper.className = "rating-group";

  // 1..5
  for (let val = 1; val <= 5; val++) {
    const label = document.createElement("label");
    label.className = "rating-option";

    const input = document.createElement("input");
    input.type = "radio";
    input.name = `rate__${teammateUsername}__${criterionId}`; // unique group per teammate+criterion
    input.value = String(val);

    label.appendChild(input);
    label.appendChild(document.createTextNode(String(val)));
    wrapper.appendChild(label);
  }

  return wrapper;
}

async function loadTeammates() {
  const token = localStorage.getItem("access_token");
  const currentUsername = (localStorage.getItem("username") || "").toLowerCase();
  const MEMBERS_ENDPOINT = `${BACKEND_URL}/team/members`;

  const res = await fetch(MEMBERS_ENDPOINT, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`members HTTP ${res.status}`);
  const members = await res.json();

  return members.filter(m => (m.username || "").toLowerCase() !== currentUsername);
}

document.addEventListener("DOMContentLoaded", async () => {
  const root = document.getElementById("peerReview");
  const err = document.getElementById("reviewError");

  try {
    const teammates = await loadTeammates();

    root.innerHTML = "";
    teammates.forEach(t => {
      const card = document.createElement("div");
      card.className = "review-card";

      const title = document.createElement("h3");
      title.textContent = t.name || t.username;
      card.appendChild(title);

      CRITERIA.forEach(c => {
        const row = document.createElement("div");
        row.className = "criterion-row";

        const label = document.createElement("div");
        label.className = "criterion-title";
        label.textContent = c.title;

        row.appendChild(label);
        row.appendChild(createRatingGroup(t.username, c.id));
        card.appendChild(row);
      });

      root.appendChild(card);
    });
  } catch (e) {
    console.error(e);
    err.textContent = "Failed to build rating UI. Check backend /team/members.";
  }
});
