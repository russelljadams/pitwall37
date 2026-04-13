/**
 * TelemetryChart — comprehensive telemetry visualization.
 * Shows all available channels with computed derived traces.
 * Charts are grouped into categories that can be toggled.
 */
import { useRef, useEffect } from 'preact/hooks';
import { useSignal } from '@preact/signals';
import uPlot from 'uplot';
import 'uplot/dist/uPlot.min.css';
import {
  selectedLapNumbers, selectedLapData, lapLoadingSet, selectedSession,
} from '../state/selection.js';
import { PanelShell } from '../components/PanelShell.jsx';
import { getLapColor } from '../lib/format.js';

/**
 * Chart definitions grouped by category.
 * transform: function to apply to raw channel data per sample
 * channels: for computed traces that combine multiple raw channels
 */
const CHART_GROUPS = [
  {
    id: 'driving',
    label: 'DRIVING INPUTS',
    charts: [
      { key: 'speed', label: 'Speed', unit: 'km/h', transform: v => v * 3.6, min: 0, decimals: 0 },
      { key: 'throttle', label: 'Throttle', unit: '%', transform: v => v * 100, min: 0, max: 100, decimals: 0 },
      { key: 'brake', label: 'Brake', unit: '%', transform: v => v * 100, min: 0, max: 100, decimals: 0 },
      { key: 'steering', label: 'Steering', unit: 'rad', transform: v => v, decimals: 2 },
      { key: 'gear', label: 'Gear', unit: '', transform: v => v, min: 0, max: 7, decimals: 0, stepped: true },
    ],
  },
  {
    id: 'aero',
    label: 'RIDE HEIGHT & AERO',
    charts: [
      {
        key: '_front_rh',
        label: 'Front Ride Height',
        unit: 'mm',
        computed: (ch) => {
          const lf = ch.lf_rh, rf = ch.rf_rh;
          if (!lf || !rf) return null;
          return lf.map((v, i) => ((v + rf[i]) / 2) * 1000);
        },
        decimals: 1,
        dangerZone: { below: 5, color: 'rgba(239,68,68,0.15)' },
      },
      {
        key: '_rear_rh',
        label: 'Rear Ride Height',
        unit: 'mm',
        computed: (ch) => {
          const lr = ch.lr_rh, rr = ch.rr_rh;
          if (!lr || !rr) return null;
          return lr.map((v, i) => ((v + rr[i]) / 2) * 1000);
        },
        decimals: 1,
        dangerZone: { below: 5, color: 'rgba(239,68,68,0.15)' },
      },
      {
        key: '_rake',
        label: 'Rake (Pitch)',
        unit: 'deg',
        computed: (ch) => {
          if (!ch.pitch) return null;
          return ch.pitch.map(v => v * (180 / Math.PI));
        },
        decimals: 2,
      },
      {
        key: '_bottoming',
        label: 'Bottoming',
        unit: 'mm',
        computed: (ch) => {
          const lf = ch.lf_rh, rf = ch.rf_rh, lr = ch.lr_rh, rr = ch.rr_rh;
          if (!lf || !rf || !lr || !rr) return null;
          // Min of all 4 corners in mm — negative = bottoming out
          return lf.map((v, i) => Math.min(v, rf[i], lr[i], rr[i]) * 1000);
        },
        decimals: 1,
        dangerZone: { below: 0, color: 'rgba(239,68,68,0.25)' },
      },
    ],
  },
  {
    id: 'dynamics',
    label: 'CAR DYNAMICS',
    charts: [
      { key: 'lat_g', label: 'Lateral G', unit: 'g', transform: v => v / 9.81, decimals: 2 },
      { key: 'long_g', label: 'Longitudinal G', unit: 'g', transform: v => v / 9.81, decimals: 2 },
      {
        key: '_yaw_deg',
        label: 'Yaw Rate',
        unit: 'deg/s',
        computed: (ch) => {
          if (!ch.yaw_rate) return null;
          return ch.yaw_rate.map(v => v * (180 / Math.PI));
        },
        decimals: 1,
      },
    ],
  },
  {
    id: 'engine',
    label: 'ENGINE & FUEL',
    charts: [
      { key: 'rpm', label: 'RPM', unit: '', transform: v => v, min: 3000, decimals: 0 },
      { key: 'fuel', label: 'Fuel Level', unit: 'L', transform: v => v, decimals: 2 },
    ],
  },
];

const GRID_SIZE = 500;

/** Build uniform dist_pct x-axis */
function buildDistPct(telem) {
  const ch = telem.channels;
  if (ch.dist_pct) return ch.dist_pct;
  const len = ch.speed ? ch.speed.length : telem.samples || 100;
  const arr = new Array(len);
  for (let i = 0; i < len; i++) arr[i] = i / (len - 1);
  return arr;
}

/** Resample to uniform grid for overlay */
function resampleToGrid(xArr, yArr) {
  const grid = new Float64Array(GRID_SIZE);
  const xOut = new Float64Array(GRID_SIZE);
  for (let i = 0; i < GRID_SIZE; i++) xOut[i] = i / (GRID_SIZE - 1) * 100;
  if (!xArr || !yArr || xArr.length === 0) return { x: xOut, y: grid };

  let j = 0;
  for (let i = 0; i < GRID_SIZE; i++) {
    const target = xOut[i] / 100;
    while (j < xArr.length - 1 && xArr[j + 1] < target) j++;
    if (j >= xArr.length - 1) {
      grid[i] = yArr[yArr.length - 1];
    } else {
      const t = (target - xArr[j]) / (xArr[j + 1] - xArr[j] || 1);
      grid[i] = yArr[j] + t * (yArr[j + 1] - yArr[j]);
    }
  }
  return { x: xOut, y: grid };
}

/** Get processed data for a chart definition from a lap's telemetry */
function getChartData(chartDef, telem) {
  const ch = telem.channels;
  let raw;

  if (chartDef.computed) {
    raw = chartDef.computed(ch);
  } else {
    raw = ch[chartDef.key];
    if (raw && chartDef.transform) {
      raw = raw.map(chartDef.transform);
    }
  }
  return raw;
}

/** Single uPlot chart */
function ChartRow({ chartDef, laps, lapData, width }) {
  const containerRef = useRef(null);
  const plotRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || laps.length === 0 || width < 100) return;

    let xData = null;
    const series = [];
    const seriesOpts = [{ label: 'Track %' }];

    for (let i = 0; i < laps.length; i++) {
      const lapNum = laps[i];
      const telem = lapData[lapNum];
      if (!telem || !telem.channels) continue;

      const distPct = buildDistPct(telem);
      const rawY = getChartData(chartDef, telem);
      if (!rawY) continue;

      const { x, y } = resampleToGrid(distPct, rawY);
      if (!xData) xData = x;
      series.push(y);

      const color = getLapColor(i);
      seriesOpts.push({
        label: `L${lapNum}`,
        stroke: color,
        width: 1.5,
        points: { show: false },
        paths: chartDef.stepped ? uPlot.paths.stepped({ align: 1 }) : undefined,
      });
    }

    if (!xData || series.length === 0) {
      if (containerRef.current) containerRef.current.innerHTML = '';
      return;
    }

    const data = [xData, ...series];

    // Compute range from data if not fixed
    let yRange;
    if (chartDef.min != null && chartDef.max != null) {
      yRange = [chartDef.min, chartDef.max];
    } else if (chartDef.min != null) {
      let maxVal = -Infinity;
      for (const s of series) for (let i = 0; i < s.length; i++) if (s[i] > maxVal) maxVal = s[i];
      const pad = (maxVal - chartDef.min) * 0.05 || 1;
      yRange = [chartDef.min, maxVal + pad];
    } else {
      yRange = (u, min, max) => {
        const pad = (max - min) * 0.08 || 1;
        return [min - pad, max + pad];
      };
    }

    // Danger zone band plugin
    const hooks = {};
    if (chartDef.dangerZone) {
      const dz = chartDef.dangerZone;
      hooks.drawSeries = [(u) => {
        const ctx = u.ctx;
        const y0 = u.valToPos(dz.below, 'y');
        const yBottom = u.valToPos(u.scales.y.min, 'y');
        const left = u.bbox.left;
        const w = u.bbox.width;
        ctx.save();
        ctx.fillStyle = dz.color;
        const top = Math.min(y0, yBottom);
        const h = Math.abs(yBottom - y0);
        ctx.fillRect(left, top, w, h);
        ctx.restore();
      }];
    }

    const opts = {
      width,
      height: 110,
      cursor: {
        sync: { key: 'pw37-sync' },
        drag: { x: false, y: false },
      },
      legend: { show: false },
      hooks,
      scales: {
        x: { time: false, range: [0, 100] },
        y: { range: yRange },
      },
      axes: [
        {
          stroke: '#4a4a56',
          grid: { stroke: 'rgba(42,42,50,0.3)', width: 1 },
          ticks: { stroke: '#2a2a32', width: 1 },
          font: '9px JetBrains Mono',
          size: 24,
          values: (u, vals) => vals.map(v => v + '%'),
        },
        {
          stroke: '#4a4a56',
          grid: { stroke: 'rgba(42,42,50,0.3)', width: 1 },
          ticks: { stroke: '#2a2a32', width: 1 },
          font: '9px JetBrains Mono',
          size: 40,
          values: (u, vals) => vals.map(v =>
            chartDef.decimals === 0 ? Math.round(v).toString() : v.toFixed(chartDef.decimals)
          ),
        },
      ],
      series: seriesOpts,
    };

    if (plotRef.current) plotRef.current.destroy();
    const el = containerRef.current;
    el.innerHTML = '';
    plotRef.current = new uPlot(opts, data, el);

    return () => {
      if (plotRef.current) { plotRef.current.destroy(); plotRef.current = null; }
    };
  }, [laps, lapData, width, chartDef]);

  return (
    <div class="tc-chart-wrap">
      <div class="tc-chart-label">
        <span>{chartDef.label}</span>
        {chartDef.unit && <span class="tc-chart-unit">{chartDef.unit}</span>}
        {chartDef.dangerZone && <span class="tc-danger-badge">DANGER ZONE</span>}
      </div>
      <div ref={containerRef} />
    </div>
  );
}

/** Chart group with toggle */
function ChartGroup({ group, laps, lapData, width, defaultOpen }) {
  const open = useSignal(defaultOpen);

  return (
    <div class={`tc-group ${open.value ? 'tc-group--open' : ''}`}>
      <button
        class="tc-group-header"
        onClick={() => { open.value = !open.value; }}
      >
        <span class="tc-group-arrow">{open.value ? '\u25BE' : '\u25B8'}</span>
        <span class="tc-group-label">{group.label}</span>
        <span class="tc-group-count">{group.charts.length}</span>
      </button>
      {open.value && (
        <div class="tc-group-body">
          {group.charts.map(ch => (
            <ChartRow
              key={ch.key}
              chartDef={ch}
              laps={laps}
              lapData={lapData}
              width={width}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export function TelemetryChart() {
  const laps = selectedLapNumbers.value;
  const lapData = selectedLapData.value;
  const loading = lapLoadingSet.value;
  const containerRef = useRef(null);
  const chartWidth = useSignal(600);

  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        chartWidth.value = Math.floor(entry.contentRect.width - 16);
      }
    });
    ro.observe(containerRef.current);
    chartWidth.value = Math.floor(containerRef.current.clientWidth - 16);
    return () => ro.disconnect();
  }, []);

  if (laps.length === 0) {
    return (
      <PanelShell title="TELEMETRY">
        <div class="panel-empty">
          <div class="panel-empty-label">NO LAP SELECTED</div>
          <div class="panel-empty-hint">Select a lap to view telemetry traces</div>
        </div>
      </PanelShell>
    );
  }

  const isLoading = loading.size > 0;
  const hasData = laps.some(n => lapData[n]);

  // Compute summary stats for selected laps
  const summaries = laps.map((n, i) => {
    const telem = lapData[n];
    if (!telem || !telem.channels) return null;
    const ch = telem.channels;
    const rh = telem.ride_height || {};
    const speedKmh = ch.speed ? ch.speed.map(v => v * 3.6) : [];
    const maxSpeed = speedKmh.length ? Math.max(...speedKmh) : 0;
    const minRH = rh.front_mm?.min != null ? Math.min(rh.front_mm.min, rh.rear_mm?.min ?? 999) : null;
    const bottoming = rh.bottoming_pct ?? null;
    return {
      lap: n,
      color: getLapColor(i),
      maxSpeed: maxSpeed.toFixed(0),
      time: telem.lap_time_s ? telem.lap_time_s.toFixed(3) : '?',
      fuelUsed: (telem.fuel_start_l && telem.fuel_end_l)
        ? (telem.fuel_start_l - telem.fuel_end_l).toFixed(3)
        : '?',
      minRH: minRH != null ? minRH.toFixed(1) : '?',
      bottoming: bottoming != null ? bottoming.toFixed(1) : '?',
      sampleRate: telem.sample_rate_hz || '?',
    };
  }).filter(Boolean);

  return (
    <PanelShell title="TELEMETRY" badge={laps.length > 1 ? `${laps.length} laps` : `Lap ${laps[0]}`}>
      <div class="tc-container" ref={containerRef}>
        {/* Summary cards */}
        {summaries.length > 0 && (
          <div class="tc-summary">
            {summaries.map(s => (
              <div class="tc-summary-card" key={s.lap}>
                <div class="tc-summary-lap" style={{ borderColor: s.color }}>
                  <span class="tc-summary-swatch" style={{ background: s.color }} />
                  L{s.lap}
                </div>
                <div class="tc-summary-stats">
                  <span title="Lap time">{s.time}s</span>
                  <span title="Max speed">{s.maxSpeed} km/h</span>
                  <span title="Fuel used">{s.fuelUsed} L</span>
                  <span title="Min ride height" class={parseFloat(s.minRH) < 0 ? 'tc-danger' : ''}>
                    RH: {s.minRH}mm
                  </span>
                  <span title="Bottoming %" class={parseFloat(s.bottoming) > 5 ? 'tc-warn' : ''}>
                    BTM: {s.bottoming}%
                  </span>
                  <span title="Sample rate">{s.sampleRate}Hz</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {isLoading && <div class="tc-loading">LOADING TELEMETRY...</div>}

        {hasData && (
          <div class="tc-charts">
            {CHART_GROUPS.map((group, i) => (
              <ChartGroup
                key={group.id}
                group={group}
                laps={laps}
                lapData={lapData}
                width={chartWidth.value}
                defaultOpen={i < 2}
              />
            ))}
          </div>
        )}
      </div>
    </PanelShell>
  );
}
