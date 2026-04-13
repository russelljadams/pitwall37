/**
 * Formatting utilities for the PitWall37 workstation.
 */

/** Format lap time (seconds) as M:SS.mmm */
export function formatLapTime(seconds) {
  if (!seconds || seconds <= 0) return '--:--.---';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toFixed(3).padStart(6, '0')}`;
}

/** Format delta as +/-S.mmm with sign */
export function formatDelta(delta) {
  if (delta === null || delta === undefined) return '';
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${delta.toFixed(3)}`;
}

/** Format speed: m/s to km/h */
export function formatSpeed(mps) {
  if (!mps && mps !== 0) return '---';
  return Math.round(mps * 3.6).toString();
}

/** Format date string to compact display */
export function formatDate(dateStr) {
  if (!dateStr) return '--';
  const d = new Date(dateStr);
  if (isNaN(d)) return dateStr;
  return d.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: '2-digit',
  });
}

/** Format timestamp for chat log */
export function formatTimestamp(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Format a setup value for display */
export function formatSetupValue(val) {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'string') return val;
  if (typeof val === 'number') {
    if (Number.isInteger(val)) return val.toString();
    return val.toFixed(2);
  }
  if (typeof val === 'object' && !Array.isArray(val)) {
    // Nested object — show key:value pairs inline
    return Object.entries(val)
      .map(([k, v]) => `${k}: ${formatSetupValue(v)}`)
      .join(', ');
  }
  if (Array.isArray(val)) {
    return val.map(v => formatSetupValue(v)).join(', ');
  }
  return String(val);
}

/** Lap comparison color palette */
export const LAP_COLORS = [
  '#e8364e', // red
  '#3b82f6', // blue
  '#22c55e', // green
  '#f59e0b', // amber
  '#a855f7', // purple
  '#06b6d4', // cyan
];

/** Get color for a lap index in the selection */
export function getLapColor(index) {
  return LAP_COLORS[index % LAP_COLORS.length];
}
