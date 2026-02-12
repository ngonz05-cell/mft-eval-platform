import React from 'react';

function Header({ view, onNavigate }) {
  return (
    <header className="header">
      <div className="header-logo">
        <h1>📊 MFT Eval Platform</h1>
      </div>

      <nav className="header-nav">
        <button
          className={view === 'list' ? 'active' : ''}
          onClick={() => onNavigate('list')}
        >
          My Evals
        </button>
        <button
          className={['guided'].includes(view) ? 'active' : ''}
          onClick={() => onNavigate('guided')}
        >
          + Create New
        </button>
      </nav>
    </header>
  );
}

export default Header;
