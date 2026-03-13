let _selectedRunId = null;
let _historyMounted = false;

async function mount_history() {
  if (!_historyMounted) {
    document.getElementById("refreshHistory").addEventListener("click", _loadHistory);
    document.getElementById("closeDetail").addEventListener("click", _closeDetail);
    document.getElementById("cloneRunBtn").addEventListener("click", _cloneRun);
    _historyMounted = true;
  }
  await _loadHistory();
}

async function _loadHistory() {
  const list = document.getElementById("runList");
  list.innerHTML = `<p class="hint">Loading...</p>`;
  try {
    const runs = await API.runs.list();
    if (runs.length === 0) {
      list.innerHTML = `<p class="empty-hint">No runs yet. <a href="#/run">Start a run →</a></p>`;
      return;
    }
    list.innerHTML = runs.map(r => {
      const passRate = r.case_count > 0
        ? Math.round((r.passed_count || 0) / r.case_count * 100) + "%"
        : "—";
      const modeLabel = r.mode === "agent"
        ? "Agent: " + (r.agent || "?")
        : "Dataset: " + (r.dataset_id || "?");
      const date = r.started_at ? new Date(r.started_at).toLocaleString() : "—";
      const promptSnippet = r.custom_system_prompt
        ? `<span class="hint prompt-snippet" title="${r.custom_system_prompt}">"${r.custom_system_prompt.slice(0, 60)}${r.custom_system_prompt.length > 60 ? "…" : ""}"</span>`
        : "";
      const evalVerdict = r.auto_eval_verdict
        ? `<span class="status-badge ${r.auto_eval_verdict === "pass" ? "status-completed" : "status-failed"}" style="font-size:10px">AI: ${r.auto_eval_verdict}</span>`
        : "";
      const envBadge = r.environment_name
        ? `<span class="env-badge-inline">${r.environment_name}</span>`
        : "";
      return `
        <div class="run-card" data-run-id="${r.run_id}">
          <div class="run-card-left">
            <span class="status-badge status-${r.status}">${r.status}</span>
            ${evalVerdict}
            ${envBadge}
            <div class="run-card-info">
              <span class="run-card-mode">${modeLabel}</span>
              ${promptSnippet}
            </div>
          </div>
          <div class="run-card-right">
            <span class="run-card-pass ${r.case_count > 0 ? (r.passed_count === r.case_count ? "stat-good" : "stat-bad") : ""}">${passRate} passed</span>
            <span class="hint">${r.case_count} turns/cases</span>
            <span class="hint">${date}</span>
          </div>
        </div>`;
    }).join("");

    list.querySelectorAll(".run-card").forEach(card => {
      card.addEventListener("click", () => _openRun(card.dataset.runId));
    });
  } catch (err) {
    list.innerHTML = `<div class="error-hint">Failed to load runs: ${err.message}</div>`;
  }
}

async function _openRun(runId) {
  _selectedRunId = runId;
  const panel = document.getElementById("runDetailPanel");
  document.getElementById("detailRunId").textContent = runId;
  document.getElementById("runDetailReport").innerHTML = `<p class="hint">Loading...</p>`;
  panel.classList.remove("hidden");
  panel.scrollIntoView({ behavior: "smooth" });

  try {
    const run = await API.runs.get(runId);
    document.getElementById("runDetailRaw").value = JSON.stringify(run, null, 2);
    renderRunReport(run, document.getElementById("runDetailReport"));
  } catch (err) {
    document.getElementById("runDetailReport").innerHTML =
      `<div class="error-hint">Failed to load: ${err.message}</div>`;
  }
}

function _closeDetail() {
  document.getElementById("runDetailPanel").classList.add("hidden");
  _selectedRunId = null;
}

function _cloneRun() {
  if (_selectedRunId) navigate("#/run?clone=" + _selectedRunId);
}
