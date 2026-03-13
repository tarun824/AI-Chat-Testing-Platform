// Entry point — routing handled by router.js, API by api.js,
// report rendering by report.js, pages in pages/

// ── Sidebar Environment Switcher ─────────────────────────────────────────────
// Renders the 3-button segmented env switcher in the sidebar.
// Called on load and whenever env-changed fires.

async function _refreshSidebarEnv() {
  const container = document.getElementById("navEnvButtons");
  if (!container) return;
  try {
    const envs = await API.environments.list();
    const activeId = ENV.getActiveId() || (envs[0] && envs[0].env_id) || "";
    // Auto-select first env if nothing stored yet
    if (!ENV.getActiveId() && envs.length > 0) {
      ENV.setActiveId(envs[0].env_id);
    }
    container.innerHTML = envs.map(e => `
      <button
        class="env-seg-btn ${e.env_id === activeId ? "env-seg-btn-active env-seg-active-" + (e.color || "slate") : ""}"
        onclick="ENV.setActiveId('${e.env_id}'); _refreshSidebarEnv(); _notifyEnvChange('${e.env_id}');"
        title="${e.webhook_base_url || 'No webhook URL set'}"
      >
        <span class="env-dot env-dot-${e.color || "slate"}"></span>
        ${e.name}
      </button>`).join("");
  } catch (e) {
    // silently ignore if server not ready
  }
}

function _notifyEnvChange(envId) {
  // Trigger page-level refresh if the run page is visible
  const runPage = document.getElementById("page-run");
  if (runPage && !runPage.classList.contains("hidden")) {
    if (typeof _refreshEnvNotice === "function") _refreshEnvNotice();
  }
}

document.addEventListener("DOMContentLoaded", () => {
  _refreshSidebarEnv();
  document.addEventListener("env-changed", () => _refreshSidebarEnv());
});
