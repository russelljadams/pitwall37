import { StatusBar } from './panels/StatusBar.jsx';
import { Telemetry } from './panels/Telemetry.jsx';
import { Setup } from './panels/Setup.jsx';
import { LapTicker } from './panels/LapTicker.jsx';
import { Engineer } from './panels/Engineer.jsx';

export function App() {
  return (
    <div class="app-grid">
      <StatusBar />
      <Telemetry />
      <Setup />
      <LapTicker />
      <Engineer />
    </div>
  );
}
