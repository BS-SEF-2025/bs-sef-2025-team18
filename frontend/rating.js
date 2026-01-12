(function() {
  'use strict';
  // Use global BACKEND_URL from window
  const BACKEND_URL = window.BACKEND_URL;

  let criteria = [];
  let commentsByTeammate = {};
  let currentTeammateId = null;

  document.addEventListener("DOMContentLoaded", async () => {
    const ratingContainer = document.getElementById("ratingContainer");
    const teammateSelect = document.getElementById("teammateSelect");
    const commentBox = document.getElementById("commentBox");
    const commentCount = document.getElementById("commentCount");
    const submitReviewBtn = document.getElementById("submitReviewBtn");
    const submitMessage = document.getElementById("submitMessage");

    const token = localStorage.getItem("access_token");

    if (!token) {
      return;
    }

    // Load criteria from /peer-reviews/form
    try {
      const formRes = await fetch(`${BACKEND_URL}/peer-reviews/form`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
        },
      });

      if (!formRes.ok) {
        throw new Error(`Failed to fetch criteria: HTTP ${formRes.status}`);
      }

      const formData = await formRes.json();
      criteria = formData.criteria || [];

      if (criteria.length === 0) {
        if (ratingContainer) {
          ratingContainer.innerHTML = '<p class="muted">No criteria available.</p>';
        }
        return;
      }

      // Render rating inputs
      renderRatingInputs();
    } catch (e) {
      console.error("Failed to load criteria:", e);
      if (ratingContainer) {
        ratingContainer.innerHTML = `<p class="error">Failed to load criteria: ${e.message}</p>`;
      }
      return;
    }

    // Handle teammate selection change
    if (teammateSelect) {
      teammateSelect.addEventListener("change", () => {
        handleTeammateChange();
      });
    }

    // Handle comment input
    if (commentBox && commentCount) {
      commentBox.addEventListener("input", () => {
        updateCommentCounter();
      });
    }

    // Handle submit
    if (submitReviewBtn) {
      submitReviewBtn.addEventListener("click", async () => {
        await handleSubmit();
      });
    }

    // Initialize
    if (commentCount) {
      updateCommentCounter();
    }
  });

  function renderRatingInputs() {
    const ratingContainer = document.getElementById("ratingContainer");
    if (!ratingContainer) return;

    ratingContainer.innerHTML = "";

    if (criteria.length === 0) {
      ratingContainer.innerHTML = '<p class="muted">No criteria available.</p>';
      return;
    }

    criteria.forEach(criterion => {
      const criterionDiv = document.createElement("div");
      criterionDiv.className = "criterion-group";

      const label = document.createElement("label");
      label.className = "criterion-label";
      label.textContent = criterion.title;
      if (criterion.required) {
        label.innerHTML += ' <span class="required">*</span>';
      }

      const ratingGroup = document.createElement("div");
      ratingGroup.className = "rating-group";

      const scaleMin = criterion.scale?.min || 1;
      const scaleMax = criterion.scale?.max || 5;

      for (let val = scaleMin; val <= scaleMax; val++) {
        const labelEl = document.createElement("label");
        labelEl.className = "rating-option";

        const input = document.createElement("input");
        input.type = "radio";
        input.name = `rating-${criterion.id}`;
        input.value = String(val);
        input.id = `rating-${criterion.id}-${val}`;
        input.required = criterion.required || false;

        const span = document.createElement("span");
        span.textContent = val;

        labelEl.appendChild(input);
        labelEl.appendChild(span);
        ratingGroup.appendChild(labelEl);
      }

      criterionDiv.appendChild(label);
      criterionDiv.appendChild(ratingGroup);
      ratingContainer.appendChild(criterionDiv);
    });
  }

  function handleTeammateChange() {
    const teammateSelect = document.getElementById("teammateSelect");
    const commentBox = document.getElementById("commentBox");

    if (!teammateSelect || !commentBox) return;

    const newId = teammateSelect.value;

    // Save previous teammate comment
    if (currentTeammateId) {
      commentsByTeammate[currentTeammateId] = commentBox.value;
    }

    currentTeammateId = newId || null;

    // Load new teammate comment
    if (currentTeammateId && commentsByTeammate[currentTeammateId]) {
      commentBox.value = commentsByTeammate[currentTeammateId];
    } else {
      commentBox.value = "";
    }

    updateCommentCounter();
  }

  function updateCommentCounter() {
    const commentBox = document.getElementById("commentBox");
    const commentCount = document.getElementById("commentCount");

    if (!commentBox || !commentCount) return;

    const length = commentBox.value.length;
    commentCount.textContent = `${length}/500`;
    
    if (length > 450) {
      commentCount.classList.add("warning");
    } else {
      commentCount.classList.remove("warning");
    }
  }

  function setSubmitMessage(text, type = "info") {
    const submitMessage = document.getElementById("submitMessage");
    if (!submitMessage) return;
    submitMessage.textContent = text;
    submitMessage.className = `msg ${type}`;
  }

  async function handleSubmit() {
    const token = localStorage.getItem("access_token");
    const teammateSelect = document.getElementById("teammateSelect");
    const submitReviewBtn = document.getElementById("submitReviewBtn");

    if (!token) {
      setSubmitMessage("You are not logged in.", "error");
      window.location.href = "login.html";
      return;
    }

    const revieweeId = teammateSelect?.value;
    if (!revieweeId) {
      setSubmitMessage("Please select a teammate.", "error");
      return;
    }

    // Save current comment
    if (currentTeammateId) {
      const commentBox = document.getElementById("commentBox");
      if (commentBox) {
        commentsByTeammate[currentTeammateId] = commentBox.value;
      }
    }

    // Collect ratings for all criteria
    const answers = [];
    for (const criterion of criteria) {
      const ratingInput = document.querySelector(`input[name="rating-${criterion.id}"]:checked`);
      
      if (!ratingInput) {
        if (criterion.required) {
          setSubmitMessage(`Please provide a rating for "${criterion.title}".`, "error");
          return;
        }
        continue; // Skip optional criteria without ratings
      }

      const rating = Number(ratingInput.value);
      const scaleMin = criterion.scale?.min || 1;
      const scaleMax = criterion.scale?.max || 5;

      if (rating < scaleMin || rating > scaleMax) {
        setSubmitMessage(`Rating for "${criterion.title}" must be between ${scaleMin} and ${scaleMax}.`, "error");
        return;
      }

      answers.push({
        criterion_id: criterion.id,
        rating: rating
      });
    }

    // Build payload matching backend schema
    const payload = {
      reviews: [
        {
          teammate_id: Number(revieweeId),
          answers: answers
        }
      ]
    };

    // Disable submit button
    if (submitReviewBtn) {
      submitReviewBtn.disabled = true;
      submitReviewBtn.textContent = "Submitting...";
    }

    try {
      const res = await fetch(`${BACKEND_URL}/peer-reviews/submit`, {
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
        setSubmitMessage("Review submitted successfully!", "success");
        
        // Clear the comment for this teammate after successful submission
        if (revieweeId) {
          commentsByTeammate[revieweeId] = "";
          const commentBox = document.getElementById("commentBox");
          if (commentBox) {
            commentBox.value = "";
            updateCommentCounter();
          }
        }

        // Reset rating inputs
        document.querySelectorAll('input[type="radio"]:checked').forEach(input => {
          input.checked = false;
        });

        return;
      }

      if (res.status === 401) {
        setSubmitMessage("Unauthorized. Please login again.", "error");
        setTimeout(() => {
          window.location.href = "login.html";
        }, 1500);
        return;
      }

      if (res.status === 409) {
        const detail = extractDetail(data) || "Conflict: This review may have already been submitted.";
        setSubmitMessage(detail, "error");
        return;
      }

      if (res.status === 400 || res.status === 422) {
        const detail = extractDetail(data) || "Validation error: Please check your input.";
        setSubmitMessage(detail, "error");
        return;
      }

      const detail = extractDetail(data) || `Submit failed (HTTP ${res.status}).`;
      setSubmitMessage(detail, "error");
    } catch (err) {
      setSubmitMessage("Network error: backend not reachable. Is it running?", "error");
    } finally {
      if (submitReviewBtn) {
        submitReviewBtn.disabled = false;
        submitReviewBtn.textContent = "Submit Review";
      }
    }
  }

  function extractDetail(data) {
    if (!data) return null;
    if (Array.isArray(data.detail)) {
      return data.detail.map((x) => x.msg || x.message || String(x)).join(", ");
    }
    return data.detail || data.message || null;
  }
})();
