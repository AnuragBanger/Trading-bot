import React, { useState, useEffect } from 'react';

const EXAMPLE_THESES = [
  'AI chip shortage will drive semiconductor stocks higher in 2025',
  'Rising interest rates will benefit regional bank stocks',
  'Electric vehicle adoption will boost lithium mining companies',
];

export default function HypothesisResearch({ apiBase }) {
  const [thesis,    setThesis]    = useState('');
  const [result,    setResult]    = useState(null);
  const [loading,   setLoading]   = useState(false);
  const [error,     setError]     = useState(null);
  const [watchlist, setWatchlist] = useState([]);
  const [tab,       setTab]       = useState('research'); // 'research' | 'watchlist'

  const loadWatchlist = () => {
    fetch(`${apiBase}/api/hypothesis/watchlist`)
      .then(r => r.json())
      .then(j => setWatchlist(j.data || []))
      .catch(() => {});
  };

  useEffect(() => { loadWatchlist(); }, [apiBase]);

  const handleSubmit = async () => {
    if (!thesis.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res  = await fetch(`${apiBase}/api/hypothesis`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thesis: thesis.trim() }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.detail || `HTTP ${res.status}`);
      setResult(json.data);
      loadWatchlist(); // refresh watchlist after research
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Tab header ───────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 2, borderBottom: '1px solid #1e293b' }}>
        {[['research', 'RESEARCH A THESIS'], ['watchlist', `WATCHLIST (${watchlist.length})`]].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)} style={{
            padding: '8px 18px', background: tab === id ? '#0f172a' : 'transparent',
            color: tab === id ? '#00d4ff' : '#475569',
            border: 'none', borderBottom: tab === id ? '2px solid #00d4ff' : '2px solid transparent',
            cursor: 'pointer', fontSize: 11, letterSpacing: 2, fontFamily: 'inherit',
          }}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'research' && (
        <>
          {/* ── Thesis input ─────────────────────────────────────────────────── */}
          <div style={card}>
            <SectionTitle>Submit a Market Thesis</SectionTitle>
            <p style={{ fontSize: 12, color: '#64748b', margin: '0 0 14px', lineHeight: 1.6 }}>
              Describe a market trend or macro thesis. Claude will identify relevant tickers,
              research recent news, and score confidence for each one. High-confidence tickers
              (≥ 70) are added to the watchlist for priority in the next discovery cycle.
            </p>

            <textarea
              value={thesis}
              onChange={e => setThesis(e.target.value)}
              placeholder="e.g. AI chip shortage will drive semiconductor stocks higher in 2025"
              rows={3}
              maxLength={1000}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: '#0a0e1a', border: '1px solid #1e293b',
                borderRadius: 6, padding: '10px 12px',
                color: '#e2e8f0', fontSize: 13, fontFamily: 'inherit',
                resize: 'vertical', outline: 'none',
                lineHeight: 1.6,
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
              <span style={{ fontSize: 10, color: '#334155' }}>{thesis.length} / 1000 characters</span>
              <button
                onClick={handleSubmit}
                disabled={loading || !thesis.trim()}
                style={{
                  padding: '8px 20px',
                  background: loading || !thesis.trim() ? '#1e293b' : '#0c1e40',
                  color: loading || !thesis.trim() ? '#475569' : '#00d4ff',
                  border: `1px solid ${loading || !thesis.trim() ? '#1e293b' : '#00d4ff'}`,
                  borderRadius: 4, cursor: loading || !thesis.trim() ? 'default' : 'pointer',
                  fontSize: 11, letterSpacing: 1, fontFamily: 'inherit',
                }}
              >
                {loading ? '⟳ RESEARCHING…' : '▶ RESEARCH THESIS'}
              </button>
            </div>

            {/* Example theses */}
            <div style={{ marginTop: 14 }}>
              <div style={{ fontSize: 10, color: '#334155', letterSpacing: 1, marginBottom: 6 }}>EXAMPLES:</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {EXAMPLE_THESES.map((ex, i) => (
                  <button key={i} onClick={() => setThesis(ex)} style={{
                    padding: '4px 10px', background: '#0a0e1a', border: '1px solid #1e293b',
                    borderRadius: 4, color: '#64748b', fontSize: 11, cursor: 'pointer',
                    fontFamily: 'inherit', textAlign: 'left',
                  }}>
                    {ex}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* ── Error ────────────────────────────────────────────────────────── */}
          {error && (
            <div style={{ ...card, border: '1px solid #f8717155', background: '#2a0a0a' }}>
              <span style={{ color: '#f87171', fontSize: 13 }}>⚠ {error}</span>
            </div>
          )}

          {/* ── Loading state ─────────────────────────────────────────────────── */}
          {loading && (
            <div style={{ ...card, textAlign: 'center', padding: '40px 20px' }}>
              <div style={{ fontSize: 36, marginBottom: 12 }}>🔍</div>
              <div style={{ color: '#00d4ff', fontSize: 14, marginBottom: 8 }}>Researching your thesis…</div>
              <p style={{ color: '#64748b', fontSize: 12, margin: 0 }}>
                Claude is identifying relevant tickers, fetching recent headlines, and scoring conviction.
                This usually takes 15–30 seconds.
              </p>
            </div>
          )}

          {/* ── Results ──────────────────────────────────────────────────────── */}
          {result && !loading && (
            <>
              {/* Overall confidence */}
              <div style={{
                ...card,
                border: `1px solid ${confidenceColor(result.overall_confidence)}44`,
                background: '#0a0e1a',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <SectionTitle>Thesis Assessment</SectionTitle>
                    <p style={{ fontSize: 13, color: '#94a3b8', margin: '0 0 10px', lineHeight: 1.7 }}>
                      "{result.thesis}"
                    </p>
                    <p style={{ fontSize: 12, color: '#e2e8f0', margin: 0, lineHeight: 1.7 }}>
                      {result.thesis_summary}
                    </p>
                  </div>
                  <ConfidenceBadge value={result.overall_confidence} label="OVERALL CONFIDENCE" large />
                </div>

                {result.watchlist_added?.length > 0 && (
                  <div style={{
                    marginTop: 14, padding: '10px 14px',
                    background: '#0f2a1a', border: '1px solid #22c55e44', borderRadius: 6,
                  }}>
                    <span style={{ fontSize: 12, color: '#22c55e' }}>
                      ✓ Added to watchlist: {result.watchlist_added.join(', ')}
                    </span>
                  </div>
                )}
              </div>

              {/* Ticker cards */}
              {result.tickers?.length > 0 && (
                <div style={card}>
                  <SectionTitle>Recommended Tickers ({result.tickers.length})</SectionTitle>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 8 }}>
                    {[...result.tickers]
                      .sort((a, b) => b.confidence - a.confidence)
                      .map((t, i) => (
                        <TickerCard key={i} ticker={t} watchlistAdded={result.watchlist_added?.includes(t.ticker)} />
                      ))}
                  </div>
                </div>
              )}
            </>
          )}
        </>
      )}

      {tab === 'watchlist' && (
        <WatchlistPanel watchlist={watchlist} onRefresh={loadWatchlist} />
      )}
    </div>
  );
}

/* ── Sub-components ──────────────────────────────────────────────────────── */

function TickerCard({ ticker: t, watchlistAdded }) {
  const color = confidenceColor(t.confidence);
  return (
    <div style={{
      background: '#0a0e1a', border: `1px solid ${color}33`,
      borderRadius: 8, padding: '14px 16px',
      display: 'grid', gridTemplateColumns: '80px 1fr auto', gap: 16, alignItems: 'start',
    }}>
      <div>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#e2e8f0' }}>{t.ticker}</div>
        {watchlistAdded && (
          <div style={{ fontSize: 10, color: '#22c55e', marginTop: 4 }}>★ watchlisted</div>
        )}
      </div>
      <div>
        <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 6px', lineHeight: 1.6 }}>{t.rationale}</p>
        {t.risk && (
          <p style={{ fontSize: 11, color: '#f59e0b', margin: 0 }}>⚠ Risk: {t.risk}</p>
        )}
      </div>
      <ConfidenceBadge value={t.confidence} />
    </div>
  );
}

function ConfidenceBadge({ value, label, large }) {
  const color = confidenceColor(value);
  return (
    <div style={{ textAlign: 'center', minWidth: large ? 110 : 80 }}>
      {label && <div style={{ fontSize: 10, color: '#475569', letterSpacing: 1, marginBottom: 6 }}>{label}</div>}
      <div style={{
        fontSize: large ? 32 : 22, fontWeight: 700, color,
        padding: large ? '10px 14px' : '6px 10px',
        background: `${color}11`, border: `1px solid ${color}44`, borderRadius: 8,
      }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: '#475569', marginTop: 4 }}>/ 100</div>
    </div>
  );
}

function WatchlistPanel({ watchlist, onRefresh }) {
  return (
    <div style={card}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <SectionTitle>Hypothesis Watchlist</SectionTitle>
        <button onClick={onRefresh} style={{
          padding: '4px 12px', background: '#1e293b', color: '#94a3b8',
          border: '1px solid #1e293b', borderRadius: 4, cursor: 'pointer',
          fontSize: 10, letterSpacing: 1, fontFamily: 'inherit',
        }}>REFRESH</button>
      </div>

      {watchlist.length === 0 ? (
        <p style={{ color: '#334155', fontSize: 12, textAlign: 'center', padding: '30px 0' }}>
          No tickers on the watchlist yet. Research a thesis to add tickers.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {watchlist.map((w, i) => (
            <div key={i} style={{
              background: '#0a0e1a', border: '1px solid #1e293b', borderRadius: 6,
              padding: '12px 16px', display: 'grid',
              gridTemplateColumns: '70px 1fr 70px 120px', gap: 12, alignItems: 'center',
            }}>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#e2e8f0' }}>{w.ticker}</div>
              <div>
                <p style={{ fontSize: 11, color: '#64748b', margin: 0, lineHeight: 1.5 }}>{w.thesis}</p>
              </div>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 10, color: '#475569', marginBottom: 3 }}>CONFIDENCE</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: confidenceColor(w.confidence) }}>{w.confidence}</div>
              </div>
              <div style={{ textAlign: 'right', fontSize: 10, color: '#334155' }}>
                {w.added_at ? new Date(w.added_at).toLocaleDateString() : ''}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SectionTitle({ children }) {
  return <h3 style={{ margin: '0 0 4px', fontSize: 12, color: '#00d4ff', letterSpacing: 2, textTransform: 'uppercase' }}>{children}</h3>;
}

function confidenceColor(v) {
  if (v >= 80) return '#22c55e';
  if (v >= 70) return '#4ade80';
  if (v >= 50) return '#f59e0b';
  return '#f87171';
}

const card = {
  background: '#0f172a', border: '1px solid #1e293b',
  borderRadius: 8, padding: '20px',
};
