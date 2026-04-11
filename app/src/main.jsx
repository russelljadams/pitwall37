import './styles/reset.css';
import './styles/variables.css';
import './styles/layout.css';
import './styles/telemetry.css';
import './styles/ticker.css';
import './styles/engineer.css';
import './styles/setup.css';

import { render } from 'preact';
import { App } from './app.jsx';
import { connect } from './state/live.js';

connect();
render(<App />, document.getElementById('app'));
