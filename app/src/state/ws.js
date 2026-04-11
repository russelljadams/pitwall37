import { signal } from '@preact/signals';
import { dispatch } from './live.js';

// 'disconnected' | 'connecting' | 'connected'
export const connectionState = signal('disconnected');

let ws = null;
let reconnectTimer = null;
let backoff = 1000;

const MIN_BACKOFF = 1000;
const MAX_BACKOFF = 30000;

function getWsUrl() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${location.host}/ws/live`;
}

function scheduleReconnect() {
  if (reconnectTimer) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, backoff);
  backoff = Math.min(backoff * 2, MAX_BACKOFF);
}

/**
 * Opens a WebSocket connection to /ws/live.
 * Automatically reconnects with exponential backoff on close or error.
 */
export function connect() {
  // Tear down any existing connection
  if (ws) {
    try { ws.close(); } catch (_) { /* noop */ }
    ws = null;
  }

  connectionState.value = 'connecting';

  ws = new WebSocket(getWsUrl());

  ws.onopen = () => {
    connectionState.value = 'connected';
    backoff = MIN_BACKOFF;
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      dispatch(msg);
    } catch (err) {
      console.warn('[ws] failed to parse message', err);
    }
  };

  ws.onclose = () => {
    ws = null;
    connectionState.value = 'disconnected';
    scheduleReconnect();
  };

  ws.onerror = () => {
    // onclose will fire after onerror, triggering reconnect
    connectionState.value = 'disconnected';
  };
}

/**
 * Manually disconnect and stop reconnection attempts.
 */
export function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer);
    reconnectTimer = null;
  }
  if (ws) {
    try { ws.close(); } catch (_) { /* noop */ }
    ws = null;
  }
  connectionState.value = 'disconnected';
  backoff = MIN_BACKOFF;
}
