import React, { useState, useEffect, useRef, useCallback } from 'react';

// ── Colour rules (first match wins) ──────────────────────────────────────────
const LINE_STYLES = [
  { test: l => l.level === 'ERROR',                         color: '#f87171' },  // red
  { test: l => l.level === 'WARNING',                       color: '#fbbf24' },  // amber
  { test: l => /opened position/i.test(l.message),          color: '#34d399' },  // green
  { test: l => /closed|trailing_stop|stop_loss/i.test(l.message), color: '#60a5fa' }, // blue
  { test: l => /claude|signal|generate/i.test(l.message),   color: '#c084fc' },  // purple
  { test: l => /regime/i.test(l.message),                   color: '#f472b6' },  // pink
  { test: l => /circuit breaker/i.test(l.message),          color: '#fb923c' },  // orange
  { test: l => /refinement|refiner/i.test(l.message),       color: '#2dd4bf' },  // teal
  { test: l => /skipping|skip/i.test(l.message),            color: '#475569' },  // muted
  { test: () => true,                                        color: '#94a3b8' },  // default gray
];

function lineColor(logEntry) {
  return (LINE_STYLES.find(r => r.test(logEntry)) || LINE_STYLES.at(-1)).color;
}

function formatTs(iso) {
  try {
    return new Date(iso).toLocaleTimeString('en-US', { hour12: false });
  } catch {
    return iso?.slice(11, 19) ?? '';
  }
}

export default function LiveLog({ apiBase }) {
  const [logs,       setLogs]       = useState([]);
  const [paused,     setPaused]     = useState(false);
  const [filter,     setFilter]     = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const bottomRef  = useRef(null);
  const containerRef = useRef(null);

  const fetchLogs = useCallback(async () => {
    if (paused) return;
    try {
      const res  = await fetch(`${apiBase}/api/logs?limit=200`);
      const json = await res.json();
      if (json.status === 'ok') setLogs(json.data);
    } catch { /* backend might be momentarily unavailable */ }
  }, [apiBase, paused]);

  // Poll every 2 s
  useEffect(() => {
    fetchLogs();
    const id = setInterval(fetchLogs, 2000);
    return () => clearInterval(id);
  }, [fetchLogs]);

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  // Detect manual scroll-up → disable auto-scroll
  const onScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  };

  const filtered = filter
    ? logs.filter(l =>
        l.message.toLowerCase().includes(filter.toLowerCase()) ||
        l.level.toLowerCase().includes(filter.toLowerCase()) ||
        l.name.toLowerCase().includes(filter.toLowerCase())
      )
    : logs;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 10 }}>

      {/* ── Toolbar ─────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 11, color: '#475569', letterSpacing: 2 }}>
          LIVE LOG
        </span>

        {/* Live indicator */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <div style={{
            width: 7, height: 7, borderRadius: '50%',
            background: paused ? '#475569' : '#22c55e',
            boxShadow: paused ? 'none' : '0 0 6px #22c55e',
            animation: paused ? 'none' : 'logpulse 2s infinite',
          }} />
          <span style={{ fontSize: 10, color: paused ? '#475569' : '#22c55e' }}>
            {paused ? 'PAUSED' : 'LIVE'}
          </span>
        </div>

        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="filter logs…"
          style={{
            flex: 1, minWidth: 160, maxWidth: 320,
            background: '#0f172a', border: '1px solid #1e293b',
            color: '#94a3b8', padding: '4px 10px', borderRadius: 4,
            fontSize: 11, fontFamily: 'inherit', outline: 'none',
          }}
        />

        <span style={{ fontSize: 10, color: '#334155', marginLeft: 'auto' }}>
          {filtered.length} / {logs.length} lines
        </span>

        <button onClick={() => setPaused(p => !p)} style={btn(paused ? '#1a2f1a' : '#1a1a2e', paused ? '#4ade80' : '#94a3b8')}>
          {paused ? '▶ RESUME' : '⏸ PAUSE'}
        </button>
        <button onClick={() => setLogs([])} style={btn('#1a1a1a', '#475569')}>
          CLEAR
        </button>
      </div>

      {/* ── Legend ──────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
        {[
          ['OPEN',     '#34d399'],
          ['CLOSE',    '#60a5fa'],
          ['CLAUDE',   '#c084fc'],
          ['REGIME',   '#f472b6'],
          ['CB',       '#fb923c'],
          ['REFINE',   '#2dd4bf'],
          ['WARN',     '#fbbf24'],
          ['ERROR',    '#f87171'],
        ].map(([label, color]) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, cursor: 'pointer' }}
               onClick={() => setFilter(f => f === label.toLowerCase() ? '' : label.toLowerCase())}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />
            <span style={{ fontSize: 9, color, letterSpacing: 1 }}>{label}</span>
          </div>
        ))}
      </div>

      {/* ── Log terminal ────────────────────────────────────────────────── */}
      <div
        ref={containerRef}
        onScroll={onScroll}
        style={{
          flex: 1,
          overflowY: 'auto',
          background: '#020817',
          border: '1px solid #0f172a',
          borderRadius: 6,
          padding: '10px 14px',
          fontFamily: "'JetBrains Mono','Fira Code','Courier New',monospace",
          fontSize: 12,
          lineHeight: 1.7,
          minHeight: 400,
          maxHeight: 600,
        }}
      >
        {filtered.length === 0 ? (
          <div style={{ color: '#1e293b', textAlign: 'center', marginTop: 40 }}>
            {logs.length === 0 ? 'Waiting for log entries…' : 'No lines match filter'}
          </div>
        ) : (
          filtered.map((entry, i) => {
            const color = lineColor(entry);
            return (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                <span style={{ color: '#334155', flexShrink: 0, userSelect: 'none', fontSize: 10, paddingTop: 2 }}>
                  {formatTs(entry.ts)}
                </span>
                <span style={{
                  flexShrink: 0, fontSize: 9, letterSpacing: 1, paddingTop: 3,
                  color: entry.level === 'ERROR' ? '#f87171'
                       : entry.level === 'WARNING' ? '#fbbf24'
                       : '#334155',
                  minWidth: 40,
                }}>
                  {entry.level.slice(0, 4)}
                </span>
                <span style={{ color: '#1e3a5f', flexShrink: 0, fontSize: 10, paddingTop: 2, maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {entry.name}
                </span>
                <span style={{ color, wordBreak: 'break-word', flex: 1 }}>
                  {entry.message}
                </span>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      {/* Auto-scroll indicator */}
      {!autoScroll && (
        <button
          onClick={() => { setAutoScroll(true); bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }}
          style={{
            alignSelf: 'flex-end',
            padding: '4px 12px', fontSize: 10, letterSpacing: 1,
            background: '#0c1e40', color: '#00d4ff',
            border: '1px solid #00d4ff', borderRadius: 4,
            cursor: 'pointer', fontFamily: 'inherit',
          }}
        >
          ↓ SCROLL TO BOTTOM
        </button>
      )}

      <style>{`
        @keyframes logpulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}

function btn(bg, color) {
  return {
    padding: '4px 12px', fontSize: 10, letterSpacing: 1,
    background: bg, color,
    border: `1px solid ${color}`, borderRadius: 4,
    cursor: 'pointer', fontFamily: 'inherit',
  };
}
