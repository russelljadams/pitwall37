/**
 * Global selection state — drives what all panels show.
 */
import { signal, computed } from '@preact/signals';
import { fetchSession, fetchLapTelemetry, fetchSetup } from '../lib/api.js';

// Primary session
export const selectedSessionId = signal(null);
export const selectedSession = signal(null);       // { session, laps, setup }
export const sessionLoading = signal(false);

// Selected laps within the session
export const selectedLapNumbers = signal([]);       // array of lap numbers
export const selectedLapData = signal({});          // lap_number -> telemetry data
export const lapLoadingSet = signal(new Set());     // which laps are currently loading

// Compare session (for setup diff)
export const compareSessionId = signal(null);
export const compareSession = signal(null);
export const compareLoading = signal(false);

// Focused setup parameter (clicked in setup viewer)
export const focusedSetupParam = signal(null);

/** Select a session — fetches full detail */
export async function selectSession(id) {
  if (selectedSessionId.value === id) return;

  selectedSessionId.value = id;
  selectedSession.value = null;
  selectedLapNumbers.value = [];
  selectedLapData.value = {};
  sessionLoading.value = true;
  focusedSetupParam.value = null;

  try {
    const data = await fetchSession(id);
    selectedSession.value = data;
  } catch (e) {
    console.error('[WS] Failed to load session:', e);
    selectedSession.value = null;
  } finally {
    sessionLoading.value = false;
  }
}

/** Set a compare session (shift-click in session browser) */
export async function setCompareSession(id) {
  if (compareSessionId.value === id) {
    // Deselect
    compareSessionId.value = null;
    compareSession.value = null;
    return;
  }
  compareSessionId.value = id;
  compareSession.value = null;
  compareLoading.value = true;
  try {
    const data = await fetchSession(id);
    compareSession.value = data;
  } catch (e) {
    console.error('[WS] Failed to load compare session:', e);
    compareSession.value = null;
  } finally {
    compareLoading.value = false;
  }
}

/** Select a single lap (replaces selection) */
export async function selectLap(lapNumber) {
  selectedLapNumbers.value = [lapNumber];
  await loadLapTelemetry(lapNumber);
}

/** Toggle a lap in the selection (Ctrl/Cmd+click) */
export async function toggleLap(lapNumber) {
  const current = selectedLapNumbers.value;
  const idx = current.indexOf(lapNumber);
  if (idx >= 0) {
    // Remove
    selectedLapNumbers.value = current.filter(n => n !== lapNumber);
    const data = { ...selectedLapData.value };
    delete data[lapNumber];
    selectedLapData.value = data;
  } else {
    // Add (max 6)
    if (current.length >= 6) return;
    selectedLapNumbers.value = [...current, lapNumber];
    await loadLapTelemetry(lapNumber);
  }
}

/** Load telemetry for a lap */
async function loadLapTelemetry(lapNumber) {
  const sid = selectedSessionId.value;
  if (!sid) return;

  const loading = new Set(lapLoadingSet.value);
  loading.add(lapNumber);
  lapLoadingSet.value = loading;

  try {
    const data = await fetchLapTelemetry(sid, lapNumber);
    selectedLapData.value = { ...selectedLapData.value, [lapNumber]: data };
  } catch (e) {
    console.error(`[WS] Failed to load telemetry for lap ${lapNumber}:`, e);
  } finally {
    const done = new Set(lapLoadingSet.value);
    done.delete(lapNumber);
    lapLoadingSet.value = done;
  }
}

/** Computed context for the agent */
export const agentContext = computed(() => {
  const sess = selectedSession.value;
  const ctx = {};

  if (sess && sess.session) {
    ctx.session = {
      id: sess.session.id,
      track: sess.session.track,
      track_config: sess.session.track_config,
      date: sess.session.session_date,
      best_time: sess.session.best_lap_time,
      car: sess.session.car,
      total_laps: sess.session.total_laps,
    };
  }

  if (selectedLapNumbers.value.length > 0) {
    ctx.selected_laps = selectedLapNumbers.value;
  }

  const cmp = compareSession.value;
  if (cmp && cmp.session) {
    ctx.compare_session = {
      id: cmp.session.id,
      track: cmp.session.track,
      date: cmp.session.session_date,
    };
  }

  if (focusedSetupParam.value) {
    ctx.focused_param = focusedSetupParam.value;
  }

  return ctx;
});

/** Build context summary string for display */
export const contextSummary = computed(() => {
  const parts = [];
  const sess = selectedSession.value;
  if (sess && sess.session) {
    const track = sess.session.track || '?';
    const date = sess.session.session_date
      ? new Date(sess.session.session_date).toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit' })
      : '';
    parts.push(`${track} ${date}`);
  }
  if (selectedLapNumbers.value.length > 0) {
    parts.push(`Laps ${selectedLapNumbers.value.join(', ')}`);
  }
  if (compareSession.value) {
    parts.push('Setup diff active');
  }
  if (focusedSetupParam.value) {
    parts.push(focusedSetupParam.value);
  }
  return parts.join(' \u2022 ');
});
