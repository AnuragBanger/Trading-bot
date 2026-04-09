import React from 'react';

const STATUS_CONFIG = {
  learning: {
    color:     '#3b82f6',
    bg:        '#1a2744',
    label:     'LEARNING',
    desc:      'Still building the trade history needed to evaluate readiness.',
    icon:      '🎓',
  },
  improving: {
    color:     '#22c55e',
    bg:        '#1a2f1a',
    label:     'IMPROVING',
    desc:      'Strong progress! Some graduation criteria are met. Keep trading.',
    icon:      '📈',
  },
  ready: {
    color:     '#f97316',
    bg:        '#2a1a0a',
    label:     'READY TO GRADUATE',
    desc:      'All criteria met! The bot is ready to consider real-money trading.',
    icon:      '🚀',
  },
};

export default function GraduationStatus({ graduation }) {
  const g = graduation || {};
  const status    = g.status    || 'learning';
  const criteria  = g.criteria  || {};
  const cfg       = STATUS_CONFIG[status] || STATUS_CONFIG.learning;
  const metCount  = g.met_count || 0;
  const total     = g.total_criteria || 6;
  const progress  = (metCount / total) * 100;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Status hero */}
      <div style={{ ...card, background: cfg.bg, border: `1px solid ${cfg.color}44`, textAlign: 'center', padding: '30px 20px' }}>
        <div style={{ fontSize: 48, marginBottom: 12 }}>{cfg.icon}</div>
        <div style={{
          display: 'inline-block', padding: '6px 20px', borderRadius: 20,
          background: `${cfg.color}22`, border: `1px solid ${cfg.color}`,
          color: cfg.color, fontSize: 14, fontWeight: 700, letterSpacing: 3,
          marginBottom: 14,
        }}>
          {cfg.label}
        </div>
        <p style={{ margin: '0 0 20px', color: '#94a3b8', fontSize: 13, lineHeight: 1.7, maxWidth: 500, marginLeft: 'auto', marginRight: 'auto' }}>
          {cfg.desc}
        </p>

        {/* Overall progress bar */}
        <div style={{ maxWidth: 400, margin: '0 auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#475569', marginBottom: 6 }}>
            <span>Graduation Progress</span>
            <span style={{ color: cfg.color }}>{metCount} / {total} criteria met</span>
          </div>
          <div style={{ height: 12, background: '#1e293b', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ width: `${progress}%`, height: '100%', background: cfg.color, borderRadius: 6, transition: 'width 0.5s', boxShadow: `0 0 8px ${cfg.color}66` }} />
          </div>
        </div>
      </div>

      {/* Criteria breakdown */}
      <div style={card}>
        <h3 style={{ margin: '0 0 20px', fontSize: 12, color: '#00d4ff', letterSpacing: 2 }}>GRADUATION CRITERIA</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>

          <CriterionCard
            title="Win Rate ≥ 60%"
            description="Over last 20+ closed trades"
            criterion={criteria.win_rate_60_pct}
            format={v => `${v}%`}
          />
          <CriterionCard
            title="Avg Loss < 15%"
            description="Average loss on bad trades"
            criterion={criteria.avg_loss_under_15_pct}
            format={v => `${v}%`}
            lowerIsBetter
          />
          <CriterionCard
            title="2 Profitable Months"
            description="Consecutive months with positive P&L"
            criterion={criteria.profitable_2_months}
            format={v => `${v} month${v !== 1 ? 's' : ''}`}
          />
          <CriterionCard
            title="Min 20 Closed Trades"
            description="Minimum sample size for evaluation"
            criterion={criteria.min_20_closed_trades}
            format={v => `${v} trades`}
          />
          <CriterionCard
            title="Sharpe Ratio > 1.0"
            description="Risk-adjusted return (annualised)"
            criterion={criteria.sharpe_ratio_over_1}
            format={v => v != null ? v.toFixed(2) : 'N/A'}
          />
          <CriterionCard
            title="Profit Factor > 1.3"
            description="Gross wins ÷ gross losses"
            criterion={criteria.profit_factor_over_1_3}
            format={v => v != null ? v.toFixed(2) : 'N/A'}
          />
        </div>
      </div>

      {/* Stats summary */}
      <div style={card}>
        <h3 style={{ margin: '0 0 16px', fontSize: 12, color: '#00d4ff', letterSpacing: 2 }}>PERFORMANCE SUMMARY</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
          <StatBox label="Overall Win Rate"  value={`${(g.overall_win_rate || 0).toFixed(1)}%`}  target="60%" met={(g.overall_win_rate || 0) >= 60} />
          <StatBox label="Last 20 Win Rate"  value={`${(g.last20_win_rate || 0).toFixed(1)}%`}   target="60%" met={(g.last20_win_rate || 0) >= 60} />
          <StatBox label="Total Trades"      value={g.total_trades || 0}                           target="20"  met={(g.total_trades || 0) >= 20} />
          <StatBox label="Met / Total"       value={`${g.met_count || 0} / ${g.total_criteria || 6}`} target="6/6" met={(g.met_count || 0) >= 6} />
          <StatBox label="Avg Win"           value={`+${(g.avg_win_pct || 0).toFixed(2)}%`}      target=">0%"  met={(g.avg_win_pct || 0) > 0} />
          <StatBox label="Avg Loss"          value={`-${(g.avg_loss_pct || 0).toFixed(2)}%`}     target="<15%" met={(g.avg_loss_pct || 0) < 15} />
          <StatBox label="Trades Remaining"  value={g.trades_remaining || 0}                       target="0"    met={(g.trades_remaining || 0) === 0} />
          <StatBox label="Sharpe Ratio"      value={g.sharpe_ratio != null ? g.sharpe_ratio.toFixed(2) : 'N/A'} target=">1.0" met={(g.sharpe_ratio || 0) > 1.0} />
          <StatBox label="Profit Factor"     value={g.profit_factor != null ? g.profit_factor.toFixed(2) : 'N/A'} target=">1.3" met={(g.profit_factor || 0) > 1.3} />
        </div>
      </div>

      {/* Alert when ready */}
      {status === 'ready' && (
        <div style={{
          padding: '20px 24px', background: '#1a2f1a',
          border: '1px solid #22c55e', borderRadius: 8,
          display: 'flex', alignItems: 'flex-start', gap: 16,
        }}>
          <span style={{ fontSize: 24 }}>🎉</span>
          <div>
            <div style={{ color: '#22c55e', fontWeight: 700, fontSize: 14, marginBottom: 6 }}>
              GRADUATION CRITERIA MET
            </div>
            <p style={{ margin: 0, color: '#4ade80', fontSize: 13, lineHeight: 1.7 }}>
              The bot has demonstrated consistent performance in paper trading. You may now
              consider transitioning to real-money trading with a small initial capital.
              Start conservatively — use a real broker with the same $500/month budget
              and monitor for at least 2 real-money months before scaling up.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function CriterionCard({ title, description, criterion, format, lowerIsBetter }) {
  const c    = criterion || { met: false, value: 0, target: 0 };
  const met  = c.met;
  const color= met ? '#22c55e' : '#f87171';

  const pct  = lowerIsBetter
    ? Math.max(0, Math.min(100, ((c.target - c.value) / c.target) * 100))
    : Math.max(0, Math.min(100, (c.value / c.target) * 100));

  return (
    <div style={{
      background: '#0a0e1a', borderRadius: 8, padding: '16px',
      border: `1px solid ${met ? '#22c55e44' : '#1e293b'}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 13, color: '#e2e8f0', fontWeight: 600 }}>{title}</span>
        <span style={{ fontSize: 18 }}>{met ? '✅' : '⭕'}</span>
      </div>
      <p style={{ fontSize: 11, color: '#475569', margin: '0 0 12px' }}>{description}</p>
      <div style={{ height: 6, background: '#1e293b', borderRadius: 3, overflow: 'hidden', marginBottom: 8 }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.5s' }} />
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
        <span style={{ color }}>Current: {format ? format(c.value) : c.value}</span>
        <span style={{ color: '#334155' }}>Target: {format ? format(c.target) : c.target}</span>
      </div>
    </div>
  );
}

function StatBox({ label, value, target, met }) {
  return (
    <div style={{ background: '#0a0e1a', borderRadius: 6, padding: '12px 14px', border: '1px solid #1e293b' }}>
      <div style={{ fontSize: 10, color: '#475569', letterSpacing: 1, marginBottom: 6 }}>{label.toUpperCase()}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: met ? '#22c55e' : '#e2e8f0' }}>{value}</div>
      <div style={{ fontSize: 10, color: '#334155', marginTop: 4 }}>Target: {target}</div>
    </div>
  );
}

const card = {
  background: '#0f172a', border: '1px solid #1e293b',
  borderRadius: 8, padding: '20px',
};
