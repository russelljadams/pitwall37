/**
 * Agent chat state — WebSocket connection to Claude race engineer.
 * Context-aware: sends current selection state with every message.
 */
import { signal } from '@preact/signals';
import { agentContext } from './selection.js';

export const messages = signal([]);
export const isStreaming = signal(false);
export const activeTools = signal([]);
export const isConnected = signal(false);

let ws = null;
let reconnectTimer = null;

function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = `${proto}//${location.host}/ws/engineer`;

  ws = new WebSocket(url);

  ws.onopen = () => {
    console.log('[WS] Engineer connected');
    isConnected.value = true;
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      handleMessage(msg);
    } catch (err) {
      console.error('[WS] Parse error:', err);
    }
  };

  ws.onclose = () => {
    console.log('[WS] Engineer disconnected');
    ws = null;
    isConnected.value = false;
    isStreaming.value = false;
    activeTools.value = [];
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, 3000);
  };

  ws.onerror = () => {
    ws.close();
  };
}

function handleMessage(msg) {
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

  } else if (msg.type === 'tool_use') {
    const toolName = msg.tool || 'unknown';
    activeTools.value = [...activeTools.value, toolName];

    const current = messages.value;
    const last = current[current.length - 1];
    if (last && last.streaming) {
      const label = formatToolName(toolName);
      const updated = [...current];
      const tools = last.tools || [];
      updated[updated.length - 1] = {
        ...last,
        tools: [...tools, { name: toolName, label, status: 'running' }],
      };
      messages.value = updated;
    }

  } else if (msg.type === 'tool_result') {
    activeTools.value = activeTools.value.slice(1);

    const current = messages.value;
    const last = current[current.length - 1];
    if (last && last.tools) {
      const updated = [...current];
      const tools = [...last.tools];
      const idx = tools.findIndex(t => t.status === 'running');
      if (idx >= 0) {
        tools[idx] = { ...tools[idx], status: msg.is_error ? 'error' : 'done' };
      }
      updated[updated.length - 1] = { ...last, tools };
      messages.value = updated;
    }

  } else if (msg.type === 'done') {
    const current = messages.value;
    const last = current[current.length - 1];
    if (last && last.streaming) {
      const updated = [...current];
      updated[updated.length - 1] = {
        ...last,
        streaming: false,
        cost: msg.cost_usd,
      };
      messages.value = updated;
    }
    isStreaming.value = false;
    activeTools.value = [];

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
    activeTools.value = [];
  }
}

function formatToolName(name) {
  const labels = {
    'mcp__pitwall37__query_telemetry_db': 'Querying database',
    'mcp__pitwall37__analyze_lap': 'Analyzing lap',
    'mcp__pitwall37__compare_laps': 'Comparing laps',
    'mcp__pitwall37__get_live_bridge_data': 'Reading live data',
    'mcp__pitwall37__validate_setup_change': 'Validating setup',
    'mcp__pitwall37__predict_setup_effects': 'Predicting effects',
    'mcp__pitwall37__compare_session_setups': 'Comparing setups',
    'mcp__pitwall37__log_recommendation': 'Logging recommendation',
    'mcp__pitwall37__log_experiment': 'Logging experiment',
    'mcp__pitwall37__grade_recommendation': 'Grading recommendation',
    'mcp__pitwall37__get_driver_model': 'Loading driver model',
    'mcp__pitwall37__get_taxonomy_summary': 'Loading taxonomy',
    'mcp__pitwall37__get_session_debrief': 'Building debrief',
    'mcp__pitwall37__list_engineering_log': 'Reading engineering log',
    'mcp__pitwall37__list_session_events': 'Reading session events',
    'WebSearch': 'Searching web',
    'WebFetch': 'Fetching page',
    'Bash': 'Running command',
    'Read': 'Reading file',
    'Write': 'Writing file',
    'Glob': 'Searching files',
    'Grep': 'Searching code',
  };
  return labels[name] || name;
}

export function sendMessage(text) {
  if (!text.trim() || isStreaming.value) return;
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    connect();
    setTimeout(() => sendMessage(text), 1000);
    return;
  }

  const now = new Date().toISOString();

  // Add driver message
  messages.value = [
    ...messages.value,
    { role: 'driver', text: text.trim(), ts: now, streaming: false },
  ];

  // Add placeholder agent message
  messages.value = [
    ...messages.value,
    { role: 'agent', text: '', ts: now, streaming: true, tools: [] },
  ];

  isStreaming.value = true;

  // Send with context
  ws.send(JSON.stringify({
    message: text.trim(),
    context: agentContext.value,
  }));
}

// Auto-connect
connect();
