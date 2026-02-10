import React from 'react';

function Header({ view, onNavigate }) {
  return (
    <header className="header">
      <div className="header-logo">
        <h1>📊 MFT Eval Platform</h1>
        <span>Meta Fintech</span>
      </div>

      <nav className="header-nav">
        <button
          className={view === 'list' ? 'active' : ''}
          onClick={() => onNavigate('list')}
        >
          My Evals
        </button>
        <button
          className={view === 'create' ? 'active' : ''}
          onClick={() => onNavigate('create')}
        >
          + Create New
        </button>
      </nav>
    </header>
  );
}

export default Header;
