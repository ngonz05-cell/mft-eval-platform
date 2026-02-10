import React, { useState, useCallback } from 'react';
import StepBasics from './wizard/StepBasics';
import StepDataset from './wizard/StepDataset';
import StepScoring from './wizard/StepScoring';
import StepThresholds from './wizard/StepThresholds';
import StepAutomation from './wizard/StepAutomation';
import StepReview from './wizard/StepReview';

const STEPS = [
  { id: 'basics', label: 'Basics', component: StepBasics },
  { id: 'scoring', label: 'Metrics & Scoring', component: StepScoring },
  { id: 'thresholds', label: 'Thresholds', component: StepThresholds },
  { id: 'dataset', label: 'Example Data', component: StepDataset },
  { id: 'automation', label: 'Automation', component: StepAutomation },
  { id: 'review', label: 'Review & Create', component: StepReview },
];

function EvalWizard({ onComplete, onCancel }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [visitedSteps, setVisitedSteps] = useState([0]); // Track which steps have been visited
  const [evalConfig, setEvalConfig] = useState({
    // Basics
    name: '',
    team: '',
    subTeam: '',
    customTeam: '',
    customSubTeam: '',
    description: '',
    capabilityWhat: '',
    capabilityWhy: '',
    owner: null,  // Will be set to current user by StepBasics

    // Metrics (extracted from capabilityWhat)
    metrics: [], // Array of { field, measurement: [], description, thresholds: {} }

    // Dataset
    datasetSource: 'csv',
    datasetFile: null,
    datasetUrl: '',
    datasetSize: 50,

    // Scoring
    scoringMethod: 'simple',
    selectedScorers: [],

    // Thresholds (global)
    baselineThreshold: 80,
    targetThreshold: 95,
    metricThresholds: {}, // Per-metric thresholds
    blocking: false,

    // Automation
    schedule: 'manual',
    alertOnRegression: true,
    alertChannel: '',
  });

  const updateConfig = (updates) => {
    setEvalConfig(prev => ({ ...prev, ...updates }));
  };

  // Validation functions for each step
  const isStepComplete = useCallback((stepId) => {
    switch (stepId) {
      case 'basics':
        return !!(evalConfig.name && evalConfig.team && evalConfig.capabilityWhat);
      case 'scoring':
        return evalConfig.metrics && evalConfig.metrics.length > 0 &&
          evalConfig.metrics.every(m => m.measurement && m.measurement.length > 0);
      case 'thresholds':
        return evalConfig.baselineThreshold > 0;
      case 'dataset':
        return !!(evalConfig.datasetFile || evalConfig.datasetUrl);
      case 'automation':
        return true; // Automation is optional - always considered complete
      case 'review':
        return true; // Review is always "complete" - it's just for viewing
      default:
        return false;
    }
  }, [evalConfig]);

  const getStepStatus = useCallback((index) => {
    const step = STEPS[index];
    const isVisited = visitedSteps.includes(index);
    const isComplete = isStepComplete(step.id);
    const isCurrent = index === currentStep;

    if (isCurrent) return 'active';
    if (isVisited && isComplete) return 'completed';
    if (isVisited && !isComplete) return 'incomplete';
    return 'pending';
  }, [visitedSteps, currentStep, isStepComplete]);

  const handleStepClick = (index) => {
    // Mark current step as visited before navigating away
    if (!visitedSteps.includes(currentStep)) {
      setVisitedSteps(prev => [...prev, currentStep]);
    }
    // Mark target step as visited
    if (!visitedSteps.includes(index)) {
      setVisitedSteps(prev => [...prev, index]);
    }
    setCurrentStep(index);
  };

  const handleNext = () => {
    if (currentStep < STEPS.length - 1) {
      // Mark current step as visited
      if (!visitedSteps.includes(currentStep)) {
        setVisitedSteps(prev => [...prev, currentStep]);
      }
      const nextStep = currentStep + 1;
      if (!visitedSteps.includes(nextStep)) {
        setVisitedSteps(prev => [...prev, nextStep]);
      }
      setCurrentStep(nextStep);
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const handleComplete = () => {
    onComplete(evalConfig);
  };

  const StepComponent = STEPS[currentStep].component;

  return (
    <div className="wizard">
      <div className="wizard-header">
        <h2>Create New Evaluation</h2>
        <p>Set up an eval to measure your AI product's quality. This wizard will guide you through the process.</p>
      </div>

      <div className="wizard-progress">
        {STEPS.map((step, index) => {
          const status = getStepStatus(index);
          return (
            <div
              key={step.id}
              className={`wizard-step ${status} clickable`}
              onClick={() => handleStepClick(index)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => e.key === 'Enter' && handleStepClick(index)}
            >
              <span className="wizard-step-number">
                {status === 'completed' ? '✓' : status === 'incomplete' ? '!' : index + 1}
              </span>
              {step.label}
            </div>
          );
        })}
      </div>

      <div className="wizard-content">
        <StepComponent
          config={evalConfig}
          updateConfig={updateConfig}
        />
      </div>

      <div className="wizard-footer">
        <div>
          {currentStep > 0 && (
            <button className="btn-secondary" onClick={handleBack}>
              ← Back
            </button>
          )}
        </div>

        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="btn-secondary" onClick={onCancel}>
            Cancel
          </button>

          {currentStep < STEPS.length - 1 ? (
            <button className="btn-primary" onClick={handleNext}>
              Continue →
            </button>
          ) : (
            <button className="btn-primary" onClick={handleComplete}>
              🚀 Create Eval
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export default EvalWizard;
