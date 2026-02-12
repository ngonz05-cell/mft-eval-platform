import React, { useState, useEffect, useCallback } from 'react';
import EvalList from './components/EvalList';
import Header from './components/Header';
import GuidedEval from './components/GuidedEval';
import { createEval, listEvals } from './api';
import './App.css';

const DEMO_EVALS = [
  {
    id: 'demo-1',
    name: 'payment_metadata_extraction',
    description: 'Evaluates extraction of payment metadata (amount, merchant, timestamp, payment method) from transaction records across 12 markets.',
    team: 'Payments Platform',
    status: 'active',
    lastScore: 0.92,
    lastRun: '2024-01-15',
    metrics: [
      { field: 'Field Accuracy', measurement: ['exact_match_ratio'], baseline: 85, target: 95 },
      { field: 'Completeness', measurement: ['field_f1'], baseline: 80, target: 92 },
      { field: 'Format Compliance', measurement: ['simple_pass_fail'], baseline: 90, target: 98 },
    ],
  },
  {
    id: 'demo-2',
    name: 'fraud_detection_classifier',
    description: 'Classifies transactions as legitimate, suspicious, or fraudulent based on user behavior patterns and transaction signals.',
    team: 'Risk & Compliance',
    status: 'active',
    lastScore: 0.88,
    lastRun: '2024-01-14',
    metrics: [
      { field: 'Classification F1', measurement: ['classification_f1'], baseline: 85, target: 93 },
      { field: 'False Positive Rate', measurement: ['numeric_tolerance'], baseline: 90, target: 97 },
    ],
  },
  {
    id: 'demo-3',
    name: 'payment_dispute_chatbot_eval',
    description: 'Payment dispute chatbot for Meta Pay. Classifies dispute type, matches transaction ID, provides recommended actions, and generates case summary.',
    team: 'MFT Payments',
    status: 'active',
    lastScore: null,
    lastRun: '2026-02-12',
    metrics: [
      { field: 'Dispute Classification Accuracy', measurement: ['classification_f1'], baseline: 85, target: 92 },
      { field: 'Transaction Match Rate', measurement: ['exact_match_ratio'], baseline: 95, target: 98 },
      { field: 'Recommended Actions Quality', measurement: ['llm_judge'], baseline: 80, target: 90 },
    ],
  },
];

function App() {
  const [view, setView] = useState('list');
  const [evals, setEvals] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [demoMode, setDemoMode] = useState(false);

  const fetchEvals = useCallback(async () => {
    try {
      setIsLoading(true);
      const result = await listEvals();
      setEvals(result.evals || []);
      setDemoMode(false);
    } catch (err) {
      console.warn('Backend not available — entering demo mode:', err.message);
      setEvals(DEMO_EVALS);
      setDemoMode(true);
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
          <EvalList evals={evals} isLoading={isLoading} onRefresh={fetchEvals} demoMode={demoMode} />
        );
    }
  };

  return (
    <div className="app">
      <Header
        view={view}
        onNavigate={setView}
      />

      {demoMode && (
        <div className="demo-banner">
          <span className="demo-banner-icon">🎭</span>
          <span className="demo-banner-text">
            <strong>Demo Mode</strong> — Backend API is not connected. You're viewing sample data.
            To enable full functionality, run the API server locally.
            See <a href="https://github.com/ngonz05-cell/mft-eval-platform#readme" target="_blank" rel="noopener noreferrer">README</a> for setup instructions.
          </span>
        </div>
      )}

      <main className="main-content">
        {renderView()}
      </main>
    </div>
  );
}

export default App;
