const ROUTES = {
  "/":             "dashboard",
  "/datasets":     "datasets",
  "/run":          "run",
  "/history":      "history",
  "/environments": "environments",
};

function getHash() {
  return window.location.hash.replace("#", "") || "/";
}

function navigate(hash) {
  window.location.hash = hash;
}

function renderRoute() {
  const hash = getHash();
  const base = "/" + (hash.replace(/^\//, "").split("/")[0] || "");
  const pageId = ROUTES[base] || "dashboard";

  document.querySelectorAll(".page-view").forEach(el => el.classList.add("hidden"));
  const page = document.getElementById("page-" + pageId);
  if (page) page.classList.remove("hidden");

  document.querySelectorAll(".nav-item").forEach(a => {
    a.classList.toggle("active", a.dataset.page === pageId);
  });

  const mountFn = window["mount_" + pageId];
  if (typeof mountFn === "function") mountFn(hash);
}

window.addEventListener("hashchange", renderRoute);
window.addEventListener("load", renderRoute);
