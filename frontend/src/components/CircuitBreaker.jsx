import React, { useState, useEffect } from 'react';

const STATUS_CFG = {
  normal: { color: '#22c55e', bg: '#0f2a1a', label: 'NORMAL', icon: '✓', desc: 'Portfolio drawdown is within acceptable range. Full trading capacity active.' },
  soft:   { color: '#f59e0b', bg: '#2a1e0a', label: 'SOFT LIMIT', icon: '⚠', desc: 'Drawdown > 15% from peak. Confidence threshold raised, position sizes reduced.' },
  hard:   { color: '#f87171', bg: '#2a0a0a', label: 'HARD STOP', icon: '✗', desc: 'Drawdown > 25% from peak. All new position opens are blocked until recovery.' },
};

export default function CircuitBreaker({ apiBase }) {
  const [cb, setCb]         = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${apiBase}/api/circuit-breaker`)
      .then(r => r.json())
      .then(j => { setCb(j.data); setLoading(false); })
      .catch(() => setLoading(false));
  }, [apiBase]);

  if (loading) return <LoadingBox />;
  if (!cb) return <ErrorBox msg="Could not load circuit breaker data." />;

  const cfg      = STATUS_CFG[cb.status] || STATUS_CFG.normal;
  const ddPct    = (cb.current_drawdown * 100).toFixed(1);
  const softPct  = 15;
  const hardPct  = 25;
  const barFill  = Math.min(100, cb.current_drawdown * 100 / hardPct * 100);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Status hero ─────────────────────────────────────────────────────── */}
      <div style={{ ...card, background: cfg.bg, border: `1px solid ${cfg.color}55`, textAlign: 'center', padding: '28px 24px' }}>
        <div style={{ fontSize: 40, marginBottom: 10 }}>{cb.status === 'normal' ? '🛡' : cb.status === 'soft' ? '⚡' : '🚨'}</div>
        <div style={{
          display: 'inline-block', padding: '5px 20px', borderRadius: 20,
          background: `${cfg.color}22`, border: `1px solid ${cfg.color}`,
          color: cfg.color, fontSize: 13, fontWeight: 700, letterSpacing: 3, marginBottom: 12,
        }}>
          {cfg.label}
        </div>
        <p style={{ margin: '0 auto', color: '#94a3b8', fontSize: 13, lineHeight: 1.7, maxWidth: 520 }}>
          {cfg.desc}
        </p>
      </div>

      {/* ── Drawdown gauge ───────────────────────────────────────────────────── */}
      <div style={card}>
        <SectionTitle>Drawdown from Peak</SectionTitle>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 20 }}>
          <Metric label="Current Value"  value={`$${cb.current_value?.toFixed(2)}`} color="#e2e8f0" />
          <Metric label="Peak Value"     value={`$${cb.peak_value?.toFixed(2)}`}   color="#94a3b8" />
          <Metric label="Drawdown"       value={`${ddPct}%`}                        color={cfg.color} large />
        </div>

        {/* Segmented drawdown bar */}
        <div style={{ position: 'relative', marginBottom: 8 }}>
          <div style={{ height: 20, background: '#1e293b', borderRadius: 4, overflow: 'hidden', display: 'flex' }}>
            <div style={{
              width: `${barFill}%`,
              background: cb.status === 'normal' ? '#22c55e' : cb.status === 'soft' ? '#f59e0b' : '#f87171',
              transition: 'width 0.5s, background 0.3s',
              borderRadius: 4,
            }} />
          </div>
          {/* Soft limit marker at 60% of bar (15/25 = 60%) */}
          <div style={{
            position: 'absolute', top: 0, left: '60%',
            width: 2, height: 20, background: '#f59e0b', opacity: 0.8,
          }} title="15% soft limit" />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#475569' }}>
          <span>0%</span>
          <span style={{ color: '#f59e0b' }}>⚠ 15% soft</span>
          <span style={{ color: '#f87171' }}>✗ 25% hard</span>
        </div>
      </div>

      {/* ── Active restrictions ──────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div style={card}>
          <SectionTitle>Active Restrictions</SectionTitle>
          <RestrictionRow
            label="New Position Opens"
            value={cb.new_opens_blocked ? 'BLOCKED' : 'Allowed'}
            color={cb.new_opens_blocked ? '#f87171' : '#22c55e'}
          />
          <RestrictionRow
            label="Min Confidence Override"
            value={cb.min_confidence_override != null ? `${cb.min_confidence_override}%` : 'None'}
            color={cb.min_confidence_override != null ? '#f59e0b' : '#64748b'}
          />
          <RestrictionRow
            label="Max Position Size Override"
            value={cb.max_position_override != null ? `${(cb.max_position_override * 100).toFixed(0)}%` : 'None'}
            color={cb.max_position_override != null ? '#f59e0b' : '#64748b'}
          />
        </div>

        <div style={card}>
          <SectionTitle>Recovery Target</SectionTitle>
          {cb.status === 'hard' ? (
            <>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 14px', lineHeight: 1.6 }}>
                Hard stop clears when portfolio recovers to within 20% of peak.
              </p>
              <Metric label="Recovery Target" value={`$${(cb.peak_value * 0.80).toFixed(2)}`} color="#f87171" />
              <Metric label="Needed Gain"     value={`$${Math.max(0, cb.peak_value * 0.80 - cb.current_value).toFixed(2)}`} color="#f59e0b" />
            </>
          ) : cb.status === 'soft' ? (
            <p style={{ fontSize: 12, color: '#94a3b8', margin: 0, lineHeight: 1.6 }}>
              Soft restrictions lift automatically when drawdown falls below 15%.
              Current: <span style={{ color: '#f59e0b' }}>{ddPct}%</span> — need to recover to&nbsp;
              <span style={{ color: '#f59e0b' }}>${(cb.peak_value * 0.85).toFixed(2)}</span>.
            </p>
          ) : (
            <p style={{ fontSize: 12, color: '#4ade80', margin: 0, lineHeight: 1.6 }}>
              No recovery action needed. Portfolio is within normal operating range.
            </p>
          )}
        </div>
      </div>

      {/* ── Correlation Guard rules ─────────────────────────────────────────── */}
      <div style={card}>
        <SectionTitle>Correlation Guard Rules</SectionTitle>
        <p style={{ fontSize: 12, color: '#64748b', margin: '0 0 14px', lineHeight: 1.6 }}>
          These rules run before every new position open to prevent over-concentration.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          <RuleCard
            icon="📊"
            title="Pairwise Correlation"
            rule="Blocked if 60-day return correlation > 0.75 with any existing position"
            color="#60a5fa"
          />
          <RuleCard
            icon="🏭"
            title="Sector Limit"
            rule="Maximum 2 positions per GICS sector at any time (ETFs exempt)"
            color="#a78bfa"
          />
          <RuleCard
            icon="⏰"
            title="Earnings Blackout"
            rule="No new buys within 5 trading days of an earnings announcement"
            color="#34d399"
          />
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────────────────────── */

function SectionTitle({ children }) {
  return <h3 style={{ margin: '0 0 14px', fontSize: 12, color: '#00d4ff', letterSpacing: 2, textTransform: 'uppercase' }}>{children}</h3>;
}

function Metric({ label, value, color, large }) {
  return (
    <div style={{ background: '#0a0e1a', borderRadius: 6, padding: '12px 14px', border: '1px solid #1e293b' }}>
      <div style={{ fontSize: 10, color: '#475569', letterSpacing: 1, marginBottom: 6 }}>{label.toUpperCase()}</div>
      <div style={{ fontSize: large ? 24 : 18, fontWeight: 700, color: color || '#e2e8f0' }}>{value}</div>
    </div>
  );
}

function RestrictionRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '9px 0', borderBottom: '1px solid #0f1f36' }}>
      <span style={{ fontSize: 12, color: '#64748b' }}>{label}</span>
      <span style={{ fontSize: 12, fontWeight: 700, color }}>{value}</span>
    </div>
  );
}

function RuleCard({ icon, title, rule, color }) {
  return (
    <div style={{ background: '#0a0e1a', border: `1px solid ${color}33`, borderRadius: 8, padding: '14px' }}>
      <div style={{ fontSize: 22, marginBottom: 8 }}>{icon}</div>
      <div style={{ fontSize: 12, color, fontWeight: 600, marginBottom: 6 }}>{title}</div>
      <p style={{ fontSize: 11, color: '#64748b', margin: 0, lineHeight: 1.6 }}>{rule}</p>
    </div>
  );
}

function LoadingBox() {
  return (
    <div style={{ ...card, display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
      <span style={{ color: '#475569', fontSize: 13 }}>Loading circuit breaker data…</span>
    </div>
  );
}

function ErrorBox({ msg }) {
  return (
    <div style={{ ...card, display: 'flex', alignItems: 'center', justifyContent: 'center', height: 200 }}>
      <span style={{ color: '#f87171', fontSize: 13 }}>⚠ {msg}</span>
    </div>
  );
}

const card = {
  background: '#0f172a', border: '1px solid #1e293b',
  borderRadius: 8, padding: '20px',
};
