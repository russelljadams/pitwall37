import { useRef, useEffect } from 'preact/hooks';
import { telemetry, speedKmh, fuelLaps } from '../state/live.js';
import { formatGear, formatRPM, formatFuel } from '../lib/format.js';

// G-force ring buffer for trail
const G_BUFFER_SIZE = 30;
const gBuffer = new Array(G_BUFFER_SIZE).fill(null);
let gIdx = 0;

function drawGForce(canvas, latG, lonG) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width;
  const h = canvas.height;
  const cx = w / 2;
  const cy = h / 2;
  const scale = w / 6; // +/-3g range

  // Store sample
  gBuffer[gIdx] = { lat: latG, lon: lonG };
  gIdx = (gIdx + 1) % G_BUFFER_SIZE;

  ctx.clearRect(0, 0, w, h);

  // Background crosshair
  ctx.strokeStyle = 'var(--pw-border, #2a2a32)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(cx, 0);
  ctx.lineTo(cx, h);
  ctx.moveTo(0, cy);
  ctx.lineTo(w, cy);
  ctx.stroke();

  // Circle guides at 1g, 2g
  ctx.strokeStyle = 'rgba(42, 42, 50, 0.5)';
  ctx.beginPath();
  ctx.arc(cx, cy, scale, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx, cy, scale * 2, 0, Math.PI * 2);
  ctx.stroke();

  // Draw trail
  for (let i = 0; i < G_BUFFER_SIZE; i++) {
    const idx = (gIdx + i) % G_BUFFER_SIZE;
    const pt = gBuffer[idx];
    if (!pt) continue;
    const age = i / G_BUFFER_SIZE;
    const alpha = age * 0.6;
    const x = cx + pt.lat * scale;
    const y = cy - pt.lon * scale;
    ctx.fillStyle = `rgba(232, 54, 78, ${alpha})`;
    ctx.beginPath();
    ctx.arc(x, y, 2 + age * 2, 0, Math.PI * 2);
    ctx.fill();
  }

  // Draw current dot
  const dx = cx + latG * scale;
  const dy = cy - lonG * scale;
  ctx.fillStyle = '#e8364e';
  ctx.shadowColor = '#e8364e';
  ctx.shadowBlur = 8;
  ctx.beginPath();
  ctx.arc(dx, dy, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.shadowBlur = 0;
}

export function Telemetry() {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    // Set actual pixel size
    canvas.width = 150;
    canvas.height = 150;

    let lastTs = 0;
    function tick() {
      const t = telemetry.value;
      if (t && t.ts !== lastTs) {
        lastTs = t.ts;
        drawGForce(canvas, t.lat_accel / 9.81, t.lon_accel / 9.81);
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const t = telemetry.value;
  const throttle = t ? t.throttle : 0;
  const brake = t ? t.brake : 0;
  const rpm = t ? t.rpm : 0;
  const rpmPct = rpm / 7500; // F324 max ~7200rpm, use 7500 for headroom

  return (
    <div class="panel panel-telemetry">
      <div class="panel-header">LIVE TELEMETRY</div>
      <div class="panel-body telem-body">
        <div class="telem-top">
          {/* Speed + Gear cluster */}
          <div class="telem-speed-cluster">
            <div class="telem-speed">{Math.round(speedKmh.value)}</div>
            <div class="telem-speed-unit">KM/H</div>
          </div>
          <div class="telem-gear">{formatGear(t?.gear)}</div>
          <div class="telem-rpm-cluster">
            <div class="telem-rpm-value">{formatRPM(rpm)}</div>
            <div class="telem-rpm-bar-bg">
              <div
                class="telem-rpm-bar-fill"
                style={`transform: scaleX(${Math.min(rpmPct, 1)})`}
              />
            </div>
          </div>
        </div>

        {/* Pedals */}
        <div class="telem-pedals">
          <div class="telem-pedal-row">
            <span class="telem-pedal-label">THR</span>
            <div class="telem-pedal-bar-bg">
              <div
                class="telem-pedal-bar telem-pedal-bar--throttle"
                style={`transform: scaleX(${throttle})`}
              />
            </div>
            <span class="telem-pedal-pct">{Math.round(throttle * 100)}%</span>
          </div>
          <div class="telem-pedal-row">
            <span class="telem-pedal-label">BRK</span>
            <div class="telem-pedal-bar-bg">
              <div
                class="telem-pedal-bar telem-pedal-bar--brake"
                style={`transform: scaleX(${brake})`}
              />
            </div>
            <span class="telem-pedal-pct">{Math.round(brake * 100)}%</span>
          </div>
        </div>

        {/* Bottom row: G-force + Fuel */}
        <div class="telem-bottom">
          <div class="telem-gforce">
            <div class="telem-gforce-label">G-FORCE</div>
            <canvas ref={canvasRef} class="telem-gforce-canvas" />
          </div>
          <div class="telem-fuel">
            <div class="telem-fuel-label">FUEL</div>
            <div class="telem-fuel-value">{formatFuel(t?.fuel_level)} <span class="telem-fuel-unit">L</span></div>
            <div class="telem-fuel-laps">
              {fuelLaps.value !== null
                ? <>{fuelLaps.value.toFixed(1)} <span class="telem-fuel-unit">LAPS EST</span></>
                : <span class="telem-fuel-unit">-- LAPS EST</span>
              }
            </div>
            <div class="telem-fuel-bar-bg">
              <div
                class="telem-fuel-bar-fill"
                style={`transform: scaleX(${t?.fuel_pct ?? 0})`}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
