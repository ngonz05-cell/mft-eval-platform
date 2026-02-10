import React, { useState, useEffect, useRef } from 'react';

// Simulated Meta employee directory (in production, this would call an API)
const MOCK_EMPLOYEES = [
  { id: 1, name: 'Nate Gonzalez', username: 'nategonzalez', title: 'Product Manager', team: 'Payments Platform' },
  { id: 2, name: 'Sarah Chen', username: 'sarachen', title: 'Software Engineer', team: 'Risk & Compliance' },
  { id: 3, name: 'Mike Johnson', username: 'mikejohnson', title: 'Data Scientist', team: 'Fraud Detection' },
  { id: 4, name: 'Emily Rodriguez', username: 'emilyrodriguez', title: 'Product Manager', team: 'Customer Support AI' },
  { id: 5, name: 'David Kim', username: 'davidkim', title: 'Engineering Manager', team: 'Transaction Processing' },
  { id: 6, name: 'Lisa Wang', username: 'lisawang', title: 'Software Engineer', team: 'Financial Analytics' },
  { id: 7, name: 'James Wilson', username: 'jameswilson', title: 'Product Manager', team: 'Payments Platform' },
  { id: 8, name: 'Amanda Torres', username: 'amandatorres', title: 'Data Scientist', team: 'Risk & Compliance' },
  { id: 9, name: 'Chris Lee', username: 'chrislee', title: 'Software Engineer', team: 'Fraud Detection' },
  { id: 10, name: 'Rachel Green', username: 'rachelgreen', title: 'Product Manager', team: 'Customer Support AI' },
];

// Simulated current logged-in user
const CURRENT_USER = MOCK_EMPLOYEES[0]; // Nate Gonzalez

function OwnerSearch({ value, onChange }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [filteredEmployees, setFilteredEmployees] = useState([]);
  const wrapperRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Filter employees based on search query
  useEffect(() => {
    if (searchQuery.length > 0) {
      const query = searchQuery.toLowerCase();
      const filtered = MOCK_EMPLOYEES.filter(emp =>
        emp.name.toLowerCase().includes(query) ||
        emp.username.toLowerCase().includes(query) ||
        emp.title.toLowerCase().includes(query) ||
        emp.team.toLowerCase().includes(query)
      );
      setFilteredEmployees(filtered);
      setIsOpen(true);
    } else {
      setFilteredEmployees([]);
      setIsOpen(false);
    }
  }, [searchQuery]);

  const handleSelect = (employee) => {
    onChange(employee);
    setSearchQuery('');
    setIsOpen(false);
  };

  const handleClear = () => {
    onChange(null);
  };

  return (
    <div className="owner-search" ref={wrapperRef}>
      {value ? (
        // Selected owner display
        <div className="selected-owner">
          <div className="owner-avatar">
            {value.name.split(' ').map(n => n[0]).join('')}
          </div>
          <div className="owner-info">
            <div className="owner-name">{value.name}</div>
            <div className="owner-details">@{value.username} · {value.title}</div>
          </div>
          <button
            className="owner-clear"
            onClick={handleClear}
            title="Change owner"
          >
            ✕
          </button>
        </div>
      ) : (
        // Search input
        <div className="owner-search-input-wrapper">
          <input
            type="text"
            className="owner-search-input"
            placeholder="Search by name, username, or team..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => searchQuery.length > 0 && setIsOpen(true)}
          />
          <span className="owner-search-icon">🔍</span>
        </div>
      )}

      {/* Dropdown results */}
      {isOpen && filteredEmployees.length > 0 && (
        <div className="owner-dropdown">
          {filteredEmployees.map(emp => (
            <div
              key={emp.id}
              className="owner-option"
              onClick={() => handleSelect(emp)}
            >
              <div className="owner-avatar small">
                {emp.name.split(' ').map(n => n[0]).join('')}
              </div>
              <div className="owner-option-info">
                <div className="owner-name">{emp.name}</div>
                <div className="owner-details">@{emp.username} · {emp.title} · {emp.team}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {isOpen && searchQuery.length > 0 && filteredEmployees.length === 0 && (
        <div className="owner-dropdown">
          <div className="owner-no-results">
            No employees found matching "{searchQuery}"
          </div>
        </div>
      )}
    </div>
  );
}

// Team and Sub-team configuration
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
  // Add sub-teams for other teams as needed
};

function TeamSelector({ team, subTeam, customTeam, customSubTeam, onUpdate }) {
  const [showAddTeam, setShowAddTeam] = useState(false);
  const [showAddSubTeam, setShowAddSubTeam] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [newSubTeamName, setNewSubTeamName] = useState('');

  const handleTeamChange = (value) => {
    if (value === '__add_new__') {
      setShowAddTeam(true);
    } else {
      onUpdate({
        team: value,
        subTeam: '',
        customTeam: '',
        customSubTeam: ''
      });
      setShowAddTeam(false);
    }
  };

  const handleSubTeamChange = (value) => {
    if (value === '__add_new__') {
      setShowAddSubTeam(true);
    } else {
      onUpdate({ subTeam: value, customSubTeam: '' });
      setShowAddSubTeam(false);
    }
  };

  const handleAddTeam = () => {
    if (newTeamName.trim()) {
      onUpdate({
        team: '__custom__',
        customTeam: newTeamName.trim(),
        subTeam: '',
        customSubTeam: ''
      });
      setShowAddTeam(false);
      setNewTeamName('');
    }
  };

  const handleAddSubTeam = () => {
    if (newSubTeamName.trim()) {
      onUpdate({
        subTeam: '__custom__',
        customSubTeam: newSubTeamName.trim()
      });
      setShowAddSubTeam(false);
      setNewSubTeamName('');
    }
  };

  const currentTeamId = team === '__custom__' ? null : team;
  const hasSubTeams = currentTeamId && SUB_TEAMS[currentTeamId];

  return (
    <div className="team-selector">
      {/* Team Selection */}
      <div className="form-group">
        <label>Team <span style={{ color: '#dc3545' }}>*</span></label>

        {showAddTeam ? (
          <div className="add-new-input">
            <input
              type="text"
              placeholder="Enter new team name..."
              value={newTeamName}
              onChange={(e) => setNewTeamName(e.target.value)}
              autoFocus
            />
            <button
              className="btn-add"
              onClick={handleAddTeam}
              disabled={!newTeamName.trim()}
            >
              Add
            </button>
            <button
              className="btn-cancel"
              onClick={() => {
                setShowAddTeam(false);
                setNewTeamName('');
              }}
            >
              Cancel
            </button>
          </div>
        ) : team === '__custom__' && customTeam ? (
          <div className="custom-value-display">
            <span className="custom-badge">Custom</span>
            <span className="custom-value">{customTeam}</span>
            <button
              className="btn-change"
              onClick={() => onUpdate({ team: '', customTeam: '', subTeam: '', customSubTeam: '' })}
            >
              Change
            </button>
          </div>
        ) : (
          <select
            value={team}
            onChange={(e) => handleTeamChange(e.target.value)}
          >
            <option value="">Select your team...</option>
            {TEAMS.map(t => (
              <option key={t.id} value={t.id}>{t.name}</option>
            ))}
            <option value="__add_new__">+ Add new team...</option>
          </select>
        )}
      </div>

      {/* Sub-team Selection - Only show if team has sub-teams */}
      {(hasSubTeams || (team === '__custom__' && customTeam)) && (
        <div className="form-group" style={{ marginTop: '16px' }}>
          <label>Sub-team</label>

          {showAddSubTeam ? (
            <div className="add-new-input">
              <input
                type="text"
                placeholder="Enter new sub-team name..."
                value={newSubTeamName}
                onChange={(e) => setNewSubTeamName(e.target.value)}
                autoFocus
              />
              <button
                className="btn-add"
                onClick={handleAddSubTeam}
                disabled={!newSubTeamName.trim()}
              >
                Add
              </button>
              <button
                className="btn-cancel"
                onClick={() => {
                  setShowAddSubTeam(false);
                  setNewSubTeamName('');
                }}
              >
                Cancel
              </button>
            </div>
          ) : subTeam === '__custom__' && customSubTeam ? (
            <div className="custom-value-display">
              <span className="custom-badge">Custom</span>
              <span className="custom-value">{customSubTeam}</span>
              <button
                className="btn-change"
                onClick={() => onUpdate({ subTeam: '', customSubTeam: '' })}
              >
                Change
              </button>
            </div>
          ) : (
            <select
              value={subTeam}
              onChange={(e) => handleSubTeamChange(e.target.value)}
            >
              <option value="">Select sub-team (optional)...</option>
              {hasSubTeams && SUB_TEAMS[currentTeamId].map(st => (
                <option key={st.id} value={st.id}>{st.name}</option>
              ))}
              <option value="__add_new__">+ Add new sub-team...</option>
            </select>
          )}
        </div>
      )}
    </div>
  );
}

function StepBasics({ config, updateConfig }) {
  // Set default owner to current user on mount if not already set
  useEffect(() => {
    if (!config.owner) {
      updateConfig({ owner: CURRENT_USER });
    }
  }, []);

  const handleTeamUpdate = (updates) => {
    updateConfig(updates);
  };

  // Helper to get display name for team
  const getTeamDisplayName = () => {
    if (config.team === '__custom__' && config.customTeam) {
      return config.customTeam;
    }
    const team = TEAMS.find(t => t.id === config.team);
    return team ? team.name : '';
  };

  // Helper to get display name for sub-team
  const getSubTeamDisplayName = () => {
    if (config.subTeam === '__custom__' && config.customSubTeam) {
      return config.customSubTeam;
    }
    const subTeams = SUB_TEAMS[config.team] || [];
    const subTeam = subTeams.find(st => st.id === config.subTeam);
    return subTeam ? subTeam.name : '';
  };

  return (
    <div className="step-basics">
      <div className="form-group">
        <label>
          Eval Name <span style={{ color: '#dc3545' }}>*</span>
        </label>
        <p className="helper-text">
          A unique identifier for this evaluation. Use snake_case (e.g., payment_extraction_accuracy)
        </p>
        <input
          type="text"
          placeholder="e.g., payment_metadata_extraction"
          value={config.name}
          onChange={(e) => updateConfig({ name: e.target.value })}
        />
      </div>

      <div className="form-row">
        <TeamSelector
          team={config.team}
          subTeam={config.subTeam}
          customTeam={config.customTeam}
          customSubTeam={config.customSubTeam}
          onUpdate={handleTeamUpdate}
        />

        <div className="form-group">
          <label>Owner <span style={{ color: '#dc3545' }}>*</span></label>
          <p className="helper-text">
            The person responsible for maintaining this eval
          </p>
          <OwnerSearch
            value={config.owner}
            onChange={(owner) => updateConfig({ owner })}
          />
        </div>
      </div>

      <div className="form-group">
        <label>
          What does this eval measure? <span style={{ color: '#dc3545' }}>*</span>
        </label>
        <p className="helper-text">
          List the fields/metrics you want to evaluate, separated by commas. Be specific about each field.
        </p>
        <textarea
          placeholder="e.g., Amount, Currency, Date, Merchant, Transaction ID"
          value={config.capabilityWhat}
          onChange={(e) => updateConfig({ capabilityWhat: e.target.value })}
        />
      </div>

      <div className="form-group">
        <label>Why does this capability matter?</label>
        <p className="helper-text">
          Connect the capability to user or business value. This helps prioritize improvements.
        </p>
        <textarea
          placeholder="e.g., Enables automated dispute resolution and reduces manual review time by 80%"
          value={config.capabilityWhy}
          onChange={(e) => updateConfig({ capabilityWhy: e.target.value })}
        />
      </div>

      <div className="form-group">
        <label>Additional Info</label>
        <p className="helper-text">
          Additional context about this eval, its scope, and any important notes.
        </p>
        <textarea
          placeholder="Optional: Add any additional context about this evaluation..."
          value={config.description}
          onChange={(e) => updateConfig({ description: e.target.value })}
        />
      </div>

      <div className="info-box warning">
        <h4>⚠️ Checklist before proceeding</h4>
        <ul className="checklist" style={{ marginTop: '8px', paddingLeft: '20px' }}>
          <li style={{ marginBottom: '4px' }}>✓ Eval name is specific and descriptive</li>
          <li style={{ marginBottom: '4px' }}>✓ Capability is precisely defined (not vague)</li>
          <li>✓ You can explain why this matters to users/business</li>
        </ul>
      </div>
    </div>
  );
}

export default StepBasics;
