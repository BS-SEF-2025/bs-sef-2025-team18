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
      
      // Setup validation listeners after rendering
      setupValidationListeners();
    } catch (e) {
      console.error("Failed to load criteria:", e);
      if (ratingContainer) {
        let errorMessage = e.message || "Unknown error";
        if (e.name === 'AbortError') {
          errorMessage = `Backend server not responding. Please ensure the backend is running on ${BACKEND_URL}`;
        }
        ratingContainer.innerHTML = `<p class="error">Failed to load criteria: ${errorMessage}</p>`;
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
    
    // Update the character count (support both old and new structure)
    const charCountSpan = commentCount.querySelector('.char-count');
    if (charCountSpan) {
      charCountSpan.textContent = length;
    } else {
      // Fallback for old structure
      commentCount.textContent = `${length}/500`;
    }
    
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

  /**
   * Validates peer review input before submission
   * Returns an object with isValid (boolean) and errors (array of error objects)
   */
  function validatePeerReviewInput() {
    const errors = [];
    const teammateSelect = document.getElementById("teammateSelect");
    const revieweeId = teammateSelect?.value;

    // Validate teammate selection
    if (!revieweeId) {
      errors.push({
        type: "teammate",
        message: "Please select a teammate to review.",
        element: teammateSelect
      });
    }

    // Validate all criteria
    for (const criterion of criteria) {
      const ratingInput = document.querySelector(`input[name="rating-${criterion.id}"]:checked`);
      const criterionDiv = document.querySelector(`input[name="rating-${criterion.id}"]`)?.closest('.criterion-group');
      
      // Check if required criteria have ratings
      if (criterion.required && !ratingInput) {
        errors.push({
          type: "missing_rating",
          criterion_id: criterion.id,
          criterion_title: criterion.title,
          message: `Rating is required for "${criterion.title}"`,
          element: criterionDiv
        });
        continue;
      }

      // If rating exists, validate it's within scale range
      if (ratingInput) {
        const rating = Number(ratingInput.value);
        const scaleMin = criterion.scale?.min || 1;
        const scaleMax = criterion.scale?.max || 5;

        if (rating < scaleMin || rating > scaleMax) {
          errors.push({
            type: "out_of_range",
            criterion_id: criterion.id,
            criterion_title: criterion.title,
            message: `Rating for "${criterion.title}" must be between ${scaleMin} and ${scaleMax}`,
            element: criterionDiv,
            scaleMin: scaleMin,
            scaleMax: scaleMax
          });
        }
      }
    }

    return {
      isValid: errors.length === 0,
      errors: errors
    };
  }

  /**
   * Displays validation errors with visual indicators
   */
  function displayValidationErrors(validationResult) {
    // Clear previous error indicators
    clearValidationErrors();

    if (validationResult.isValid) {
      return;
    }

    const errorMessages = [];
    
    validationResult.errors.forEach(error => {
      // Handle teammate selection error
      if (error.type === "teammate" && error.element) {
        error.element.classList.add('validation-error');
        // Find the form step containing the teammate select
        const formStep = error.element.closest('.form-step');
        if (formStep) {
          let errorMsgEl = formStep.querySelector('.validation-error-message');
          if (!errorMsgEl) {
            errorMsgEl = document.createElement('div');
            errorMsgEl.className = 'validation-error-message';
            const formInputWrapper = formStep.querySelector('.form-input-wrapper');
            if (formInputWrapper) {
              formInputWrapper.appendChild(errorMsgEl);
            } else {
              formStep.appendChild(errorMsgEl);
            }
          }
          errorMsgEl.textContent = error.message;
        }
      }
      // Handle criterion errors
      else if (error.element) {
        error.element.classList.add('validation-error');
        
        // Create or update error message element
        let errorMsgEl = error.element.querySelector('.validation-error-message');
        if (!errorMsgEl) {
          errorMsgEl = document.createElement('div');
          errorMsgEl.className = 'validation-error-message';
          error.element.appendChild(errorMsgEl);
        }
        errorMsgEl.textContent = error.message;
      }

      // Collect error messages for summary
      errorMessages.push(error.message);
    });

    // Display summary error message
    if (errorMessages.length > 0) {
      const summaryMessage = errorMessages.length === 1 
        ? errorMessages[0]
        : `Please fix ${errorMessages.length} validation error(s): ${errorMessages.join('; ')}`;
      setSubmitMessage(summaryMessage, "error");
    }
  }

  /**
   * Clears all validation error indicators
   */
  function clearValidationErrors() {
    // Remove error classes and error message elements from criterion groups
    document.querySelectorAll('.criterion-group').forEach(group => {
      group.classList.remove('validation-error');
      const errorMsg = group.querySelector('.validation-error-message');
      if (errorMsg) {
        errorMsg.remove();
      }
    });

    // Clear teammate select error
    const teammateSelect = document.getElementById("teammateSelect");
    if (teammateSelect) {
      teammateSelect.classList.remove('validation-error');
      // Remove error message from form step
      const formStep = teammateSelect.closest('.form-step');
      if (formStep) {
        const errorMsg = formStep.querySelector('.validation-error-message');
        if (errorMsg) {
          errorMsg.remove();
        }
      }
    }
  }

  /**
   * Updates validation state when user interacts with form
   */
  function setupValidationListeners() {
    // Clear errors when user selects a teammate
    const teammateSelect = document.getElementById("teammateSelect");
    if (teammateSelect) {
      teammateSelect.addEventListener('change', () => {
        clearValidationErrors();
        setSubmitMessage("", "");
      });
    }

    // Use event delegation for dynamically created rating inputs
    // Listen on the rating container for change events on radio buttons
    const ratingContainer = document.getElementById("ratingContainer");
    if (ratingContainer) {
      ratingContainer.addEventListener('change', (e) => {
        if (e.target.type === 'radio' && e.target.name.startsWith('rating-')) {
          const criterionGroup = e.target.closest('.criterion-group');
          if (criterionGroup) {
            criterionGroup.classList.remove('validation-error');
            const errorMsg = criterionGroup.querySelector('.validation-error-message');
            if (errorMsg) {
              errorMsg.remove();
            }
            // Clear summary message if all errors are resolved
            const validationResult = validatePeerReviewInput();
            if (validationResult.isValid) {
              setSubmitMessage("", "");
            }
          }
        }
      });
    }
  }

  async function handleSubmit() {
    const token = localStorage.getItem("access_token");
    const submitReviewBtn = document.getElementById("submitReviewBtn");

    if (!token) {
      setSubmitMessage("You are not logged in.", "error");
      window.location.href = "login.html";
      return;
    }

    // Validate input before proceeding
    const validationResult = validatePeerReviewInput();
    
    if (!validationResult.isValid) {
      // Display validation errors and prevent submission
      displayValidationErrors(validationResult);
      return;
    }

    // Clear any previous error indicators since validation passed
    clearValidationErrors();

    const teammateSelect = document.getElementById("teammateSelect");
    const revieweeId = teammateSelect?.value;

    // Save current comment
    if (currentTeammateId) {
      const commentBox = document.getElementById("commentBox");
      if (commentBox) {
        commentsByTeammate[currentTeammateId] = commentBox.value;
      }
    }

    // Collect ratings for all criteria (validation already passed, so we can safely collect)
    const answers = [];
    for (const criterion of criteria) {
      const ratingInput = document.querySelector(`input[name="rating-${criterion.id}"]:checked`);
      
      // Only include answered criteria (required ones are guaranteed to be answered after validation)
      if (ratingInput) {
        const rating = Number(ratingInput.value);
        answers.push({
          criterion_id: criterion.id,
          rating: rating
        });
      }
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
      const buttonText = submitReviewBtn.querySelector("span:last-child");
      if (buttonText) {
        buttonText.textContent = "Submitting...";
      } else {
        submitReviewBtn.textContent = "Submitting...";
      }
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
        // Show prominent confirmation message
        setSubmitMessage("✓ Peer review submitted successfully! Thank you for your feedback.", "success");
        
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

        // Reset teammate selection to show form is ready for next review
        if (teammateSelect) {
          teammateSelect.value = "";
          currentTeammateId = null;
        }

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
        const buttonText = submitReviewBtn.querySelector("span:last-child");
        if (buttonText) {
          buttonText.textContent = "Submit Review";
        } else {
          submitReviewBtn.textContent = "Submit Review";
        }
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
