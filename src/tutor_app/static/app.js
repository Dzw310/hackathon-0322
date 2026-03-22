const state = {
  sessionId: null,
  currentStep: null,
  totalSteps: 0,
  history: [],
};

const questionInput = document.getElementById("questionInput");
const startButton = document.getElementById("startButton");
const statusText = document.getElementById("statusText");
const sessionMeta = document.getElementById("sessionMeta");
const currentStep = document.getElementById("currentStep");
const answerForm = document.getElementById("answerForm");
const answerInput = document.getElementById("answerInput");
const answerButton = document.getElementById("answerButton");
const timeline = document.getElementById("timeline");
const summaryPanel = document.getElementById("summaryPanel");

startButton.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) {
    updateStatus("Please enter a question first.", true);
    return;
  }

  setLoading(true, "Breaking the problem into steps...");
  summaryPanel.classList.add("hidden");

  try {
    const data = await postJson("/api/session", { question });
    state.sessionId = data.sessionId;
    state.currentStep = data.currentStep;
    state.totalSteps = data.totalSteps;
    state.history = data.history || [];

    renderSessionMeta(data.problemReframed, data.totalSteps);
    renderCurrentStep(data.currentStep, data.intro);
    renderHistory();
    answerForm.classList.remove("hidden");
    updateStatus("The first step is ready.");
  } catch (error) {
    updateStatus(error.message, true);
  } finally {
    setLoading(false);
  }
});

answerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const answer = answerInput.value.trim();
  if (!answer || !state.sessionId) {
    updateStatus("Please write an answer for this step first.", true);
    return;
  }

  setLoading(true, "Checking this step...");
  try {
    const data = await postJson("/api/session/answer", {
      sessionId: state.sessionId,
      answer,
    });

    state.history = data.history || state.history;
    renderHistory(data);

    if (data.status === "step_advanced") {
      state.currentStep = data.currentStep;
      renderCurrentStep(data.currentStep, data.message, data.miniExplanation);
      answerInput.value = "";
      updateStatus("Nice work. Move on to the next step.");
      return;
    }

    if (data.status === "try_again") {
      state.currentStep = data.currentStep;
      renderCurrentStep(data.currentStep, data.message, data.miniExplanation, data.hint);
      updateStatus("Try thinking about this step one more time.", true);
      return;
    }

    if (data.status === "completed") {
      answerForm.classList.add("hidden");
      renderCompletedState(data.message, data.miniExplanation);
      renderSummary(data.summary);
      updateStatus("This problem is complete.");
    }
  } catch (error) {
    updateStatus(error.message, true);
  } finally {
    setLoading(false);
  }
});

function renderSessionMeta(problemReframed, totalSteps) {
  sessionMeta.classList.remove("hidden");
  sessionMeta.innerHTML = `
    <div class="meta-pill">${totalSteps} steps total</div>
    <p>${escapeHtml(problemReframed)}</p>
  `;
}

function renderCurrentStep(step, intro, explanation = "", hint = "") {
  currentStep.classList.remove("empty-state");
  currentStep.innerHTML = `
    <div class="step-badge">Step ${step.stepNumber} / ${step.totalSteps}</div>
    <h2>${escapeHtml(step.title)}</h2>
    <p class="step-goal">${escapeHtml(step.goal)}</p>
    <p class="step-prompt">${escapeHtml(step.prompt)}</p>
    ${intro ? `<div class="bubble info">${escapeHtml(intro)}</div>` : ""}
    ${explanation ? `<div class="bubble explain">${escapeHtml(explanation)}</div>` : ""}
    ${hint ? `<div class="bubble hint">Hint: ${escapeHtml(hint)}</div>` : ""}
  `;
}

function renderCompletedState(message, explanation = "") {
  currentStep.innerHTML = `
    <div class="step-badge complete">Complete</div>
    <h2>You finished the full thinking journey</h2>
    <div class="bubble info">${escapeHtml(message || "Well done.")}</div>
    ${
      explanation
        ? `<div class="bubble explain">${escapeHtml(explanation)}</div>`
        : ""
    }
  `;
}

function renderHistory(latestResponse) {
  if (!state.history.length) {
    timeline.innerHTML =
      '<p class="empty-state">Each attempt, hint, and encouraging message will appear here.</p>';
    return;
  }

  const latestFeedback = latestResponse?.message || "";
  const latestHint = latestResponse?.hint || "";

  timeline.innerHTML = state.history
    .map((item, index) => {
      const toneClass = item.isCorrect ? "correct" : "retry";
      const suffix =
        index === state.history.length - 1 && latestHint
          ? `<p class="timeline-hint">Hint: ${escapeHtml(latestHint)}</p>`
          : "";
      const extra =
        index === state.history.length - 1 && latestFeedback
          ? `<p class="timeline-feedback">${escapeHtml(latestFeedback)}</p>`
          : "";
      return `
        <article class="timeline-item ${toneClass}">
          <p class="timeline-step">Step ${item.stepIndex + 1}</p>
          <p class="timeline-answer">${escapeHtml(item.answer)}</p>
          ${extra}
          ${suffix}
        </article>
      `;
    })
    .join("");
}

function renderSummary(summary) {
  summaryPanel.classList.remove("hidden");
  const recapHtml = summary.step_recap
    .map(
      (item) => `
        <article class="recap-item">
          <h3>${escapeHtml(item.title)}</h3>
          <p><strong>Your work:</strong>${escapeHtml(item.learner_answered)}</p>
          <p><strong>Tutor feedback:</strong>${escapeHtml(item.feedback)}</p>
        </article>
      `
    )
    .join("");

  const strengthsHtml = summary.strengths
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const tipsHtml = summary.next_time_tips
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  summaryPanel.innerHTML = `
    <div class="summary-header">
      <p class="eyebrow">Final feedback</p>
      <h2>${escapeHtml(summary.summary_title)}</h2>
      <p>${escapeHtml(summary.celebration)}</p>
    </div>
    <div class="summary-answer">
      <h3>Complete answer</h3>
      <p>${escapeHtml(summary.final_answer)}</p>
    </div>
    <div class="summary-columns">
      <section>
        <h3>What went well</h3>
        <ul>${strengthsHtml}</ul>
      </section>
      <section>
        <h3>What to keep improving</h3>
        <ul>${tipsHtml}</ul>
      </section>
    </div>
    <div class="summary-recap">
      <h3>Step recap</h3>
      ${recapHtml}
    </div>
  `;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function updateStatus(message, isWarning = false) {
  statusText.textContent = message;
  statusText.classList.toggle("warning", isWarning);
}

function setLoading(isLoading, message = "") {
  startButton.disabled = isLoading;
  answerButton.disabled = isLoading;
  if (message) {
    updateStatus(message);
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
