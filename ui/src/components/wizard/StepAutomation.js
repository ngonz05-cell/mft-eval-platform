import React from 'react';

function StepAutomation({ config, updateConfig }) {
  return (
    <div className="step-automation">
      <div className="info-box">
        <h4>📅 Automation Settings</h4>
        <p>
          Configure when and how your eval runs automatically.
          Set up alerts to get notified when metrics drop below thresholds.
        </p>
      </div>

      <div className="form-group">
        <label>Run Schedule</label>
        <p className="helper-text">
          How often should this eval run automatically?
        </p>
        <select
          value={config.schedule}
          onChange={(e) => updateConfig({ schedule: e.target.value })}
        >
          <option value="manual">Manual only</option>
          <option value="daily">Daily (2 AM)</option>
          <option value="weekly">Weekly (Sundays)</option>
          <option value="on_deploy">On every deployment</option>
        </select>
      </div>

      <div className="form-group" style={{ marginTop: '24px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={config.alertOnRegression}
            onChange={(e) => updateConfig({ alertOnRegression: e.target.checked })}
            style={{ width: '20px', height: '20px' }}
          />
          <div>
            <strong>Alert on regression</strong>
            <p style={{ fontSize: '13px', color: '#65676b', margin: 0 }}>
              Send a notification when any metric drops below baseline.
            </p>
          </div>
        </label>
      </div>

      {config.alertOnRegression && (
        <div className="form-group" style={{ marginTop: '16px', marginLeft: '32px' }}>
          <label>Alert Channel</label>
          <p className="helper-text">
            Slack channel or email group to receive alerts
          </p>
          <input
            type="text"
            placeholder="#mft-ai-alerts"
            value={config.alertChannel}
            onChange={(e) => updateConfig({ alertChannel: e.target.value })}
          />
        </div>
      )}

      <div className="info-box success" style={{ marginTop: '32px' }}>
        <h4>💡 Automation Tips</h4>
        <ul style={{ paddingLeft: '20px', fontSize: '13px', marginTop: '8px' }}>
          <li><strong>Start with manual:</strong> Run evals manually until you're confident in the setup</li>
          <li><strong>Daily runs:</strong> Good for catching regressions early in active development</li>
          <li><strong>On deploy:</strong> Best for production-critical features</li>
          <li><strong>Set up alerts:</strong> Don't miss regressions - connect to your team's Slack channel</li>
        </ul>
      </div>
    </div>
  );
}

export default StepAutomation;
