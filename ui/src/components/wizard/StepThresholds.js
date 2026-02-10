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

function getMeasurementName(id) {
  return MEASUREMENT_OPTIONS.find(m => m.id === id)?.name || id;
}

function StepThresholds({ config, updateConfig }) {
  const metrics = config.metrics || [];

  // Collect all metric/measurement pairings
  const metricMeasurementPairs = [];
  metrics.forEach(metric => {
    (metric.measurement || []).forEach(measurementId => {
      metricMeasurementPairs.push({
        field: metric.field,
        measurementId,
        measurementName: getMeasurementName(measurementId),
        key: `${metric.field}_${measurementId}`,
      });
    });
  });

  // Get thresholds for a specific pairing
  const getThreshold = (key, field) => {
    const thresholds = config.metricThresholds || {};
    return thresholds[key]?.[field];
  };

  // Update threshold for a specific pairing
  const updateThreshold = (key, field, value) => {
    const thresholds = { ...(config.metricThresholds || {}) };
    if (!thresholds[key]) {
      thresholds[key] = { baseline: 80, target: 95 };
    }
    thresholds[key] = { ...thresholds[key], [field]: value };
    updateConfig({ metricThresholds: thresholds });
  };

  return (
    <div className="step-thresholds">
      <div className="info-box">
        <h4>🎯 Set Thresholds for Each Metric</h4>
        <p>
          Define <strong>baseline</strong> (minimum acceptable) and <strong>target</strong> (goal) thresholds for each metric/measurement pairing.
          Start with 80% baseline for a minimum viable eval.
        </p>
      </div>

      {/* Per-Metric Thresholds */}
      {metricMeasurementPairs.length > 0 && (
        <>
          <p style={{ fontSize: '13px', color: '#65676b', marginBottom: '16px' }}>
            Set baseline and target thresholds for each metric. Default is 80% baseline / 95% target.
          </p>

          <div className="metric-thresholds-table">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th style={{ width: '25%' }}>Metric</th>
                  <th style={{ width: '25%' }}>Measurement</th>
                  <th style={{ width: '20%' }}>Baseline %</th>
                  <th style={{ width: '20%' }}>Target %</th>
                  <th style={{ width: '10%' }}>Parameters</th>
                </tr>
              </thead>
              <tbody>
                {metricMeasurementPairs.map((pair) => (
                  <tr key={pair.key}>
                    <td>
                      <strong>{pair.field}</strong>
                    </td>
                    <td>
                      <span className="measurement-badge">{pair.measurementName}</span>
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        placeholder={config.baselineThreshold}
                        value={getThreshold(pair.key, 'baseline') || ''}
                        onChange={(e) => updateThreshold(pair.key, 'baseline', parseInt(e.target.value) || null)}
                        className="threshold-input"
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        placeholder={config.targetThreshold}
                        value={getThreshold(pair.key, 'target') || ''}
                        onChange={(e) => updateThreshold(pair.key, 'target', parseInt(e.target.value) || null)}
                        className="threshold-input"
                      />
                    </td>
                    <td>
                      {pair.measurementId === 'numeric_tolerance' && (
                        <input
                          type="text"
                          placeholder="±0.01"
                          value={getThreshold(pair.key, 'tolerance') || ''}
                          onChange={(e) => updateThreshold(pair.key, 'tolerance', e.target.value)}
                          className="param-input"
                          title="Tolerance value"
                        />
                      )}
                      {pair.measurementId === 'fuzzy_string_match' && (
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.1"
                          placeholder="0.8"
                          value={getThreshold(pair.key, 'minSimilarity') || ''}
                          onChange={(e) => updateThreshold(pair.key, 'minSimilarity', parseFloat(e.target.value) || null)}
                          className="param-input"
                          title="Minimum similarity"
                        />
                      )}
                      {pair.measurementId === 'weighted_composite' && (
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.1"
                          placeholder="1.0"
                          value={getThreshold(pair.key, 'weight') || ''}
                          onChange={(e) => updateThreshold(pair.key, 'weight', parseFloat(e.target.value) || null)}
                          className="param-input"
                          title="Weight"
                        />
                      )}
                      {!['numeric_tolerance', 'fuzzy_string_match', 'weighted_composite'].includes(pair.measurementId) && (
                        <span style={{ color: '#65676b', fontSize: '12px' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {metricMeasurementPairs.length === 0 && (
        <div className="info-box warning" style={{ marginTop: '16px' }}>
          <h4>⚠️ No metrics defined</h4>
          <p>
            Go back to Metrics & Scoring to define your metrics and measurements first.
          </p>
        </div>
      )}
    </div>
  );
}

export default StepThresholds;
