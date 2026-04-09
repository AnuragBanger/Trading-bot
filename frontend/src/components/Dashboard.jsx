import React, { useState, useEffect } from 'react';
import PortfolioOverview from './PortfolioOverview';
import ActiveTrades from './ActiveTrades';
import SignalFeed from './SignalFeed';
import PerformanceChart from './PerformanceChart';
import RefinementLog from './RefinementLog';
import GraduationStatus from './GraduationStatus';
import CircuitBreaker from './CircuitBreaker';
import HypothesisResearch from './HypothesisResearch';
import LiveLog from './LiveLog';

const NAV_ITEMS = [
  { id: 'overview',    label: 'PORTFOLIO' },
  { id: 'trades',      label: 'POSITIONS' },
  { id: 'signals',     label: 'SIGNALS' },
  { id: 'performance', label: 'PERFORMANCE' },
  { id: 'refinement',  label: 'REFINEMENT' },
  { id: 'graduation',  label: 'GRADUATION' },
  { id: 'circuit',     label: 'RISK GUARD' },
  { id: 'hypothesis',  label: 'HYPOTHESIS' },
  { id: 'logs',        label: 'LIVE LOG' },
];

const STATUS_COLORS = {
  learning:  { bg: '#1a2744', text: '#60a5fa', dot: '#3b82f6' },
  improving: { bg: '#1a2f1a', text: '#4ade80', dot: '#22c55e' },
  ready:     { bg: '#2a1a0a', text: '#fb923c', dot: '#f97316' },
};

const CB_COLORS = {
  normal: null,
  soft:   { bg: '#2a1e0a', border: '#f59e0b', text: '#f59e0b', label: '⚡ SOFT LIMIT' },
  hard:   { bg: '#2a0a0a', border: '#f87171', text: '#f87171', label: '🚨 HARD STOP' },
};

export default function Dashboard({ data, lastRefresh, cycleRunning, onRefresh, onTriggerCycle, apiBase, activeTab, setActiveTab }) {
  const [cbStatus, setCbStatus] = useState(null);

  // Fetch circuit-breaker status independently (not in main dashboard poll)
  useEffect(() => {
    const fetchCb = () => {
      fetch(`${apiBase}/api/circuit-breaker`)
        .then(r => r.json())
        .then(j => setCbStatus(j.data))
        .catch(() => {});
    };
    fetchCb();
    const id = setInterval(fetchCb, 60_000);
    return () => clearInterval(id);
  }, [apiBase]);

  const status       = data.graduation?.status || 'learning';
  const statusColors = STATUS_COLORS[status] || STATUS_COLORS.learning;
  const marketOpen   = data.market_open;
  const cbCfg        = cbStatus ? CB_COLORS[cbStatus.status] : null;

  return (
    <div style={{ maxWidth: 1400, margin: '0 auto', padding: '0 16px' }}>

      {/* ── Header ────────────────────────────────────────────────────────── */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px 0', borderBottom: '1px solid #1e293b',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 24 }}>⚡</span>
          <div>
            <h1 style={{ margin: 0, fontSize: 18, color: '#00d4ff', letterSpacing: 2, fontWeight: 700 }}>
              INVESTMENT ADVISORY BOT
            </h1>
            <p style={{ margin: 0, fontSize: 11, color: '#475569', letterSpacing: 1 }}>
              PAPER TRADING ENGINE v2.0
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          {/* Circuit breaker warning badge */}
          {cbCfg && (
            <button
              onClick={() => setActiveTab('circuit')}
              style={{
                padding: '4px 12px', borderRadius: 4,
                background: cbCfg.bg, border: `1px solid ${cbCfg.border}`,
                color: cbCfg.text, fontSize: 11, letterSpacing: 1,
                cursor: 'pointer', fontFamily: 'inherit',
                animation: cbStatus?.status === 'hard' ? 'pulse 2s infinite' : 'none',
              }}
            >
              {cbCfg.label}
            </button>
          )}

          {/* Market status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: marketOpen ? '#22c55e' : '#64748b',
              boxShadow: marketOpen ? '0 0 6px #22c55e' : 'none',
            }} />
            <span style={{ fontSize: 11, color: marketOpen ? '#22c55e' : '#64748b', letterSpacing: 1 }}>
              MARKET {marketOpen ? 'OPEN' : 'CLOSED'}
            </span>
          </div>

          {/* Bot status badge */}
          <div style={{
            padding: '4px 10px', borderRadius: 4,
            background: statusColors.bg,
            border: `1px solid ${statusColors.dot}`,
            display: 'flex', alignItems: 'center', gap: 6,
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: statusColors.dot, boxShadow: `0 0 4px ${statusColors.dot}` }} />
            <span style={{ fontSize: 11, color: statusColors.text, letterSpacing: 1, textTransform: 'uppercase' }}>
              {status}
            </span>
          </div>

          {/* Cycle info */}
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 11, color: '#475569' }}>
              Cycle #{data.cycle_count || 0}
            </div>
            <div style={{ fontSize: 10, color: '#334155' }}>
              {lastRefresh ? lastRefresh.toLocaleTimeString() : '—'}
            </div>
          </div>

          {/* Action buttons */}
          <button onClick={onRefresh} disabled={cycleRunning} style={btnStyle('#1e293b', cycleRunning ? '#334155' : '#94a3b8')}>REFRESH</button>
          <button
            onClick={onTriggerCycle}
            disabled={cycleRunning}
            style={{
              ...btnStyle(cycleRunning ? '#0a1f0a' : '#0c1e40', cycleRunning ? '#22c55e' : '#00d4ff'),
              animation: cycleRunning ? 'pulse 1.5s infinite' : 'none',
              minWidth: 110,
            }}
          >
            {cycleRunning ? '⟳ RUNNING…' : '▶ RUN CYCLE'}
          </button>
        </div>
      </header>

      {/* ── Cycle running banner ─────────────────────────────────────────── */}
      {cycleRunning && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12,
          margin: '10px 0 0', padding: '10px 16px',
          background: '#0a1f0a', border: '1px solid #166534',
          borderRadius: 6,
        }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e', boxShadow: '0 0 8px #22c55e', animation: 'pulse 1.5s infinite', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <span style={{ color: '#22c55e', fontSize: 12, letterSpacing: 1 }}>ANALYSIS CYCLE RUNNING</span>
            <span style={{ color: '#4ade80', fontSize: 11, marginLeft: 12 }}>
              Scanning watchlist → computing TA → sending to Claude AI → evaluating signals…
            </span>
          </div>
          <button
            onClick={() => setActiveTab('logs')}
            style={{ ...btnStyle('#0a2a0a', '#4ade80'), fontSize: 10 }}
          >
            VIEW LOGS →
          </button>
        </div>
      )}

      {/* ── Top-line KPIs ─────────────────────────────────────────────────── */}
      <TopKpis portfolio={data.portfolio} stats={data.stats} />

      {/* ── Navigation ───────────────────────────────────────────────────── */}
      <nav style={{ display: 'flex', gap: 2, marginTop: 20, borderBottom: '1px solid #1e293b', flexWrap: 'wrap' }}>
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            style={{
              padding: '8px 16px',
              background: activeTab === item.id ? '#0f172a' : 'transparent',
              color: activeTab === item.id ? '#00d4ff'
                : (item.id === 'circuit' && cbCfg) ? CB_COLORS[cbStatus?.status]?.text
                : '#475569',
              border: 'none',
              borderBottom: activeTab === item.id ? '2px solid #00d4ff' : '2px solid transparent',
              cursor: 'pointer',
              fontSize: 11,
              letterSpacing: 2,
              fontFamily: 'inherit',
              transition: 'all 0.15s',
            }}
          >
            {item.label}
            {item.id === 'circuit' && cbStatus?.status !== 'normal' && cbStatus?.status && (
              <span style={{ marginLeft: 4, fontSize: 9 }}>●</span>
            )}
          </button>
        ))}
      </nav>

      {/* ── Panel content ─────────────────────────────────────────────────── */}
      <main style={{ paddingTop: 20, paddingBottom: 40 }}>
        {activeTab === 'overview'    && <PortfolioOverview portfolio={data.portfolio} />}
        {activeTab === 'trades'      && <ActiveTrades positions={data.active_positions} />}
        {activeTab === 'signals'     && <SignalFeed signals={data.last_signals} apiBase={apiBase} />}
        {activeTab === 'performance' && <PerformanceChart stats={data.stats} portfolio={data.portfolio} apiBase={apiBase} />}
        {activeTab === 'refinement'  && <RefinementLog apiBase={apiBase} />}
        {activeTab === 'graduation'  && <GraduationStatus graduation={data.graduation} />}
        {activeTab === 'circuit'     && <CircuitBreaker apiBase={apiBase} />}
        {activeTab === 'hypothesis'  && <HypothesisResearch apiBase={apiBase} />}
        {activeTab === 'logs'        && <LiveLog apiBase={apiBase} />}
      </main>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.6; }
        }
      `}</style>
    </div>
  );
}

function TopKpis({ portfolio, stats }) {
  const p   = portfolio || {};
  const s   = stats     || {};
  const pnl    = p.total_pnl ?? 0;
  const pnlPct = p.total_pnl_pct ?? 0;
  const pnlColor = pnl >= 0 ? '#22c55e' : '#f87171';

  const row1 = [
    { label: 'TOTAL VALUE',    value: `$${(p.total_value ?? 0).toFixed(2)}`,    sub: `Started $${(p.starting_capital ?? 500).toFixed(0)}` },
    { label: 'TOTAL P&L',      value: `${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}`, sub: `${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%`, color: pnlColor },
    { label: 'AVAILABLE CASH', value: `$${(p.available_cash ?? 0).toFixed(2)}`, sub: `${((p.available_cash ?? 0) / (p.total_value || 1) * 100).toFixed(0)}% of portfolio` },
    { label: 'WIN RATE',       value: `${(s.win_rate ?? 0).toFixed(1)}%`,        sub: `${s.winning_trades ?? 0}W / ${s.losing_trades ?? 0}L`, color: (s.win_rate ?? 0) >= 60 ? '#22c55e' : '#f59e0b' },
    { label: 'SHARPE',         value: s.sharpe_ratio != null ? s.sharpe_ratio.toFixed(2) : '—', sub: 'Risk-adj. return', color: s.sharpe_ratio >= 1 ? '#22c55e' : s.sharpe_ratio >= 0.5 ? '#f59e0b' : '#f87171' },
    { label: 'PROFIT FACTOR',  value: s.profit_factor != null ? s.profit_factor.toFixed(2) : '—', sub: 'Win / loss ratio', color: s.profit_factor >= 1.3 ? '#22c55e' : s.profit_factor >= 1 ? '#f59e0b' : '#f87171' },
  ];

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginTop: 16 }}>
      {row1.map(k => (
        <div key={k.label} style={{
          background: '#0f172a', border: '1px solid #1e293b',
          borderRadius: 8, padding: '14px 16px',
        }}>
          <div style={{ fontSize: 10, color: '#475569', letterSpacing: 2, marginBottom: 6 }}>{k.label}</div>
          <div style={{ fontSize: 20, fontWeight: 700, color: k.color || '#e2e8f0' }}>{k.value}</div>
          <div style={{ fontSize: 11, color: '#334155', marginTop: 4 }}>{k.sub}</div>
        </div>
      ))}
    </div>
  );
}

function btnStyle(bg, color) {
  return {
    padding: '6px 14px', background: bg, color,
    border: `1px solid ${color}`, borderRadius: 4,
    cursor: 'pointer', fontSize: 11, letterSpacing: 1,
    fontFamily: 'inherit',
  };
}
