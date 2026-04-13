import './styles/variables.css';
import './styles/reset.css';
import './styles/layout.css';
import './styles/panels.css';
import './styles/sessions.css';
import './styles/laps.css';
import './styles/telemetry.css';
import './styles/setup.css';
import './styles/agent.css';
import './styles/alien.css';

import { render } from 'preact';
import { App } from './app.jsx';

render(<App />, document.getElementById('app'));
