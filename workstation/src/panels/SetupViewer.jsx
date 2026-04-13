/**
 * SetupViewer — display car setup, with diff mode when comparing sessions.
 */
import { useSignal } from '@preact/signals';
import { useEffect } from 'preact/hooks';
import {
  selectedSession, compareSession, focusedSetupParam,
} from '../state/selection.js';
import { PanelShell } from '../components/PanelShell.jsx';
import { formatSetupValue } from '../lib/format.js';
import {
  fetchDriverModel,
  fetchSessionDebrief,
  fetchTaxonomy,
} from '../lib/api.js';

/** Group setup keys into sections — handles iRacing's 3-level nesting:
 *  TiresAero.AeroCalculator.FrontRhAtSpeed = "7.0 mm"
 *  Chassis.Front.HeaveSpring = "140 N/mm"
 *  Top-level scalars go into "General".
 */
function groupSetup(setup) {
  if (!setup || typeof setup !== 'object') return [];

  const groups = {};

  function addParam(section, key, fullKey, value) {
    if (!groups[section]) groups[section] = [];
    groups[section].push({ key, fullKey, value });
  }

  for (const [topKey, topVal] of Object.entries(setup)) {
    if (topKey.startsWith('_') || topKey === 'UpdateCount') continue;

    if (typeof topVal !== 'object' || topVal === null || Array.isArray(topVal)) {
      // Top-level scalar
      addParam('General', topKey, topKey, topVal);
      continue;
    }

    // Level 2: e.g., TiresAero.AeroCalculator or Chassis.Front
    for (const [midKey, midVal] of Object.entries(topVal)) {
      if (typeof midVal !== 'object' || midVal === null || Array.isArray(midVal)) {
        // 2-level: topKey.midKey = scalar
        addParam(topKey, midKey, `${topKey}.${midKey}`, midVal);
        continue;
      }

      // Level 3: e.g., TiresAero.AeroCalculator.FrontRhAtSpeed
      // Use midKey as the section name (AeroCalculator, Front, LeftFront, etc.)
      for (const [leafKey, leafVal] of Object.entries(midVal)) {
        addParam(midKey, leafKey, `${topKey}.${midKey}.${leafKey}`, leafVal);
      }
    }
  }

  // Sort: AeroCalculator first, AeroSetup second, then alphabetical
  const priority = ['AeroCalculator', 'AeroSetup'];
  const sorted = Object.entries(groups).sort(([a], [b]) => {
    const ai = priority.indexOf(a);
    const bi = priority.indexOf(b);
    if (ai !== -1 && bi !== -1) return ai - bi;
    if (ai !== -1) return -1;
    if (bi !== -1) return 1;
    return a.localeCompare(b);
  });

  return sorted;
}

/** Flatten a nested setup into dot-path key-value pairs (handles 3 levels) */
function flattenSetup(setup, prefix = '') {
  const flat = {};
  if (!setup) return flat;

  for (const [key, val] of Object.entries(setup)) {
    if (key === 'UpdateCount' || key.startsWith('_')) continue;
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (typeof val === 'object' && val !== null && !Array.isArray(val)) {
      Object.assign(flat, flattenSetup(val, fullKey));
    } else {
      flat[fullKey] = val;
    }
  }
  return flat;
}

function SetupSection({ name, params, diffMap, isDiff, defaultOpen }) {
  const open = useSignal(defaultOpen || false);

  const changedCount = isDiff
    ? params.filter(p => diffMap && diffMap[p.fullKey] !== undefined).length
    : 0;

  return (
    <div class={`sv-section ${open.value ? 'sv-open' : ''}`}>
      <div class="sv-section-header" onClick={() => { open.value = !open.value; }}>
        <span class="sv-section-arrow">{'\u25B6'}</span>
        <span class="sv-section-name">{name}</span>
        {isDiff && changedCount > 0 && (
          <span class="sv-section-count" style={{ color: 'var(--pw-amber)' }}>
            {changedCount} changed
          </span>
        )}
        <span class="sv-section-count">{params.length}</span>
      </div>
      <div class="sv-section-body">
        {params.map(param => {
          const isFocused = focusedSetupParam.value === param.fullKey;
          const diffVal = isDiff && diffMap ? diffMap[param.fullKey] : undefined;
          const hasChanged = diffVal !== undefined;

          let rowClass = 'sv-row';
          if (isFocused) rowClass += ' sv-focused';
          if (isDiff && hasChanged) rowClass += ' sv-changed';
          if (isDiff && !hasChanged) rowClass += ' sv-same';

          return (
            <div
              key={param.fullKey}
              class={rowClass}
              onClick={() => {
                focusedSetupParam.value =
                  focusedSetupParam.value === param.fullKey ? null : param.fullKey;
              }}
            >
              <span class="sv-param">{param.key}</span>
              {isDiff && hasChanged ? (
                <div class="sv-diff-values">
                  <span class="sv-diff-a">{formatSetupValue(param.value)}</span>
                  <span class="sv-diff-arrow">{'\u2192'}</span>
                  <span class="sv-diff-b">{formatSetupValue(diffVal)}</span>
                  {typeof param.value === 'number' && typeof diffVal === 'number' && (
                    <span class={`sv-diff-delta ${diffVal > param.value ? 'sv-up' : 'sv-down'}`}>
                      {(diffVal - param.value) > 0 ? '+' : ''}{(diffVal - param.value).toFixed(2)}
                    </span>
                  )}
                </div>
              ) : (
                <span class="sv-value">{formatSetupValue(param.value)}</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function InsightList({ title, items, tone }) {
  if (!items || items.length === 0) return null;
  return (
    <div class="sv-insight-group">
      <div class={`sv-insight-title sv-insight-title--${tone}`}>{title}</div>
      {items.slice(0, 3).map((item) => (
        <div key={`${item.category}:${item.focus_area || 'none'}`} class="sv-insight-card">
          <div class="sv-insight-head">
            <span>{item.focus_area || item.category}</span>
            <span class="sv-insight-confidence">{item.confidence}</span>
          </div>
          <div class="sv-insight-text">{item.evidence}</div>
        </div>
      ))}
    </div>
  );
}

export function SetupViewer() {
  const primary = selectedSession.value;
  const compare = compareSession.value;
  const driverModel = useSignal(null);
  const taxonomy = useSignal(null);
  const debrief = useSignal(null);

  const setup = primary?.setup;
  const compareSetup = compare?.setup;
  const isDiff = setup && compareSetup;

  useEffect(() => {
    if (!primary?.id) {
      driverModel.value = null;
      taxonomy.value = null;
      debrief.value = null;
      return;
    }

    fetchDriverModel(primary.track).then((data) => {
      driverModel.value = data;
    }).catch(() => {
      driverModel.value = null;
    });

    fetchTaxonomy(primary.track).then((data) => {
      taxonomy.value = data;
    }).catch(() => {
      taxonomy.value = null;
    });

    fetchSessionDebrief(primary.id).then((data) => {
      debrief.value = data;
    }).catch(() => {
      debrief.value = null;
    });
  }, [primary?.id, primary?.track]);

  if (!setup) {
    return (
      <PanelShell title="SETUP">
        <div class="panel-empty">
          <div class="panel-empty-label">NO SETUP</div>
          <div class="panel-empty-hint">Select a session with setup data</div>
        </div>
      </PanelShell>
    );
  }

  const sections = groupSetup(setup);

  // Build diff map if comparing
  let diffMap = null;
  if (isDiff) {
    const flatA = flattenSetup(setup);
    const flatB = flattenSetup(compareSetup);
    diffMap = {};
    for (const key of Object.keys(flatA)) {
      if (flatB[key] !== undefined && flatB[key] !== flatA[key]) {
        diffMap[key] = flatB[key];
      }
    }
  }

  const diffCount = diffMap ? Object.keys(diffMap).length : 0;
  const model = driverModel.value;
  const sessionDebrief = debrief.value;
  const taxonomyData = taxonomy.value;

  return (
    <PanelShell title="SETUP" badge={isDiff ? `${diffCount} diffs` : 'single'}>
      <div class="sv-container">
        <div class="sv-mode">
          <span class="sv-mode-label">MODE</span>
          <span class={`sv-mode-badge ${isDiff ? 'sv-diff' : 'sv-single'}`}>
            {isDiff ? 'DIFF' : 'SINGLE'}
          </span>
          {isDiff && (
            <span style={{ fontSize: '10px', color: 'var(--pw-text-muted)', fontFamily: 'var(--pw-font-data)' }}>
              Shift+click session to compare
            </span>
          )}
        </div>
        <div class="sv-body">
          {sessionDebrief && (
            <div class="sv-insights">
              <div class="sv-summary-grid">
                <div class="sv-summary-card">
                  <span class="sv-summary-label">BEST</span>
                  <span class="sv-summary-value">{sessionDebrief.lap_summary.best_lap?.toFixed?.(3) ?? sessionDebrief.lap_summary.best_lap ?? '--'}</span>
                </div>
                <div class="sv-summary-card">
                  <span class="sv-summary-label">MEDIAN</span>
                  <span class="sv-summary-value">{sessionDebrief.lap_summary.median_valid_lap?.toFixed?.(3) ?? sessionDebrief.lap_summary.median_valid_lap ?? '--'}</span>
                </div>
                <div class="sv-summary-card">
                  <span class="sv-summary-label">TOP-5 SPREAD</span>
                  <span class="sv-summary-value">{sessionDebrief.lap_summary.top5_spread?.toFixed?.(3) ?? sessionDebrief.lap_summary.top5_spread ?? '--'}</span>
                </div>
                <div class="sv-summary-card">
                  <span class="sv-summary-label">TRACK GAP</span>
                  <span class="sv-summary-value">
                    {sessionDebrief.lap_summary.gap_to_track_best != null
                      ? `${sessionDebrief.lap_summary.gap_to_track_best > 0 ? '+' : ''}${sessionDebrief.lap_summary.gap_to_track_best.toFixed(3)}`
                      : '--'}
                  </span>
                </div>
              </div>

              {model && (
                <>
                  <InsightList
                    title={`${primary.track} strengths`}
                    items={model.track?.strengths || []}
                    tone="strength"
                  />
                  <InsightList
                    title={`${primary.track} weaknesses`}
                    items={model.track?.weaknesses || []}
                    tone="weakness"
                  />
                </>
              )}

              {taxonomyData?.items?.length > 0 && (
                <div class="sv-insight-group">
                  <div class="sv-insight-title sv-insight-title--neutral">active taxonomy</div>
                  {taxonomyData.items.slice(0, 3).map((item) => (
                    <div key={`${item.category}:${item.focus_area || 'none'}`} class="sv-insight-card">
                      <div class="sv-insight-head">
                        <span>{item.focus_area || item.category}</span>
                        <span class="sv-insight-confidence">
                          {item.recommendations.improved || 0}R / {item.experiments.improved || 0}E
                        </span>
                      </div>
                      <div class="sv-insight-text">
                        {item.category}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {sections.map(([name, params], i) => (
            <SetupSection
              key={name}
              name={name}
              params={params}
              diffMap={diffMap}
              isDiff={isDiff}
              defaultOpen={name === 'AeroCalculator' || i === 0}
            />
          ))}
        </div>
      </div>
    </PanelShell>
  );
}
