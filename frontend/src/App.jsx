import React, { useState, useEffect, useCallback, useRef } from 'react';
import Dashboard from './components/Dashboard';

const API_BASE = process.env.REACT_APP_API_URL || '';

function App() {
  const [dashData,    setDashData]    = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [cycleRunning, setCycleRunning] = useState(false);
  const [activeTab,   setActiveTab]   = useState('overview');

  // Track whether we're actively in a forced run so we can poll faster
  const pollingRef = useRef(null);

  const fetchDashboard = useCallback(async () => {
    try {
      const res  = await fetch(`${API_BASE}/api/dashboard`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setDashData(json.data);
      setLastRefresh(new Date());
      setError(null);
      // Sync running state from backend (in case another client triggered a cycle)
      if (json.data?.is_running !== undefined) {
        setCycleRunning(json.data.is_running);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Dynamic polling: every 3s while running, every 60s at rest
  useEffect(() => {
    const interval = cycleRunning ? 3_000 : 60_000;
    clearInterval(pollingRef.current);
    pollingRef.current = setInterval(fetchDashboard, interval);
    return () => clearInterval(pollingRef.current);
  }, [cycleRunning, fetchDashboard]);

  // Initial load
  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  const triggerCycle = async () => {
    if (cycleRunning) return;
    setCycleRunning(true);
    setActiveTab('logs'); // auto-open live log so user can watch progress

    try {
      const res  = await fetch(`${API_BASE}/api/scheduler/run?force=true`, { method: 'POST' });
      const json = await res.json();
      if (json.status === 'ok') {
        // Cycle finished — refresh dashboard immediately
        await fetchDashboard();
        // If signals were generated, jump to signals tab
        if (json.data?.signals_generated?.length > 0) {
          setActiveTab('signals');
        }
      }
    } catch (err) {
      console.error('Manual cycle trigger failed', err);
    } finally {
      setCycleRunning(false);
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
          cycleRunning={cycleRunning}
          onRefresh={fetchDashboard}
          onTriggerCycle={triggerCycle}
          apiBase={API_BASE}
          activeTab={activeTab}
          setActiveTab={setActiveTab}
        />
      )}
    </div>
  );
}

export default App;
