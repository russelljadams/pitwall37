/**
 * Engineer chat state — pit wall radio comms via Claude Code SDK agent.
 * Handles text chunks, tool usage indicators, and result messages.
 */
import { signal } from '@preact/signals';
import { sessionInfo, telemetry, laps, liveSetup } from './live.js';

export const messages = signal([]);
export const isStreaming = signal(false);
export const activeTools = signal([]);  // Currently executing tools

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
        // Text from the agent — append to current streaming message
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
        // Agent is calling a tool — show indicator
        const toolName = msg.tool || 'unknown';
        activeTools.value = [...activeTools.value, toolName];

        // Add tool usage note to the message stream
        const current = messages.value;
        const last = current[current.length - 1];
        if (last && last.streaming) {
          const toolLabel = _formatToolName(toolName);
          const updated = [...current];
          const existingTools = last.tools || [];
          updated[updated.length - 1] = {
            ...last,
            tools: [...existingTools, { name: toolName, label: toolLabel, status: 'running' }],
          };
          messages.value = updated;
        }

      } else if (msg.type === 'tool_result') {
        // Tool completed — remove from active
        activeTools.value = activeTools.value.slice(1);

        // Mark tool as complete in message
        const current = messages.value;
        const last = current[current.length - 1];
        if (last && last.tools) {
          const updated = [...current];
          const tools = [...last.tools];
          const runningIdx = tools.findIndex(t => t.status === 'running');
          if (runningIdx >= 0) {
            tools[runningIdx] = { ...tools[runningIdx], status: msg.is_error ? 'error' : 'done' };
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
            turns: msg.turns,
            sessionId: msg.session_id,
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
    } catch (err) {
      console.error('[PW37] Engineer parse error:', err);
    }
  };

  engineerWs.onclose = () => {
    console.log('[PW37] Engineer WS disconnected');
    engineerWs = null;
    isStreaming.value = false;
    activeTools.value = [];
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connectEngineer, 3000);
  };

  engineerWs.onerror = () => {
    engineerWs.close();
  };
}

function _formatToolName(name) {
  // Convert tool names to readable labels
  const labels = {
    'mcp__pitwall37__query_telemetry_db': 'Querying database',
    'mcp__pitwall37__analyze_lap': 'Analyzing lap telemetry',
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
    'WebSearch': 'Searching the web',
    'WebFetch': 'Fetching web page',
    'Bash': 'Running command',
    'Read': 'Reading file',
    'Write': 'Writing file',
    'Glob': 'Searching files',
    'Grep': 'Searching code',
  };
  return labels[name] || name;
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
    { role: 'ENGINEER', text: '', ts: now, streaming: true, tools: [] },
  ];

  isStreaming.value = true;

  engineerWs.send(JSON.stringify({
    message: text.trim(),
    context: buildContext(),
  }));
}

// Handle proactive messages from the live WebSocket
window._onProactiveEngineer = (data) => {
  messages.value = [
    ...messages.value,
    {
      role: data.role || 'ENGINEER',
      text: data.text,
      ts: data.ts || new Date().toISOString(),
      streaming: false,
      proactive: true,
      event: data.event,
    },
  ];
};

// Auto-connect on import
connectEngineer();
