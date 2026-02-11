import React, { useState } from 'react';
import EvalWizard from './components/EvalWizard';
import EvalList from './components/EvalList';
import Header from './components/Header';
import LandingPage from './components/LandingPage';
import GuidedEval from './components/GuidedEval';
import './App.css';

function App() {
  const [view, setView] = useState('list'); // 'list', 'landing', 'create', 'guided'
  const [evals, setEvals] = useState([
    {
      id: 1,
      name: 'payment_metadata_extraction',
      team: 'Payments Platform',
      status: 'active',
      lastScore: 0.92,
      lastRun: '2024-01-15',
    },
    {
      id: 2,
      name: 'fraud_detection_classifier',
      team: 'Risk & Compliance',
      status: 'active',
      lastScore: 0.88,
      lastRun: '2024-01-14',
    },
  ]);

  const handleCreateEval = (evalConfig) => {
    const newEval = {
      id: evals.length + 1,
      name: evalConfig.name,
      team: evalConfig.team,
      status: 'draft',
      lastScore: null,
      lastRun: null,
    };
    setEvals([...evals, newEval]);
    setView('list');
  };

  const renderView = () => {
    switch (view) {
      case 'landing':
        return (
          <LandingPage
            onSelectGuided={() => setView('guided')}
            onSelectExpert={() => setView('create')}
          />
        );
      case 'guided':
        return (
          <GuidedEval
            onComplete={handleCreateEval}
            onCancel={() => setView('list')}
          />
        );
      case 'create':
        return (
          <EvalWizard
            onComplete={handleCreateEval}
            onCancel={() => setView('list')}
          />
        );
      case 'list':
      default:
        return (
          <EvalList
            evals={evals}
            onCreateNew={() => setView('landing')}
          />
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
