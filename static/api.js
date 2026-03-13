const API = {
  async _fetch(path, options = {}) {
    const res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    return res.json();
  },

  get(path)          { return API._fetch(path); },
  post(path, body)   { return API._fetch(path, { method: "POST",  body: JSON.stringify(body) }); },
  put(path, body)    { return API._fetch(path, { method: "PUT",   body: JSON.stringify(body) }); },

  datasets: {
    list: ()       => API.get("/api/datasets"),
    get:  (id)     => API.get(`/api/datasets/${id}`),
    save: (id, d)  => API.put(`/api/datasets/${id}`, d),
    create: (d)    => API.post("/api/datasets", d),
  },
  runs: {
    list: ()       => API.get("/api/runs"),
    get:  (id)     => API.get(`/api/runs/${id}`),
    start: (body)  => API.post("/api/runs", body),
    stop:  (id)    => API.post(`/api/runs/${id}/stop`, {}),
  },
  agents: {
    list: ()       => API.get("/api/agents"),
  },
  environments: {
    list:   ()        => API.get("/api/environments"),
    get:    (id)      => API.get(`/api/environments/${id}`),
    save:   (id, d)   => API.put(`/api/environments/${id}`, d),
    create: (d)       => API.post("/api/environments", d),
    delete: (id)      => API._fetch(`/api/environments/${id}`, { method: "DELETE" }),
  },
};
