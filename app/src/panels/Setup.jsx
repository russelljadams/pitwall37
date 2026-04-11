import { useSignal } from '@preact/signals';
import { liveSetup } from '../state/live.js';
import { formatSetupValue } from '../lib/format.js';

// Categories and their display order. AeroCalculator is always expanded.
const CATEGORY_ORDER = [
  { key: 'TiresAero', label: 'TIRES & AERO', subcategories: [
    'AeroCalculator', 'AeroSetup', 'LeftFrontTire', 'LeftRearTire', 'RightFrontTire', 'RightRearTire',
  ]},
  { key: 'Chassis', label: 'CHASSIS', subcategories: [
    'Front', 'LeftFront', 'RightFront', 'Rear', 'LeftRear', 'RightRear', 'BrakesInCarMisc', 'Differential',
  ]},
];

function SetupSection({ name, data, defaultOpen }) {
  const open = useSignal(defaultOpen ?? false);

  if (!data || typeof data !== 'object') return null;
  const entries = Object.entries(data);
  if (entries.length === 0) return null;

  return (
    <div class="setup-section">
      <button
        class={`setup-section-header ${open.value ? 'setup-section-header--open' : ''}`}
        onClick={() => { open.value = !open.value; }}
      >
        <span class="setup-section-arrow">{open.value ? '\u25BE' : '\u25B8'}</span>
        <span class="setup-section-name">{name}</span>
      </button>
      {open.value && (
        <div class="setup-section-body">
          {entries.map(([key, val]) => (
            <div class="setup-row" key={key}>
              <span class="setup-key">{key}</span>
              <span class="setup-val">{formatSetupValue(val)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function Setup() {
  const setup = liveSetup.value;

  return (
    <div class="panel panel-setup">
      <div class="panel-header">CAR SETUP</div>
      <div class="panel-body setup-body">
        {!setup ? (
          <div class="setup-empty">
            <div class="setup-empty-label">NO LIVE SETUP</div>
            <div class="setup-empty-hint">Connect bridge and enter garage</div>
          </div>
        ) : (
          CATEGORY_ORDER.map(cat => {
            const catData = setup[cat.key];
            if (!catData) return null;
            return (
              <div class="setup-category" key={cat.key}>
                <div class="setup-category-label">{cat.label}</div>
                {cat.subcategories.map(sub => {
                  const subData = catData[sub];
                  if (!subData) return null;
                  return (
                    <SetupSection
                      key={sub}
                      name={sub}
                      data={subData}
                      defaultOpen={sub === 'AeroCalculator'}
                    />
                  );
                })}
                {/* Also render any subcategories not in the explicit list */}
                {Object.keys(catData)
                  .filter(k => !cat.subcategories.includes(k) && typeof catData[k] === 'object')
                  .map(sub => (
                    <SetupSection key={sub} name={sub} data={catData[sub]} />
                  ))
                }
              </div>
            );
          })
        )}
        {/* Render top-level keys outside known categories */}
        {setup && Object.keys(setup)
          .filter(k => !CATEGORY_ORDER.some(c => c.key === k) && typeof setup[k] === 'object')
          .map(k => (
            <div class="setup-category" key={k}>
              <div class="setup-category-label">{k.toUpperCase()}</div>
              {typeof setup[k] === 'object' && Object.entries(setup[k]).map(([sub, data]) => (
                typeof data === 'object' && data !== null
                  ? <SetupSection key={sub} name={sub} data={data} />
                  : <div class="setup-row" key={sub}>
                      <span class="setup-key">{sub}</span>
                      <span class="setup-val">{formatSetupValue(data)}</span>
                    </div>
              ))}
            </div>
          ))
        }
      </div>
    </div>
  );
}
