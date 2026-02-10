import React from 'react';

function StepDataset({ config, updateConfig }) {
  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      updateConfig({
        datasetFile: file,
        datasetSize: 50 // Will be updated after parsing
      });
    }
  };

  return (
    <div className="step-dataset">
      <div className="info-box">
        <h4>📊 Dataset Requirements</h4>
        <p>
          Your eval needs <strong>realistic inputs, not toy examples</strong>. Include historical production data (sanitized),
          edge cases, and failure modes. Start with <strong>20-100 examples</strong> for a minimum viable eval.
        </p>
      </div>

      <div className="form-group">
        <label>Where is your test data? <span style={{ color: '#dc3545' }}>*</span></label>
        <div className="card-selection">
          <div
            className={`selection-card ${config.datasetSource === 'csv' ? 'selected' : ''}`}
            onClick={() => updateConfig({ datasetSource: 'csv' })}
          >
            <div className="card-icon">📄</div>
            <h4>CSV File Upload</h4>
            <p>Upload a CSV file with your test cases. Good for quick testing.</p>
          </div>

          <div
            className={`selection-card ${config.datasetSource === 'gsheet' ? 'selected' : ''}`}
            onClick={() => updateConfig({ datasetSource: 'gsheet' })}
          >
            <div className="card-icon">📊</div>
            <h4>Google Sheet</h4>
            <p>Link to a Google Sheet. Great for collaborative dataset curation.</p>
          </div>

          <div
            className={`selection-card ${config.datasetSource === 'hive' ? 'selected' : ''}`}
            onClick={() => updateConfig({ datasetSource: 'hive' })}
          >
            <div className="card-icon">🗄️</div>
            <h4>Hive Table</h4>
            <p>Connect to a Hive table. Best for large, production-sampled datasets.</p>
          </div>
        </div>
      </div>

      {config.datasetSource === 'csv' && (
        <div className="form-group">
          <label>Upload your CSV file</label>
          <div
            className={`file-upload ${config.datasetFile ? 'has-file' : ''}`}
            onClick={() => document.getElementById('file-input').click()}
          >
            <input
              id="file-input"
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              style={{ display: 'none' }}
            />
            <div className="file-upload-icon">
              {config.datasetFile ? '✅' : '📁'}
            </div>
            <h4>
              {config.datasetFile
                ? config.datasetFile.name
                : 'Click to upload or drag and drop'
              }
            </h4>
            <p>
              {config.datasetFile
                ? 'File ready! Click to replace.'
                : 'CSV file with columns: input, expected_output'
              }
            </p>
          </div>
        </div>
      )}

      {config.datasetSource === 'gsheet' && (
        <div className="form-group">
          <label>Google Sheet URL</label>
          <p className="helper-text">
            Paste the URL of your Google Sheet. Make sure it's accessible to the MFT team.
          </p>
          <input
            type="url"
            placeholder="https://docs.google.com/spreadsheets/d/..."
            value={config.datasetUrl}
            onChange={(e) => updateConfig({ datasetUrl: e.target.value })}
          />
        </div>
      )}

      {config.datasetSource === 'hive' && (
        <div className="form-group">
          <label>Hive Table Path</label>
          <p className="helper-text">
            Enter the full Hive table path (e.g., mft_evals.payment_extraction_v1)
          </p>
          <input
            type="text"
            placeholder="mft_evals.your_table_name"
            value={config.datasetUrl}
            onChange={(e) => updateConfig({ datasetUrl: e.target.value })}
          />
        </div>
      )}

      <div className="form-group">
        <label>Approximate dataset size</label>
        <p className="helper-text">
          How many test cases are in your dataset?
        </p>
        <div className="form-row">
          <input
            type="number"
            min="10"
            max="10000"
            value={config.datasetSize}
            onChange={(e) => updateConfig({ datasetSize: parseInt(e.target.value) || 50 })}
            style={{ width: '120px' }}
          />
          <span style={{ alignSelf: 'center', color: '#65676b' }}>examples</span>
        </div>
      </div>

      <div className="info-box" style={{ marginTop: '24px' }}>
        <h4>📋 Required CSV Columns</h4>
        <p style={{ marginTop: '8px', marginBottom: '8px' }}>
          Your dataset should have at least these columns:
        </p>
        <ul style={{ paddingLeft: '20px', fontSize: '13px', color: '#65676b' }}>
          <li><strong>input</strong> - The input to your AI system (e.g., raw transaction text)</li>
          <li><strong>expected_output</strong> - The correct/expected output (ground truth)</li>
          <li><em>Optional:</em> Any additional metadata columns for filtering/analysis</li>
        </ul>
      </div>

      <div className="info-box warning" style={{ marginTop: '16px' }}>
        <h4>⚠️ Data Privacy Reminder</h4>
        <p>
          Ensure your dataset does <strong>NOT contain PII or UII</strong>.
          All data must be properly anonymized before use in evals.
        </p>
      </div>
    </div>
  );
}

export default StepDataset;
