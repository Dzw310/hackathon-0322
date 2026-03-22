const state = {
  sessionId: null,
  currentStep: null,
  totalSteps: 0,
  history: [],
  userId: null,
  ageGroup: "8-10",
  coins: 0,
  streak: 0,
};

// DOM elements
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
const rewardBanner = document.getElementById("rewardBanner");
const ageGroupSelect = document.getElementById("ageGroupSelect");

// Auth elements
const loginView = document.getElementById("loginView");
const registerView = document.getElementById("registerView");
const userView = document.getElementById("userView");
const usernameInput = document.getElementById("usernameInput");
const loginBtn = document.getElementById("loginBtn");
const showRegisterBtn = document.getElementById("showRegisterBtn");
const regUsername = document.getElementById("regUsername");
const regDisplayName = document.getElementById("regDisplayName");
const regAgeGroup = document.getElementById("regAgeGroup");
const registerBtn = document.getElementById("registerBtn");
const backToLoginBtn = document.getElementById("backToLoginBtn");
const displayNameText = document.getElementById("displayNameText");
const coinsDisplay = document.getElementById("coinsDisplay");
const streakDisplay = document.getElementById("streakDisplay");
const logoutBtn = document.getElementById("logoutBtn");
const authStatus = document.getElementById("authStatus");

// ---- Auth ----
function showAuthStatus(msg, isError = false) {
  authStatus.textContent = msg;
  authStatus.className = "auth-status" + (isError ? " warning" : "");
}

function setLoggedIn(user) {
  state.userId = user.user_id;
  state.ageGroup = user.age_group;
  state.coins = user.coins;
  state.streak = user.current_streak;

  displayNameText.textContent = user.display_name;
  coinsDisplay.textContent = user.coins + " coins";
  streakDisplay.textContent = user.current_streak + " streak";
  ageGroupSelect.value = user.age_group;

  loginView.classList.add("hidden");
  registerView.classList.add("hidden");
  userView.classList.remove("hidden");
  showAuthStatus("");

  localStorage.setItem("thinkstep_username", user.username);
}

function logout() {
  state.userId = null;
  state.coins = 0;
  state.streak = 0;
  loginView.classList.remove("hidden");
  registerView.classList.add("hidden");
  userView.classList.add("hidden");
  localStorage.removeItem("thinkstep_username");
}

loginBtn.addEventListener("click", async () => {
  const username = usernameInput.value.trim();
  if (!username) { showAuthStatus("Enter a username.", true); return; }
  try {
    const data = await postJson("/api/login", { username });
    setLoggedIn(data.user);
  } catch (e) { showAuthStatus(e.message, true); }
});

showRegisterBtn.addEventListener("click", () => {
  loginView.classList.add("hidden");
  registerView.classList.remove("hidden");
});

backToLoginBtn.addEventListener("click", () => {
  registerView.classList.add("hidden");
  loginView.classList.remove("hidden");
});

registerBtn.addEventListener("click", async () => {
  const username = regUsername.value.trim();
  const displayName = regDisplayName.value.trim();
  const ageGroup = regAgeGroup.value;
  if (!username || !displayName) { showAuthStatus("Fill in all fields.", true); return; }
  try {
    const data = await postJson("/api/register", { username, displayName, ageGroup });
    setLoggedIn(data.user);
  } catch (e) { showAuthStatus(e.message, true); }
});

logoutBtn.addEventListener("click", logout);

// Auto-login from localStorage
(async function autoLogin() {
  const saved = localStorage.getItem("thinkstep_username");
  if (saved) {
    try {
      const data = await postJson("/api/login", { username: saved });
      setLoggedIn(data.user);
    } catch (_) { /* ignore */ }
  }
})();

// ---- Session ----
startButton.addEventListener("click", async () => {
  const question = questionInput.value.trim();
  if (!question) {
    updateStatus("Please enter a question first.", true);
    return;
  }

  setLoading(true, "Breaking the problem into steps...");
  summaryPanel.classList.add("hidden");
  rewardBanner.classList.add("hidden");

  try {
    const payload = {
      question,
      ageGroup: ageGroupSelect.value,
    };
    if (state.userId) payload.userId = state.userId;

    const data = await postJson("/api/session", payload);
    state.sessionId = data.sessionId;
    state.currentStep = data.currentStep;
    state.totalSteps = data.totalSteps;
    state.history = data.history || [];

    renderSessionMeta(data.problemReframed, data.totalSteps, data.ageGroup);
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
  rewardBanner.classList.add("hidden");

  try {
    const data = await postJson("/api/session/answer", {
      sessionId: state.sessionId,
      answer,
    });

    state.history = data.history || state.history;
    renderHistory(data);

    if (data.reward) showReward(data.reward);
    if (data.reward && state.userId) refreshUserStats();

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

async function refreshUserStats() {
  if (!state.userId) return;
  try {
    const data = await postJson("/api/user/stats", { userId: state.userId });
    const user = data.user;
    state.coins = user.coins;
    state.streak = user.current_streak;
    coinsDisplay.textContent = user.coins + " coins";
    streakDisplay.textContent = user.current_streak + " streak";
  } catch (_) { /* ignore */ }
}

// ---- Reward banner ----
function showReward(reward) {
  if (!reward || reward.type === "none") return;

  let html = "";
  if (reward.type === "correct") {
    html += `<span class="reward-msg">${escapeHtml(reward.message)}</span>`;
    if (reward.coinsEarned) html += ` <span class="reward-coins">+${reward.coinsEarned} coins</span>`;
    if (reward.currentStreak) html += ` <span class="reward-streak">streak: ${reward.currentStreak}</span>`;
    if (reward.streakMessage) html += `<br><span class="reward-streak-msg">${escapeHtml(reward.streakMessage)}</span>`;
    if (reward.completionMessage) html += `<br><span class="reward-complete">${escapeHtml(reward.completionMessage)}</span>`;
  } else if (reward.type === "encouragement") {
    html += `<span class="reward-encourage">${escapeHtml(reward.message)}</span>`;
  }

  rewardBanner.innerHTML = html;
  rewardBanner.className = "reward-banner " + reward.type;
  rewardBanner.classList.remove("hidden");
}

// ---- Renders ----
function renderSessionMeta(problemReframed, totalSteps, ageGroup) {
  sessionMeta.classList.remove("hidden");
  const ageLabels = {
    "5-7": "Early learners",
    "8-10": "Elementary",
    "11-14": "Middle school",
    "15-18": "High school"
  };
  const ageLabel = ageLabels[ageGroup] || ageGroup;
  sessionMeta.innerHTML = `
    <div class="meta-pill">${totalSteps} steps total</div>
    <div class="meta-pill age-pill">${escapeHtml(ageLabel)}</div>
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

// ---- Utilities ----
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
