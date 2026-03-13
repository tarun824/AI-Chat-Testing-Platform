async function mount_dashboard() {
  const container = document.getElementById("dashboard-stats");
  const recent = document.getElementById("dashboard-recent");
  if (!container) return;

  try {
    const runs = await API.runs.list();
    const total = runs.length;
    const completed = runs.filter(r => r.status === "completed").length;
    const failed = runs.filter(r => r.status === "failed").length;
    const running = runs.filter(r => r.status === "running").length;

    // Pass rate = passed_count / case_count across all completed runs
    const completedRuns = runs.filter(r => r.status === "completed" && r.case_count > 0);
    const totalCases = completedRuns.reduce((s, r) => s + r.case_count, 0);
    const totalPassed = completedRuns.reduce((s, r) => s + (r.passed_count || 0), 0);
    const passRate = totalCases > 0 ? Math.round(totalPassed / totalCases * 100) : null;
    const passRateDisplay = passRate !== null ? passRate + "%" : "—";
    const passRateClass = passRate === null ? "" : passRate >= 80 ? "stat-good" : passRate >= 50 ? "stat-warn" : "stat-bad";

    container.innerHTML = `
      <div class="stat-card">
        <div class="stat-value">${total}</div>
        <div class="stat-label">Total Runs</div>
      </div>
      <div class="stat-card stat-green">
        <div class="stat-value stat-good">${completed}</div>
        <div class="stat-label">Completed</div>
      </div>
      <div class="stat-card stat-red">
        <div class="stat-value stat-bad">${failed}</div>
        <div class="stat-label">Failed</div>
      </div>
      <div class="stat-card stat-blue">
        <div class="stat-value stat-info">${running}</div>
        <div class="stat-label">Running Now</div>
      </div>
      <div class="stat-card ${passRate !== null && passRate >= 80 ? "stat-green" : passRate !== null ? "stat-amber" : ""}">
        <div class="stat-value ${passRateClass}">${passRateDisplay}</div>
        <div class="stat-label">Overall Pass Rate</div>
      </div>
    `;

    const recentRuns = runs.slice(0, 6);
    recent.innerHTML = `
      <div class="section-header">
        <h2>Recent Runs</h2>
        <a href="#/run" class="btn-primary btn-sm">+ New Run</a>
      </div>
      ${recentRuns.length === 0 ? `<p class="empty-hint">No runs yet. <a href="#/run">Start your first run →</a></p>` : ""}
      ${recentRuns.map(r => {
        const passRate = r.case_count > 0
          ? Math.round((r.passed_count || 0) / r.case_count * 100) + "%"
          : "—";
        const modeLabel = r.mode === "agent"
          ? "Agent: " + (r.agent || "?")
          : "Dataset: " + (r.dataset_id || "?");
        const date = r.started_at ? new Date(r.started_at).toLocaleString() : "—";
        return `
          <div class="run-card" onclick="navigate('#/history')">
            <div class="run-card-left">
              <span class="status-badge status-${r.status}">${r.status}</span>
              <span class="run-card-mode">${modeLabel}</span>
            </div>
            <div class="run-card-right">
              <span class="run-card-pass ${r.case_count > 0 ? (r.passed_count === r.case_count ? "stat-good" : "stat-bad") : ""}">${passRate}</span>
              <span class="hint">${date}</span>
            </div>
          </div>`;
      }).join("")}
    `;
  } catch (err) {
    container.innerHTML = `<div class="error-hint">Could not load dashboard: ${err.message}</div>`;
  }
}
