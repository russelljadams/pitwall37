import { laps } from '../state/live.js';
import { formatLapTime, formatDelta } from '../lib/format.js';

export function LapTicker() {
  const lapList = laps.value;

  return (
    <div class="panel panel-ticker">
      <div class="panel-header">LAP TIMES</div>
      <div class="panel-body ticker-body">
        {lapList.length === 0 ? (
          <div class="ticker-empty">No laps recorded</div>
        ) : (
          lapList.map((lap, i) => (
            <div
              key={lap.lap_number}
              class={`ticker-row ${i === 0 ? 'ticker-row--new' : ''} ${lap.isPB ? 'ticker-row--pb' : ''}`}
            >
              <span class="ticker-lap-num">L{lap.lap_number}</span>
              <span class="ticker-time">{formatLapTime(lap.lap_time)}</span>
              <span class={`ticker-delta ${
                lap.delta === null ? '' :
                lap.delta < 0 ? 'ticker-delta--faster' :
                lap.delta > 0 ? 'ticker-delta--slower' : ''
              }`}>
                {formatDelta(lap.delta)}
              </span>
              {lap.isPB && <span class="ticker-pb" title="Personal Best">PB</span>}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
