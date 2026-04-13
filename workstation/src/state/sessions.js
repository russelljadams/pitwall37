/**
 * Sessions state — fetch and cache session list.
 */
import { signal } from '@preact/signals';
import { fetchSessions } from '../lib/api.js';

export const sessions = signal([]);
export const sessionsLoading = signal(false);
export const sessionsError = signal(null);
export const trackFilter = signal(null);
export const sortField = signal('session_date');
export const sortDir = signal('desc');

/** Unique track names from loaded sessions */
export function getTracks() {
  const tracks = new Set();
  for (const s of sessions.value) {
    if (s.track) tracks.add(s.track);
  }
  return Array.from(tracks).sort();
}

/** Get filtered and sorted sessions */
export function getFilteredSessions() {
  let list = sessions.value;
  const filter = trackFilter.value;
  if (filter) {
    list = list.filter(s => s.track === filter);
  }
  const field = sortField.value;
  const dir = sortDir.value === 'asc' ? 1 : -1;
  return [...list].sort((a, b) => {
    let va = a[field];
    let vb = b[field];
    if (va == null) return 1;
    if (vb == null) return -1;
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return -1 * dir;
    if (va > vb) return 1 * dir;
    return 0;
  });
}

/** Toggle sort on a column */
export function toggleSort(field) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc';
  } else {
    sortField.value = field;
    sortDir.value = field === 'session_date' ? 'desc' : 'asc';
  }
}

/** Load sessions from API */
export async function loadSessions() {
  if (sessionsLoading.value) return;
  sessionsLoading.value = true;
  sessionsError.value = null;
  try {
    sessions.value = await fetchSessions();
  } catch (e) {
    sessionsError.value = e.message;
  } finally {
    sessionsLoading.value = false;
  }
}
