// ENV — manages active environment selection in localStorage.
// Exposed as a global so all page modules can use it.
const ENV = (() => {
  const KEY = "ai_test_active_env";

  function getActiveId() {
    return localStorage.getItem(KEY) || "";
  }

  function setActiveId(id) {
    localStorage.setItem(KEY, id);
    document.dispatchEvent(new CustomEvent("env-changed", { detail: id }));
  }

  // Returns the active env object from a pre-fetched list, falling back to
  // the first environment in the list if nothing is stored yet.
  function getActiveEnv(environments) {
    const id = getActiveId();
    return environments.find(e => e.env_id === id) || environments[0] || null;
  }

  return { getActiveId, setActiveId, getActiveEnv };
})();
