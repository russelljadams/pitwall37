/**
 * Live telemetry state — signals updated by the WebSocket connection.
 * All dashboard panels read from these signals reactively.
 */
import { signal, computed } from '@preact/signals';

// --- Connection state ---
export const bridgeConnected = signal(false);
export const iracingConnected = signal(false);

// --- Session info ---
export const sessionInfo = signal(null);

// --- Live telemetry (10Hz from bridge) ---
export const telemetry = signal(null);

// --- Completed laps ---
export const laps = signal([]);

// --- Live setup from iRacing ---
export const liveSetup = signal(null);

// --- Derived values ---
export const currentLap = computed(() => telemetry.value?.lap ?? 0);
export const speedKmh = computed(() => (telemetry.value?.speed ?? 0) * 3.6);
export const fuelLaps = computed(() => {
  const t = telemetry.value;
  const lapList = laps.value;
  if (!t || lapList.length < 2) return null;
  const recent = lapList.slice(0, 5); // newest first
  let totalUsed = 0;
  let count = 0;
  for (let i = 0; i < recent.length - 1; i++) {
    const used = recent[i + 1].fuel_level - recent[i].fuel_level;
    if (used > 0) { totalUsed += used; count++; }
  }
  if (count === 0) return null;
  const avgPerLap = totalUsed / count;
  if (avgPerLap <= 0) return null;
  return t.fuel_level / avgPerLap;
});

export const personalBest = computed(() => {
  const lapList = laps.value;
  if (lapList.length === 0) return null;
  let best = Infinity;
  for (const l of lapList) {
    if (l.lap_time > 0 && l.lap_time < best) best = l.lap_time;
  }
  return best === Infinity ? null : best;
});

// --- WebSocket connection ---
let ws = null;
let reconnectTimer = null;

function processMessage(msg) {
  const { type, data } = msg;

  switch (type) {
    case 'init':
      bridgeConnected.value = data.bridge_connected;
      iracingConnected.value = data.iracing_connected;
      if (data.session_info) sessionInfo.value = data.session_info;
      break;

    case 'telemetry':
      telemetry.value = data;
      break;

    case 'session_info':
      sessionInfo.value = data;
      break;

    case 'setup_update':
      liveSetup.value = data.setup ?? data;
      break;

    case 'lap_complete': {
      const pb = personalBest.value;
      const delta = pb && data.lap_time > 0 ? data.lap_time - pb : null;
      const isPB = pb === null || (data.lap_time > 0 && data.lap_time <= pb);
      const lap = {
        lap_number: data.lap_number,
        lap_time: data.lap_time,
        fuel_level: data.fuel_level,
        delta,
        isPB,
      };
      laps.value = [lap, ...laps.value];
      break;
    }

    case 'state':
      if (data.event === 'in_garage') {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ command: 'get_setup' }));
        }
      }
      break;

    case 'bridge_disconnected':
      bridgeConnected.value = false;
      iracingConnected.value = false;
      break;
  }
}

export function connect() {
  if (ws) return;

  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${location.host}/ws/live`;

  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('[PW37] Live WS connected');
    ws.send(JSON.stringify({ command: 'get_setup' }));
  };

  ws.onmessage = (e) => {
    try {
      processMessage(JSON.parse(e.data));
    } catch (err) {
      console.error('[PW37] Parse error:', err);
    }
  };

  ws.onclose = () => {
    console.log('[PW37] Live WS disconnected, reconnecting...');
    ws = null;
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = (err) => {
    console.error('[PW37] WS error:', err);
    ws.close();
  };
}

export function getWs() {
  return ws;
}
