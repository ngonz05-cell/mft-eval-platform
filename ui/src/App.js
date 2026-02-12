import React, { useState, useEffect, useCallback } from 'react';
import EvalList from './components/EvalList';
import Header from './components/Header';
import GuidedEval from './components/GuidedEval';
import { createEval, listEvals } from './api';
import './App.css';

function App() {
  const [view, setView] = useState('list');
  const [evals, setEvals] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const fetchEvals = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await listEvals();
      setEvals(result.evals || []);
    } catch (err) {
      console.warn('Could not fetch evals from API, using defaults:', err.message);
      setEvals([
        {
          id: '1',
          name: 'payment_metadata_extraction',
          team: 'Payments Platform',
          status: 'active',
          lastScore: 0.92,
          lastRun: '2024-01-15',
        },
        {
          id: '2',
          name: 'fraud_detection_classifier',
          team: 'Risk & Compliance',
          status: 'active',
          lastScore: 0.88,
          lastRun: '2024-01-14',
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvals();
  }, [fetchEvals]);

  const handleCreateEval = async (evalConfig) => {
    try {
      await createEval(evalConfig);
      await fetchEvals();
    } catch (err) {
      console.error('Failed to create eval:', err);
      const fallbackEval = {
        id: String(Date.now()),
        name: evalConfig.evalName || evalConfig.name || 'New Eval',
        team: evalConfig.team || '',
        status: 'draft',
        lastScore: null,
        lastRun: null,
      };
      setEvals(prev => [...prev, fallbackEval]);
    }
    setView('list');
  };

  const renderView = () => {
    switch (view) {
      case 'guided':
        return (
          <GuidedEval
            onComplete={handleCreateEval}
            onCancel={() => setView('list')}
          />
        );
      case 'list':
      default:
        return (
          <EvalList evals={evals} isLoading={isLoading} onRefresh={fetchEvals} />
        );
    }
  };

  return (
    <div className="app">
      <Header
        view={view}
        onNavigate={setView}
      />

      <main className="main-content">
        {renderView()}
      </main>
    </div>
  );
}

export default App;
