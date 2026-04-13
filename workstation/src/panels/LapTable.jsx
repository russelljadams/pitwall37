/**
 * LapTable — display laps for the selected session.
 * Click to select, Ctrl/Cmd+click to multi-select for comparison.
 */
import {
  selectedSession, sessionLoading, selectedLapNumbers,
  selectLap, toggleLap,
} from '../state/selection.js';
import { PanelShell } from '../components/PanelShell.jsx';
import { formatLapTime, formatDelta, formatSpeed } from '../lib/format.js';

export function LapTable() {
  const data = selectedSession.value;
  const loading = sessionLoading.value;
  const selLaps = selectedLapNumbers.value;

  if (!data && !loading) {
    return (
      <PanelShell title="LAPS">
        <div class="panel-empty">
          <div class="panel-empty-label">NO SESSION</div>
          <div class="panel-empty-hint">Select a session to view laps</div>
        </div>
      </PanelShell>
    );
  }

  if (loading) {
    return (
      <PanelShell title="LAPS">
        <div class="sb-loading">LOADING...</div>
      </PanelShell>
    );
  }

  const laps = data.laps || [];
  const session = data.session || {};

  // Find best lap time
  const validLaps = laps.filter(l => l.valid && l.lap_time > 0);
  const bestTime = validLaps.length > 0
    ? Math.min(...validLaps.map(l => l.lap_time))
    : null;

  function handleClick(e, lapNum) {
    if (e.ctrlKey || e.metaKey) {
      toggleLap(lapNum);
    } else {
      selectLap(lapNum);
    }
  }

  return (
    <PanelShell title="LAPS" badge={`${validLaps.length} valid`}>
      <div class="lt-hint">Click to select / Ctrl+click to compare</div>
      <table class="lt-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Time</th>
            <th>S1</th>
            <th>S2</th>
            <th>S3</th>
            <th>Spd</th>
            <th>Fuel</th>
          </tr>
        </thead>
        <tbody>
          {laps.map(lap => {
            const isBest = lap.lap_time === bestTime && lap.valid;
            const selIdx = selLaps.indexOf(lap.lap_number);
            const isSelected = selIdx >= 0;
            const delta = bestTime && lap.lap_time > 0 && lap.valid
              ? lap.lap_time - bestTime
              : null;

            let rowClass = '';
            if (!lap.valid) rowClass += ' lt-invalid';
            if (isBest) rowClass += ' lt-best';
            if (isSelected) rowClass += ` lt-selected lt-sel-${selIdx}`;

            return (
              <tr
                key={lap.lap_number}
                class={rowClass}
                onClick={(e) => handleClick(e, lap.lap_number)}
              >
                <td>{lap.lap_number}</td>
                <td class="lt-time">{formatLapTime(lap.lap_time)}</td>
                <td class="lt-sector">{lap.sector_1 ? lap.sector_1.toFixed(2) : '-'}</td>
                <td class="lt-sector">{lap.sector_2 ? lap.sector_2.toFixed(2) : '-'}</td>
                <td class="lt-sector">{lap.sector_3 ? lap.sector_3.toFixed(2) : '-'}</td>
                <td class="lt-speed">{formatSpeed(lap.avg_speed_ms)}</td>
                <td class="lt-fuel">{lap.fuel_used != null ? lap.fuel_used.toFixed(2) : '-'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </PanelShell>
  );
}
