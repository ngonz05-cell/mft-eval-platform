import React from 'react';

const MEASUREMENT_OPTIONS = [
  { id: 'exact_match_ratio', name: 'Exact Match Ratio' },
  { id: 'simple_pass_fail', name: 'Simple Pass/Fail' },
  { id: 'weighted_composite', name: 'Weighted Composite' },
  { id: 'contains_check', name: 'Contains Check' },
  { id: 'numeric_tolerance', name: 'Numeric match (w/tolerance)' },
  { id: 'fuzzy_string_match', name: 'Fuzzy String match' },
  { id: 'classification_f1', name: 'Classification (F1 score)' },
  { id: 'llm_judge', name: 'LLM-as-judge' },
];

// Team and Sub-team configuration (must match StepBasics.js)
const TEAMS = [
  { id: 'b2b', name: 'B2B' },
  { id: 'dcp', name: 'DCP' },
  { id: 'financial_integrity', name: 'Financial Integrity' },
  { id: 'platform', name: 'Platform' },
];

const SUB_TEAMS = {
  platform: [
    { id: 'checkout', name: 'Checkout' },
    { id: 'payments_engine', name: 'Payments Engine' },
    { id: 'business_services', name: 'Business Services' },
    { id: 'fit', name: 'FIT' },
  ],
};

// Helper to get display name for team
const getTeamDisplayName = (config) => {
  if (config.team === '__custom__' && config.customTeam) {
    return `${config.customTeam} (custom)`;
  }
  const team = TEAMS.find(t => t.id === config.team);
  return team ? team.name : config.team || '';
};

// Helper to get display name for sub-team
const getSubTeamDisplayName = (config) => {
  if (config.subTeam === '__custom__' && config.customSubTeam) {
    return `${config.customSubTeam} (custom)`;
  }
  const subTeams = SUB_TEAMS[config.team] || [];
  const subTeam = subTeams.find(st => st.id === config.subTeam);
  return subTeam ? subTeam.name : '';
};

// Helper to get measurement names
const getMeasurementNames = (measurementIds) => {
  return (measurementIds || [])
    .map(id => MEASUREMENT_OPTIONS.find(m => m.id === id)?.name || id)
    .join(', ');
};

function StepReview({ config }) {
  const metrics = config.metrics || [];

  const generateYAML = () => {
    const metricsYaml = metrics.map(m => {
      const measurements = (m.measurement || []).map(mid =>
        MEASUREMENT_OPTIONS.find(mo => mo.id === mid)?.name || mid
      );
      return `    - field: "${m.field}"
      measurements: [${measurements.map(n => `"${n}"`).join(', ')}]
      description: "${m.description || ''}"`;
    }).join('\n');

    const thresholdsYaml = Object.entries(config.metricThresholds || {}).map(([key, val]) => {
      return `    ${key}:
      baseline: ${val.baseline || config.baselineThreshold}
      target: ${val.target || config.targetThreshold}${val.tolerance ? `\n      tolerance: "${val.tolerance}"` : ''}${val.weight ? `\n      weight: ${val.weight}` : ''}${val.minSimilarity ? `\n      min_similarity: ${val.minSimilarity}` : ''}`;
    }).join('\n');

    return `name: ${config.name || 'untitled_eval'}
version: "1.0.0"
team: ${getTeamDisplayName(config) || 'unassigned'}
${getSubTeamDisplayName(config) ? `sub_team: ${getSubTeamDisplayName(config)}` : ''}
owner: "${config.owner?.name || ''}" # @${config.owner?.username || ''}

description: |
  ${config.description || 'No description provided'}

what_it_measures: "${config.capabilityWhat || ''}"
why_it_matters: "${config.capabilityWhy || ''}"

metrics:
${metricsYaml || '    # No metrics defined'}

dataset:
  source: ${config.datasetSource === 'csv'
    ? `csv://${config.datasetFile?.name || 'uploaded_file.csv'}`
    : config.datasetUrl || 'not_specified'}
  size: ${config.datasetSize || 50}

thresholds:
  defaults:
    baseline: ${config.baselineThreshold}
    target: ${config.targetThreshold}
  per_metric:
${thresholdsYaml || '    # Using defaults for all metrics'}
  blocking: ${config.blocking}

automation:
  schedule: "${config.schedule}"
  alert_on_regression: ${config.alertOnRegression}
  ${config.alertChannel ? `alert_channel: "${config.alertChannel}"` : ''}

status: draft`;
  };

  const isComplete = (field) => {
    switch (field) {
      case 'name': return !!config.name;
      case 'team': return !!config.team;
      case 'metrics': return metrics.length > 0 && metrics.every(m => m.measurement && m.measurement.length > 0);
      case 'dataset': return config.datasetFile || config.datasetUrl;
      case 'thresholds': return config.baselineThreshold > 0;
      case 'owner': return !!config.owner;
      default: return false;
    }
  };

  const checklist = [
    { id: 'name', label: 'Eval Name', description: 'A unique identifier for this evaluation' },
    { id: 'metrics', label: 'Metrics Defined', description: 'What fields/metrics are being evaluated?' },
    { id: 'thresholds', label: 'Thresholds Set', description: 'What score is acceptable to ship?' },
    { id: 'dataset', label: 'Example Data Configured', description: 'Where do the test cases come from?' },
    { id: 'owner', label: 'Owner Assigned', description: 'Who maintains this eval?' },
  ];

  const allComplete = checklist.every(item => isComplete(item.id));

  return (
    <div className="step-review">
      <div className={`info-box ${allComplete ? 'success' : 'warning'}`}>
        <h4>{allComplete ? '✅ Ready to Create!' : '⚠️ Almost There!'}</h4>
        <p>
          {allComplete
            ? 'Your eval configuration looks complete. Review the details below and create your eval.'
            : 'Please complete all required fields before creating your eval.'
          }
        </p>
      </div>

      {/* Validation Checklist */}
      <div className="review-section">
        <h3>Validation Checklist</h3>
        <ul className="checklist">
          {checklist.map(item => (
            <li key={item.id} className="checklist-item">
              <div className={`checklist-check ${isComplete(item.id) ? 'complete' : 'incomplete'}`}>
                {isComplete(item.id) ? '✓' : '○'}
              </div>
              <div className="checklist-content">
                <h4>{item.label}</h4>
                <p>{item.description}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Configuration Summary */}
      <div className="review-section">
        <h3>Configuration Summary</h3>

        <div className="review-item">
          <span className="label">Eval Name</span>
          <span className="value">{config.name || '—'}</span>
        </div>

        <div className="review-item">
          <span className="label">Team</span>
          <span className="value">
            {getTeamDisplayName(config) || '—'}
            {getSubTeamDisplayName(config) && (
              <span style={{ color: '#65676b' }}> → {getSubTeamDisplayName(config)}</span>
            )}
          </span>
        </div>

        <div className="review-item">
          <span className="label">What it measures</span>
          <span className="value">{config.capabilityWhat || '—'}</span>
        </div>

        {/* Metrics Table */}
        {metrics.length > 0 && (
          <div className="review-item" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
            <span className="label" style={{ marginBottom: '8px' }}>Metrics</span>
            <table className="metrics-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Measurement</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((m, i) => (
                  <tr key={i}>
                    <td><strong>{m.field}</strong></td>
                    <td>{getMeasurementNames(m.measurement) || '—'}</td>
                    <td>{m.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="review-item">
          <span className="label">Example Data</span>
          <span className="value">
            {config.datasetSource === 'csv' && config.datasetFile
              ? `CSV: ${config.datasetFile.name}`
              : config.datasetUrl || '—'}
            {config.datasetSize && ` (${config.datasetSize} examples)`}
          </span>
        </div>

        <div className="review-item">
          <span className="label">Baseline / Target</span>
          <span className="value">
            <span style={{ color: '#ffc107' }}>⚠️ {config.baselineThreshold}%</span>
            {' → '}
            <span style={{ color: '#28a745' }}>✓ {config.targetThreshold}%</span>
          </span>
        </div>

        <div className="review-item">
          <span className="label">Owner</span>
          <span className="value">
            {config.owner ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{
                  width: '24px',
                  height: '24px',
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #0064e0, #00a3ff)',
                  color: 'white',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '10px',
                  fontWeight: '600'
                }}>
                  {config.owner.name.split(' ').map(n => n[0]).join('')}
                </span>
                {config.owner.name} (@{config.owner.username})
              </span>
            ) : '—'}
          </span>
        </div>

        <div className="review-item">
          <span className="label">Blocking</span>
          <span className="value">
            {config.blocking
              ? <span style={{ color: '#dc3545' }}>🚫 Yes - blocks deploy on regression</span>
              : <span style={{ color: '#65676b' }}>No - advisory only</span>
            }
          </span>
        </div>

        <div className="review-item">
          <span className="label">Schedule</span>
          <span className="value">{config.schedule}</span>
        </div>
      </div>

      {/* YAML Preview */}
      <div className="review-section">
        <h3>
          Generated Configuration
          <button
            style={{
              marginLeft: '12px',
              fontSize: '12px',
              padding: '4px 12px',
              background: '#e4e6eb',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
            onClick={() => navigator.clipboard.writeText(generateYAML())}
          >
            📋 Copy YAML
          </button>
        </h3>
        <pre className="yaml-preview">
          {generateYAML()}
        </pre>
      </div>

      {/* Quote from reference doc */}
      <div className="info-box" style={{ marginTop: '24px' }}>
        <h4>📖 Remember</h4>
        <p style={{ fontStyle: 'italic' }}>
          "Evals are your PRD. If you don't have an eval, you don't yet have an AI product."
        </p>
        <p style={{ marginTop: '8px', fontSize: '13px' }}>
          This eval will run automatically according to your schedule.
          You can refine it over time as you learn from production results.
        </p>
      </div>
    </div>
  );
}

export default StepReview;
