import { bridgeConnected, iracingConnected, sessionInfo, currentLap } from '../state/live.js';

export function StatusBar() {
  return (
    <div class="status-bar">
      <span class="sb-brand">PITWALL37</span>

      <div class="sb-indicator">
        <span class={`sb-dot ${bridgeConnected.value ? 'sb-dot--on' : 'sb-dot--off'}`} />
        <span class="sb-label">BRIDGE</span>
      </div>

      <div class="sb-indicator">
        <span class={`sb-dot ${iracingConnected.value ? 'sb-dot--on' : 'sb-dot--off'}`} />
        <span class="sb-label">iRACING</span>
      </div>

      {sessionInfo.value && (
        <span class="sb-session">
          {sessionInfo.value.car}
          <span class="sb-sep">//</span>
          {sessionInfo.value.track}
          {sessionInfo.value.track_config ? ` — ${sessionInfo.value.track_config}` : ''}
        </span>
      )}

      <span class="sb-spacer" />

      <span class="sb-lap">
        LAP <span class="sb-lap-num">{currentLap}</span>
      </span>
    </div>
  );
}
