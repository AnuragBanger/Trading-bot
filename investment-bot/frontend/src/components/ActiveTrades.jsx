import React from 'react';

const RISK_COLORS = { low: '#22c55e', medium: '#f59e0b', high: '#f87171' };

export default function ActiveTrades({ positions }) {
  const pos = positions || [];

  if (pos.length === 0) {
    return (
      <div style={{ ...card, textAlign: 'center', padding: 60 }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>📊</div>
        <div style={{ color: '#475569', fontSize: 14 }}>No active positions</div>
        <div style={{ color: '#334155', fontSize: 12, marginTop: 8 }}>Positions will appear here after the bot opens trades</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 12, color: '#00d4ff', letterSpacing: 2 }}>
          ACTIVE POSITIONS ({pos.length})
        </h3>
        <span style={{ fontSize: 11, color: '#475569' }}>Updates every 60s</span>
      </div>

      {pos.map(p => (
        <PositionCard key={p.id} pos={p} />
      ))}
    </div>
  );
}

function PositionCard({ pos }) {
  const pnlColor = pos.pnl_pct >= 0 ? '#22c55e' : '#f87171';
  const riskColor = RISK_COLORS[pos.risk_level] || '#f59e0b';

  const entry  = pos.entry_price;
  const curr   = pos.current_price || entry;
  const tp1    = pos.take_profit_1;
  const tp2    = pos.take_profit_2;
  const sl     = pos.stop_loss;

  // Progress between SL → entry → TP2
  const range  = tp2 && sl ? tp2 - sl : 1;
  const pct    = tp2 && sl ? ((curr - sl) / range * 100) : 50;
  const pctClamped = Math.max(0, Math.min(100, pct));

  const daysSince = pos.entry_date
    ? Math.floor((Date.now() - new Date(pos.entry_date).getTime()) / 86400000)
    : 0;

  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
        {/* Left */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ width: 40, height: 40, background: '#1e293b', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#00d4ff' }}>
            {pos.ticker.slice(0, 4)}
          </div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>{pos.ticker}</div>
            <div style={{ fontSize: 11, color: '#475569' }}>{pos.type?.toUpperCase()} · {daysSince}d held</div>
          </div>
        </div>
        {/* Right */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: pnlColor }}>
            {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct?.toFixed(2)}%
          </div>
          <div style={{ fontSize: 12, color: '#475569' }}>
            {pos.pnl >= 0 ? '+' : ''}${pos.pnl?.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Price row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 14 }}>
        <PriceTag label="ENTRY"    value={`$${entry?.toFixed(2)}`} />
        <PriceTag label="CURRENT"  value={`$${curr?.toFixed(4)}`}  highlight />
        <PriceTag label="COST"     value={`$${pos.cost_basis?.toFixed(2)}`} />
        <PriceTag label="VALUE"    value={`$${pos.current_value?.toFixed(2)}`} />
      </div>

      {/* Target progress bar */}
      {sl && tp2 && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#475569', marginBottom: 4 }}>
            <span style={{ color: '#f87171' }}>SL ${sl?.toFixed(2)}</span>
            {tp1 && <span style={{ color: '#f59e0b' }}>TP1 ${tp1?.toFixed(2)}</span>}
            <span style={{ color: '#22c55e' }}>TP2 ${tp2?.toFixed(2)}</span>
          </div>
          <div style={{ height: 8, background: '#1e293b', borderRadius: 4, overflow: 'hidden', position: 'relative' }}>
            {/* SL → Entry zone */}
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${((entry - sl) / (tp2 - sl) * 100).toFixed(1)}%`, background: '#1e293b', borderRight: '1px dashed #475569' }} />
            {/* TP1 marker */}
            {tp1 && (
              <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${((tp1 - sl) / (tp2 - sl) * 100).toFixed(1)}%`, width: 2, background: '#f59e0b', opacity: 0.7 }} />
            )}
            {/* Current price cursor */}
            <div style={{
              position: 'absolute', top: 0, bottom: 0,
              width: `${pctClamped}%`,
              background: pos.pnl_pct >= 0
                ? 'linear-gradient(90deg, #1e4080, #22c55e)'
                : 'linear-gradient(90deg, #f87171, #991b1b)',
              borderRadius: 4,
              transition: 'width 0.5s',
            }} />
          </div>
        </div>
      )}

      {/* Badges row */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Badge color={riskColor}>{pos.risk_level?.toUpperCase()} RISK</Badge>
        <Badge color="#60a5fa">HOLD: {pos.holding_period?.toUpperCase()}</Badge>
        <Badge color={pos.tp1_hit ? '#22c55e' : '#334155'}>TP1 {pos.tp1_hit ? '✓ HIT' : 'PENDING'}</Badge>
        <Badge color="#334155">CONF: {pos.confidence}%</Badge>
        {pos.stop_moved_to_breakeven && <Badge color="#22c55e">STOP=BREAKEVEN</Badge>}
      </div>

      {/* Signals */}
      {pos.key_signals?.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {pos.key_signals.map(s => (
            <span key={s} style={{ fontSize: 10, padding: '2px 6px', background: '#0f1f36', color: '#60a5fa', borderRadius: 3, border: '1px solid #1e293b' }}>
              {s}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function PriceTag({ label, value, highlight }) {
  return (
    <div style={{ background: '#0a0e1a', borderRadius: 6, padding: '8px 10px', border: `1px solid ${highlight ? '#1e40af' : '#1e293b'}` }}>
      <div style={{ fontSize: 10, color: '#475569', marginBottom: 4, letterSpacing: 1 }}>{label}</div>
      <div style={{ fontSize: 13, color: highlight ? '#60a5fa' : '#94a3b8', fontWeight: highlight ? 700 : 400 }}>{value}</div>
    </div>
  );
}

function Badge({ color, children }) {
  return (
    <span style={{ fontSize: 10, padding: '3px 8px', background: `${color}22`, color, border: `1px solid ${color}44`, borderRadius: 3, letterSpacing: 0.5 }}>
      {children}
    </span>
  );
}

const card = {
  background: '#0f172a', border: '1px solid #1e293b',
  borderRadius: 8, padding: '20px',
};
