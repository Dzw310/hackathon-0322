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
    updateStatus("请先输入一个问题。", true);
    return;
  }

  setLoading(true, "正在拆解问题...");
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
    updateStatus("第一步已经准备好了。");
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
    updateStatus("请先写下这一步的答案。", true);
    return;
  }

  setLoading(true, "正在判断这一步...");
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
      updateStatus("答对了，继续下一步。");
      return;
    }

    if (data.status === "try_again") {
      state.currentStep = data.currentStep;
      renderCurrentStep(data.currentStep, data.message, data.miniExplanation, data.hint);
      updateStatus("这一步还可以再想想。", true);
      return;
    }

    if (data.status === "completed") {
      answerForm.classList.add("hidden");
      renderCompletedState(data.message, data.miniExplanation);
      renderSummary(data.summary);
      updateStatus("这道题已经完成。");
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
    <div class="meta-pill">总共 ${totalSteps} 步</div>
    <p>${escapeHtml(problemReframed)}</p>
  `;
}

function renderCurrentStep(step, intro, explanation = "", hint = "") {
  currentStep.classList.remove("empty-state");
  currentStep.innerHTML = `
    <div class="step-badge">第 ${step.stepNumber} / ${step.totalSteps} 步</div>
    <h2>${escapeHtml(step.title)}</h2>
    <p class="step-goal">${escapeHtml(step.goal)}</p>
    <p class="step-prompt">${escapeHtml(step.prompt)}</p>
    ${intro ? `<div class="bubble info">${escapeHtml(intro)}</div>` : ""}
    ${explanation ? `<div class="bubble explain">${escapeHtml(explanation)}</div>` : ""}
    ${hint ? `<div class="bubble hint">提示：${escapeHtml(hint)}</div>` : ""}
  `;
}

function renderCompletedState(message, explanation = "") {
  currentStep.innerHTML = `
    <div class="step-badge complete">完成</div>
    <h2>你已经走完整个思考流程</h2>
    <div class="bubble info">${escapeHtml(message || "做得很好。")}</div>
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
      '<p class="empty-state">孩子的每一步尝试、提示和鼓励会显示在这里。</p>';
    return;
  }

  const latestFeedback = latestResponse?.message || "";
  const latestHint = latestResponse?.hint || "";

  timeline.innerHTML = state.history
    .map((item, index) => {
      const toneClass = item.isCorrect ? "correct" : "retry";
      const suffix =
        index === state.history.length - 1 && latestHint
          ? `<p class="timeline-hint">提示：${escapeHtml(latestHint)}</p>`
          : "";
      const extra =
        index === state.history.length - 1 && latestFeedback
          ? `<p class="timeline-feedback">${escapeHtml(latestFeedback)}</p>`
          : "";
      return `
        <article class="timeline-item ${toneClass}">
          <p class="timeline-step">步骤 ${item.stepIndex + 1}</p>
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
          <p><strong>你的表现：</strong>${escapeHtml(item.learner_answered)}</p>
          <p><strong>老师反馈：</strong>${escapeHtml(item.feedback)}</p>
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
      <h3>完整答案</h3>
      <p>${escapeHtml(summary.final_answer)}</p>
    </div>
    <div class="summary-columns">
      <section>
        <h3>这次做得好的地方</h3>
        <ul>${strengthsHtml}</ul>
      </section>
      <section>
        <h3>下次可以继续加强</h3>
        <ul>${tipsHtml}</ul>
      </section>
    </div>
    <div class="summary-recap">
      <h3>步骤回顾</h3>
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
    throw new Error(data.error || "请求失败");
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

