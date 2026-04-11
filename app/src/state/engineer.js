/**
 * Engineer chat state — pit wall radio comms with the AI race engineer.
 */
import { signal } from '@preact/signals';
import { sessionInfo, telemetry, laps, liveSetup } from './live.js';

export const messages = signal([]);
export const isStreaming = signal(false);

let engineerWs = null;
let reconnectTimer = null;

function connectEngineer() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${location.host}/ws/engineer`;

  engineerWs = new WebSocket(url);

  engineerWs.onopen = () => {
    console.log('[PW37] Engineer WS connected');
  };

  engineerWs.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === 'chunk') {
        const current = messages.value;
        const last = current[current.length - 1];
        if (last && last.streaming) {
          const updated = [...current];
          updated[updated.length - 1] = {
            ...last,
            text: last.text + msg.content,
          };
          messages.value = updated;
        }
      } else if (msg.type === 'done') {
        const current = messages.value;
        const last = current[current.length - 1];
        if (last && last.streaming) {
          const updated = [...current];
          updated[updated.length - 1] = { ...last, streaming: false };
          messages.value = updated;
        }
        isStreaming.value = false;
      } else if (msg.type === 'error') {
        const current = messages.value;
        const last = current[current.length - 1];
        if (last && last.streaming) {
          const updated = [...current];
          updated[updated.length - 1] = {
            ...last,
            text: last.text || `[Error: ${msg.content}]`,
            streaming: false,
          };
          messages.value = updated;
        }
        isStreaming.value = false;
      }
    } catch (err) {
      console.error('[PW37] Engineer parse error:', err);
    }
  };

  engineerWs.onclose = () => {
    console.log('[PW37] Engineer WS disconnected');
    engineerWs = null;
    isStreaming.value = false;
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectEngineer, 3000);
  };

  engineerWs.onerror = () => {
    engineerWs.close();
  };
}

function buildContext() {
  const ctx = {};
  if (sessionInfo.value) ctx.session = sessionInfo.value;
  if (telemetry.value) {
    const t = telemetry.value;
    ctx.telemetry = {
      speed: t.speed,
      rpm: t.rpm,
      gear: t.gear,
      fuel_level: t.fuel_level,
      fuel_pct: t.fuel_pct,
      lap: t.lap,
      on_track: t.on_track,
      in_garage: t.in_garage,
    };
  }
  const lapList = laps.value;
  if (lapList.length > 0) {
    ctx.recent_laps = lapList.slice(0, 10).map(l => ({
      lap: l.lap_number,
      time: l.lap_time,
      delta: l.delta,
      isPB: l.isPB,
    }));
  }
  if (liveSetup.value) {
    ctx.setup = liveSetup.value;
  }
  return ctx;
}

export function sendMessage(text) {
  if (!text.trim() || isStreaming.value) return;
  if (!engineerWs || engineerWs.readyState !== WebSocket.OPEN) {
    connectEngineer();
    setTimeout(() => sendMessage(text), 1000);
    return;
  }

  const now = new Date().toISOString();

  messages.value = [
    ...messages.value,
    { role: 'DRIVER', text: text.trim(), ts: now, streaming: false },
  ];

  messages.value = [
    ...messages.value,
    { role: 'ENGINEER', text: '', ts: now, streaming: true },
  ];

  isStreaming.value = true;

  engineerWs.send(JSON.stringify({
    message: text.trim(),
    context: buildContext(),
  }));
}

// Auto-connect on import
connectEngineer();
