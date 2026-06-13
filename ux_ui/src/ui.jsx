/* ============================================================
   MoneyMind — UI primitives (icons + small components)
   Exposed to window for use by views.jsx and app.jsx
   ============================================================ */

const { useState, useEffect, useRef, useMemo } = React;

// ─────────────────────────────────────────────────────────────
// Icons — line-style, currentColor
// ─────────────────────────────────────────────────────────────
const Ic = {
  home: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 11l9-7 9 7v9a2 2 0 0 1-2 2h-3v-7H8v7H5a2 2 0 0 1-2-2z" /></svg>,
  list: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M8 6h12M8 12h12M8 18h12M3 6h.01M3 12h.01M3 18h.01" /></svg>,
  upload: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 16V4M6 10l6-6 6 6M4 20h16" /></svg>,
  spark: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l1.6 4.8L18 9.4l-4.4 1.6L12 16l-1.6-4.9L6 9.4l4.4-1.6z" /><path d="M19 14l.8 2.4L22 17.2l-2.2.8L19 20l-.8-2.4L16 17.2l2.2-.8z" /></svg>,
  bell: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10 21a2 2 0 0 0 4 0" /></svg>,
  search: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7" /><path d="m20 20-3-3" /></svg>,
  arrow: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14m-6-6 6 6-6 6" /></svg>,
  arrUp: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m6 14 6-6 6 6" /></svg>,
  arrDn: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m6 10 6 6 6-6" /></svg>,
  close: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M6 6l12 12M18 6 6 18" /></svg>,
  send: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="m4 12 16-8-6 18-3-7z" /></svg>,
  sliders: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M4 6h10M4 12h6M4 18h14" /><circle cx="17" cy="6" r="2" /><circle cx="13" cy="12" r="2" /><circle cx="20" cy="18" r="2" /></svg>,
  trend: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="m3 17 6-6 4 4 8-8M14 7h7v7" /></svg>,
  wallet: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 7a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><path d="M16 12h4M3 11h14" /></svg>,
  target: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></svg>,
  file: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><path d="M14 3v6h6" /></svg>,
  check: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 5 5 9-11" /></svg>,
  plus: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 5v14M5 12h14" /></svg>,
  sparkles: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1" /></svg>,
  logout: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></svg>,
  lock: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></svg>,
  mail: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></svg>,
  user: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>,
  eye: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></svg>,
  eyeOff: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M3 3l18 18M10.6 10.6a3 3 0 0 0 4.2 4.2M9.4 5.2A10 10 0 0 1 22 12a17.7 17.7 0 0 1-3.5 4.5M6.2 6.2A17.4 17.4 0 0 0 2 12s3.5 7 10 7a10 10 0 0 0 4.4-1" /></svg>,
  google: <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M22.5 12.3c0-.8-.1-1.4-.2-2H12v3.9h5.9c-.1.9-.8 2.4-2.2 3.3l-.02.13 3.2 2.48.22.02c2-1.9 3.4-4.6 3.4-7.83" fill="#4285F4" /><path d="M12 23c2.9 0 5.4-1 7.2-2.6l-3.4-2.6c-.9.6-2.1 1.1-3.8 1.1-2.9 0-5.3-1.9-6.2-4.6l-.13.01-3.3 2.6-.05.12C4.1 20.5 7.8 23 12 23" fill="#34A853" /><path d="M5.8 14.3c-.2-.7-.4-1.4-.4-2.3s.1-1.6.4-2.3V7.1H2.4C1.5 8.6 1 10.3 1 12s.5 3.4 1.4 4.9l3.4-2.6" fill="#FBBC05" /><path d="M12 5.4c2 0 3.4.9 4.2 1.6l3-2.9C17.4 2.4 14.9 1 12 1 7.8 1 4.1 3.5 2.4 7.1l3.4 2.6C6.7 7 9.1 5.4 12 5.4" fill="#EA4335" /></svg>,
  apple: <svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.05 12.04c-.03-2.74 2.24-4.07 2.34-4.13-1.27-1.86-3.25-2.12-3.96-2.15-1.69-.17-3.3 1-4.16 1-.87 0-2.19-.98-3.61-.95-1.86.03-3.57 1.08-4.52 2.74-1.93 3.34-.49 8.27 1.38 10.98.92 1.32 2 2.8 3.43 2.75 1.38-.06 1.9-.89 3.57-.89 1.66 0 2.13.89 3.59.86 1.48-.03 2.42-1.34 3.32-2.67 1.05-1.53 1.48-3.01 1.5-3.08-.03-.01-2.87-1.1-2.9-4.36zM14.49 4c.76-.93 1.28-2.21 1.13-3.49-1.1.05-2.43.74-3.21 1.66-.71.81-1.33 2.12-1.16 3.37 1.22.1 2.48-.62 3.24-1.54z" /></svg>
};

// ─────────────────────────────────────────────────────────────
// Animated number counter
// ─────────────────────────────────────────────────────────────
function useCountUp(target, { duration = 900, delay = 0 } = {}) {
  const [value, setValue] = useState(0);
  useEffect(() => {
    let start;
    let raf;
    const startVal = 0;
    const ease = (t) => 1 - Math.pow(1 - t, 3);
    const tick = (ts) => {
      if (!start) start = ts + delay;
      const elapsed = ts - start;
      if (elapsed < 0) {raf = requestAnimationFrame(tick);return;}
      const p = Math.min(1, elapsed / duration);
      setValue(startVal + (target - startVal) * ease(p));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);
  return value;
}

// ─────────────────────────────────────────────────────────────
// Big balance display
// ─────────────────────────────────────────────────────────────
function BalanceDisplay({ amount, currency, lang }) {
  const animated = useCountUp(amount, { duration: 1100 });
  const parts = fmtParts(animated, currency, lang);
  return (
    <div className="balance-number" style={{ fontFamily: "var(--num)" }}>
      <span className="currency" style={{ fontFamily: "var(--num)" }}>{parts.currency}</span>
      <span className="digits" style={{ fontSize: "50px", fontFamily: "var(--num)" }}>{parts.sign}{parts.digits}</span>
    </div>);

}

// ─────────────────────────────────────────────────────────────
// Sparkline (area chart) — accepts series array, draws SVG path
// ─────────────────────────────────────────────────────────────
function Sparkline({ series, height = 80, color = 'var(--accent)', fill = 'var(--accent-soft)', showAxis = false }) {
  const W = 800,H = height;
  const max = Math.max(...series, 1);
  const stepX = W / (series.length - 1);
  const points = series.map((v, i) => [i * stepX, H - v / max * (H - 8) - 4]);

  // smooth path using catmull-rom -> cubic bezier
  const path = useMemo(() => {
    if (points.length < 2) return '';
    let d = `M${points[0][0]},${points[0][1]}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i - 1] || points[i];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[i + 2] || p2;
      const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
      const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
      const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
      const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${p2[0]},${p2[1]}`;
    }
    return d;
  }, [series.join(',')]);

  const areaPath = `${path} L${W},${H} L0,${H} Z`;

  const gradId = useMemo(() => 'spark-grad-' + Math.random().toString(36).slice(2, 8), []);

  // Animate stroke draw
  const pathRef = useRef(null);
  useEffect(() => {
    const el = pathRef.current;
    if (!el) return;
    const len = el.getTotalLength();
    el.style.strokeDasharray = len;
    el.style.strokeDashoffset = len;
    requestAnimationFrame(() => {
      el.style.transition = 'stroke-dashoffset 1.2s cubic-bezier(0.2, 0.8, 0.2, 1)';
      el.style.strokeDashoffset = 0;
    });
  }, [path]);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: '100%', height }}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradId})`} />
      <path ref={pathRef} d={path} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>);

}

// ─────────────────────────────────────────────────────────────
// Donut chart (animated arcs)
// ─────────────────────────────────────────────────────────────
function Donut({ slices, size = 220, thickness = 22, totalLabel, totalValue }) {
  const cx = size / 2;
  const cy = size / 2;
  const r = (size - thickness) / 2;
  const total = slices.reduce((a, s) => a + s.value, 0) || 1;
  const circ = 2 * Math.PI * r;

  let cumulative = 0;
  const arcs = slices.map((s, i) => {
    const pct = s.value / total;
    const len = pct * circ;
    const offset = circ - cumulative * circ;
    cumulative += pct;
    return { ...s, len, offset, idx: i };
  });

  const [draw, setDraw] = useState(false);
  useEffect(() => {const t = setTimeout(() => setDraw(true), 60);return () => clearTimeout(t);}, []);

  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      preserveAspectRatio="xMidYMid meet"
      style={{
        overflow: 'visible',
        width: '100%',
        height: 'auto',
        maxWidth: size,
        display: 'block',
        aspectRatio: '1 / 1'
      }}>
      {/* Track */}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface-strong)" strokeWidth={thickness} />
      {/* Arcs — use SVG `transform` attribute (user-space coords) instead of
          CSS transform with transformOrigin:'center' which resolved to the
          viewport center on some mobile browsers and caused arcs to start
          at slightly different angles (gap at the seam). */}
      {arcs.map((a, i) =>
      <circle
        key={i}
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke={a.color}
        strokeWidth={thickness}
        strokeDasharray={`${draw ? a.len : 0} ${circ}`}
        strokeDashoffset={a.offset}
        strokeLinecap="butt"
        transform={`rotate(-90 ${cx} ${cy})`}
        style={{
          transition: `stroke-dasharray 1.1s cubic-bezier(0.2, 0.8, 0.2, 1) ${i * 80}ms`
        }} />

      )}
      {/* Center labels */}
      {totalValue &&
      <g>
          <text x={cx} y={cy - 4} textAnchor="middle" fill="var(--ink-subtle)" fontSize="10" letterSpacing="2" style={{ textTransform: 'uppercase' }}>
            {totalLabel}
          </text>
          <text x={cx} y={cy + 22} textAnchor="middle" fill="var(--ink)" fontSize="26" fontFamily="var(--num)" fontWeight="600" style={{ letterSpacing: '-0.5px' }}>
            {totalValue}
          </text>
        </g>
      }
    </svg>);

}

// ─────────────────────────────────────────────────────────────
// Area chart for trend (line + area + axes + tooltip + touch)
// ─────────────────────────────────────────────────────────────
// Format a baht value into a short axis label: 1234 -> "1.2K", 12000 -> "12K"
function fmtAxisShort(v) {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(v >= 10_000_000 ? 0 : 1).replace(/\.0$/, '') + 'M';
  if (v >= 1_000) return (v / 1_000).toFixed(v >= 10_000 ? 0 : 1).replace(/\.0$/, '') + 'K';
  return String(Math.round(v));
}

// Round a max value up to a "nice" number so y-axis ticks read cleanly
function niceCeil(v) {
  if (v <= 0) return 1;
  const pow = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / pow;
  let nice;
  if (n <= 1) nice = 1;else
  if (n <= 2) nice = 2;else
  if (n <= 2.5) nice = 2.5;else
  if (n <= 5) nice = 5;else
  nice = 10;
  return nice * pow;
}

function AreaChart({ series, height = 280, labels, tooltipLabel }) {
  const W = 1000,H = height;
  // Wider left padding leaves room for the HTML-overlay Y-axis labels
  const padL = 44,padR = 16,padTop = 24,padBottom = 32;
  const innerH = H - padTop - padBottom;
  const innerW = W - padL - padR;
  const rawMax = Math.max(...series, 1);
  const max = niceCeil(rawMax);
  const stepX = innerW / Math.max(series.length - 1, 1);
  const points = series.map((v, i) => [padL + i * stepX, padTop + innerH - v / max * innerH]);

  // Highlight peak point (max value within the series)
  const peakIdx = series.reduce((acc, v, i) => v > series[acc] ? i : acc, 0);

  const path = useMemo(() => {
    if (!points.length) return '';
    let d = `M${points[0][0]},${points[0][1]}`;
    for (let i = 0; i < points.length - 1; i++) {
      const p0 = points[i - 1] || points[i];
      const p1 = points[i];
      const p2 = points[i + 1];
      const p3 = points[i + 2] || p2;
      const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
      const cp1y = p1[1] + (p2[1] - p0[1]) / 6;
      const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
      const cp2y = p2[1] - (p3[1] - p1[1]) / 6;
      d += ` C${cp1x},${cp1y} ${cp2x},${cp2y} ${p2[0]},${p2[1]}`;
    }
    return d;
  }, [series.join(',')]);

  const area = `${path} L${padL + innerW},${padTop + innerH} L${padL},${padTop + innerH} Z`;

  const [hover, setHover] = useState(null);

  const pathRef = useRef(null);
  useEffect(() => {
    const el = pathRef.current;
    if (!el) return;
    const len = el.getTotalLength();
    el.style.strokeDasharray = len;
    el.style.strokeDashoffset = len;
    requestAnimationFrame(() => {
      el.style.transition = 'stroke-dashoffset 1.4s cubic-bezier(0.2, 0.8, 0.2, 1)';
      el.style.strokeDashoffset = 0;
    });
  }, [path]);

  // Translate a pointer X (clientX) into a series index + hover point
  const pickHover = (clientX, rect) => {
    const xPct = (clientX - rect.left) / rect.width;
    const idx = Math.round(xPct * (series.length - 1));
    const i = Math.max(0, Math.min(series.length - 1, idx));
    setHover({ i, x: points[i][0], y: points[i][1], value: series[i] });
  };

  const handleMove = (e) => pickHover(e.clientX, e.currentTarget.getBoundingClientRect());
  const handleTouch = (e) => {
    if (!e.touches || !e.touches.length) return;
    pickHover(e.touches[0].clientX, e.currentTarget.getBoundingClientRect());
  };

  // Y-axis tick values (top to bottom: max, 75%, 50%, 25%)
  const yTicks = [1, 0.75, 0.5, 0.25].map((p) => ({ pct: p, value: max * p }));

  // Choose a small subset of x labels to render as HTML so they stay legible
  // (the SVG's preserveAspectRatio="none" would stretch them weirdly).
  const xLabelCount = labels ? Math.min(labels.length, 5) : 0;
  const xLabelIdx = xLabelCount > 0 ?
  Array.from({ length: xLabelCount }, (_, i) => Math.round(i * (labels.length - 1) / Math.max(xLabelCount - 1, 1))) :
  [];

  return (
    <div style={{ position: 'relative', width: '100%', height }}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: '100%', height, display: 'block' }}
      onMouseMove={handleMove}
      onMouseLeave={() => setHover(null)}
      onTouchStart={handleTouch}
      onTouchMove={handleTouch}
      onTouchEnd={() => setHover(null)}>

        <defs>
          <linearGradient id="area-grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* horizontal grid (incl. baseline) */}
        {[0, 0.25, 0.5, 0.75, 1].map((g, i) =>
        <line key={i}
        x1={padL} x2={padL + innerW}
        y1={padTop + innerH * (1 - g)} y2={padTop + innerH * (1 - g)}
        stroke="var(--border)"
        strokeDasharray={g === 0 ? '0' : '2 5'}
        strokeOpacity={g === 0 ? 0.6 : 1} />

        )}

        {/* area + line */}
        <path d={area} fill="url(#area-grad)" />
        <path ref={pathRef} d={path} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />

        {/* peak marker (always visible) */}
        {series.length > 0 && series[peakIdx] > 0 &&
        <g style={{ pointerEvents: 'none' }}>
            <circle cx={points[peakIdx][0]} cy={points[peakIdx][1]} r="14" fill="var(--accent)" fillOpacity="0.15" />
            <circle cx={points[peakIdx][0]} cy={points[peakIdx][1]} r="5" fill="var(--accent)" stroke="var(--bg)" strokeWidth="2" />
          </g>
        }

        {/* hover indicator */}
        {hover &&
        <g style={{ pointerEvents: 'none' }}>
            <line x1={hover.x} x2={hover.x} y1={padTop} y2={padTop + innerH} stroke="var(--accent)" strokeOpacity="0.5" strokeDasharray="2 3" vectorEffect="non-scaling-stroke" />
            <circle cx={hover.x} cy={hover.y} r="6" fill="var(--bg)" stroke="var(--accent)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
          </g>
        }
      </svg>

      {/* ── Y-axis labels (HTML overlay — immune to SVG stretch) ── */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        {yTicks.map((t, i) =>
        <div key={i}
        style={{
          position: 'absolute',
          left: 0,
          width: `${padL / W * 100}%`,
          top: `${(padTop + innerH * (1 - t.pct)) / H * 100}%`,
          transform: 'translateY(-50%)',
          paddingRight: 6,
          textAlign: 'right',
          fontSize: 10,
          color: 'var(--ink-subtle)',
          fontFamily: 'var(--num)',
          letterSpacing: '0.2px',
          lineHeight: 1
        }}>

            {fmtAxisShort(t.value)}
          </div>
        )}
      </div>

      {/* ── X-axis labels (HTML overlay) ── */}
      {labels && xLabelIdx.length > 0 &&
      <div style={{ position: 'absolute', left: 0, right: 0, bottom: 6, pointerEvents: 'none' }}>
          {xLabelIdx.map((idx) => {
          const xPct = (padL + idx * stepX) / W * 100;
          const isFirst = idx === 0;
          const isLast = idx === labels.length - 1;
          return (
            <div key={idx}
            style={{
              position: 'absolute',
              left: `${xPct}%`,
              transform: isFirst ? 'translateX(0)' : isLast ? 'translateX(-100%)' : 'translateX(-50%)',
              fontSize: 9.5,
              color: 'var(--ink-subtle)',
              fontFamily: 'var(--sans)',
              letterSpacing: '0.8px',
              textTransform: 'uppercase',
              whiteSpace: 'nowrap'
            }}>

                {labels[idx]}
              </div>);

        })}
        </div>
      }

      {/* ── Peak amount label (small floating chip) ── */}
      {series.length > 0 && series[peakIdx] > 0 && !hover &&
      <div style={{
        position: 'absolute',
        left: `${points[peakIdx][0] / W * 100}%`,
        top: `${Math.max(points[peakIdx][1] / H * 100 - 12, 0)}%`,
        transform: 'translate(-50%, -100%)',
        pointerEvents: 'none',
        background: 'var(--accent-soft)',
        border: '1px solid var(--accent-glow)',
        color: 'var(--accent)',
        padding: '3px 8px',
        borderRadius: 8,
        fontSize: 10.5,
        fontFamily: 'var(--num)',
        fontWeight: 600,
        letterSpacing: '0.2px',
        whiteSpace: 'nowrap'
      }}>
          ฿{series[peakIdx].toLocaleString()}
        </div>
      }

      {/* ── Hover tooltip ── */}
      {hover &&
      <div style={{
        position: 'absolute',
        left: `${hover.x / W * 100}%`,
        top: 6,
        transform: 'translateX(-50%)',
        pointerEvents: 'none',
        background: 'var(--bg)',
        border: '1px solid var(--border-strong)',
        padding: '8px 12px',
        borderRadius: 10,
        fontSize: 11.5,
        color: 'var(--ink)',
        fontFamily: 'var(--num)',
        whiteSpace: 'nowrap',
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)'
      }}>
          {tooltipLabel ? tooltipLabel(hover.i) : `Day ${hover.i + 1}`} · ฿{hover.value.toLocaleString()}
        </div>
      }
    </div>);

}

// ─────────────────────────────────────────────────────────────
// KPI Card
// ─────────────────────────────────────────────────────────────
function KPI({ label, icon, amount, currency, lang, delta, deltaText, footer, barPct, over }) {
  const animated = useCountUp(amount, { duration: 900 });
  const parts = fmtParts(animated, currency, lang);
  return (
    <div className="card kpi">
      <div className="kpi-label">{icon}{label}</div>
      <div className="kpi-value">
        <span className="currency-sm">{parts.currency}</span>
        <span className="count" style={{ fontFamily: "var(--num)" }}>{parts.sign}{parts.digits}</span>
      </div>
      {(delta != null || footer) &&
      <div className="kpi-foot">
          {delta != null &&
        <span className={'delta ' + (delta >= 0 ? 'up' : 'down')}>
              {delta >= 0 ? Ic.arrUp : Ic.arrDn}{Math.abs(delta).toFixed(1)}%
            </span>
        }
          <span style={{ color: 'var(--ink-subtle)' }}>{deltaText || footer}</span>
        </div>
      }
      {barPct != null &&
      <div className={'mini-bar' + (over ? ' over' : '')}>
          <span style={{ width: `${Math.min(barPct, 100)}%` }}></span>
        </div>
      }
    </div>);

}

// ─────────────────────────────────────────────────────────────
// Transaction row
// ─────────────────────────────────────────────────────────────
function TransactionRow({ tx, currency, lang }) {
  const cat = CATEGORIES[tx.category] || CATEGORIES.other;
  const isIncome = tx.amount > 0;
  const parts = fmtParts(tx.amount, currency, lang);
  return (
    <div className="tx-row">
      <div className="tx-icon" style={{ background: `${cat.color}22`, color: cat.color }}>
        <span style={{ fontSize: 16 }}>{cat.icon}</span>
      </div>
      <div>
        <div className="tx-merchant">{tx.merchant}</div>
        <div className="tx-meta">
          <span className="tx-cat-pill">{t(cat, lang)}</span>
          <span>·</span>
          <span>{formatDate(tx.date, lang)}</span>
          {tx.note && <><span>·</span><span style={{ fontStyle: 'italic' }}>{tx.note}</span></>}
        </div>
      </div>
      <div className={'tx-amount ' + (isIncome ? 'income' : 'expense')}>
        {isIncome ? '+' : ''}{parts.sign}{parts.currency}{parts.digits}
      </div>
      <div className="tx-arrow">{Ic.arrow}</div>
    </div>);

}

function formatDate(dateStr, lang) {
  const d = new Date(dateStr);
  if (lang === 'th') {
    const months = ['ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.', 'ต.ค.', 'พ.ย.', 'ธ.ค.'];
    return `${d.getDate()} ${months[d.getMonth()]}`;
  }
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function formatGroupDate(dateStr, lang) {
  const today = new Date('2026-05-15');
  const d = new Date(dateStr);
  const diff = Math.floor((today - d) / (1000 * 60 * 60 * 24));
  if (lang === 'th') {
    if (diff === 0) return 'วันนี้';
    if (diff === 1) return 'เมื่อวาน';
    if (diff < 7) return `${diff} วันก่อน`;
    return formatDate(dateStr, lang);
  }
  if (diff === 0) return 'Today';
  if (diff === 1) return 'Yesterday';
  if (diff < 7) return `${diff} days ago`;
  return formatDate(dateStr, lang);
}

// ─────────────────────────────────────────────────────────────
// Score Ring for AI Health Score
// ─────────────────────────────────────────────────────────────
function ScoreRing({ score, size = 200, thickness = 14 }) {
  const cx = size / 2,cy = size / 2;
  const r = (size - thickness) / 2;
  const circ = 2 * Math.PI * r;
  const animated = useCountUp(score, { duration: 1400 });
  const offset = circ - animated / 100 * circ;
  return (
    <div className="score-ring" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} width="100%" height="100%" preserveAspectRatio="xMidYMid meet">
        <defs>
          <linearGradient id="score-grad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--accent)" />
            <stop offset="100%" stopColor="var(--positive)" />
          </linearGradient>
        </defs>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--surface-strong)" strokeWidth={thickness} />
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke="url(#score-grad)"
          strokeWidth={thickness}
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 200ms linear' }} />
        
      </svg>
      <div className="score-text" style={{ flexDirection: 'column' }}>
        <div>
          <div className="score-num">{Math.round(animated)}</div>
          <div className="score-out" style={{ marginTop: 4 }}>/ 100</div>
        </div>
      </div>
    </div>);

}

// Expose to window for views.jsx/app.jsx
Object.assign(window, {
  Ic, BalanceDisplay, Sparkline, Donut, AreaChart,
  KPI, TransactionRow, ScoreRing, useCountUp,
  formatDate, formatGroupDate
});