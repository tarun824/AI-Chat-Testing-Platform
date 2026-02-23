const datasetSelect = document.getElementById("datasetSelect");
const datasetEditor = document.getElementById("datasetEditor");
const runDetails = document.getElementById("runDetails");
const runStatus = document.getElementById("runStatus");
const runMode = document.getElementById("runMode");
const agentSelect = document.getElementById("agentSelect");
const maxTurnsInput = document.getElementById("maxTurns");
const stopRunButton = document.getElementById("stopRun");
const tagFilterInput = document.getElementById("tagFilter");

let currentRunId = null;

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

function setStatus(text) {
  runStatus.textContent = text;
}

function updateModeUI() {
  const isAgent = runMode.value === "agent";
  tagFilterInput.disabled = isAgent;
  tagFilterInput.placeholder = isAgent
    ? "Tag filter disabled in agent mode"
    : "Tag filter (comma separated)";
}

async function refreshDatasets() {
  const datasets = await fetchJson("/api/datasets");
  datasetSelect.innerHTML = "";
  if (datasets.length === 0) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No datasets found";
    datasetSelect.appendChild(opt);
    setStatus(
      "No datasets found. Check datasets folder or AI_TEST_DATASETS_DIR.",
    );
    return;
  } else {
    console.log(datasets);
  }
  datasets.forEach((ds) => {
    const opt = document.createElement("option");
    opt.value = ds.dataset_id;
    opt.textContent = `${ds.dataset_id} (${ds.case_count})`;
    datasetSelect.appendChild(opt);
  });
}

async function loadDataset() {
  const datasetId = datasetSelect.value;
  if (!datasetId) {
    return;
  }
  const dataset = await fetchJson(`/api/datasets/${datasetId}`);
  datasetEditor.value = JSON.stringify(dataset, null, 2);
}

async function saveDataset() {
  const datasetId = datasetSelect.value;
  if (!datasetId) {
    setStatus("Select dataset before saving.");
    return;
  }
  let payload;
  try {
    payload = JSON.parse(datasetEditor.value || "{}");
  } catch (err) {
    setStatus("Dataset JSON is invalid.");
    return;
  }
  await fetchJson(`/api/datasets/${datasetId}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  setStatus("Dataset saved.");
  await refreshDatasets();
}

async function createDataset() {
  const newId = document.getElementById("newDatasetId").value.trim();
  if (!newId) {
    setStatus("Dataset id is required.");
    return;
  }
  const payload = {
    dataset_id: newId,
    name: newId,
    tags: [],
    defaults: {
      userid: "",
      admin_id: "",
      phone_number_id: "",
      display_phone_number: "",
      unique_contact_per_case: true,
      contact_name: "Automation User",
      country_code: "91",
      poll_timeout_sec: 45,
      poll_interval_ms: 1500,
    },
    cases: [],
  };
  await fetchJson("/api/datasets", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  setStatus("Dataset created.");
  await refreshDatasets();
  datasetSelect.value = newId;
  datasetEditor.value = JSON.stringify(payload, null, 2);
}

async function refreshRuns() {
  const runs = await fetchJson("/api/runs");
  const tbody = document.querySelector("#runsTable tbody");
  tbody.innerHTML = "";
  runs.forEach((run) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${run.run_id}</td>
      <td>${run.dataset_id}</td>
      <td>${run.status}</td>
      <td>${run.started_at || ""}</td>
      <td>${run.ended_at || ""}</td>
      <td>${run.case_count}</td>
    `;
    tr.addEventListener("click", () => loadRun(run.run_id));
    tbody.appendChild(tr);
  });
}

async function loadRun(runId) {
  const run = await fetchJson(`/api/runs/${runId}`);
  runDetails.value = JSON.stringify(run, null, 2);
}

async function startRun() {
  const datasetId = datasetSelect.value;
  const mode = runMode.value;
  if (!datasetId && mode === "dataset") {
    setStatus("Select dataset before running.");
    return;
  }
  const tagFilter = tagFilterInput.value
    .split(",")
    .map((t) => t.trim())
    .filter((t) => t.length > 0);
  const agent = agentSelect.value;
  const maxTurns = parseInt(maxTurnsInput.value || "5", 10);
  if (mode === "agent" && !agent) {
    setStatus("Select agent before running.");
    return;
  }

  const res = await fetchJson("/api/runs", {
    method: "POST",
    body: JSON.stringify({
      mode,
      dataset_id: datasetId,
      tags: tagFilter,
      agent,
      max_turns: maxTurns,
    }),
  });

  setStatus(`Run started: ${res.run_id}`);
  currentRunId = res.run_id;
  await refreshRuns();
  await pollRun(res.run_id);
}

async function pollRun(runId) {
  let done = false;
  for (let i = 0; i < 120; i += 1) {
    const run = await fetchJson(`/api/runs/${runId}`);
    runDetails.value = JSON.stringify(run, null, 2);
    if (
      run.status === "completed" ||
      run.status === "failed" ||
      run.status === "stopped"
    ) {
      done = true;
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  if (done) {
    setStatus(`Run completed: ${runId}`);
  } else {
    setStatus(`Run in progress: ${runId}`);
  }
  await refreshRuns();
}

async function stopRun() {
  if (!currentRunId) {
    setStatus("No active run to stop.");
    return;
  }
  await fetchJson(`/api/runs/${currentRunId}/stop`, { method: "POST" });
  setStatus(`Stopping run: ${currentRunId}`);
}

document
  .getElementById("refreshDatasets")
  .addEventListener("click", refreshDatasets);
document.getElementById("loadDataset").addEventListener("click", loadDataset);
document.getElementById("saveDataset").addEventListener("click", saveDataset);
document
  .getElementById("createDataset")
  .addEventListener("click", createDataset);
document.getElementById("refreshRuns").addEventListener("click", refreshRuns);
document.getElementById("startRun").addEventListener("click", startRun);
runMode.addEventListener("change", updateModeUI);
stopRunButton.addEventListener("click", stopRun);

refreshDatasets()
  .then(refreshRuns)
  .catch(() => {});

updateModeUI();
