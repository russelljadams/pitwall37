/**
 * PitWall37 // WORKSTATION
 * Chat-centric engineering workstation with resizable split panels.
 */
import { useSignal } from '@preact/signals';
import { useEffect, useRef, useCallback } from 'preact/hooks';
import { SessionBrowser } from './panels/SessionBrowser.jsx';
import { LapTable } from './panels/LapTable.jsx';
import { TelemetryChart } from './panels/TelemetryChart.jsx';
import { SetupViewer } from './panels/SetupViewer.jsx';
import { AgentChat } from './panels/AgentChat.jsx';
import { sessions } from './state/sessions.js';
import { fetchStats } from './lib/api.js';

/* ── Constants ── */
const STORAGE_KEY = 'pw37-layout';

const DEFAULTS = {
  leftWidth: 280,
  rightWidth: 300,
  bottomHeight: 220,
};

const MINS = {
  leftWidth: 200,
  rightWidth: 200,
  bottomHeight: 100,
};

const MOBILE_TABS = [
  { id: 'agent', label: 'Agent', icon: '\u2609' },
  { id: 'sessions', label: 'Sessions', icon: '\u2630' },
  { id: 'telemetry', label: 'Telemetry', icon: '\u223F' },
  { id: 'setup', label: 'Setup', icon: '\u2699' },
];

/* ── Persistence ── */
function loadSizes() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...DEFAULTS, ...parsed };
    }
  } catch {}
  return { ...DEFAULTS };
}

function saveSizes(sizes) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sizes));
  } catch {}
}

/* ── Collapsed sidebar tab ── */
function CollapsedTab({ label, onClick }) {
  return (
    <div class="ws-collapsed-tab" onClick={onClick} title={`Expand ${label}`}>
      <span class="ws-collapsed-tab-label">{label}</span>
      <span class="ws-collapsed-tab-icon">+</span>
    </div>
  );
}

/* ── Resize handle hook ── */
function useResizer(gridRef, sizes, axis, prop, direction) {
  const onMouseDown = useCallback((e) => {
    e.preventDefault();
    const startPos = axis === 'x' ? e.clientX : e.clientY;
    const startVal = sizes.value[prop];
    const grid = gridRef.current;
    if (!grid) return;

    const maxBound = axis === 'x'
      ? grid.offsetWidth - MINS.leftWidth - MINS.rightWidth - 12
      : grid.offsetHeight - MINS.bottomHeight - 40;

    document.body.style.cursor = axis === 'x' ? 'col-resize' : 'row-resize';
    document.body.style.userSelect = 'none';

    const onMove = (ev) => {
      const delta = (axis === 'x' ? ev.clientX : ev.clientY) - startPos;
      const raw = startVal + delta * direction;
      const clamped = Math.max(MINS[prop], Math.min(raw, maxBound));
      sizes.value = { ...sizes.value, [prop]: clamped };
    };

    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      saveSizes(sizes.value);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [gridRef, sizes, axis, prop, direction]);

  const onDoubleClick = useCallback(() => {
    sizes.value = { ...sizes.value, [prop]: DEFAULTS[prop] };
    saveSizes(sizes.value);
  }, [sizes, prop]);

  return { onMouseDown, onDoubleClick };
}


export function App() {
  const mobileTab = useSignal('agent');
  const stats = useSignal(null);
  const sizes = useSignal(loadSizes());
  const gridRef = useRef(null);

  /* Panel collapse states */
  const leftCollapsed = useSignal(false);
  const rightCollapsed = useSignal(false);
  const bottomCollapsed = useSignal(false);

  useEffect(() => {
    fetchStats().then(s => { stats.value = s; }).catch(() => {});
  }, []);

  /* Resize handles */
  const leftHandle = useResizer(gridRef, sizes, 'x', 'leftWidth', 1);
  const rightHandle = useResizer(gridRef, sizes, 'x', 'rightWidth', -1);
  const bottomHandle = useResizer(gridRef, sizes, 'y', 'bottomHeight', -1);

  const st = stats.value;
  const tab = mobileTab.value;
  const s = sizes.value;
  const lc = leftCollapsed.value;
  const rc = rightCollapsed.value;
  const bc = bottomCollapsed.value;

  /* Compute grid columns based on collapse state */
  const leftCol = lc ? '36px' : `${s.leftWidth}px`;
  const rightCol = rc ? '36px' : `${s.rightWidth}px`;

  const gridStyle = {
    '--left-col': leftCol,
    '--right-col': rightCol,
    '--bottom-row': bc ? '0px' : `${s.bottomHeight}px`,
    '--bottom-handle': bc ? '0px' : '4px',
  };

  return (
    <div class="ws-app">
      {/* Title bar */}
      <div class="ws-titlebar">
        <span class="ws-titlebar-brand">PitWall37</span>
        <span class="ws-titlebar-sep">//</span>
        <span class="ws-titlebar-sub">Workstation</span>
        <span class="ws-titlebar-spacer" />
        <div class="ws-titlebar-stats">
          {st && (
            <>
              <span class="ws-titlebar-stat">
                <span>SES</span> {st.total_sessions}
              </span>
              <span class="ws-titlebar-stat">
                <span>LAPS</span> {st.total_valid_laps}
              </span>
              <span class="ws-titlebar-stat">
                <span>TRACKS</span> {st.tracks_driven}
              </span>
            </>
          )}
        </div>
      </div>

      {/* Desktop grid */}
      <div class="ws-grid" ref={gridRef} style={gridStyle}>

        {/* Left sidebar */}
        <div class={`ws-area-left ${lc ? 'ws-area--collapsed' : ''} ${tab === 'sessions' ? 'ws-mobile-active' : ''}`}>
          {lc ? (
            <CollapsedTab label="DATA" onClick={() => { leftCollapsed.value = false; }} />
          ) : (
            <>
              <div class="ws-left-top">
                <SessionBrowser />
              </div>
              <div class="ws-left-bottom">
                <LapTable />
              </div>
            </>
          )}
        </div>

        {/* Resize handle: left | center */}
        {!lc && (
          <div
            class="ws-resize-handle ws-resize-col"
            onMouseDown={leftHandle.onMouseDown}
            onDblClick={leftHandle.onDoubleClick}
          />
        )}
        {lc && <div class="ws-resize-spacer" />}

        {/* Center: Agent chat + Telemetry bottom */}
        <div class="ws-area-center">
          {/* Collapse buttons for sidebars — floating in center area */}
          {!lc && (
            <button
              class="ws-sidebar-toggle ws-sidebar-toggle--left"
              onClick={() => { leftCollapsed.value = true; }}
              title="Collapse left sidebar"
            >
              {'\u25C0'}
            </button>
          )}
          {!rc && (
            <button
              class="ws-sidebar-toggle ws-sidebar-toggle--right"
              onClick={() => { rightCollapsed.value = true; }}
              title="Collapse right sidebar"
            >
              {'\u25B6'}
            </button>
          )}

          <div class={`ws-center-top ${tab === 'agent' ? 'ws-mobile-active' : ''}`}>
            <AgentChat />
          </div>

          {/* Resize handle: chat | telemetry */}
          {!bc && (
            <div
              class="ws-resize-handle ws-resize-row"
              onMouseDown={bottomHandle.onMouseDown}
              onDblClick={bottomHandle.onDoubleClick}
            />
          )}

          <div class={`ws-center-bottom ${bc ? 'ws-center-bottom--collapsed' : ''} ${tab === 'telemetry' ? 'ws-mobile-active' : ''}`}>
            {bc ? (
              <div class="ws-bottom-collapsed-bar" onClick={() => { bottomCollapsed.value = false; }}>
                <span class="ws-bottom-collapsed-label">TELEMETRY</span>
                <span class="ws-bottom-collapsed-icon">+</span>
              </div>
            ) : (
              <>
                <div class="ws-bottom-header-zone">
                  <button
                    class="ws-bottom-collapse-btn"
                    onClick={() => { bottomCollapsed.value = true; }}
                    title="Collapse telemetry"
                  >
                    {'\u2013'}
                  </button>
                </div>
                <div class="ws-center-bottom-content">
                  <TelemetryChart />
                </div>
              </>
            )}
          </div>
        </div>

        {/* Resize handle: center | right */}
        {!rc && (
          <div
            class="ws-resize-handle ws-resize-col"
            onMouseDown={rightHandle.onMouseDown}
            onDblClick={rightHandle.onDoubleClick}
          />
        )}
        {rc && <div class="ws-resize-spacer" />}

        {/* Right sidebar */}
        <div class={`ws-area-right ${rc ? 'ws-area--collapsed' : ''} ${tab === 'setup' ? 'ws-mobile-active' : ''}`}>
          {rc ? (
            <CollapsedTab label="SETUP" onClick={() => { rightCollapsed.value = false; }} />
          ) : (
            <SetupViewer />
          )}
        </div>
      </div>

      {/* Mobile tab bar */}
      <div class="ws-mobile-tabs">
        {MOBILE_TABS.map(t => (
          <button
            key={t.id}
            class={`ws-mobile-tab ${tab === t.id ? 'active' : ''}`}
            onClick={() => { mobileTab.value = t.id; }}
          >
            <span class="ws-mobile-tab-icon">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>
    </div>
  );
}
