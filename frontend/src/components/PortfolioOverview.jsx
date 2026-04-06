import React from 'react';

export default function PortfolioOverview({ portfolio }) {
  const p = portfolio || {};
  const totalValue   = p.total_value   ?? 500;
  const deposited    = p.total_deposited ?? 500;
  const avail        = p.available_cash  ?? 500;
  const invested     = p.invested_amount ?? 0;
  const pnl          = p.total_pnl       ?? 0;
  const pnlPct       = p.total_pnl_pct   ?? 0;
  const monthly      = p.monthly_deposits ?? [];
  const curve        = p.equity_curve     ?? [];

  const pnlColor = pnl >= 0 ? '#22c55e' : '#f87171';
  const investedPct = totalValue > 0 ? (invested / totalValue * 100) : 0;
  const availPct    = totalValue > 0 ? (avail    / totalValue * 100) : 0;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

      {/* Left: Portfolio breakdown */}
      <div style={card}>
        <SectionTitle>Portfolio Breakdown</SectionTitle>
        <Row label="Total Portfolio Value" value={`$${totalValue.toFixed(2)}`} large />
        <Row label="Total Deposited"       value={`$${deposited.toFixed(2)}`} />
        <Row label="Total P&L"             value={`${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)} (${pnlPct >= 0 ? '+' : ''}${pnlPct.toFixed(2)}%)`} color={pnlColor} />
        <Divider />
        <Row label="Available Cash"  value={`$${avail.toFixed(2)}`} />
        <Row label="Invested Amount" value={`$${invested.toFixed(2)}`} />
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 11, color: '#475569', marginBottom: 6 }}>ALLOCATION</div>
          <div style={{ height: 20, background: '#1e293b', borderRadius: 4, overflow: 'hidden', display: 'flex' }}>
            <div style={{ width: `${investedPct}%`, background: '#3b82f6', transition: 'width 0.5s' }} title={`Invested ${investedPct.toFixed(0)}%`} />
            <div style={{ width: `${availPct}%`, background: '#1e4080', transition: 'width 0.5s' }} title={`Available ${availPct.toFixed(0)}%`} />
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 6, fontSize: 10, color: '#64748b' }}>
            <span><span style={{ color: '#3b82f6' }}>■</span> Invested {investedPct.toFixed(0)}%</span>
            <span><span style={{ color: '#1e4080' }}>■</span> Available {availPct.toFixed(0)}%</span>
          </div>
        </div>
      </div>

      {/* Right: Monthly deposits */}
      <div style={card}>
        <SectionTitle>Monthly Deposits</SectionTitle>
        <p style={{ fontSize: 12, color: '#475569', margin: '0 0 16px' }}>
          $500 added automatically on the 1st of each month. All profits compound.
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {monthly.length === 0 && (
            <span style={{ color: '#334155', fontSize: 12 }}>No deposits recorded yet.</span>
          )}
          {monthly.slice(-6).reverse().map((d, i) => (
            <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '8px 12px', background: '#0f172a', borderRadius: 6, border: '1px solid #1e293b' }}>
              <span style={{ fontSize: 12, color: '#94a3b8' }}>{d.date}</span>
              <span style={{ fontSize: 12, color: '#22c55e', fontWeight: 600 }}>+${d.amount.toFixed(2)}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Mini equity curve — text representation */}
      {curve.length > 1 && (
        <div style={{ ...card, gridColumn: '1 / -1' }}>
          <SectionTitle>Equity Curve ({curve.length} data points)</SectionTitle>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 80, marginTop: 8 }}>
            {curve.slice(-60).map((point, i, arr) => {
              const min = Math.min(...arr.map(a => a.value));
              const max = Math.max(...arr.map(a => a.value));
              const range = max - min || 1;
              const heightPct = ((point.value - min) / range) * 100;
              const isUp = i > 0 ? point.value >= arr[i-1].value : true;
              return (
                <div
                  key={i}
                  title={`$${point.value.toFixed(2)} — ${new Date(point.date).toLocaleDateString()}`}
                  style={{
                    flex: 1, minWidth: 2,
                    height: `${Math.max(4, heightPct)}%`,
                    background: isUp ? '#22c55e' : '#f87171',
                    borderRadius: 1,
                    opacity: 0.7 + (i / arr.length) * 0.3,
                  }}
                />
              );
            })}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4, fontSize: 10, color: '#334155' }}>
            <span>{curve[0]?.date ? new Date(curve[0].date).toLocaleDateString() : ''}</span>
            <span style={{ color: '#94a3b8' }}>${(curve[curve.length-1]?.value || 0).toFixed(2)}</span>
            <span>{curve[curve.length-1]?.date ? new Date(curve[curve.length-1].date).toLocaleDateString() : ''}</span>
          </div>
        </div>
      )}
    </div>
  );
}

const card = {
  background: '#0f172a', border: '1px solid #1e293b',
  borderRadius: 8, padding: '20px',
};

function SectionTitle({ children }) {
  return <h3 style={{ margin: '0 0 16px', fontSize: 12, color: '#00d4ff', letterSpacing: 2, textTransform: 'uppercase' }}>{children}</h3>;
}

function Row({ label, value, large, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid #0f1f36' }}>
      <span style={{ fontSize: 12, color: '#64748b' }}>{label}</span>
      <span style={{ fontSize: large ? 18 : 13, color: color || '#e2e8f0', fontWeight: large ? 700 : 400 }}>{value}</span>
    </div>
  );
}

function Divider() {
  return <div style={{ height: 1, background: '#1e293b', margin: '12px 0' }} />;
}
