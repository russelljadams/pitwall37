/**
 * PanelShell — wrapper for all panels with title bar and minimize.
 *
 * Supports two modes:
 * 1. Self-managed: local signal tracks minimize state (default)
 * 2. Layout-managed: parent passes onMinimize callback + isMinimized flag
 *    so the layout can reclaim space when panels collapse.
 */
import { useSignal } from '@preact/signals';

export function PanelShell({ title, badge, children, className = '', onMinimize, isMinimized }) {
  const localMin = useSignal(false);

  /* Use layout-managed state if provided, otherwise local */
  const managed = typeof onMinimize === 'function';
  const minimized = managed ? isMinimized : localMin.value;

  const toggle = () => {
    if (managed) {
      onMinimize();
    } else {
      localMin.value = !localMin.value;
    }
  };

  return (
    <div class={`panel ${className} ${minimized ? 'panel--minimized' : ''}`}>
      <div class="panel-header">
        <span class="panel-title">{title}</span>
        {badge != null && <span class="panel-badge">{badge}</span>}
        <span class="panel-header-spacer" />
        <button
          class="panel-btn"
          onClick={toggle}
          title={minimized ? 'Expand' : 'Minimize'}
          aria-label={minimized ? 'Expand panel' : 'Minimize panel'}
        >
          {minimized ? '+' : '\u2013'}
        </button>
      </div>
      {!minimized && (
        <div class="panel-body">
          {children}
        </div>
      )}
    </div>
  );
}
