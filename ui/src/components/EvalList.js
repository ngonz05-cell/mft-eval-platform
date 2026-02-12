import React from 'react';

function EvalList({ evals }) {
  const getScoreColor = (score) => {
    if (score === null) return '';
    if (score >= 0.9) return 'good';
    if (score >= 0.8) return 'warning';
    return 'bad';
  };

  return (
    <div className="eval-list">
      <div className="eval-list-header">
        <h2>Your Evaluations</h2>
      </div>

      {evals.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <h3>No evaluations yet</h3>
          <p>Click <strong>+ Create New</strong> in the top bar to start building your first eval.</p>
        </div>
      ) : (
        <table className="eval-table">
          <thead>
            <tr>
              <th>Eval Name</th>
              <th>Team</th>
              <th>Status</th>
              <th>Last Score</th>
              <th>Last Run</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {evals.map((eval_item) => (
              <tr key={eval_item.id}>
                <td>
                  <strong>{eval_item.name}</strong>
                </td>
                <td>{eval_item.team}</td>
                <td>
                  <span className={`status-badge status-${eval_item.status}`}>
                    {eval_item.status}
                  </span>
                </td>
                <td>
                  {eval_item.lastScore !== null ? (
                    <span className={`score-badge ${getScoreColor(eval_item.lastScore)}`}>
                      {eval_item.lastScore >= 0.9 ? '✓' : eval_item.lastScore >= 0.8 ? '⚠' : '✗'}
                      {' '}
                      {(eval_item.lastScore * 100).toFixed(1)}%
                    </span>
                  ) : (
                    <span style={{ color: '#65676b' }}>—</span>
                  )}
                </td>
                <td>{eval_item.lastRun || '—'}</td>
                <td>
                  <button className="btn-secondary" style={{ padding: '6px 12px', fontSize: '13px' }}>
                    View Details
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default EvalList;
