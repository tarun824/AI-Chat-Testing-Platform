let _agents = [];
let _currentRunId = null;
let _pollTimer = null;
let _runMounted = false;

async function _refreshEnvNotice() {
  const notice = document.getElementById("activeEnvNotice");
  if (!notice) return;
  try {
    const envs = await API.environments.list();
    const active = ENV.getActiveEnv(envs);
    if (active) {
      const urlHtml = active.webhook_base_url
        ? `<span class="hint" style="font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:260px">${active.webhook_base_url}</span>`
        : `<span class="hint warn" style="font-size:11px">No webhook URL set — <a href="#/environments">configure →</a></span>`;
      notice.innerHTML = `
        <span class="env-dot env-dot-${active.color || "slate"}" style="width:9px;height:9px;flex-shrink:0"></span>
        <span style="font-weight:600">${active.name}</span>
        ${urlHtml}
        <a href="#/environments" class="hint" style="margin-left:auto;white-space:nowrap;font-size:11px">Change →</a>`;
      notice.classList.remove("hidden");
    }
  } catch (e) { /* ignore */ }
}

async function mount_run(hash) {
  if (!_runMounted) {
    _bindRunEvents();
    document.addEventListener("env-changed", _refreshEnvNotice);
    _runMounted = true;
  }

  await _refreshEnvNotice();

  try {
    const [datasets, agents] = await Promise.all([
      API.datasets.list(),
      API.agents.list(),
    ]);
    _agents = agents;

    const dsSel = document.getElementById("runDatasetSelect");
    dsSel.innerHTML = datasets.map(d =>
      `<option value="${d.dataset_id}">${d.dataset_id} (${d.case_count} cases)</option>`
    ).join("") || `<option value="">No datasets found</option>`;

    const agSel = document.getElementById("agentSelect");
    agSel.innerHTML = agents.map(a =>
      `<option value="${a.name}">${a.name}</option>`
    ).join("");

    // Handle pre-select from datasets page
    const preselect = sessionStorage.getItem("preselect_dataset");
    if (preselect) {
      dsSel.value = preselect;
      sessionStorage.removeItem("preselect_dataset");
    }

    // Handle clone from history
    const params = new URLSearchParams((hash.split("?")[1] || ""));
    const cloneId = params.get("clone");
    if (cloneId) {
      await _prefillFromRun(cloneId);
    } else {
      _loadAgentPrompt();
    }
  } catch (err) {
    document.getElementById("runStatusMsg").textContent = "Failed to load: " + err.message;
  }
}

function _switchTab(mode) {
  document.querySelectorAll(".tab-btn").forEach(b =>
    b.classList.toggle("active", b.dataset.mode === mode)
  );
  document.getElementById("panel-dataset").classList.toggle("hidden", mode !== "dataset");
  document.getElementById("panel-agent").classList.toggle("hidden", mode !== "agent");
}

function _loadAgentPrompt() {
  const agent = document.getElementById("agentSelect").value;
  const isCustom = document.getElementById("customModeToggle").checked;
  const textarea = document.getElementById("agentPrompt");
  const hint = document.getElementById("promptHint");
  const label = document.getElementById("promptLabel");
  const badge = document.getElementById("promptBadge");

  if (isCustom) {
    textarea.value = "";
    textarea.placeholder = "Write your full test instructions here. Describe the user persona, what to test, and edge cases to cover.";
    label.textContent = "Custom Prompt";
    hint.textContent = "You have full control. The AI will follow exactly what you write here.";
    if (badge) { badge.textContent = "Custom"; badge.className = "prompt-badge custom"; }
  } else {
    const found = _agents.find(a => a.name === agent);
    textarea.value = found ? found.system_prompt : "";
    label.textContent = "System Prompt (editable)";
    hint.textContent = "This is the preset for the selected persona. Edit it freely or switch to Custom Mode for a blank slate.";
    if (badge) { badge.textContent = "Preset"; badge.className = "prompt-badge"; }
  }
}

async function _prefillFromRun(runId) {
  try {
    const run = await API.runs.get(runId);
    if (run.mode === "agent") {
      _switchTab("agent");
      const agSel = document.getElementById("agentSelect");
      if (run.agent) agSel.value = run.agent;
      if (run.custom_system_prompt) {
        document.getElementById("customModeToggle").checked = true;
        document.getElementById("agentPrompt").value = run.custom_system_prompt;
        document.getElementById("promptLabel").textContent = "Custom Prompt";
        document.getElementById("promptHint").textContent = "Pre-filled from cloned run. Edit as needed.";
      } else {
        _loadAgentPrompt();
      }
      document.getElementById("maxTurns").value = run.max_turns || 5;
    } else {
      _switchTab("dataset");
      if (run.dataset_id) document.getElementById("runDatasetSelect").value = run.dataset_id;
    }
    document.getElementById("runStatusMsg").textContent = `Cloned from run: ${runId}`;
  } catch (err) {
    document.getElementById("runStatusMsg").textContent = "Could not load run to clone: " + err.message;
  }
}

function _bindRunEvents() {
  document.querySelectorAll(".tab-btn").forEach(btn =>
    btn.addEventListener("click", () => _switchTab(btn.dataset.mode))
  );
  document.getElementById("agentSelect").addEventListener("change", _loadAgentPrompt);
  document.getElementById("customModeToggle").addEventListener("change", _loadAgentPrompt);
  document.getElementById("startDatasetRun").addEventListener("click", _startDatasetRun);
  document.getElementById("startAgentRun").addEventListener("click", _startAgentRun);
  document.getElementById("stopRun").addEventListener("click", _stopRun);
}

async function _startDatasetRun() {
  const datasetId = document.getElementById("runDatasetSelect").value;
  if (!datasetId) { alert("Select a dataset."); return; }
  const tags = document.getElementById("tagFilter").value
    .split(",").map(t => t.trim()).filter(Boolean);
  try {
    const res = await API.runs.start({
      mode: "dataset",
      dataset_id: datasetId,
      tags,
      environment_id: ENV.getActiveId() || undefined,
    });
    _startPolling(res.run_id);
  } catch (err) {
    document.getElementById("runStatusMsg").textContent = "Error: " + err.message;
  }
}

async function _startAgentRun() {
  const agent = document.getElementById("agentSelect").value;
  if (!agent) { alert("Select an agent."); return; }
  const customPrompt = document.getElementById("agentPrompt").value.trim();
  const maxTurns = parseInt(document.getElementById("maxTurns").value || "5", 10);
  try {
    const res = await API.runs.start({
      mode: "agent",
      agent,
      max_turns: maxTurns,
      custom_system_prompt: customPrompt || undefined,
      environment_id: ENV.getActiveId() || undefined,
    });
    _startPolling(res.run_id);
  } catch (err) {
    document.getElementById("runStatusMsg").textContent = "Error: " + err.message;
  }
}

function _startPolling(runId) {
  _currentRunId = runId;
  const panel = document.getElementById("runStatusPanel");
  panel.classList.remove("hidden");
  document.getElementById("activeRunId").textContent = runId;
  document.getElementById("runStatusMsg").textContent = "Run started — waiting for first result...";
  document.getElementById("runSpinner").classList.remove("spinner-done");

  clearInterval(_pollTimer);
  _pollTimer = setInterval(async () => {
    try {
      const run = await API.runs.get(runId);
      const badge = document.getElementById("activeRunStatus");
      badge.textContent = run.status;
      badge.className = "status-badge status-" + run.status;

      // Turn progress for agent runs
      const cases = run.cases || [];
      if (run.mode === "agent" && run.max_turns && cases.length > 0) {
        const done = ["completed", "failed", "stopped"].includes(run.status);
        document.getElementById("runStatusMsg").textContent = done
          ? `Run ${run.status}. ${cases.length} turns completed.`
          : `Turn ${cases.length} / ${run.max_turns} running...`;
      }

      renderRunReport(run, document.getElementById("liveRunReport"));

      if (["completed", "failed", "stopped"].includes(run.status)) {
        clearInterval(_pollTimer);
        document.getElementById("runSpinner").classList.add("spinner-done");
        if (run.mode !== "agent") {
          document.getElementById("runStatusMsg").textContent =
            `Run ${run.status}.` + (run.status === "completed" ? " View details in History →" : "");
        }
      }
    } catch (e) {
      // ignore transient errors during polling
    }
  }, 2000);
}

async function _stopRun() {
  if (!_currentRunId) return;
  try {
    await API.runs.stop(_currentRunId);
    document.getElementById("runStatusMsg").textContent = "Stopping run...";
  } catch (err) {
    document.getElementById("runStatusMsg").textContent = "Stop error: " + err.message;
  }
}
