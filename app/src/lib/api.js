/**
 * REST API wrappers. Uses relative URLs so the Vite dev proxy
 * forwards to the backend at localhost:3737.
 */

async function request(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${url} — ${body}`);
  }

  return res.json();
}

/** GET /api/sessions — list all sessions */
export function fetchSessions() {
  return request('/api/sessions');
}

/** GET /api/sessions/:id — single session detail */
export function fetchSession(id) {
  return request(`/api/sessions/${id}`);
}

/** GET /api/stats — aggregated stats */
export function fetchStats() {
  return request('/api/stats');
}

/** GET /api/progress — driver progress / trends */
export function fetchProgress() {
  return request('/api/progress');
}

/**
 * POST /api/bridge/pit — send a pit command to the bridge.
 * @param {object} params - Pit stop parameters (fuel, tires, etc.)
 */
export function sendPitCommand(params) {
  return request('/api/bridge/pit', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}
