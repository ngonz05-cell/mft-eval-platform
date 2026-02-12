import React, { useState } from 'react';
import { runEval, listRuns, deleteEval, getRunResults } from '../api';

function EvalList({ evals, isLoading, onRefresh }) {
  const [expandedEval, setExpandedEval] = useState(null);
  const [evalRuns, setEvalRuns] = useState({});
  const [runningEvals, setRunningEvals] = useState({});
  const [expandedRun, setExpandedRun] = useState(null);
  const [runDetails, setRunDetails] = useState({});
  const [deletingEvals, setDeletingEvals] = useState({});

  const getScoreColor = (score) => {
    if (score === null || score === undefined) return '';
    if (score >= 0.9) return 'good';
    if (score >= 0.8) return 'warning';
    return 'bad';
  };

  const getScoreEmoji = (score) => {
    if (score === null || score === undefined) return '';
    if (score >= 0.9) return '✓';
    if (score >= 0.8) return '⚠';
    return '✗';
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  const formatDuration = (ms) => {
    if (!ms) return '—';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const handleToggleExpand = async (evalItem) => {
    const evalId = evalItem.id;
    if (expandedEval === evalId) {
      setExpandedEval(null);
      return;
    }
    setExpandedEval(evalId);
    if (!evalRuns[evalId]) {
      try {
        const result = await listRuns(evalId);
        setEvalRuns(prev => ({ ...prev, [evalId]: result.runs || [] }));
      } catch (err) {
        console.error('Failed to fetch runs:', err);
        setEvalRuns(prev => ({ ...prev, [evalId]: [] }));
      }
    }
  };

  const handleRunEval = async (evalId) => {
    setRunningEvals(prev => ({ ...prev, [evalId]: true }));
    try {
      await runEval(evalId, 'manual');
      const result = await listRuns(evalId);
      setEvalRuns(prev => ({ ...prev, [evalId]: result.runs || [] }));
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Run failed:', err);
      alert(`Run failed: ${err.message}`);
    } finally {
      setRunningEvals(prev => ({ ...prev, [evalId]: false }));
    }
  };

  const handleDeleteEval = async (evalId) => {
    if (!window.confirm('Delete this eval and all its runs? This cannot be undone.')) return;
    setDeletingEvals(prev => ({ ...prev, [evalId]: true }));
    try {
      await deleteEval(evalId);
      if (onRefresh) onRefresh();
    } catch (err) {
      console.error('Delete failed:', err);
      alert(`Delete failed: ${err.message}`);
    } finally {
      setDeletingEvals(prev => ({ ...prev, [evalId]: false }));
    }
  };

  const handleToggleRunDetails = async (runId) => {
    if (expandedRun === runId) {
      setExpandedRun(null);
      return;
    }
    setExpandedRun(runId);
    if (!runDetails[runId]) {
      try {
        const result = await getRunResults(runId);
        setRunDetails(prev => ({ ...prev, [runId]: result }));
      } catch (err) {
        console.error('Failed to fetch run details:', err);
      }
    }
  };

  const getMetrics = (evalItem) => {
    let metrics = evalItem.metrics || evalItem.metrics_json;
    if (typeof metrics === 'string') {
      try { metrics = JSON.parse(metrics); } catch { metrics = []; }
    }
    return Array.isArray(metrics) ? metrics : [];
  };

  const getLastRun = (evalId) => {
    const runs = evalRuns[evalId] || [];
    return runs.find(r => r.status === 'completed') || runs[0] || null;
  };

  if (isLoading) {
    return (
      <div className="eval-list">
        <div className="eval-list-header"><h2>My Evaluations</h2></div>
        <div className="empty-state">
          <div className="empty-state-icon">⏳</div>
          <p>Loading evals...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="eval-list">
      <div className="eval-list-header">
        <h2>My Evaluations</h2>
        {onRefresh && (
          <button className="btn-secondary" onClick={onRefresh} style={{ padding: '6px 14px', fontSize: '13px' }}>
            🔄 Refresh
          </button>
        )}
      </div>

      {evals.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📋</div>
          <h3>No evaluations yet</h3>
          <p>Click <strong>+ Create New</strong> in the top bar to start building your first eval.</p>
        </div>
      ) : (
        <div className="eval-cards">
          {evals.map((evalItem) => {
            const isExpanded = expandedEval === evalItem.id;
            const metrics = getMetrics(evalItem);
            const runs = evalRuns[evalItem.id] || [];
            const isRunning = runningEvals[evalItem.id];
            const isDeleting = deletingEvals[evalItem.id];
            const lastScore = evalItem.primary_score || evalItem.lastScore;

            return (
              <div key={evalItem.id} className={`eval-card ${isExpanded ? 'expanded' : ''}`}>
                <div className="eval-card-header" onClick={() => handleToggleExpand(evalItem)}>
                  <div className="eval-card-main">
                    <div className="eval-card-title">
                      <strong>{evalItem.name}</strong>
                      <span className={`status-badge status-${evalItem.status}`}>{evalItem.status}</span>
                    </div>
                    <div className="eval-card-meta">
                      <span className="eval-meta-item">👥 {evalItem.team || '—'}</span>
                      <span className="eval-meta-item">📊 {metrics.length} metric{metrics.length !== 1 ? 's' : ''}</span>
                      <span className="eval-meta-item">📅 {formatDate(evalItem.created_at || evalItem.lastRun)}</span>
                    </div>
                  </div>
                  <div className="eval-card-score">
                    {lastScore != null ? (
                      <span className={`score-badge-lg ${getScoreColor(lastScore)}`}>
                        {getScoreEmoji(lastScore)} {(lastScore * 100).toFixed(1)}%
                      </span>
                    ) : (
                      <span className="score-badge-lg none">No runs</span>
                    )}
                    <span className="expand-arrow">{isExpanded ? '▲' : '▼'}</span>
                  </div>
                </div>

                {isExpanded && (
                  <div className="eval-card-body">
                    {/* Description */}
                    {evalItem.description && (
                      <div className="eval-detail-section">
                        <div className="eval-detail-label">Description</div>
                        <p className="eval-detail-text">{evalItem.description}</p>
                      </div>
                    )}

                    {/* Metrics summary */}
                    {metrics.length > 0 && (
                      <div className="eval-detail-section">
                        <div className="eval-detail-label">Configured Metrics</div>
                        <div className="eval-metrics-grid">
                          {metrics.map((m, i) => (
                            <div key={i} className="eval-metric-chip">
                              <span className="metric-chip-name">{m.field}</span>
                              <span className="metric-chip-range">
                                {m.baseline || m.thresholds?.baseline || '?'}% → {m.target || m.thresholds?.target || '?'}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="eval-detail-actions">
                      <button
                        className="btn-primary"
                        onClick={(e) => { e.stopPropagation(); handleRunEval(evalItem.id); }}
                        disabled={isRunning}
                        style={{ padding: '8px 16px', fontSize: '13px' }}
                      >
                        {isRunning ? '⏳ Running...' : '▶️ Run Eval'}
                      </button>
                      <button
                        className="btn-secondary btn-danger"
                        onClick={(e) => { e.stopPropagation(); handleDeleteEval(evalItem.id); }}
                        disabled={isDeleting}
                        style={{ padding: '8px 16px', fontSize: '13px' }}
                      >
                        {isDeleting ? '...' : '🗑️ Delete'}
                      </button>
                    </div>

                    {/* Run History */}
                    <div className="eval-detail-section">
                      <div className="eval-detail-label">Run History ({runs.length})</div>
                      {runs.length === 0 ? (
                        <p className="eval-detail-text" style={{ color: '#65676b' }}>No runs yet — click "Run Eval" to execute.</p>
                      ) : (
                        <div className="run-history">
                          {runs.map((run) => {
                            const isRunExpanded = expandedRun === run.id;
                            const details = runDetails[run.id];
                            const runMetrics = details?.metrics || run.metrics;
                            const parsedMetrics = typeof runMetrics === 'string' ? JSON.parse(runMetrics) : runMetrics;

                            return (
                              <div key={run.id} className={`run-row ${isRunExpanded ? 'expanded' : ''}`}>
                                <div className="run-row-header" onClick={() => handleToggleRunDetails(run.id)}>
                                  <div className="run-row-status">
                                    {run.status === 'completed' ? (
                                      run.passed_baseline ? '✅' : '❌'
                                    ) : run.status === 'running' ? '⏳' : run.status === 'failed' ? '💥' : '⏸️'}
                                  </div>
                                  <div className="run-row-info">
                                    <span className="run-id">Run {run.id.slice(0, 8)}</span>
                                    <span className="run-date">{formatDate(run.completed_at || run.created_at)}</span>
                                  </div>
                                  <div className="run-row-score">
                                    {run.status === 'completed' && run.primary_score != null ? (
                                      <span className={`score-badge ${getScoreColor(run.primary_score)}`}>
                                        {(run.primary_score * 100).toFixed(1)}%
                                      </span>
                                    ) : run.status === 'failed' ? (
                                      <span className="score-badge bad">Failed</span>
                                    ) : (
                                      <span style={{ color: '#65676b' }}>{run.status}</span>
                                    )}
                                  </div>
                                  <div className="run-row-stats">
                                    {run.num_examples != null && (
                                      <span>{run.num_passed}/{run.num_examples} passed</span>
                                    )}
                                    <span>{formatDuration(run.duration_ms)}</span>
                                  </div>
                                  <span className="expand-arrow-sm">{isRunExpanded ? '▲' : '▼'}</span>
                                </div>

                                {isRunExpanded && details && (
                                  <div className="run-details-panel">
                                    {/* Per-metric scores */}
                                    {parsedMetrics && typeof parsedMetrics === 'object' && (
                                      <div className="run-detail-metrics">
                                        <strong>Metric Scores:</strong>
                                        {Object.entries(parsedMetrics).map(([name, score]) => (
                                          <div key={name} className="run-metric-row">
                                            <span>{name}</span>
                                            <span className={`score-badge ${getScoreColor(score)}`}>
                                              {(score * 100).toFixed(1)}%
                                            </span>
                                          </div>
                                        ))}
                                      </div>
                                    )}

                                    {/* Failures */}
                                    {details.failures && details.failures.length > 0 && (
                                      <div className="run-detail-failures">
                                        <strong>Failures ({details.failures.length}):</strong>
                                        <div className="failures-list">
                                          {(typeof details.failures === 'string' ? JSON.parse(details.failures) : details.failures)
                                            .slice(0, 10)
                                            .map((f, i) => (
                                              <div key={i} className="failure-row">
                                                <span className="failure-id">{f.test_case_id || `#${i + 1}`}</span>
                                                <span className="failure-expected">Expected: <code>{String(f.expected).slice(0, 50)}</code></span>
                                                <span className="failure-actual">Got: <code>{String(f.actual).slice(0, 50)}</code></span>
                                              </div>
                                            ))}
                                        </div>
                                      </div>
                                    )}

                                    {/* Error message for failed runs */}
                                    {details.error_message && (
                                      <div className="run-error-message">
                                        <strong>Error:</strong> {details.error_message}
                                      </div>
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default EvalList;
