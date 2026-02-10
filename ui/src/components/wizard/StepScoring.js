import React, { useEffect, useState, useRef } from 'react';

const MEASUREMENT_OPTIONS = [
  { id: 'exact_match_ratio', name: 'Exact Match Ratio', description: '% of records where all fields match perfectly' },
  { id: 'simple_pass_fail', name: 'Simple Pass/Fail', description: 'Binary pass or fail assessment' },
  { id: 'weighted_composite', name: 'Weighted Composite', description: 'Combined score from multiple metrics with weights' },
  { id: 'contains_check', name: 'Contains Check', description: 'Check if output contains expected value' },
  { id: 'numeric_tolerance', name: 'Numeric match (w/tolerance)', description: 'Numbers match within a tolerance' },
  { id: 'fuzzy_string_match', name: 'Fuzzy String match', description: 'Accounts for variations in naming/spelling' },
  { id: 'classification_f1', name: 'Classification (F1 score)', description: 'Precision/Recall balance for classification' },
  { id: 'llm_judge', name: 'LLM-as-judge', description: 'Use an LLM to evaluate quality' },
];

function MultiSelectDropdown({ selectedIds, onChange, options }) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleToggle = (id) => {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter(i => i !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  const selectedNames = selectedIds
    .map(id => options.find(o => o.id === id)?.name)
    .filter(Boolean);

  return (
    <div className="multi-select-dropdown" ref={dropdownRef}>
      <div
        className="multi-select-trigger"
        onClick={() => setIsOpen(!isOpen)}
      >
        {selectedNames.length === 0 ? (
          <span className="placeholder">Select measurement(s)...</span>
        ) : (
          <span className="selected-values">{selectedNames.join(', ')}</span>
        )}
        <span className="dropdown-arrow">{isOpen ? '▲' : '▼'}</span>
      </div>
      {isOpen && (
        <div className="multi-select-options">
          {options.map(option => (
            <label key={option.id} className="multi-select-option">
              <input
                type="checkbox"
                checked={selectedIds.includes(option.id)}
                onChange={() => handleToggle(option.id)}
              />
              <div className="option-content">
                <span className="option-name">{option.name}</span>
                <span className="option-desc">{option.description}</span>
              </div>
            </label>
          ))}
        </div>
      )}
    </div>
  );
}

function StepScoring({ config, updateConfig }) {
  // Parse capabilityWhat to extract metrics
  useEffect(() => {
    if (config.capabilityWhat && (!config.metrics || config.metrics.length === 0)) {
      const fields = config.capabilityWhat
        .split(/[,\n]+/)
        .map(f => f.trim())
        .filter(f => f.length > 0);

      if (fields.length > 0) {
        const newMetrics = fields.map(field => ({
          field,
          measurement: [],
          description: '',
        }));
        updateConfig({ metrics: newMetrics });
      }
    }
  }, [config.capabilityWhat]);

  const handleAddMetric = () => {
    const newMetrics = [...(config.metrics || []), { field: '', measurement: [], description: '' }];
    updateConfig({ metrics: newMetrics });
  };

  const handleRemoveMetric = (index) => {
    const newMetrics = (config.metrics || []).filter((_, i) => i !== index);
    updateConfig({ metrics: newMetrics });
  };

  const handleMetricChange = (index, field, value) => {
    const newMetrics = [...(config.metrics || [])];
    newMetrics[index] = { ...newMetrics[index], [field]: value };
    updateConfig({ metrics: newMetrics });
  };

  const metrics = config.metrics || [];

  return (
    <div className="step-scoring">
      <div className="info-box">
        <h4>📊 Define Your Metrics</h4>
        <p>
          Based on what you want to measure, define the fields/metrics below.
          For each metric, select one or more measurement methods and provide a description.
        </p>
      </div>

      {metrics.length === 0 ? (
        <div className="empty-metrics">
          <p>No metrics defined yet. Go back to Basics and enter what this eval measures, or add metrics manually below.</p>
          <button className="btn-primary" onClick={handleAddMetric}>
            + Add First Metric
          </button>
        </div>
      ) : (
        <>
          <div className="metrics-table-container">
            <table className="metrics-table">
              <thead>
                <tr>
                  <th style={{ width: '20%' }}>Metric</th>
                  <th style={{ width: '35%' }}>Measurement</th>
                  <th style={{ width: '40%' }}>Description</th>
                  <th style={{ width: '5%' }}></th>
                </tr>
              </thead>
              <tbody>
                {metrics.map((metric, index) => (
                  <tr key={index}>
                    <td>
                      <input
                        type="text"
                        className="metric-field-input"
                        value={metric.field}
                        onChange={(e) => handleMetricChange(index, 'field', e.target.value)}
                        placeholder="e.g., Amount"
                      />
                    </td>
                    <td>
                      <MultiSelectDropdown
                        selectedIds={metric.measurement || []}
                        onChange={(values) => handleMetricChange(index, 'measurement', values)}
                        options={MEASUREMENT_OPTIONS}
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        className="metric-desc-input"
                        value={metric.description}
                        onChange={(e) => handleMetricChange(index, 'description', e.target.value)}
                        placeholder="Describe how this is evaluated..."
                      />
                    </td>
                    <td>
                      <button
                        className="btn-remove"
                        onClick={() => handleRemoveMetric(index)}
                        title="Remove metric"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <button className="btn-secondary add-metric-btn" onClick={handleAddMetric}>
            + Add Another Metric
          </button>
        </>
      )}

      {metrics.some(m => m.measurement?.includes('llm_judge')) && (
        <div className="info-box warning" style={{ marginTop: '24px' }}>
          <h4>⚠️ LLM-as-Judge Best Practices</h4>
          <ul style={{ paddingLeft: '20px', fontSize: '13px', marginTop: '8px' }}>
            <li>Use a stronger model to judge a weaker model</li>
            <li>Validate LLM judge scores against human labels (sample 100 examples)</li>
            <li>Watch for bias (preferring longer responses, specific phrasings)</li>
            <li><strong>Avoid for:</strong> High-stakes decisions, fraud detection, compliance</li>
          </ul>
        </div>
      )}

      <div className="info-box success" style={{ marginTop: '24px' }}>
        <h4>💡 Tips for Choosing Measurements</h4>
        <ul style={{ paddingLeft: '20px', fontSize: '13px', marginTop: '8px' }}>
          <li><strong>IDs & Categories:</strong> Use Exact Match Ratio</li>
          <li><strong>Amounts & Numbers:</strong> Use Numeric match (w/tolerance)</li>
          <li><strong>Names & Addresses:</strong> Use Fuzzy String match</li>
          <li><strong>Classifications:</strong> Use F1 score</li>
          <li><strong>Subjective Quality:</strong> Use LLM-as-judge (with caution)</li>
        </ul>
      </div>
    </div>
  );
}

export default StepScoring;
