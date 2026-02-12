const analyzeBtn = document.getElementById("analyzeBtn");
const ideaInput = document.getElementById("idea");
const statusEl = document.getElementById("status");
const resultsEl = document.getElementById("results");

const textFields = [
  "market_competition",
  "monetization_potential",
  "target_users",
  "risk_score",
  "summary",
];

function fillList(id, items, ordered = false) {
  const list = document.getElementById(id);
  list.innerHTML = "";
  const safeItems = Array.isArray(items) ? items : [String(items || "")];

  safeItems.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    list.appendChild(li);
  });

  if (!safeItems.length) {
    const li = document.createElement("li");
    li.textContent = ordered ? "No steps returned." : "No suggestions returned.";
    list.appendChild(li);
  }
}

function resetStatus(error = false) {
  statusEl.classList.toggle("error", error);
}

analyzeBtn.addEventListener("click", async () => {
  const idea = ideaInput.value.trim();

  if (!idea) {
    resetStatus(true);
    statusEl.textContent = "Please enter your project idea first.";
    return;
  }

  resetStatus(false);
  analyzeBtn.disabled = true;
  statusEl.textContent = "Thinking...";

  try {
    const resp = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idea }),
    });

    const data = await resp.json();

    if (!resp.ok) {
      throw new Error(data.error || "Analysis failed.");
    }

    textFields.forEach((field) => {
      const el = document.getElementById(field);
      el.textContent = data[field] || "Not provided";
    });

    fillList("feature_suggestions", data.feature_suggestions);
    fillList("mvp_plan", data.mvp_plan, true);

    resultsEl.classList.remove("hidden");
    statusEl.textContent = "Analysis complete.";
  } catch (err) {
    resetStatus(true);
    statusEl.textContent = err.message;
  } finally {
    analyzeBtn.disabled = false;
  }
});
