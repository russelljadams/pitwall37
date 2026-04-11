/**
 * Formatting utilities for the PitWall37 dashboard.
 */

/** Format lap time as M:SS.mmm */
export function formatLapTime(seconds) {
  if (!seconds || seconds <= 0) return '--:--.---';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toFixed(3).padStart(6, '0')}`;
}

/** Format delta as +/-S.mmm */
export function formatDelta(delta) {
  if (delta === null || delta === undefined) return '';
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${delta.toFixed(3)}`;
}

/** Format speed in km/h */
export function formatSpeed(mps) {
  if (!mps && mps !== 0) return '---';
  return Math.round(mps * 3.6).toString();
}

/** Format RPM with comma separator */
export function formatRPM(rpm) {
  if (!rpm && rpm !== 0) return '----';
  return Math.round(rpm).toLocaleString('en-US');
}

/** Format fuel level in liters */
export function formatFuel(liters) {
  if (!liters && liters !== 0) return '--.-';
  return liters.toFixed(1);
}

/** Format gear: R, N, 1-6 */
export function formatGear(gear) {
  if (gear === undefined || gear === null) return '-';
  if (gear === -1) return 'R';
  if (gear === 0) return 'N';
  return gear.toString();
}

/** Format timestamp for radio log */
export function formatTimestamp(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

/** Format session time (seconds) as H:MM:SS */
export function formatSessionTime(seconds) {
  if (!seconds) return '0:00:00';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

/** Format a number with fixed precision for setup values */
export function formatSetupValue(val) {
  if (val === null || val === undefined) return '-';
  if (typeof val === 'string') return val;
  if (typeof val === 'number') {
    if (Number.isInteger(val)) return val.toString();
    return val.toFixed(2);
  }
  return String(val);
}
