let _envEditing = null;
let _envsMounted = false;

async function mount_environments() {
  await _loadEnvList();
  if (!_envsMounted) {
    document.getElementById("createEnvBtn").addEventListener("click", _createEnv);
    document.getElementById("saveEnv").addEventListener("click", _saveEnv);
    document.getElementById("cancelEnvEdit").addEventListener("click", _closeEnvEditor);
    // Re-render when active env changes from sidebar
    document.addEventListener("env-changed", _loadEnvList);
    _envsMounted = true;
  }
}

async function _loadEnvList() {
  const list = document.getElementById("envList");
  if (!list) return;
  try {
    const envs = await API.environments.list();
    const activeId = ENV.getActiveId();
    list.innerHTML = envs.map(e => {
      const isActive = e.env_id === activeId;
      const urlDisplay = e.webhook_base_url
        ? `<span class="hint" style="font-size:11px">${e.webhook_base_url}</span>`
        : `<span class="hint warn" style="font-size:11px">No webhook URL set</span>`;
      return `
        <div class="env-card ${isActive ? "env-card-active" : ""}">
          <div class="env-card-left">
            <span class="env-dot env-dot-${e.color || "slate"}" style="width:10px;height:10px"></span>
            <div>
              <div style="display:flex;align-items:center;gap:8px">
                <span class="env-card-name">${e.name}</span>
                ${isActive ? `<span class="env-active-badge">Active</span>` : ""}
              </div>
              ${urlDisplay}
            </div>
          </div>
          <div class="env-card-right">
            <button class="btn-sm btn-ghost" onclick="ENV.setActiveId('${e.env_id}'); _loadEnvList();">
              ${isActive ? "✓ Active" : "Set Active"}
            </button>
            <button class="btn-sm" onclick="_editEnv('${e.env_id}')">Edit</button>
            ${!["dev", "qa", "prod"].includes(e.env_id)
              ? `<button class="btn-sm btn-danger" onclick="_deleteEnv('${e.env_id}')">Delete</button>`
              : ""}
          </div>
        </div>`;
    }).join("") || `<p class="empty-hint">No environments yet.</p>`;
  } catch (err) {
    list.innerHTML = `<div class="error-hint">Failed to load environments: ${err.message}</div>`;
  }
}

async function _editEnv(envId) {
  try {
    const e = await API.environments.get(envId);
    _envEditing = envId;
    document.getElementById("envEditorTitle").textContent = "Editing: " + e.name;
    document.getElementById("envEditorFields").innerHTML = _buildEnvForm(e);
    document.getElementById("envEditorPanel").classList.remove("hidden");
    document.getElementById("envEditorPanel").scrollIntoView({ behavior: "smooth" });
  } catch (err) {
    alert("Failed to load environment: " + err.message);
  }
}

function _buildEnvForm(e) {
  const field = (label, key, placeholder, hint) => `
    <div class="field-group">
      <label class="field-label">${label}${hint ? ` <span class="field-hint">${hint}</span>` : ""}</label>
      <input class="input-full env-field" data-key="${key}"
             value="${(e[key] || "").replace(/"/g, "&quot;")}"
             placeholder="${placeholder}" />
    </div>`;

  return `
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 20px">
      ${field("Name", "name", "e.g. Staging", "")}
      <div class="field-group">
        <label class="field-label">Badge Color</label>
        <select class="env-field select-full" data-key="color">
          ${["slate", "blue", "green", "amber", "red"].map(c =>
            `<option value="${c}" ${(e.color || "slate") === c ? "selected" : ""}>${c}</option>`
          ).join("")}
        </select>
      </div>
    </div>
    ${field("Webhook Base URL", "webhook_base_url",
      "https://your-server.com/api/whatsapp/meta/webhook",
      "required — the URL test messages are POSTed to")}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 20px">
      ${field("Admin ID", "admin_id", "MongoDB ObjectId of the admin account", "AI_TEST_ADMIN_ID")}
      ${field("User ID", "user_id", "Usually same as Admin ID", "AI_TEST_USER_ID")}
      ${field("Phone Number ID", "phone_number_id", "WhatsApp phone number ID", "AI_TEST_PHONE_NUMBER_ID")}
      ${field("Display Phone Number", "display_phone_number", "+91XXXXXXXXXX", "AI_TEST_DISPLAY_PHONE_NUMBER")}
      ${field("Test Phone Number", "phone_number", "+91XXXXXXXXXX", "AI_TEST_PHONE_NUMBER — SIM used to send test messages")}
      ${field("Contact Name", "contact_name", "Automation User", "AI_TEST_USER_NAME — name shown in WhatsApp")}
      ${field("Country Code", "country_code", "91", "")}
    </div>`;
}

async function _saveEnv() {
  if (!_envEditing) return;
  const data = { env_id: _envEditing };
  document.querySelectorAll(".env-field").forEach(el => {
    data[el.dataset.key] = el.value.trim();
  });
  try {
    await API.environments.save(_envEditing, data);
    _closeEnvEditor();
    await _loadEnvList();
    if (typeof _refreshSidebarEnv === "function") _refreshSidebarEnv();
  } catch (err) {
    alert("Save failed: " + err.message);
  }
}

async function _createEnv() {
  const name = prompt("New environment name (e.g. Staging):");
  if (!name || !name.trim()) return;
  const env_id = name.trim().toLowerCase().replace(/\s+/g, "_");
  try {
    await API.environments.create({
      env_id, name: name.trim(), color: "slate",
      webhook_base_url: "", admin_id: "", user_id: "",
      phone_number: "", phone_number_id: "", display_phone_number: "",
      contact_name: "Automation User", country_code: "91",
    });
    await _loadEnvList();
    _editEnv(env_id);
  } catch (err) {
    alert("Create failed: " + err.message);
  }
}

async function _deleteEnv(envId) {
  if (!confirm(`Delete environment "${envId}"? This cannot be undone.`)) return;
  try {
    await API.environments.delete(envId);
    if (ENV.getActiveId() === envId) ENV.setActiveId("");
    await _loadEnvList();
    if (typeof _refreshSidebarEnv === "function") _refreshSidebarEnv();
  } catch (err) {
    alert("Delete failed: " + err.message);
  }
}

function _closeEnvEditor() {
  document.getElementById("envEditorPanel").classList.add("hidden");
  _envEditing = null;
}
