let _datasetsMounted = false;

async function mount_datasets() {
  await _loadDatasets();
  if (!_datasetsMounted) {
    document.getElementById("createDataset").addEventListener("click", _createDataset);
    document.getElementById("refreshDatasets").addEventListener("click", _loadDatasets);
    document.getElementById("saveDataset").addEventListener("click", _saveDataset);
    document.getElementById("cancelEdit").addEventListener("click", _closeEditor);
    _datasetsMounted = true;
  }
}

async function _loadDatasets() {
  const list = document.getElementById("datasetList");
  try {
    const datasets = await API.datasets.list();
    if (datasets.length === 0) {
      list.innerHTML = `<p class="empty-hint">No datasets yet. Create one above.</p>`;
      return;
    }
    list.innerHTML = datasets.map(d => `
      <div class="dataset-card" data-id="${d.dataset_id}">
        <div class="dataset-card-left">
          <span class="dataset-name">${d.dataset_id}</span>
          ${d.name && d.name !== d.dataset_id ? `<span class="hint">${d.name}</span>` : ""}
        </div>
        <div class="dataset-card-right">
          <span class="hint">${d.case_count} cases</span>
          <button class="btn-sm" onclick="event.stopPropagation(); _editDataset('${d.dataset_id}')">Edit</button>
          <a href="#/run" onclick="sessionStorage.setItem('preselect_dataset','${d.dataset_id}')" class="btn-sm btn-primary">Run</a>
        </div>
      </div>
    `).join("");
  } catch (err) {
    list.innerHTML = `<div class="error-hint">Failed to load datasets: ${err.message}</div>`;
  }
}

async function _editDataset(id) {
  try {
    const data = await API.datasets.get(id);
    document.getElementById("datasetEditor").value = JSON.stringify(data, null, 2);
    document.getElementById("datasetEditorTitle").textContent = "Editing: " + id;
    document.getElementById("datasetEditorPanel").classList.remove("hidden");
    document.getElementById("datasetEditorPanel").scrollIntoView({ behavior: "smooth" });
    document.getElementById("datasetEditor").dataset.editingId = id;
  } catch (err) {
    alert("Failed to load dataset: " + err.message);
  }
}

async function _saveDataset() {
  const id = document.getElementById("datasetEditor").dataset.editingId;
  if (!id) return;
  let payload;
  try {
    payload = JSON.parse(document.getElementById("datasetEditor").value);
  } catch {
    alert("Invalid JSON — please fix before saving.");
    return;
  }
  try {
    await API.datasets.save(id, payload);
    _closeEditor();
    await _loadDatasets();
  } catch (err) {
    alert("Save failed: " + err.message);
  }
}

function _closeEditor() {
  document.getElementById("datasetEditorPanel").classList.add("hidden");
  document.getElementById("datasetEditor").value = "";
  document.getElementById("datasetEditor").dataset.editingId = "";
}

async function _createDataset() {
  const newId = document.getElementById("newDatasetId").value.trim();
  if (!newId) { alert("Dataset ID is required."); return; }
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
  try {
    await API.datasets.create(payload);
    document.getElementById("newDatasetId").value = "";
    await _loadDatasets();
    _editDataset(newId);
  } catch (err) {
    alert("Create failed: " + err.message);
  }
}
