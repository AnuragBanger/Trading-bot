import React, { useState, useEffect } from 'react';

export default function PerformanceChart({ stats, portfolio, apiBase }) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    fetch(`${apiBase}/api/trades/history`)
      .then(r => r.json())
      .then(j => setHistory(j.data || []))
      .catch(() => {});
  }, [apiBase]);

  const s          = stats || {};
  const winRate    = s.win_rate    ?? 0;
  const avgWin     = s.avg_win_pct ?? 0;
  const avgLoss    = s.avg_loss_pct?? 0;
  const byIndicator= s.by_indicator || {};
  const bySector   = s.by_sector    || {};
  const monthly    = s.monthly_performance || [];
  const curve      = portfolio?.equity_curve || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Top row: Win rate gauge + Win vs Loss */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>
        <WinRateGauge winRate={winRate} total={s.total_trades} wins={s.winning_trades} losses={s.losing_trades} />
        <WinLossBar avgWin={avgWin} avgLoss={avgLoss} />
        <RiskReward avgWin={avgWin} avgLoss={avgLoss} />
      </div>

      {/* Risk-adjusted metrics panel */}
      <RiskMetricsPanel stats={s} />

      {/* Equity Curve */}
      {curve.length > 1 && (
        <div style={card}>
          <SectionTitle>Equity Curve</SectionTitle>
          <MiniChart data={curve.slice(-100)} valueKey="value" colorUp="#22c55e" colorDown="#f87171" height={120} />
        </div>
      )}

      {/* Indicator Win Rates */}
      {Object.keys(byIndicator).length > 0 && (
        <div style={card}>
          <SectionTitle>Win Rate by Indicator</SectionTitle>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 8 }}>
            {Object.entries(byIndicator)
              .sort((a, b) => b[1].win_rate - a[1].win_rate)
              .map(([sig, v]) => (
                <IndicatorBar key={sig} label={sig} winRate={v.win_rate} trades={v.trades} wins={v.wins} />
              ))}
          </div>
        </div>
      )}

      {/* Monthly performance */}
      {monthly.length > 0 && (
        <div style={card}>
          <SectionTitle>Monthly Performance</SectionTitle>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8 }}>
            {monthly.map(m => (
              <MonthCard key={m.month} month={m} />
            ))}
          </div>
        </div>
      )}

      {/* Sector breakdown */}
      {Object.keys(bySector).length > 0 && (
        <div style={card}>
          <SectionTitle>Win Rate by Sector / Type</SectionTitle>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
            {Object.entries(bySector).map(([sector, v]) => (
              <div key={sector} style={{ background: '#0a0e1a', border: '1px solid #1e293b', borderRadius: 6, padding: '10px 14px', minWidth: 120 }}>
                <div style={{ fontSize: 10, color: '#475569', marginBottom: 4, letterSpacing: 1 }}>{sector.toUpperCase()}</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: v.win_rate >= 60 ? '#22c55e' : v.win_rate >= 50 ? '#f59e0b' : '#f87171' }}>
                  {v.win_rate.toFixed(0)}%
                </div>
                <div style={{ fontSize: 11, color: '#334155' }}>{v.wins}W / {v.trades - v.wins}L</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent closed trades table */}
      {history.length > 0 && (
        <div style={card}>
          <SectionTitle>Recent Closed Trades ({history.length} total)</SectionTitle>
          <div style={{ overflowX: 'auto', marginTop: 8 }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #1e293b' }}>
                  {['Ticker','Entry','Exit','P&L%','Result','Exit Reason','Confidence'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '6px 12px', fontSize: 10, color: '#475569', letterSpacing: 1 }}>{h.toUpperCase()}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.slice(-20).reverse().map((t, i) => {
                  const pnlColor = t.was_correct ? '#22c55e' : '#f87171';
                  return (
                    <tr key={i} style={{ borderBottom: '1px solid #0f172a' }}>
                      <td style={{ padding: '6px 12px', color: '#e2e8f0', fontWeight: 600 }}>{t.ticker}</td>
                      <td style={{ padding: '6px 12px', color: '#94a3b8' }}>${t.entry_price?.toFixed(2)}</td>
                      <td style={{ padding: '6px 12px', color: '#94a3b8' }}>${t.exit_price?.toFixed(2)}</td>
                      <td style={{ padding: '6px 12px', color: pnlColor, fontWeight: 600 }}>{t.pct_change >= 0 ? '+' : ''}{t.pct_change?.toFixed(2)}%</td>
                      <td style={{ padding: '6px 12px', color: pnlColor }}>{t.result}</td>
                      <td style={{ padding: '6px 12px', color: '#64748b' }}>{t.exit_reason}</td>
                      <td style={{ padding: '6px 12px', color: '#64748b' }}>{t.confidence_at_entry}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function WinRateGauge({ winRate, total, wins, losses }) {
  const r = 40;
  const circ = 2 * Math.PI * r;
  const filled = (winRate / 100) * circ;
  const color = winRate >= 60 ? '#22c55e' : winRate >= 50 ? '#f59e0b' : '#f87171';

  return (
    <div style={{ ...card, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
      <SectionTitle>Win Rate</SectionTitle>
      <svg width={100} height={100} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={50} cy={50} r={r} fill="none" stroke="#1e293b" strokeWidth={10} />
        <circle cx={50} cy={50} r={r} fill="none" stroke={color} strokeWidth={10}
          strokeDasharray={`${filled} ${circ}`}
          strokeLinecap="round" style={{ transition: 'stroke-dasharray 0.5s' }}
        />
      </svg>
      <div style={{ marginTop: -70, fontSize: 22, fontWeight: 700, color }}>{winRate.toFixed(1)}%</div>
      <div style={{ marginTop: 30, fontSize: 11, color: '#475569' }}>{wins}W / {losses}L / {total} total</div>
      <div style={{ fontSize: 11, color: winRate >= 60 ? '#22c55e' : '#f59e0b' }}>
        {winRate >= 60 ? '✓ Target Met' : `${(60 - winRate).toFixed(1)}% to target`}
      </div>
    </div>
  );
}

function WinLossBar({ avgWin, avgLoss }) {
  const maxVal = Math.max(avgWin, avgLoss, 1);
  return (
    <div style={card}>
      <SectionTitle>Avg Win vs Avg Loss</SectionTitle>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#475569', marginBottom: 4 }}>
            <span>Avg Win</span>
            <span style={{ color: '#22c55e', fontWeight: 700 }}>+{avgWin.toFixed(2)}%</span>
          </div>
          <div style={{ height: 12, background: '#1e293b', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ width: `${(avgWin / maxVal) * 100}%`, height: '100%', background: '#22c55e', borderRadius: 6, transition: 'width 0.5s' }} />
          </div>
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#475569', marginBottom: 4 }}>
            <span>Avg Loss</span>
            <span style={{ color: '#f87171', fontWeight: 700 }}>-{avgLoss.toFixed(2)}%</span>
          </div>
          <div style={{ height: 12, background: '#1e293b', borderRadius: 6, overflow: 'hidden' }}>
            <div style={{ width: `${(avgLoss / maxVal) * 100}%`, height: '100%', background: '#f87171', borderRadius: 6, transition: 'width 0.5s' }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function RiskReward({ avgWin, avgLoss }) {
  const rr = avgLoss > 0 ? avgWin / avgLoss : 0;
  const rrColor = rr >= 2 ? '#22c55e' : rr >= 1 ? '#f59e0b' : '#f87171';
  return (
    <div style={{ ...card, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
      <SectionTitle>Risk / Reward</SectionTitle>
      <div style={{ fontSize: 36, fontWeight: 700, color: rrColor }}>{rr.toFixed(2)}</div>
      <div style={{ fontSize: 11, color: '#475569' }}>Reward per unit of risk</div>
      <div style={{ fontSize: 11, color: rrColor }}>{rr >= 2 ? '✓ Excellent' : rr >= 1.5 ? '✓ Good' : rr >= 1 ? '⚠ Acceptable' : '✗ Needs improvement'}</div>
    </div>
  );
}

function IndicatorBar({ label, winRate, trades, wins }) {
  const color = winRate >= 60 ? '#22c55e' : winRate >= 50 ? '#f59e0b' : '#f87171';
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
        <span style={{ color: '#94a3b8' }}>{label}</span>
        <span style={{ color, fontWeight: 700 }}>{winRate.toFixed(0)}% ({wins}/{trades})</span>
      </div>
      <div style={{ height: 8, background: '#1e293b', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${winRate}%`, height: '100%', background: color, borderRadius: 4, transition: 'width 0.5s' }} />
      </div>
    </div>
  );
}

function MonthCard({ month }) {
  const color = month.profitable ? '#22c55e' : '#f87171';
  return (
    <div style={{ background: '#0a0e1a', border: `1px solid ${color}33`, borderRadius: 6, padding: '10px 14px', minWidth: 100 }}>
      <div style={{ fontSize: 11, color: '#475569', marginBottom: 4 }}>{month.month}</div>
      <div style={{ fontSize: 16, fontWeight: 700, color }}>{month.total_pnl_pct >= 0 ? '+' : ''}{month.total_pnl_pct.toFixed(1)}%</div>
      <div style={{ fontSize: 10, color: '#334155' }}>{month.win_rate.toFixed(0)}% WR · {month.trades}T</div>
    </div>
  );
}

function MiniChart({ data, valueKey, height }) {
  if (!data || data.length < 2) return null;
  const vals = data.map(d => d[valueKey]);
  const min  = Math.min(...vals);
  const max  = Math.max(...vals);
  const range= max - min || 1;
  const w    = 100 / (data.length - 1);

  const points = data.map((d, i) => {
    const x = i * w;
    const y = height - ((d[valueKey] - min) / range) * (height - 10) - 5;
    return `${x},${y}`;
  }).join(' ');

  const lastVal  = vals[vals.length - 1];
  const firstVal = vals[0];
  const isUp     = lastVal >= firstVal;

  return (
    <div style={{ position: 'relative', height: height + 20 }}>
      <svg width="100%" height={height} viewBox={`0 0 100 ${height}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={isUp ? '#22c55e' : '#f87171'} stopOpacity="0.3" />
            <stop offset="100%" stopColor={isUp ? '#22c55e' : '#f87171'} stopOpacity="0" />
          </linearGradient>
        </defs>
        <polyline points={points} fill="none" stroke={isUp ? '#22c55e' : '#f87171'} strokeWidth="0.5" />
      </svg>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#334155', marginTop: 4 }}>
        <span>${firstVal?.toFixed(2)}</span>
        <span style={{ color: isUp ? '#22c55e' : '#f87171' }}>${lastVal?.toFixed(2)}</span>
      </div>
    </div>
  );
}

function RiskMetricsPanel({ stats: s }) {
  const sharpe   = s.sharpe_ratio;
  const sortino  = s.sortino_ratio;
  const pf       = s.profit_factor;
  const exp      = s.expectancy_pct;
  const maxDD    = s.max_drawdown_pct;
  const conLoss  = s.max_consecutive_losses;
  const conWin   = s.max_consecutive_wins;

  if (sharpe == null && pf == null) return null;

  const metricColor = (val, goodThresh, badThresh, lowerIsBetter = false) => {
    if (val == null) return '#475569';
    if (lowerIsBetter) return val <= goodThresh ? '#22c55e' : val <= badThresh ? '#f59e0b' : '#f87171';
    return val >= goodThresh ? '#22c55e' : val >= badThresh ? '#f59e0b' : '#f87171';
  };

  const metrics = [
    { label: 'SHARPE RATIO',      value: sharpe  != null ? sharpe.toFixed(2)  : 'N/A', color: metricColor(sharpe, 1.0, 0.5),  target: '> 1.0', desc: 'Risk-adj. return' },
    { label: 'SORTINO RATIO',     value: sortino != null ? sortino.toFixed(2) : 'N/A', color: metricColor(sortino, 1.0, 0.5), target: '> 1.0', desc: 'Downside-adj. return' },
    { label: 'PROFIT FACTOR',     value: pf      != null ? pf.toFixed(2)      : 'N/A', color: metricColor(pf, 1.3, 1.0),      target: '> 1.3', desc: 'Gross win / gross loss' },
    { label: 'EXPECTANCY',        value: exp     != null ? `${exp.toFixed(2)}%` : 'N/A', color: metricColor(exp, 1.0, 0),     target: '> 0%',  desc: 'Avg profit per trade' },
    { label: 'MAX DRAWDOWN',      value: maxDD   != null ? `${maxDD.toFixed(1)}%` : 'N/A', color: metricColor(maxDD, 10, 20, true), target: '< 15%', desc: 'Cumulative peak to trough' },
    { label: 'MAX CONSEC. LOSSES',value: conLoss != null ? conLoss : 'N/A',   color: metricColor(conLoss, 2, 4, true),       target: '≤ 3',   desc: 'Consecutive losing trades' },
  ];

  return (
    <div style={card}>
      <SectionTitle>Risk-Adjusted Metrics</SectionTitle>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(6, 1fr)', gap: 12, marginTop: 8 }}>
        {metrics.map(m => (
          <div key={m.label} style={{ background: '#0a0e1a', borderRadius: 6, padding: '12px 10px', border: `1px solid ${m.color}33` }}>
            <div style={{ fontSize: 9, color: '#475569', letterSpacing: 1, marginBottom: 6 }}>{m.label}</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: m.color }}>{m.value}</div>
            <div style={{ fontSize: 9, color: '#334155', marginTop: 4 }}>Target: {m.target}</div>
            <div style={{ fontSize: 9, color: '#1e3a5f', marginTop: 2 }}>{m.desc}</div>
          </div>
        ))}
      </div>
      {conWin != null && conLoss != null && (
        <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 11, color: '#64748b' }}>
          <span>Max win streak: <strong style={{ color: '#22c55e' }}>{conWin}</strong></span>
          <span>Max loss streak: <strong style={{ color: '#f87171' }}>{conLoss}</strong></span>
        </div>
      )}
    </div>
  );
}

function SectionTitle({ children }) {
  return <h3 style={{ margin: '0 0 4px', fontSize: 12, color: '#00d4ff', letterSpacing: 2, textTransform: 'uppercase' }}>{children}</h3>;
}

const card = {
  background: '#0f172a', border: '1px solid #1e293b',
  borderRadius: 8, padding: '20px',
};
