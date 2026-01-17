(function() {
  'use strict';
  // Use global BACKEND_URL from window
  const BACKEND_URL = window.BACKEND_URL;

  let criteria = [];
  let commentsByTeammate = {};
  let currentTeammateId = null;
  let submittedReviews = {}; // Store submitted reviews by teammate_id

  // Helper functions for localStorage
  function getStorageKey(teammateId) {
    const username = localStorage.getItem("username") || "unknown";
    return `peer_review_${username}_${teammateId}`;
  }

  function loadSubmittedReviews() {
    const username = localStorage.getItem("username") || "unknown";
    const stored = localStorage.getItem(`peer_reviews_${username}`);
    if (stored) {
      try {
        submittedReviews = JSON.parse(stored);
      } catch (e) {
        console.error("Failed to parse stored reviews:", e);
        submittedReviews = {};
      }
    }
  }

  function saveSubmittedReviews() {
    const username = localStorage.getItem("username") || "unknown";
    localStorage.setItem(`peer_reviews_${username}`, JSON.stringify(submittedReviews));
  }

  function storeSubmittedReview(teammateId, reviewData) {
    submittedReviews[teammateId] = reviewData;
    saveSubmittedReviews();
  }

  function getSubmittedReview(teammateId) {
    return submittedReviews[teammateId] || null;
  }

  async function loadReviewIntoForm(teammateId) {
    const token = localStorage.getItem("access_token");
    if (!token) {
      setSubmitMessage("Not authenticated. Please log in.", "error");
      return false;
    }

    // Save current scroll position to prevent auto-scrolling
    const scrollPosition = window.pageYOffset || document.documentElement.scrollTop;

    try {
      // Try to load from backend first
      const res = await fetch(`${BACKEND_URL}/peer-reviews/submitted/${teammateId}`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
        },
      });

      if (res.ok) {
        const data = await res.json();
        if (data.submitted && data.answers && data.answers.length > 0) {
          // Load ratings from backend without scrolling
          data.answers.forEach(answer => {
            const input = document.querySelector(`input[name="rating-${answer.criterion_id}"][value="${answer.rating}"]`);
            if (input) {
              // Prevent scrolling when checking radio buttons
              input.checked = true;
              // Remove focus to prevent scroll
              if (document.activeElement === input) {
                input.blur();
              }
            }
          });

          // Load comment from localStorage if available (comments aren't stored in backend)
          const review = getSubmittedReview(teammateId);
          if (review && review.comment !== undefined) {
            const commentBox = document.getElementById("commentBox");
            if (commentBox) {
              commentBox.value = review.comment || "";
              updateCommentCounter();
              // Remove focus to prevent scroll
              if (document.activeElement === commentBox) {
                commentBox.blur();
              }
            }
            commentsByTeammate[teammateId] = review.comment || "";
          }

          // Restore scroll position
          window.scrollTo(0, scrollPosition);
          return true;
        }
      } else if (res.status === 404) {
        // No review found, try localStorage as fallback
        const review = getSubmittedReview(teammateId);
        if (review && review.answers) {
          review.answers.forEach(answer => {
            const input = document.querySelector(`input[name="rating-${answer.criterion_id}"][value="${answer.rating}"]`);
            if (input) {
              input.checked = true;
              // Remove focus to prevent scroll
              if (document.activeElement === input) {
                input.blur();
              }
            }
          });

          if (review.comment !== undefined) {
            const commentBox = document.getElementById("commentBox");
            if (commentBox) {
              commentBox.value = review.comment || "";
              updateCommentCounter();
              // Remove focus to prevent scroll
              if (document.activeElement === commentBox) {
                commentBox.blur();
              }
            }
            commentsByTeammate[teammateId] = review.comment || "";
          }
          // Restore scroll position
          window.scrollTo(0, scrollPosition);
          return true;
        }
      }
    } catch (e) {
      console.error("Failed to load review from backend:", e);
      // Fallback to localStorage
      const review = getSubmittedReview(teammateId);
      if (review && review.answers) {
        review.answers.forEach(answer => {
          const input = document.querySelector(`input[name="rating-${answer.criterion_id}"][value="${answer.rating}"]`);
          if (input) {
            input.checked = true;
            // Remove focus to prevent scroll
            if (document.activeElement === input) {
              input.blur();
            }
          }
        });

        if (review.comment !== undefined) {
          const commentBox = document.getElementById("commentBox");
          if (commentBox) {
            commentBox.value = review.comment || "";
            updateCommentCounter();
            // Remove focus to prevent scroll
            if (document.activeElement === commentBox) {
              commentBox.blur();
            }
          }
          commentsByTeammate[teammateId] = review.comment || "";
        }
        // Restore scroll position
        window.scrollTo(0, scrollPosition);
        return true;
      }
    }

    return false;
  }

  function showEditButton(teammateId) {
    const submitSection = document.querySelector(".form-submit-section");
    if (!submitSection) return;

    // Remove existing edit button if any
    const existingEditBtn = document.getElementById("editReviewBtn");
    if (existingEditBtn) {
      existingEditBtn.remove();
    }

    // Create edit button
    const editBtn = document.createElement("button");
    editBtn.id = "editReviewBtn";
    editBtn.type = "button";
    editBtn.className = "edit-btn-secondary";
    editBtn.innerHTML = '<span class="btn-icon">✏️</span><span>Edit Review</span>';
    
    editBtn.addEventListener("click", async () => {
      editBtn.disabled = true;
      const buttonText = editBtn.querySelector("span:last-child");
      if (buttonText) {
        buttonText.textContent = "Loading...";
      }
      
      const loaded = await loadReviewIntoForm(teammateId);
      editBtn.disabled = false;
      if (buttonText) {
        buttonText.textContent = "Edit Review";
      }
      
      if (loaded) {
        setSubmitMessage("Review loaded. You can now edit and resubmit.", "info");
        // Keep edit button visible so user can reload if needed
      } else {
        setSubmitMessage("No previously submitted review found for this teammate.", "error");
      }
    });

    // Insert before submit button
    const submitReviewBtn = document.getElementById("submitReviewBtn");
    if (submitReviewBtn && submitReviewBtn.parentNode) {
      submitReviewBtn.parentNode.insertBefore(editBtn, submitReviewBtn);
    }
  }

  function hideEditButton() {
    const editBtn = document.getElementById("editReviewBtn");
    if (editBtn) {
      editBtn.remove();
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    const ratingContainer = document.getElementById("ratingContainer");
    const teammateSelect = document.getElementById("teammateSelect");
    const commentBox = document.getElementById("commentBox");
    const commentCount = document.getElementById("commentCount");
    const submitReviewBtn = document.getElementById("submitReviewBtn");
    const submitMessage = document.getElementById("submitMessage");

    const token = localStorage.getItem("access_token");

    // Load submitted reviews from localStorage
    loadSubmittedReviews();

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

      console.log("Loaded criteria:", criteria.length, "items");
      if (criteria.length > 0) {
        console.log("Sample criterion:", criteria[0]);
      }

      if (criteria.length === 0) {
        if (ratingContainer) {
          ratingContainer.innerHTML = '<p class="muted">No criteria available.</p>';
        }
        return;
      }

      // Render rating inputs (render ALL criteria, no slice)
      renderRatingInputs();
      
      // Setup validation listeners after rendering
      setupValidationListeners();
    } catch (e) {
      console.error("Failed to load criteria:", e);
      if (ratingContainer) {
        let errorMessage = e.message || "Unknown error";
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
        ratingContainer.innerHTML = `<p class="error">Failed to load criteria: ${errorMessage}</p>`;
      }
      return;
    }

    // Handle teammate selection change
    if (teammateSelect) {
      teammateSelect.addEventListener("change", async () => {
        await handleTeammateChange();
      });
    }

    // Handle comment input
    if (commentBox && commentCount) {
      commentBox.addEventListener("input", () => {
        updateCommentCounter();
        // Hide confirmation if visible (user is editing)
        hideConfirmation();
      });
    }

    // Handle confirm details button
    const confirmDetailsBtn = document.getElementById("confirmDetailsBtn");
    if (confirmDetailsBtn) {
      confirmDetailsBtn.addEventListener("click", () => {
        showConfirmation();
      });
    }

    // Handle delete submission button
    const deleteSubmissionBtn = document.getElementById("deleteSubmissionBtn");
    if (deleteSubmissionBtn) {
      deleteSubmissionBtn.addEventListener("click", () => {
        deleteSubmission();
      });
    }

    // Handle edit submission button
    const editSubmissionBtn = document.getElementById("editSubmissionBtn");
    if (editSubmissionBtn) {
      editSubmissionBtn.addEventListener("click", () => {
        hideConfirmation();
      });
    }

    // Handle submit (after confirmation)
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

  // Expose a global function to refresh the rating form
  async function refreshRatingForm() {
    const token = localStorage.getItem("access_token");
    if (!token) {
      console.warn("Cannot refresh rating form: not authenticated");
      return;
    }

    const ratingContainer = document.getElementById("ratingContainer");
    if (!ratingContainer) {
      console.warn("Cannot refresh rating form: rating container not found");
      return;
    }

    try {
      const formRes = await fetch(`${BACKEND_URL}/peer-reviews/form`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${token}`,
        },
      });

      if (!formRes.ok) {
        console.error(`Failed to refresh criteria: HTTP ${formRes.status}`);
        return;
      }

      const formData = await formRes.json();
      criteria = formData.criteria || [];

      console.log("Refreshed criteria:", criteria.length, "items");
      if (criteria.length > 0) {
        console.log("Sample criterion:", criteria[0]);
      }

      // Re-render rating inputs with updated criteria (render ALL, no slice)
      renderRatingInputs();
    } catch (e) {
      console.error("Failed to refresh rating form:", e);
    }
  }

  // Make refreshRatingForm globally accessible
  window.refreshRatingForm = refreshRatingForm;

  function renderRatingInputs() {
    const ratingContainer = document.getElementById("ratingContainer");
    if (!ratingContainer) return;

    ratingContainer.innerHTML = "";

    if (criteria.length === 0) {
      ratingContainer.innerHTML = '<p class="muted">No criteria available.</p>';
      return;
    }

    // Render ALL criteria (no slice, no hardcoded limits)
    criteria.forEach(criterion => {
      const criterionDiv = document.createElement("div");
      criterionDiv.className = "criterion-group";
      // Add unique identifier for debugging and proper rendering
      criterionDiv.setAttribute("data-criterion-id", criterion.id);
      criterionDiv.id = `criterion-${criterion.id}`;

      const label = document.createElement("label");
      label.className = "criterion-label";
      label.style.color = "#0F172A";
      label.style.fontWeight = "600";
      // Use criterion.title (from backend) - ensure it's not hardcoded
      label.textContent = criterion.title || criterion.name || "Unnamed Criterion";
      if (criterion.required) {
        label.innerHTML += ' <span class="required">*</span>';
      }

      // Add description if available
      if (criterion.description) {
        const descriptionEl = document.createElement("p");
        descriptionEl.className = "criterion-description";
        descriptionEl.textContent = criterion.description;
        descriptionEl.style.cssText = "font-size: 13px; color: #64748b; margin: 6px 0 12px 0; line-height: 1.5;";
        criterionDiv.appendChild(label);
        criterionDiv.appendChild(descriptionEl);
      } else {
        criterionDiv.appendChild(label);
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

      criterionDiv.appendChild(ratingGroup);
      ratingContainer.appendChild(criterionDiv);
    });
  }

  async function handleTeammateChange() {
    const teammateSelect = document.getElementById("teammateSelect");
    const commentBox = document.getElementById("commentBox");

    if (!teammateSelect || !commentBox) return;

    const newId = teammateSelect.value;

    // Save current scroll position to prevent auto-scrolling
    const scrollPosition = window.pageYOffset || document.documentElement.scrollTop;

    // Save previous teammate comment
    if (currentTeammateId) {
      commentsByTeammate[currentTeammateId] = commentBox.value;
    }

    currentTeammateId = newId || null;

    // Hide edit button and confirmation section when switching teammates
    hideEditButton();
    hideConfirmation();

    // Check if there's a submitted review for this teammate (from backend or localStorage)
    if (currentTeammateId) {
      const token = localStorage.getItem("access_token");
      if (token) {
        try {
          const res = await fetch(`${BACKEND_URL}/peer-reviews/submitted/${currentTeammateId}`, {
            method: "GET",
            headers: {
              "Authorization": `Bearer ${token}`,
            },
          });

          if (res.ok) {
            const data = await res.json();
            if (data.submitted && data.answers && data.answers.length > 0) {
              // Show edit button and automatically load the review for editing
              showEditButton(currentTeammateId);
              // Automatically load the review into the form
              await loadReviewIntoForm(currentTeammateId);
            } else if (getSubmittedReview(currentTeammateId)) {
              // Fallback to localStorage
              showEditButton(currentTeammateId);
              // Automatically load the review from localStorage
              await loadReviewIntoForm(currentTeammateId);
            } else {
              // Load new teammate comment (if any unsaved draft)
              if (commentsByTeammate[currentTeammateId]) {
                commentBox.value = commentsByTeammate[currentTeammateId];
              } else {
                commentBox.value = "";
              }
            }
          } else {
            // Check localStorage as fallback
            if (getSubmittedReview(currentTeammateId)) {
              showEditButton(currentTeammateId);
              // Automatically load the review from localStorage
              await loadReviewIntoForm(currentTeammateId);
            } else {
              if (commentsByTeammate[currentTeammateId]) {
                commentBox.value = commentsByTeammate[currentTeammateId];
              } else {
                commentBox.value = "";
              }
            }
          }
        } catch (e) {
          console.error("Failed to check for submitted review:", e);
          // Fallback to localStorage
          if (getSubmittedReview(currentTeammateId)) {
            showEditButton(currentTeammateId);
            // Automatically load the review from localStorage
            await loadReviewIntoForm(currentTeammateId);
          } else {
            if (commentsByTeammate[currentTeammateId]) {
              commentBox.value = commentsByTeammate[currentTeammateId];
            } else {
              commentBox.value = "";
            }
          }
        }
      } else {
        // No token, check localStorage only
        if (getSubmittedReview(currentTeammateId)) {
          showEditButton(currentTeammateId);
          // Automatically load the review from localStorage
          await loadReviewIntoForm(currentTeammateId);
        } else {
          if (commentsByTeammate[currentTeammateId]) {
            commentBox.value = commentsByTeammate[currentTeammateId];
          } else {
            commentBox.value = "";
          }
        }
      }
    } else {
      commentBox.value = "";
    }

    // Clear rating inputs when switching teammates
    document.querySelectorAll('input[type="radio"]:checked').forEach(input => {
      input.checked = false;
    });

    updateCommentCounter();
    
    // Restore scroll position after all updates (use setTimeout to ensure DOM updates are complete)
    setTimeout(() => {
      window.scrollTo(0, scrollPosition);
    }, 0);
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
        
        // Find the rating-group within this criterion
        const ratingGroup = error.element.querySelector('.rating-group');
        
        // Create or update error message element - place it after the rating-group
        let errorMsgEl = error.element.querySelector('.validation-error-message');
        if (!errorMsgEl) {
          errorMsgEl = document.createElement('div');
          errorMsgEl.className = 'validation-error-message';
          // Insert after the rating-group (right below the rating options)
          if (ratingGroup) {
            // Insert right after the rating-group element
            ratingGroup.insertAdjacentElement('afterend', errorMsgEl);
          } else {
            // Fallback: append to criterionDiv if ratingGroup not found
            error.element.appendChild(errorMsgEl);
          }
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
            // Hide confirmation if visible (user is editing)
            hideConfirmation();
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

  function showConfirmation() {
    // Validate input before showing confirmation
    const validationResult = validatePeerReviewInput();
    
    if (!validationResult.isValid) {
      // Display validation errors and prevent showing confirmation
      displayValidationErrors(validationResult);
      return;
    }

    // Clear any previous error indicators since validation passed
    clearValidationErrors();

    // Build confirmation summary
    buildConfirmationSummary();

    // Hide form submit section and show confirmation section
    const formSubmitSection = document.querySelector(".form-submit-section");
    const confirmationSection = document.getElementById("confirmationSection");
    
    if (formSubmitSection) {
      formSubmitSection.style.display = "none";
    }
    if (confirmationSection) {
      confirmationSection.style.display = "block";
      // Don't auto-scroll - let user control scrolling
    }
  }

  function hideConfirmation() {
    const formSubmitSection = document.querySelector(".form-submit-section");
    const confirmationSection = document.getElementById("confirmationSection");
    
    if (formSubmitSection) {
      formSubmitSection.style.display = "block";
    }
    if (confirmationSection) {
      confirmationSection.style.display = "none";
      // Don't auto-scroll - let user control scrolling
    }
  }

  function deleteSubmission() {
    // Confirm deletion
    if (!confirm("Are you sure you want to delete this submission? All entered data will be cleared.")) {
      return;
    }

    // Clear form inputs
    const teammateSelect = document.getElementById("teammateSelect");
    const commentBox = document.getElementById("commentBox");
    
    if (teammateSelect) {
      teammateSelect.value = "";
    }
    
    if (commentBox) {
      commentBox.value = "";
      updateCommentCounter();
    }

    // Clear all rating inputs
    document.querySelectorAll('input[type="radio"]:checked').forEach(input => {
      input.checked = false;
    });

    // Clear validation errors
    clearValidationErrors();
    setSubmitMessage("", "");

    // Hide confirmation section
    hideConfirmation();

    // Clear stored comments for current teammate
    if (currentTeammateId) {
      commentsByTeammate[currentTeammateId] = "";
      currentTeammateId = null;
    }

    // Show success message
    setSubmitMessage("Submission cleared. You can start a new review.", "info");
    
    // Clear message after 3 seconds
    setTimeout(() => {
      setSubmitMessage("", "");
    }, 3000);
  }

  function buildConfirmationSummary() {
    const teammateSelect = document.getElementById("teammateSelect");
    const selectedOption = teammateSelect?.options[teammateSelect.selectedIndex];
    const teammateName = selectedOption?.textContent || "Not selected";
    
    // Update teammate name
    const confirmationTeammate = document.getElementById("confirmationTeammate");
    if (confirmationTeammate) {
      confirmationTeammate.textContent = teammateName;
    }

    // Build ratings summary
    const confirmationRatings = document.getElementById("confirmationRatings");
    if (confirmationRatings) {
      const ratingsList = [];
      
      for (const criterion of criteria) {
        const ratingInput = document.querySelector(`input[name="rating-${criterion.id}"]:checked`);
        if (ratingInput) {
          const rating = Number(ratingInput.value);
          ratingsList.push({
            title: criterion.title,
            rating: rating
          });
        }
      }

      if (ratingsList.length > 0) {
        confirmationRatings.innerHTML = ratingsList.map(item => {
          return `
            <div class="confirmation-rating-item">
              <span class="confirmation-rating-label">${item.title}:</span>
              <span class="confirmation-rating-value">${item.rating} / 5</span>
            </div>
          `;
        }).join("");
      } else {
        confirmationRatings.innerHTML = '<em style="color: #94a3b8;">No ratings selected</em>';
      }
    }

    // Update comments
    const commentBox = document.getElementById("commentBox");
    const confirmationComments = document.getElementById("confirmationComments");
    if (confirmationComments) {
      const comment = commentBox?.value?.trim() || "";
      if (comment) {
        confirmationComments.textContent = comment;
        confirmationComments.style.color = "#1e293b";
        confirmationComments.style.fontStyle = "normal";
      } else {
        confirmationComments.innerHTML = '<em style="color: #94a3b8;">No comments provided</em>';
      }
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

    // Validate input before proceeding (double-check)
    const validationResult = validatePeerReviewInput();
    
    if (!validationResult.isValid) {
      // Hide confirmation and show form with errors
      hideConfirmation();
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
        // Store the submitted review
        const commentBox = document.getElementById("commentBox");
        const comment = commentBox ? commentBox.value : "";
        
        if (revieweeId) {
          const reviewData = {
            teammate_id: Number(revieweeId),
            answers: answers,
            comment: comment,
            submitted_at: new Date().toISOString()
          };
          storeSubmittedReview(revieweeId, reviewData);
        }

        // Hide confirmation section and show form again
        hideConfirmation();

        // Show prominent confirmation message
        setSubmitMessage("✓ Peer review submitted successfully! Thank you for your feedback.", "success");
        
        // Show edit button for this review
        if (revieweeId) {
          showEditButton(revieweeId);
        }

        // Clear the form inputs but keep teammate selected so user can edit
        if (commentBox) {
          commentBox.value = "";
          updateCommentCounter();
        }

        // Reset rating inputs
        document.querySelectorAll('input[type="radio"]:checked').forEach(input => {
          input.checked = false;
        });

        // Don't reset teammate selection - allow user to edit if needed
        // User can manually change teammate or click edit button

        // Note: Report preview will not refresh automatically
        // Students can only see reports after instructor publishes them

        return;
      }

      if (res.status === 401) {
        hideConfirmation();
        setSubmitMessage("Unauthorized. Please login again.", "error");
        setTimeout(() => {
          window.location.href = "login.html";
        }, 1500);
        return;
      }

      if (res.status === 409) {
        hideConfirmation();
        const detail = extractDetail(data) || "Conflict: This review may have already been submitted.";
        setSubmitMessage(detail, "error");
        return;
      }

      if (res.status === 400 || res.status === 422) {
        hideConfirmation();
        const detail = extractDetail(data) || "Validation error: Please check your input.";
        setSubmitMessage(detail, "error");
        return;
      }

      hideConfirmation();
      const detail = extractDetail(data) || `Submit failed (HTTP ${res.status}).`;
      setSubmitMessage(detail, "error");
    } catch (err) {
      hideConfirmation();
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
