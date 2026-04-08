/* ── SAURON REST client ──────────────────────────── */
const API = (() => {
  const base = location.origin.replace(/:\d+$/, "") + ":" + (location.port || 8000);
  // When served from the backend itself (same port) we can use origin directly.
  const origin = location.origin;
  const token = () => localStorage.getItem("sauron_token") || "";

  async function req(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    const t = token();
    if (t) headers.Authorization = "Bearer " + t;
    const r = await fetch(origin + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`${method} ${path} → ${r.status}: ${text}`);
    }
    if (r.headers.get("content-type")?.includes("application/json")) {
      return await r.json();
    }
    return await r.text();
  }

  return {
    token,
    setToken: (t) => localStorage.setItem("sauron_token", t),
    clearToken: () => localStorage.removeItem("sauron_token"),

    health: () => req("GET", "/api/health"),
    login: (username, password) => req("POST", "/api/auth/login", { username, password }),

    profiles: () => req("GET", "/api/engagements/profiles"),
    listEngagements: () => req("GET", "/api/engagements"),
    createEngagement: (data) => req("POST", "/api/engagements", data),
    startEngagement: (id) => req("POST", `/api/engagements/${id}/start`),
    findings: (id) => req("GET", `/api/engagements/${id}/findings`),
    buildReport: (id) => req("POST", `/api/engagements/${id}/report`),

    listTools: () => req("GET", "/api/tools"),
    runTool: (data) => req("POST", "/api/tools/run", data),

    llmProviders: () => req("GET", "/api/llm/providers"),
    llmChat: (data) => req("POST", "/api/llm/chat", data),
  };
})();
