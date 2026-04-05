import React, { useState, useEffect } from 'react';

export default function RefinementLog({ apiBase }) {
  const [logData, setLogData]   = useState(null);
  const [expanded, setExpanded] = useState(0);

  useEffect(() => {
    fetch(`${apiBase}/api/refinement/log`)
      .then(r => r.json())
      .then(j => setLogData(j.data))
      .catch(() => {});
  }, [apiBase]);

  if (!logData) return <div style={{ color: '#475569', padding: 40, textAlign: 'center' }}>Loading refinement history…</div>;

  const refinements = [...(logData.refinements || [])].reverse();

  if (refinements.length === 0) {
    return (
      <div style={{ ...card, textAlign: 'center', padding: 60 }}>
        <div style={{ fontSize: 40, marginBottom: 12 }}>🧠</div>
        <div style={{ color: '#475569', fontSize: 14 }}>No refinements yet</div>
        <div style={{ color: '#334155', fontSize: 12, marginTop: 8 }}>
          Refinement triggers every 20 closed trades. The bot will self-improve as it learns.
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0, fontSize: 12, color: '#00d4ff', letterSpacing: 2 }}>
          PARAMETER REFINEMENT HISTORY ({logData.total_refinements} cycles)
        </h3>
      </div>

      {refinements.map((r, i) => {
        const isOpen = expanded === i;
        return (
          <div key={i} style={{ ...card, cursor: 'pointer', borderColor: isOpen ? '#1e40af' : '#1e293b' }}
               onClick={() => setExpanded(isOpen ? -1 : i)}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{ width: 32, height: 32, background: '#1e3a5f', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700, color: '#00d4ff' }}>
                  #{r.refinement_number}
                </div>
                <div>
                  <div style={{ fontSize: 13, color: '#e2e8f0' }}>
                    Refinement #{r.refinement_number}
                    <span style={{ fontSize: 11, color: '#475569', marginLeft: 10 }}>{r.trades_analyzed} trades analyzed</span>
                  </div>
                  <div style={{ fontSize: 11, color: '#334155', marginTop: 2 }}>
                    {r.timestamp ? new Date(r.timestamp).toLocaleString() : ''}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {r.stats_at_refinement && (
                  <div style={{ textAlign: 'right', fontSize: 11 }}>
                    <div style={{ color: (r.stats_at_refinement.win_rate || 0) >= 60 ? '#22c55e' : '#f59e0b' }}>
                      {r.stats_at_refinement.win_rate?.toFixed(1)}% WR
                    </div>
                    <div style={{ color: '#334155' }}>{r.stats_at_refinement.total_trades} trades</div>
                  </div>
                )}
                <span style={{ color: '#334155', fontSize: 11 }}>{isOpen ? '▲' : '▼'}</span>
              </div>
            </div>

            {isOpen && (
              <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid #1e293b' }}>
                {/* Reasoning */}
                {r.reasoning && (
                  <div style={{ padding: '12px 14px', background: '#0a0e1a', borderRadius: 6, border: '1px solid #1e293b', marginBottom: 16 }}>
                    <div style={{ fontSize: 10, color: '#475569', letterSpacing: 1, marginBottom: 8 }}>CLAUDE'S REASONING</div>
                    <p style={{ margin: 0, fontSize: 12, color: '#94a3b8', lineHeight: 1.7 }}>{r.reasoning}</p>
                  </div>
                )}

                {/* Before/After weights */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <WeightTable title="BEFORE" weights={r.before?.indicator_weights} thresholds={r.before?.thresholds} />
                  <WeightTable title="AFTER"  weights={r.after?.indicator_weights}  thresholds={r.after?.thresholds} highlight />
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function WeightTable({ title, weights, thresholds, highlight }) {
  const borderColor = highlight ? '#1e40af' : '#1e293b';
  return (
    <div style={{ background: '#0a0e1a', border: `1px solid ${borderColor}`, borderRadius: 6, padding: '12px 14px' }}>
      <div style={{ fontSize: 10, color: highlight ? '#00d4ff' : '#475569', letterSpacing: 2, marginBottom: 10 }}>{title}</div>
      {weights && Object.entries(weights).map(([key, val]) => (
        <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: '1px solid #0f172a' }}>
          <span style={{ fontSize: 11, color: '#64748b' }}>{key}</span>
          <span style={{ fontSize: 11, color: highlight ? '#60a5fa' : '#475569', fontWeight: highlight ? 600 : 400 }}>
            {(val * 100).toFixed(1)}%
          </span>
        </div>
      ))}
      {thresholds && (
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid #1e293b' }}>
          {Object.entries(thresholds).map(([key, val]) => (
            val != null && (
              <div key={key} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
                <span style={{ fontSize: 10, color: '#334155' }}>{key}</span>
                <span style={{ fontSize: 10, color: highlight ? '#94a3b8' : '#334155' }}>{val}</span>
              </div>
            )
          ))}
        </div>
      )}
    </div>
  );
}

const card = {
  background: '#0f172a', border: '1px solid #1e293b',
  borderRadius: 8, padding: '16px 20px',
};
