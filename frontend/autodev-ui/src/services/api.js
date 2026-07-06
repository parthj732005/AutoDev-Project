const BASE = "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  getSettings: () => request("/settings/"),
  getProviders: () => request("/settings/providers"),
  saveSettings: (data) =>
    request("/settings/", { method: "POST", body: JSON.stringify(data) }),
  getGeneratedProjects: () => request("/projects/generated"),
  getGeneratedProject: (name) => request(`/projects/generated/${name}`),
  openInVSCode: (name) =>
    request(`/projects/generated/${name}/open-vscode`, { method: "POST" }),
  getSetupInstructions: (name) =>
    request(`/projects/generated/${name}/setup-instructions`, { method: "POST" }),
};
