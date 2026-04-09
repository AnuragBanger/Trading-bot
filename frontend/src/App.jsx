import React, { useState, useEffect, useCallback } from 'react';
import Dashboard from './components/Dashboard';

const API_BASE = process.env.REACT_APP_API_URL || '';

function App() {
  const [dashData, setDashData] = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE}/api/dashboard`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setDashData(json.data);
      setLastRefresh(new Date());
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 60_000); // refresh every 60s
    return () => clearInterval(interval);
  }, [fetchDashboard]);

  const triggerCycle = async () => {
    try {
      const res  = await fetch(`${API_BASE}/api/scheduler/run`, { method: 'POST' });
      const json = await res.json();
      if (json.status === 'ok') {
        setTimeout(fetchDashboard, 3000); // re-fetch after short delay
      }
    } catch (err) {
      console.error('Manual cycle trigger failed', err);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0a0e1a', color: '#e2e8f0', fontFamily: "'JetBrains Mono', 'Fira Code', 'Courier New', monospace" }}>
      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', flexDirection: 'column', gap: 16 }}>
          <div style={{ width: 40, height: 40, border: '3px solid #1e3a5f', borderTop: '3px solid #00d4ff', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <span style={{ color: '#64748b', fontSize: 14 }}>Connecting to trading engine…</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}
      {error && !loading && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh', flexDirection: 'column', gap: 16 }}>
          <span style={{ color: '#f87171', fontSize: 16 }}>⚠ Connection Error: {error}</span>
          <button onClick={fetchDashboard} style={{ padding: '8px 20px', background: '#1e3a5f', color: '#00d4ff', border: '1px solid #00d4ff', borderRadius: 6, cursor: 'pointer', fontFamily: 'inherit' }}>
            Retry
          </button>
        </div>
      )}
      {!loading && !error && dashData && (
        <Dashboard
          data={dashData}
          lastRefresh={lastRefresh}
          onRefresh={fetchDashboard}
          onTriggerCycle={triggerCycle}
          apiBase={API_BASE}
        />
      )}
    </div>
  );
}

export default App;
