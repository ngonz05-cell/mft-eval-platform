function LandingPage({ onSelectGuided, onSelectExpert }) {
  return (
    <div className="landing-page">
      <div className="landing-hero">
        <h2>Create a New Evaluation</h2>
        <p>How would you like to get started?</p>
      </div>

      <div className="landing-cards">
        <div className="landing-card guided" onClick={onSelectGuided}>
          <div className="landing-card-icon">🤖</div>
          <h3>Guided Experience</h3>
          <p className="landing-card-subtitle">Recommended for first-time users</p>
          <p className="landing-card-desc">
            Our AI assistant will walk you through creating an eval step by step.
            It will ask clarifying questions, suggest metrics and methodologies,
            and help you build a complete evaluation config.
          </p>
          <ul className="landing-card-features">
            <li>💬 Chat-based walkthrough</li>
            <li>💡 Smart metric suggestions</li>
            <li>🎯 Threshold recommendations</li>
            <li>✏️ Edit everything before creating</li>
          </ul>
          <button className="btn-primary landing-card-btn">
            Start Guided Setup →
          </button>
        </div>

        <div className="landing-card expert" onClick={onSelectExpert}>
          <div className="landing-card-icon">⚡</div>
          <h3>Expert Mode</h3>
          <p className="landing-card-subtitle">For experienced eval builders</p>
          <p className="landing-card-desc">
            Jump straight into the full eval wizard with all fields available.
            Configure metrics, thresholds, datasets, and automation directly.
          </p>
          <ul className="landing-card-features">
            <li>📋 6-step wizard</li>
            <li>🔧 Full control over all settings</li>
            <li>📊 Direct metric configuration</li>
            <li>⚙️ Advanced automation options</li>
          </ul>
          <button className="btn-secondary landing-card-btn">
            Open Expert Wizard →
          </button>
        </div>
      </div>
    </div>
  );
}

export default LandingPage;
