import React, { useState } from 'react';

const SIGNAL_COLORS = { buy: '#22c55e', hold: '#f59e0b', sell: '#f87171' };
const RISK_COLORS   = { low: '#22c55e', medium: '#f59e0b', high: '#f87171' };

export default function SignalFeed({ signals, apiBase }) {
  const [expanded, setExpanded] = useState(null);
  const sigs = [...(signals || [])].reverse(); // newest first

  if (sigs.length === 0) {
    return (
      <div style={{ ...card, textAlign: 'center', padding: 60 }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>📡</div>
        <div style={{ color: '#475569', fontSize: 14 }}>No signals yet</div>
        <div style={{ color: '#334155', fontSize: 12, marginTop: 8 }}>
          Signals are generated during market hours (9:30 AM – 4:00 PM ET)
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 12, color: '#00d4ff', letterSpacing: 2 }}>
          SIGNAL FEED ({sigs.length} signals)
        </h3>
        <div style={{ display: 'flex', gap: 12, fontSize: 11, color: '#475569' }}>
          <span style={{ color: SIGNAL_COLORS.buy }}>■ BUY</span>
          <span style={{ color: SIGNAL_COLORS.hold }}>■ HOLD</span>
          <span style={{ color: SIGNAL_COLORS.sell }}>■ SELL</span>
        </div>
      </div>

      {sigs.map((sig, i) => {
        const sigColor  = SIGNAL_COLORS[sig.signal]   || '#94a3b8';
        const riskColor = RISK_COLORS[sig.risk_level] || '#f59e0b';
        const isOpen    = expanded === i;

        return (
          <div key={i} style={{ ...card, cursor: 'pointer', transition: 'border-color 0.15s', borderColor: isOpen ? '#1e40af' : '#1e293b' }}
               onClick={() => setExpanded(isOpen ? null : i)}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {/* Signal badge */}
                <div style={{
                  padding: '4px 12px', borderRadius: 4,
                  background: `${sigColor}22`, border: `1px solid ${sigColor}`,
                  color: sigColor, fontSize: 12, fontWeight: 700, letterSpacing: 1,
                  minWidth: 48, textAlign: 'center',
                }}>
                  {sig.signal?.toUpperCase()}
                </div>
                <div>
                  <span style={{ fontSize: 15, fontWeight: 700, color: '#e2e8f0' }}>{sig.ticker}</span>
                  <span style={{ fontSize: 11, color: '#475569', marginLeft: 8 }}>{sig.type?.toUpperCase()}</span>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {/* Confidence */}
                <ConfidenceBadge confidence={sig.confidence} />
                {/* Risk */}
                <span style={{ fontSize: 11, padding: '3px 8px', background: `${riskColor}22`, color: riskColor, border: `1px solid ${riskColor}44`, borderRadius: 3 }}>
                  {sig.risk_level?.toUpperCase()}
                </span>
                <span style={{ fontSize: 11, color: '#334155' }}>{isOpen ? '▲' : '▼'}</span>
              </div>
            </div>

            {/* Expanded view */}
            {isOpen && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #1e293b' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, marginBottom: 16 }}>
                  <InfoBox label="Entry Zone" value={sig.entry_zone ? `$${sig.entry_zone.low?.toFixed(2)} – $${sig.entry_zone.high?.toFixed(2)}` : '—'} />
                  <InfoBox label="Take Profit 1" value={sig.take_profit?.target_1 ? `$${sig.take_profit.target_1?.toFixed(2)}` : '—'} color="#22c55e" />
                  <InfoBox label="Take Profit 2" value={sig.take_profit?.target_2 ? `$${sig.take_profit.target_2?.toFixed(2)}` : '—'} color="#4ade80" />
                  <InfoBox label="Stop Loss" value={sig.stop_loss ? `$${sig.stop_loss?.toFixed(2)}` : '—'} color="#f87171" />
                  <InfoBox label="Holding Period" value={sig.holding_period?.toUpperCase() || '—'} />
                  <InfoBox label="Position Size" value={sig.position_size_pct ? `${(sig.position_size_pct * 100).toFixed(0)}%` : '—'} />
                </div>

                {sig.rationale && (
                  <div style={{ padding: '10px 14px', background: '#0a0e1a', borderRadius: 6, border: '1px solid #1e293b', marginBottom: 12 }}>
                    <div style={{ fontSize: 10, color: '#475569', letterSpacing: 1, marginBottom: 6 }}>AI RATIONALE</div>
                    <p style={{ margin: 0, fontSize: 12, color: '#94a3b8', lineHeight: 1.6 }}>{sig.rationale}</p>
                  </div>
                )}

                {sig.key_signals?.length > 0 && (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {sig.key_signals.map(s => (
                      <span key={s} style={{ fontSize: 10, padding: '2px 8px', background: '#0f1f36', color: '#60a5fa', borderRadius: 3, border: '1px solid #1e293b' }}>
                        {s}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function ConfidenceBadge({ confidence }) {
  const c = confidence || 0;
  const color = c >= 80 ? '#22c55e' : c >= 70 ? '#f59e0b' : '#f87171';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 40, height: 6, background: '#1e293b', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${c}%`, height: '100%', background: color, transition: 'width 0.5s' }} />
      </div>
      <span style={{ fontSize: 11, color, fontWeight: 700 }}>{c}%</span>
    </div>
  );
}

function InfoBox({ label, value, color }) {
  return (
    <div style={{ background: '#0a0e1a', borderRadius: 6, padding: '8px 12px', border: '1px solid #1e293b' }}>
      <div style={{ fontSize: 10, color: '#475569', letterSpacing: 1, marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13, color: color || '#e2e8f0', fontWeight: 600 }}>{value}</div>
    </div>
  );
}

const card = {
  background: '#0f172a', border: '1px solid #1e293b',
  borderRadius: 8, padding: '16px 20px',
};
