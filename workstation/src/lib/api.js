/**
 * API client for PitWall37 backend.
 */

const BASE = '';

async function get(url) {
  const resp = await fetch(`${BASE}${url}`);
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status}: ${body}`);
  }
  return resp.json();
}

export function fetchSessions() {
  return get('/api/sessions');
}

export function fetchSession(id) {
  return get(`/api/sessions/${id}`);
}

export function fetchLapTelemetry(sessionId, lapNumber) {
  return get(`/api/laps/${sessionId}/${lapNumber}/telemetry`);
}

export function fetchTireData(sessionId, lapNumber) {
  return get(`/api/tires/${sessionId}/${lapNumber}`);
}

export function fetchSetup(sessionId) {
  return get(`/api/setup/${sessionId}`);
}

export function fetchStats() {
  return get('/api/stats');
}

export function fetchProgress() {
  return get('/api/progress');
}

export function fetchDriverModel(track) {
  const qs = track ? `?track=${encodeURIComponent(track)}` : '';
  return get(`/api/insights/driver-model${qs}`);
}

export function fetchTaxonomy(track) {
  const qs = track ? `?track=${encodeURIComponent(track)}` : '';
  return get(`/api/insights/taxonomy${qs}`);
}

export function fetchSessionDebrief(sessionId) {
  return get(`/api/sessions/${sessionId}/debrief`);
}

export async function createRecommendation(payload) {
  const resp = await fetch('/api/recommendations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status}: ${body}`);
  }
  return resp.json();
}

export async function createExperiment(payload) {
  const resp = await fetch('/api/experiments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`API ${resp.status}: ${body}`);
  }
  return resp.json();
}
