import { useState, useRef, useEffect, useCallback } from 'react';
import { sendChatMessage, generateMetrics, checkHealth, createEval, validateMetrics, runEval } from '../api';

const MEASUREMENT_OPTIONS = [
  { id: 'exact_match_ratio', name: 'Exact Match Ratio', description: '% of records where all fields match perfectly' },
  { id: 'simple_pass_fail', name: 'Simple Pass/Fail', description: 'Binary pass or fail assessment' },
  { id: 'weighted_composite', name: 'Weighted Composite', description: 'Combined score from multiple metrics with weights' },
  { id: 'contains_check', name: 'Contains Check', description: 'Check if output contains expected value' },
  { id: 'numeric_tolerance', name: 'Numeric match (w/tolerance)', description: 'Numbers match within a tolerance' },
  { id: 'fuzzy_string_match', name: 'Fuzzy String match', description: 'Accounts for variations in naming/spelling' },
  { id: 'classification_f1', name: 'Classification (F1 score)', description: 'Precision/Recall balance for classification' },
  { id: 'llm_judge', name: 'LLM-as-judge', description: 'Use an LLM to evaluate quality' },
  { id: 'field_f1', name: 'Field-Level F1', description: 'Per-field precision/recall for extraction tasks' },
  { id: 'task_success_rate', name: 'Task Success Rate', description: 'End-to-end task completion for agentic systems' },
  { id: 'tool_correctness', name: 'Tool Correctness', description: 'Right tool invoked with right parameters' },
];

const TEAMS = [
  'Payments Platform', 'Risk & Compliance', 'Lending', 'Commerce',
  'Customer Support AI', 'Identity & Verification', 'Treasury',
  'Insurance', 'Novi/Blockchain', 'Revenue & Growth',
];

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

const CURRENT_USER = MOCK_EMPLOYEES[0];

const PHASES = {
  OBJECTIVE: 'objective',
  REFINE: 'refine',
  METRICS: 'metrics',
  SAMPLE_DATA: 'sample_data',
  CONNECT: 'connect',
  MANAGE: 'manage',
  REVIEW: 'review',
};

// Ordered list for navigation — determines what "back" and "forward" mean
const PHASE_ORDER = [
  PHASES.OBJECTIVE,
  PHASES.REFINE,
  PHASES.METRICS,
  PHASES.SAMPLE_DATA,
  PHASES.CONNECT,
  PHASES.MANAGE,
  PHASES.REVIEW,
];

// Maps phase pills to the phases they represent
const PILL_PHASES = {
  describe: [PHASES.OBJECTIVE, PHASES.REFINE],
  metrics: [PHASES.METRICS],
  data: [PHASES.SAMPLE_DATA],
  connect: [PHASES.CONNECT],
  manage: [PHASES.MANAGE],
  review: [PHASES.REVIEW],
};

function phaseIndex(p) {
  return PHASE_ORDER.indexOf(p);
}

function previousPhase(p) {
  const idx = phaseIndex(p);
  return idx > 0 ? PHASE_ORDER[idx - 1] : null;
}

// --- Custom Compass SVG Avatars ---
const CompassClassic = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="12" r="11" stroke="#1877f2" strokeWidth="1.5" fill="#f0f6ff" />
    <circle cx="12" cy="12" r="1.5" fill="#1877f2" />
    <polygon points="12,3 13.5,10.5 12,9 10.5,10.5" fill="#e74c3c" />
    <polygon points="12,21 13.5,13.5 12,15 10.5,13.5" fill="#1877f2" />
    <polygon points="3,12 10.5,10.5 9,12 10.5,13.5" fill="#65676b" />
    <polygon points="21,12 13.5,10.5 15,12 13.5,13.5" fill="#65676b" />
    <text x="12" y="4.5" textAnchor="middle" fontSize="3" fill="#e74c3c" fontWeight="700">N</text>
  </svg>
);

const CompassMinimal = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="12" r="11" stroke="#1877f2" strokeWidth="2" fill="white" />
    <path d="M12 4L14 10L12 8.5L10 10L12 4Z" fill="#1877f2" />
    <path d="M12 20L10 14L12 15.5L14 14L12 20Z" fill="#c0d0e8" />
    <circle cx="12" cy="12" r="1.2" fill="#1877f2" />
    <circle cx="12" cy="12" r="8" stroke="#e4e6eb" strokeWidth="0.5" fill="none" strokeDasharray="2 2" />
  </svg>
);

const CompassRose = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="12" cy="12" r="11" stroke="#1877f2" strokeWidth="1.5" fill="#fafbfc" />
    <polygon points="12,2.5 13,11 12,9.5 11,11" fill="#e74c3c" opacity="0.9" />
    <polygon points="12,21.5 11,13 12,14.5 13,13" fill="#1877f2" opacity="0.7" />
    <polygon points="2.5,12 11,11 9.5,12 11,13" fill="#1877f2" opacity="0.4" />
    <polygon points="21.5,12 13,13 14.5,12 13,11" fill="#1877f2" opacity="0.4" />
    <polygon points="5,5 10.5,10.5 9.5,11 10.5,10.5" fill="#c0d0e8" />
    <polygon points="19,5 13.5,10.5 14.5,11 13.5,10.5" fill="#c0d0e8" />
    <polygon points="5,19 10.5,13.5 11,14.5 10.5,13.5" fill="#c0d0e8" />
    <polygon points="19,19 13.5,13.5 13,14.5 13.5,13.5" fill="#c0d0e8" />
    <circle cx="12" cy="12" r="1.8" fill="#1877f2" />
    <circle cx="12" cy="12" r="0.8" fill="white" />
  </svg>
);

const CompassModern = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
    {/* Outer bezel */}
    <circle cx="12" cy="12" r="11.5" fill="#1877f2" />
    <circle cx="12" cy="12" r="10.5" fill="#4a9af5" />
    <circle cx="12" cy="12" r="9.5" stroke="rgba(255,255,255,0.25)" strokeWidth="0.5" fill="none" />
    {/* Tick marks */}
    <line x1="12" y1="2" x2="12" y2="4" stroke="white" strokeWidth="1.2" strokeLinecap="round" />
    <line x1="22" y1="12" x2="20" y2="12" stroke="rgba(255,255,255,0.6)" strokeWidth="0.8" strokeLinecap="round" />
    <line x1="12" y1="22" x2="12" y2="20" stroke="rgba(255,255,255,0.6)" strokeWidth="0.8" strokeLinecap="round" />
    <line x1="2" y1="12" x2="4" y2="12" stroke="rgba(255,255,255,0.6)" strokeWidth="0.8" strokeLinecap="round" />
    {/* North needle — red */}
    <polygon points="12,3.5 13.8,11 12,9.5 10.2,11" fill="#e74c3c" />
    <polygon points="12,3.5 12,9.5 10.2,11" fill="#c0392b" />
    {/* South needle — white */}
    <polygon points="12,20.5 10.2,13 12,14.5 13.8,13" fill="white" />
    <polygon points="12,20.5 12,14.5 13.8,13" fill="#dce1e6" />
    {/* East/West needles — subtle */}
    <polygon points="20.5,12 13,10.5 14.5,12 13,13.5" fill="rgba(255,255,255,0.3)" />
    <polygon points="3.5,12 11,10.5 9.5,12 11,13.5" fill="rgba(255,255,255,0.3)" />
    {/* Center pin */}
    <circle cx="12" cy="12" r="2" fill="#1877f2" />
    <circle cx="12" cy="12" r="1.2" fill="white" />
  </svg>
);

// Choose which compass to use (swap here to try different variants)
const ChatAvatar = CompassModern;

function OwnerSearchInput({ onSelect }) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const [filtered, setFiltered] = useState([]);
  const wrapperRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(event) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (query.length > 0) {
      const q = query.toLowerCase();
      setFiltered(MOCK_EMPLOYEES.filter(emp =>
        emp.name.toLowerCase().includes(q) ||
        emp.username.toLowerCase().includes(q) ||
        emp.title.toLowerCase().includes(q) ||
        emp.team.toLowerCase().includes(q)
      ));
      setIsOpen(true);
    } else {
      setFiltered([]);
      setIsOpen(false);
    }
  }, [query]);

  return (
    <div className="owner-search" ref={wrapperRef}>
      <div className="owner-search-input-wrapper">
        <input
          type="text"
          className="owner-search-input"
          placeholder="Search by name, username, or team..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query.length > 0 && setIsOpen(true)}
        />
        <span className="owner-search-icon">🔍</span>
      </div>
      {isOpen && filtered.length > 0 && (
        <div className="owner-dropdown">
          {filtered.map(emp => (
            <div key={emp.id} className="owner-option" onClick={() => { onSelect(emp); setQuery(''); setIsOpen(false); }}>
              <div className="owner-avatar small">{emp.name.split(' ').map(n => n[0]).join('')}</div>
              <div className="owner-option-info">
                <div className="owner-name">{emp.name}</div>
                <div className="owner-details">@{emp.username} · {emp.title}</div>
              </div>
            </div>
          ))}
        </div>
      )}
      {isOpen && filtered.length === 0 && query.length > 0 && (
        <div className="owner-dropdown">
          <div className="owner-no-results">No employees found</div>
        </div>
      )}
    </div>
  );
}

function suggestMetricsWithRationale(description) {
  const desc = description.toLowerCase();
  const metrics = [];
  const rationale = [];

  if (desc.includes('extract') || desc.includes('parse') || desc.includes('field')) {
    metrics.push(
      { field: 'Field Accuracy', measurement: ['exact_match_ratio'], description: 'Percentage of fields extracted correctly', thresholds: { baseline: 80, target: 95 } },
      { field: 'Format Compliance', measurement: ['contains_check'], description: 'Output matches expected format/structure', thresholds: { baseline: 85, target: 98 } },
    );
    rationale.push(
      '**Field Accuracy → Exact Match Ratio (80% → 95%):** Since your product extracts structured fields, exact match is the gold standard — either the extracted value is correct or it isn\'t. 80% baseline is a practical starting point for extraction tasks; 95% target aligns with production-ready quality.',
      '**Format Compliance → Contains Check (85% → 98%):** Ensures outputs follow the expected schema/format. Set higher than accuracy because format errors are typically easier to fix and more critical for downstream systems.',
    );
  }
  if (desc.includes('classif') || desc.includes('detect') || desc.includes('categor')) {
    metrics.push(
      { field: 'Classification Accuracy', measurement: ['classification_f1'], description: 'F1 score for classification correctness', thresholds: { baseline: 75, target: 90 } },
      { field: 'False Positive Rate', measurement: ['numeric_tolerance'], description: 'Rate of incorrect positive predictions', thresholds: { baseline: 90, target: 98 } },
    );
    rationale.push(
      '**Classification Accuracy → F1 Score (75% → 90%):** F1 balances precision and recall, which is critical for classification tasks where both false positives and false negatives matter. 75% baseline accounts for class imbalance challenges; 90% is a strong production target.',
      '**False Positive Rate → Numeric Tolerance (90% → 98%):** Tracks how often good items are incorrectly flagged. High thresholds because false positives directly impact user experience (e.g., blocking legitimate transactions).',
    );
  }
  if (desc.includes('generat') || desc.includes('summar') || desc.includes('write') || desc.includes('respond') || desc.includes('creat') || desc.includes('stor')) {
    metrics.push(
      { field: 'Response Quality', measurement: ['llm_judge'], description: 'Overall quality rated by LLM judge', thresholds: { baseline: 70, target: 85 } },
      { field: 'Factual Accuracy', measurement: ['contains_check'], description: 'Key facts present in the output', thresholds: { baseline: 80, target: 95 } },
    );
    rationale.push(
      '**Response Quality → LLM-as-Judge (70% → 85%):** For generated content, human-like quality assessment is best captured by an LLM judge. Lower baseline (70%) reflects the inherent subjectivity of quality evaluation; 85% target is ambitious but achievable.',
      '**Factual Accuracy → Contains Check (80% → 95%):** Verifies that generated content includes required factual elements. Higher thresholds because factual errors in generated content erode trust quickly.',
    );
  }
  if (desc.includes('amount') || desc.includes('number') || desc.includes('price') || desc.includes('payment') || desc.includes('dollar')) {
    metrics.push(
      { field: 'Numeric Accuracy', measurement: ['numeric_tolerance'], description: 'Numeric values match within tolerance', thresholds: { baseline: 85, target: 99 } },
    );
    rationale.push(
      '**Numeric Accuracy → Numeric Tolerance (85% → 99%):** Financial values need near-perfect accuracy. Tolerance-based matching accounts for rounding differences. 99% target reflects that monetary errors, even small ones, have outsized impact on user trust.',
    );
  }
  if (desc.includes('name') || desc.includes('address') || desc.includes('merchant')) {
    metrics.push(
      { field: 'String Match', measurement: ['fuzzy_string_match'], description: 'Fuzzy match for names/addresses', thresholds: { baseline: 80, target: 92 } },
    );
    rationale.push(
      '**String Match → Fuzzy String Match (80% → 92%):** Names and addresses have legitimate variations (abbreviations, typos, formatting). Fuzzy matching with 80% similarity threshold avoids penalizing acceptable differences while still catching real errors.',
    );
  }
  if (desc.includes('fraud') || desc.includes('risk') || desc.includes('compliance')) {
    metrics.push(
      { field: 'Risk Detection', measurement: ['classification_f1'], description: 'Ability to detect risk/fraud cases', thresholds: { baseline: 85, target: 95 } },
    );
    rationale.push(
      '**Risk Detection → F1 Score (85% → 95%):** For fraud/risk, missing a true positive is costly, but so is over-flagging legitimate users. F1 captures this balance. Higher baseline (85%) because risk systems must perform well from day one — a miss could mean real financial harm.',
    );
  }
  if (desc.includes('safe') || desc.includes('appropriate') || desc.includes('content') || desc.includes('moderat') || desc.includes('child') || desc.includes('kid') || desc.includes('age')) {
    metrics.push(
      { field: 'Content Safety', measurement: ['simple_pass_fail'], description: 'Output is safe and age-appropriate', thresholds: { baseline: 95, target: 100 } },
      { field: 'Policy Compliance', measurement: ['llm_judge'], description: 'Content meets policy guidelines', thresholds: { baseline: 90, target: 98 } },
    );
    rationale.push(
      '**Content Safety → Simple Pass/Fail (95% → 100%):** Safety is binary — content is either safe or it isn\'t. 95% baseline is already strict; 100% target reflects zero tolerance for unsafe content, especially with vulnerable audiences like children.',
      '**Policy Compliance → LLM-as-Judge (90% → 98%):** Policy compliance involves nuanced judgment (tone, appropriateness, context) that\'s best evaluated by an LLM. High thresholds because policy violations carry reputational and legal risk.',
    );
  }

  if (metrics.length === 0) {
    metrics.push(
      { field: 'Overall Accuracy', measurement: ['exact_match_ratio'], description: 'General accuracy of outputs', thresholds: { baseline: 80, target: 95 } },
      { field: 'Output Quality', measurement: ['simple_pass_fail'], description: 'Pass/fail assessment of output quality', thresholds: { baseline: 75, target: 90 } },
    );
    rationale.push(
      '**Overall Accuracy → Exact Match Ratio (80% → 95%):** A general-purpose accuracy metric. 80% baseline gives room for initial iterations; 95% is a standard production target.',
      '**Output Quality → Simple Pass/Fail (75% → 90%):** A straightforward quality gate. Lower baseline because pass/fail criteria may need calibration as you learn what "good" looks like for your use case.',
    );
  }

  return { metrics, rationale };
}

function generateEvalName(description) {
  const words = description.toLowerCase()
    .replace(/[^a-z0-9\s]/g, '')
    .split(/\s+/)
    .filter(w => w.length > 2 && !['the', 'and', 'for', 'that', 'this', 'our', 'with', 'from', 'are', 'was', 'will', 'can', 'has', 'have'].includes(w))
    .slice(0, 4);
  return words.join('_') + '_eval';
}

function generateRefinedPrompt(userMessage) {
  const desc = userMessage.toLowerCase();
  let refined = userMessage.trim();
  if (!refined.endsWith('.')) refined += '.';

  const isAlreadyDetailed = userMessage.length > 100;
  if (!isAlreadyDetailed) {
    if (!desc.includes('measure') && !desc.includes('eval') && !desc.includes('metric') && !desc.includes('accur')) {
      refined += ' I want to measure the accuracy and quality of its outputs.';
    }
    if (!desc.includes('wrong') && !desc.includes('fail') && !desc.includes('error') && !desc.includes('miss') && !desc.includes('incorrect')) {
      if (desc.includes('extract') || desc.includes('parse')) {
        refined += ' Key failure modes include extracting wrong values, missing fields, or incorrect formatting.';
      } else if (desc.includes('classif') || desc.includes('detect')) {
        refined += ' Key failure modes include false positives, false negatives, and misclassifications.';
      } else if (desc.includes('generat') || desc.includes('creat') || desc.includes('stor')) {
        refined += ' Key failure modes include factual inaccuracies, quality issues, or inappropriate content.';
      }
    }
  }

  return refined;
}

// Offline fallback: generate clarifying questions based on what's missing from the description
// eslint-disable-next-line no-unused-vars
function generateClarifyingQuestions(userMessage) {
  const desc = userMessage.toLowerCase();
  const questions = [];

  if (!desc.includes('input') && !desc.includes('from') && !desc.includes('take') && !desc.includes('receive') && !desc.includes('process')) {
    questions.push('What are the **inputs** to your system? (e.g., raw text, images, structured data, user queries)');
  }
  if (!desc.includes('output') && !desc.includes('return') && !desc.includes('produce') && !desc.includes('generat') && !desc.includes('extract') && !desc.includes('classif') && !desc.includes('creat')) {
    questions.push('What does your system **output**? (e.g., extracted fields, classifications, generated text, scores)');
  }
  if (!desc.includes('wrong') && !desc.includes('fail') && !desc.includes('error') && !desc.includes('miss') && !desc.includes('bad') && !desc.includes('incorrect') && !desc.includes('risk')) {
    questions.push('What are the **biggest risks** if it gets something wrong? (e.g., financial loss, user harm, compliance violation)');
  }
  if (!desc.includes('how many') && !desc.includes('volume') && !desc.includes('scale') && !desc.includes('production') && !desc.includes('traffic')) {
    questions.push('Roughly how much **volume** does this handle? (helps calibrate sampling & thresholds)');
  }
  if (desc.includes('child') || desc.includes('kid') || desc.includes('age')) {
    if (!desc.includes('guideline') && !desc.includes('policy') && !desc.includes('rule')) {
      questions.push('Are there specific **content guidelines or policies** that define what\'s appropriate for this age group?');
    }
  }
  if (desc.includes('payment') || desc.includes('transaction') || desc.includes('amount')) {
    if (!desc.includes('tolerance') && !desc.includes('precision') && !desc.includes('decimal')) {
      questions.push('What **numeric precision** matters? (e.g., exact cents, or is rounding to dollars acceptable?)');
    }
  }
  if (desc.includes('classif') || desc.includes('detect') || desc.includes('fraud')) {
    if (!desc.includes('false positive') && !desc.includes('false negative')) {
      questions.push('Which is worse: **false positives** (flagging good items) or **false negatives** (missing bad items)?');
    }
  }

  return questions.slice(0, 3);
}

function buildAssistantResponse(phase, userMessage, evalConfig) {
  const msg = userMessage.toLowerCase();

  if (phase === PHASES.OBJECTIVE) {
    if (msg.length < 20) {
      return {
        text: "I'd love to help! Could you tell me a bit more about what your product does? For example:\n\n- **What problem does it solve?** (payments, documents, customer queries)\n- **What does it output?** (extracted fields, classifications, generated text)\n- **What could go wrong?** (wrong amounts, missed fraud, bad responses)\n\nThe more specific you are, the better evals I can help you create.",
        phase: PHASES.OBJECTIVE,
      };
    }

    const refinedPrompt = generateRefinedPrompt(userMessage);
    const isAlreadyGood = userMessage.length > 200;

    if (isAlreadyGood) {
      const { metrics, rationale } = suggestMetricsWithRationale(userMessage);
      const suggestedName = generateEvalName(userMessage);
      return {
        text: `This is a really detailed description — nice work! I have everything I need to suggest metrics.\n\n👇 **Review the suggested metrics on the right** — I've included explanations for why each was chosen. Everything is editable.`,
        phase: PHASES.METRICS,
        configUpdates: {
          capabilityWhat: userMessage,
          capabilityWhy: `Evaluate the quality and accuracy of ${suggestedName.replace(/_/g, ' ')}`,
          description: userMessage,
          name: suggestedName,
          metrics, rationale,
          metricThresholds: metrics.reduce((acc, m) => {
            m.measurement.forEach(mId => { acc[`${m.field}_${mId}`] = m.thresholds; });
            return acc;
          }, {}),
        },
      };
    }

    let responseText = `Thanks! Here's what I'm hearing:\n\n> ${userMessage}\n\n`;
    responseText += `I've drafted a **refined description** on the right panel that adds more specificity for eval design.\n\n`;
    responseText += `👉 **Review and edit it**, then click **"Use This & Generate Metrics"** when you're ready — or keep chatting here to refine further.`;

    return {
      text: responseText,
      phase: PHASES.REFINE,
      configUpdates: {
        capabilityWhat: userMessage,
        refinedPrompt: refinedPrompt,
      },
    };
  }

  if (phase === PHASES.REFINE) {
    const currentPrompt = evalConfig.refinedPrompt || evalConfig.capabilityWhat || '';
    const combinedDescription = currentPrompt.replace(/\.$/, '') + '. ' + userMessage;
    const newRefined = generateRefinedPrompt(combinedDescription);

    return {
      text: `Got it! I've updated the refined description on the right with your new details. Take a look and click **"Use This & Generate Metrics"** when you're ready.`,
      phase: PHASES.REFINE,
      configUpdates: {
        refinedPrompt: newRefined,
      },
    };
  }

  if (phase === PHASES.METRICS) {
    return {
      text: "I've updated the configuration based on your feedback. Take another look at the metrics on the right and let me know if everything looks right, or click **\"Looks Good, Continue\"** to move on.",
      phase: PHASES.METRICS,
    };
  }

  if (phase === PHASES.SAMPLE_DATA) {
    return {
      text: "Got it! Update your sample data settings on the right panel. When you're ready, click **\"Continue to Manage\"** to set up ownership and automation.",
      phase: PHASES.SAMPLE_DATA,
    };
  }

  if (phase === PHASES.MANAGE) {
    return {
      text: "Settings updated! Review the ownership and automation config on the right. When you're ready, click **\"Review Final Draft\"** to see everything together.",
      phase: PHASES.MANAGE,
    };
  }

  return {
    text: "Let me know how I can help refine your eval configuration!",
    phase: phase,
  };
}

const EXAMPLE_PROMPTS = [
  {
    product: 'Payment Extraction AI',
    example: '"We built an AI that extracts payment metadata (amount, merchant, date) from transaction descriptions. We want to measure extraction accuracy across all field types."',
  },
  {
    product: 'Fraud Detection Model',
    example: '"Our model classifies transactions as fraudulent or legitimate. We need to measure precision and recall, especially reducing false positives that block good users."',
  },
  {
    product: 'Customer Support Chatbot',
    example: '"We have a chatbot that answers customer questions about their account. We want to measure response accuracy and whether it resolves issues without human handoff."',
  },
  {
    product: 'Document Summarization',
    example: '"Our AI summarizes long compliance documents into key action items. We want to measure if all critical points are captured and nothing important is missed."',
  },
  {
    product: 'Identity Verification',
    example: '"We built a system that verifies user identity by matching selfies to ID documents. We want to measure match accuracy and catch rate for fraudulent IDs."',
  },
  {
    product: 'Lending Risk Assessment',
    example: '"Our model predicts loan default risk based on transaction history. We want to measure prediction accuracy and fairness across demographic groups."',
  },
];

function getRotatingExample() {
  return EXAMPLE_PROMPTS[Math.floor(Math.random() * EXAMPLE_PROMPTS.length)];
}

function GuidedEval({ onComplete, onCancel }) {
  const [example] = useState(() => getRotatingExample());
  const [phase, setPhaseRaw] = useState(PHASES.OBJECTIVE);
  const [highestPhase, setHighestPhase] = useState(PHASES.OBJECTIVE);

  // Always update highestPhase when moving forward
  const setPhase = useCallback((newPhase) => {
    setPhaseRaw(newPhase);
    setHighestPhase(prev => phaseIndex(newPhase) > phaseIndex(prev) ? newPhase : prev);
  }, []);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      phase: PHASES.OBJECTIVE,
      text: `👋 Hi! I'm here to help you create an eval for your new product/feature.\n\n**Tell me about it** — what user problem is it solving, what does it do, how do you want to measure success?\n\nThe more detail you provide, the better evals I can help you create.\n\n💡 **Example** (${example.product}):\n> ${example.example}`,
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [isGeneratingMetrics, setIsGeneratingMetrics] = useState(false);
  const [showDryRunPrompt, setShowDryRunPrompt] = useState(false);
  const [dryRunDone, setDryRunDone] = useState(false);
  const [isDryRunning, setIsDryRunning] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [createdEvalId, setCreatedEvalId] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const chatMessagesRef = useRef(null);

  const [evalConfig, setEvalConfig] = useState({
    name: '',
    team: '',
    subTeam: '',
    customTeam: '',
    customSubTeam: '',
    description: '',
    capabilityWhat: '',
    capabilityWhy: '',
    refinedPrompt: '',
    rationale: [],
    owner: CURRENT_USER,
    metrics: [],
    datasetSource: 'csv',
    datasetFile: null,
    datasetUrl: '',
    datasetSize: 20,
    sampleData: [],
    sampleDataFormat: 'json',
    // Model connection
    modelEndpoint: '',
    modelAuthType: 'none',
    modelApiKey: '',
    modelRequestFormat: 'openai_chat',
    modelRequestTemplate: '',
    modelResponsePath: 'choices[0].message.content',
    // Production log source
    prodLogEnabled: false,
    prodLogSource: 'scuba',
    prodLogTable: '',
    prodLogInputColumn: '',
    prodLogOutputColumn: '',
    prodLogTimestampColumn: '',
    prodLogSampleRate: 10,
    // Manage
    scoringMethod: 'simple',
    selectedScorers: [],
    baselineThreshold: 80,
    targetThreshold: 95,
    metricThresholds: {},
    blocking: false,
    schedule: 'manual',
    alertOnRegression: true,
    alertChannel: '',
  });

  const updateConfig = useCallback((updates) => {
    setEvalConfig(prev => ({ ...prev, ...updates }));
  }, []);

  // Validate each section for completeness
  const getPhaseValidation = useCallback(() => {
    const issues = {};
    if (!evalConfig.description && !evalConfig.capabilityWhat && !evalConfig.refinedPrompt) {
      issues.describe = 'Missing product description';
    }
    if (!evalConfig.metrics.length || evalConfig.metrics.every(m => !m.field)) {
      issues.metrics = 'No metrics defined';
    }
    if (evalConfig.datasetSource === 'hive' && !evalConfig.datasetUrl) {
      issues.data = 'Missing Hive table URL';
    }
    if (!evalConfig.modelEndpoint) {
      issues.connect = 'Missing model endpoint';
    }
    if (!evalConfig.team) {
      issues.manage = 'Missing team assignment';
    }
    return issues;
  }, [evalConfig]);

  const navigateToPhase = (targetPill) => {
    const phaseMap = {
      describe: PHASES.OBJECTIVE,
      metrics: PHASES.METRICS,
      data: PHASES.SAMPLE_DATA,
      connect: PHASES.CONNECT,
      manage: PHASES.MANAGE,
      review: PHASES.REVIEW,
    };
    const newPhase = phaseMap[targetPill];
    if (newPhase && newPhase !== phase) {
      setPhase(newPhase);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [phase]);

  const [apiAvailable, setApiAvailable] = useState(false);
  useEffect(() => {
    checkHealth()
      .then(() => {
        setApiAvailable(true);
        console.log('[MFT] API backend connected — using LLM mode');
      })
      .catch(() => {
        setApiAvailable(false);
        console.log('[MFT] API backend not available — using offline mode');
      });
  }, []);

  const handleSend = async () => {
    if (!inputValue.trim()) return;

    const userMsg = inputValue.trim();
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setInputValue('');
    setIsTyping(true);

    if (apiAvailable) {
      try {
        const result = await sendChatMessage(phase, userMsg, messages, evalConfig);

        if (result.type === 'refine') {
          const data = result.data;
          if (data.is_detailed_enough) {
            setMessages(prev => [...prev, { role: 'assistant', text: data.message }]);
            setIsTyping(false);
            setPhase(PHASES.METRICS);
            setIsGeneratingMetrics(true);

            const metricsResult = await generateMetrics(userMsg, [...messages, { role: 'user', text: userMsg }]);
            const metricsData = metricsResult;
            const metrics = metricsData.metrics.map(m => ({
              field: m.field,
              measurement: m.measurement,
              description: m.description,
              thresholds: { baseline: m.baseline, target: m.target },
            }));
            const rationale = metricsData.metrics.map(m => m.rationale);

            setMessages(prev => [...prev, {
              role: 'assistant',
              text: metricsData.message + `\n\n👉 **Review the suggested metrics on the right** — everything is editable. When you're happy, click **"Looks Good, Continue"**.`,
            }]);
            updateConfig({
              capabilityWhat: userMsg,
              description: userMsg,
              name: metricsData.eval_name,
              metrics,
              rationale,
              metricThresholds: metrics.reduce((acc, m) => {
                m.measurement.forEach(mId => { acc[`${m.field}_${mId}`] = m.thresholds; });
                return acc;
              }, {}),
            });
            setIsGeneratingMetrics(false);
          } else {
            setMessages(prev => [...prev, { role: 'assistant', text: data.message }]);
            updateConfig({
              capabilityWhat: userMsg,
              refinedPrompt: data.refined_prompt,
            });
            setPhase(PHASES.REFINE);
          }
        } else {
          const data = result.data;
          setMessages(prev => [...prev, { role: 'assistant', text: data.message }]);
          if (data.refined_prompt) {
            updateConfig({ refinedPrompt: data.refined_prompt });
          }
          if (data.config_updates) {
            updateConfig(data.config_updates);
          }
          if (data.metrics) {
            const metrics = data.metrics.map(m => ({
              field: m.field,
              measurement: m.measurement,
              description: m.description,
              thresholds: { baseline: m.baseline, target: m.target },
            }));
            const rationale = data.metrics.map(m => m.rationale);
            updateConfig({ metrics, rationale });
          }
        }
      } catch (err) {
        console.error('[MFT] API error, falling back to offline:', err);
        const response = buildAssistantResponse(phase, userMsg, evalConfig);
        setMessages(prev => [...prev, { role: 'assistant', text: response.text }]);
        if (response.configUpdates) updateConfig(response.configUpdates);
        if (response.phase !== phase) setPhase(response.phase);
      }
    } else {
      setTimeout(() => {
        const response = buildAssistantResponse(phase, userMsg, evalConfig);
        setMessages(prev => [...prev, { role: 'assistant', text: response.text }]);
        if (response.configUpdates) updateConfig(response.configUpdates);
        if (response.phase !== phase) setPhase(response.phase);
        setIsTyping(false);
      }, 800 + Math.random() * 600);
      return;
    }

    setIsTyping(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleConfirmRefinedPrompt = async () => {
    const finalDescription = evalConfig.refinedPrompt || evalConfig.capabilityWhat;
    setPhase(PHASES.METRICS);
    setIsGeneratingMetrics(true);

    if (apiAvailable) {
      try {
        const metricsResult = await generateMetrics(finalDescription, messages);
        const metricsData = metricsResult;
        const metrics = metricsData.metrics.map(m => ({
          field: m.field,
          measurement: m.measurement,
          description: m.description,
          thresholds: { baseline: m.baseline, target: m.target },
        }));
        const rationale = metricsData.metrics.map(m => m.rationale);

        updateConfig({
          description: finalDescription,
          capabilityWhat: finalDescription,
          capabilityWhy: `Evaluate the quality and accuracy of ${metricsData.eval_name.replace(/_/g, ' ')}`,
          name: metricsData.eval_name,
          metrics,
          rationale,
          metricThresholds: metrics.reduce((acc, m) => {
            m.measurement.forEach(mId => { acc[`${m.field}_${mId}`] = m.thresholds; });
            return acc;
          }, {}),
        });

        setMessages(prev => [...prev, {
          role: 'assistant',
          text: metricsData.message + `\n\n👉 **Review the suggested metrics on the right** — everything is editable. When you're happy, click **"Looks Good, Continue"**.`,
        }]);

        setIsGeneratingMetrics(false);
        return;
      } catch (err) {
        console.error('[MFT] API error generating metrics, falling back to offline:', err);
      }
    }

    // Offline fallback
    const { metrics, rationale } = suggestMetricsWithRationale(finalDescription);
    const suggestedName = generateEvalName(finalDescription);

    updateConfig({
      description: finalDescription,
      capabilityWhat: finalDescription,
      capabilityWhy: `Evaluate the quality and accuracy of ${suggestedName.replace(/_/g, ' ')}`,
      name: suggestedName,
      metrics,
      rationale,
      metricThresholds: metrics.reduce((acc, m) => {
        m.measurement.forEach(mId => { acc[`${m.field}_${mId}`] = m.thresholds; });
        return acc;
      }, {}),
    });

    let rationaleMessage = `Based on your refined description, I've suggested **${metrics.length} metrics** with measurement methods and thresholds.\n\n`;
    rationale.forEach((r) => {
      rationaleMessage += `${r}\n\n`;
    });
    rationaleMessage += `👉 **Review the suggested metrics on the right** — everything is editable. When you're happy, click **"Looks Good, Continue"**.`;

    setMessages(prev => [...prev, {
      role: 'assistant',
      text: rationaleMessage,
    }]);

    setIsGeneratingMetrics(false);
  };

  const handlePhaseAdvance = () => {
    if (phase === PHASES.METRICS) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: "Now let's **add sample data** for your eval.\n\nSample data helps validate that your metrics and thresholds work correctly before running the full eval. You can upload a CSV, paste JSON examples, or connect to a data source.\n\n👉 Configure your sample data on the right, then click **\"Continue to Connect\"** when ready.",
      }]);
      setPhase(PHASES.SAMPLE_DATA);
    } else if (phase === PHASES.SAMPLE_DATA) {
      const hasSampleData = evalConfig.sampleData && evalConfig.sampleData.length > 0;
      const hasMetrics = evalConfig.metrics && evalConfig.metrics.length > 0;
      if (hasSampleData && hasMetrics && !dryRunDone) {
        setShowDryRunPrompt(true);
        return;
      }
      advanceToConnect();
    } else if (phase === PHASES.CONNECT) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: "Let's set up **ownership and management**.\n\n- **Owner:** Defaults to you — change it if someone else should own this eval\n- **Team:** Which team does this eval belong to?\n- **Schedule:** How often should this eval run?\n- **Alerts:** Want to be notified when metrics drop below baseline?\n\n👉 Configure the settings on the right, then click **\"Review Final Draft\"** when ready.",
      }]);
      setPhase(PHASES.MANAGE);
    } else if (phase === PHASES.MANAGE) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: "🎉 **Your eval is ready for review!**\n\nI've compiled everything into a final draft on the right. Review each section carefully — you can still edit any field. When you're satisfied, click **\"Create Eval\"** to finalize it.",
      }]);
      setPhase(PHASES.REVIEW);
    }
  };

  const advanceToConnect = () => {
    setShowDryRunPrompt(false);
    setMessages(prev => [...prev, {
      role: 'assistant',
      text: "Now let's **connect your model** so the eval runner knows where to send test inputs.\n\n- **Model Endpoint:** The API URL for your model or pipeline\n- **Auth:** How to authenticate (API key, OAuth, or none for internal services)\n- **Request/Response:** How to format requests and parse responses\n\nOptionally, you can also configure **production log monitoring** to continuously evaluate real traffic.\n\n👉 Configure the connection on the right, then click **\"Continue to Manage\"** when ready.",
    }]);
    setPhase(PHASES.CONNECT);
  };

  const handleMetricChange = (index, field, value) => {
    const newMetrics = [...evalConfig.metrics];
    newMetrics[index] = { ...newMetrics[index], [field]: value };
    updateConfig({ metrics: newMetrics });
  };

  const handleAddMetric = () => {
    updateConfig({
      metrics: [...evalConfig.metrics, { field: '', measurement: [], description: '', thresholds: { baseline: 80, target: 95 } }],
    });
  };

  const handleRemoveMetric = (index) => {
    const newRationale = [...(evalConfig.rationale || [])];
    if (index < newRationale.length) newRationale.splice(index, 1);
    updateConfig({
      metrics: evalConfig.metrics.filter((_, i) => i !== index),
      rationale: newRationale,
    });
  };

  const handleThresholdChange = (index, field, value) => {
    const newMetrics = [...evalConfig.metrics];
    newMetrics[index] = {
      ...newMetrics[index],
      thresholds: { ...newMetrics[index].thresholds, [field]: parseInt(value) || 0 },
    };
    updateConfig({ metrics: newMetrics });
  };

  const handleAddSampleRow = () => {
    updateConfig({
      sampleData: [...evalConfig.sampleData, { input: '', expected_output: '', context: '' }],
    });
  };

  const handleSampleDataChange = (index, field, value) => {
    const newData = [...evalConfig.sampleData];
    newData[index] = { ...newData[index], [field]: value };
    updateConfig({ sampleData: newData });
  };

  const handleRemoveSampleRow = (index) => {
    updateConfig({
      sampleData: evalConfig.sampleData.filter((_, i) => i !== index),
    });
  };

  const handleDryRun = async () => {
    setShowDryRunPrompt(false);
    setIsDryRunning(true);
    setMessages(prev => [...prev, {
      role: 'assistant',
      text: '🔬 **Running metric validation against your sample data...**\n\nI\'m analyzing your sample data against the proposed metrics to check if the thresholds are realistic.',
    }]);

    try {
      const result = await validateMetrics(
        evalConfig.metrics,
        evalConfig.sampleData.slice(0, 10),
        evalConfig.refinedPrompt || evalConfig.description
      );

      const assessment = result.overall_assessment || 'unknown';
      const emoji = assessment === 'good' ? '✅' : assessment === 'needs_adjustment' ? '🔶' : '⚠️';
      let feedbackText = `${emoji} **Validation Result: ${assessment.replace(/_/g, ' ')}**\n\n${result.message || ''}\n\n`;

      if (result.metric_feedback && result.metric_feedback.length > 0) {
        feedbackText += '**Per-Metric Feedback:**\n';
        result.metric_feedback.forEach(fb => {
          const statusIcon = fb.status === 'good' ? '✅' : fb.status === 'adjust' ? '🔶' : '❌';
          feedbackText += `\n${statusIcon} **${fb.field}**: ${fb.suggestion}`;
          if (fb.suggested_baseline || fb.suggested_target) {
            feedbackText += ` (suggested: ${fb.suggested_baseline || '?'}% → ${fb.suggested_target || '?'}%)`;
          }
        });
      }

      feedbackText += '\n\n👉 Review the suggestions above. You can edit metrics on the right panel, or click **"Continue to Connect"** to move on.';

      setMessages(prev => [...prev, { role: 'assistant', text: feedbackText }]);
    } catch (err) {
      console.error('[MFT] Dry run error:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: `📊 **Quick validation** (API unavailable):\n\nYou have **${evalConfig.sampleData.length} sample entries** and **${evalConfig.metrics.length} metrics** configured. Based on the data structure, your thresholds look reasonable as a starting point. I'd recommend running a full validation once the model endpoint is connected.\n\n👉 Click **"Continue to Connect"** to move on.`,
      }]);
    }
    setIsDryRunning(false);
    setDryRunDone(true);
  };

  const handleSkipDryRun = () => {
    setShowDryRunPrompt(false);
    setDryRunDone(true);
    advanceToConnect();
  };

  const handleCreateEval = async () => {
    setIsCreating(true);
    try {
      const result = await createEval(evalConfig);
      const evalId = result?.eval?.id;
      if (evalId) {
        setCreatedEvalId(evalId);
        setMessages(prev => [...prev, {
          role: 'assistant',
          text: `🎉 **Eval created successfully!** (ID: ${evalId})\n\nYour eval "${evalConfig.evalName || evalConfig.name}" has been saved. You can now run it against your data to see how your metrics perform.\n\n${evalConfig.modelEndpoint ? '👉 Click **"Run Eval"** to execute the evaluation now.' : '⚠️ No model endpoint configured — connect a model in the Connect step to enable runs.'}`,
        }]);
      } else {
        onComplete(evalConfig);
      }
    } catch (err) {
      console.error('[MFT] Create eval error:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: `⚠️ Eval saved locally but API save failed: ${err.message}. The eval config has been preserved.`,
      }]);
      onComplete(evalConfig);
    } finally {
      setIsCreating(false);
    }
  };

  const handleRunEval = async () => {
    if (!createdEvalId) return;
    setIsRunning(true);
    setRunResult(null);
    setMessages(prev => [...prev, {
      role: 'assistant',
      text: '⏳ **Running eval...**\n\nExecuting test cases against your model and scoring results. This may take a moment.',
    }]);

    try {
      const result = await runEval(createdEvalId);
      const run = result?.run || {};
      setRunResult(run);

      const statusEmoji = run.passed_baseline ? '✅' : '❌';
      const metricsText = run.metrics ? Object.entries(run.metrics)
        .map(([k, v]) => `  • ${k}: ${(v * 100).toFixed(1)}%`)
        .join('\n') : 'No metrics recorded';

      setMessages(prev => [...prev, {
        role: 'assistant',
        text: `${statusEmoji} **Eval Run Complete!**\n\n**Primary Score:** ${((run.primary_score || 0) * 100).toFixed(1)}%\n**Pass Rate:** ${((run.pass_rate || 0) * 100).toFixed(1)}% (${run.num_passed || 0}/${run.num_examples || 0})\n**Duration:** ${run.duration_ms || 0}ms\n\n**Metrics:**\n${metricsText}\n\n${!run.passed_baseline ? '⚠️ **Below baseline threshold** — consider adjusting your metrics or improving your model.' : '🎯 Passed baseline! Your eval is performing well.'}`,
      }]);
    } catch (err) {
      console.error('[MFT] Run eval error:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: `❌ **Eval run failed:** ${err.message}\n\nCheck your model endpoint configuration and try again.`,
      }]);
    } finally {
      setIsRunning(false);
    }
  };

  // --- RENDER: Chat Panel (always on the left) ---
  const renderChatPanel = () => (
    <div className="guided-chat-panel">
      <div className="guided-chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            {msg.role === 'assistant' && <div className="chat-avatar"><ChatAvatar size={28} /></div>}
            <div className="chat-bubble">
              {msg.text.split('\n').map((line, j) => {
                if (line.startsWith('**') && line.endsWith('**')) {
                  return <p key={j}><strong>{line.slice(2, -2)}</strong></p>;
                }
                if (line.startsWith('> ')) {
                  return <blockquote key={j}>{line.slice(2)}</blockquote>;
                }
                if (line.startsWith('- ')) {
                  return <p key={j} className="chat-list-item">• {renderInlineMarkdown(line.slice(2))}</p>;
                }
                if (line.match(/^\d+\. /)) {
                  return <p key={j} className="chat-list-item">{renderInlineMarkdown(line)}</p>;
                }
                if (line.trim() === '') {
                  return <br key={j} />;
                }
                return <p key={j}>{renderInlineMarkdown(line)}</p>;
              })}
            </div>
            {msg.role === 'user' && <div className="chat-avatar user-avatar">You</div>}
          </div>
        ))}
        {isTyping && (
          <div className="chat-message assistant">
            <div className="chat-avatar"><ChatAvatar size={28} /></div>
            <div className="chat-bubble typing">
              <span className="typing-dot"></span>
              <span className="typing-dot"></span>
              <span className="typing-dot"></span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      <div className="guided-chat-input">
        <textarea
          ref={inputRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            phase === PHASES.OBJECTIVE
              ? "Describe your product and what you want to evaluate..."
              : phase === PHASES.REFINE
              ? "Answer the questions above, or add more detail..."
              : "Ask me anything or request changes..."
          }
          rows={2}
        />
        <button className="btn-primary chat-send-btn" onClick={handleSend} disabled={!inputValue.trim() || isTyping}>
          Send
        </button>
      </div>
    </div>
  );

  // --- RENDER: Right panel for REFINE phase ---
  const renderRefinePanel = () => (
    <div className="guided-right-panel">
      <div className="right-panel-header">
        <h3>✏️ Refined Description</h3>
        <p>Edit the description below to add more detail, then confirm to generate metrics.</p>
      </div>
      <div className="right-panel-content">
        <textarea
          className="refined-prompt-textarea"
          value={evalConfig.refinedPrompt}
          onChange={(e) => updateConfig({ refinedPrompt: e.target.value })}
          rows={8}
        />
      </div>
      <div className="right-panel-cta">
        <button className="btn-primary" onClick={handleConfirmRefinedPrompt} disabled={isGeneratingMetrics}>
          Use This & Generate Metrics →
        </button>
      </div>
    </div>
  );

  // --- RENDER: Right panel for METRICS phase ---
  const renderMetricsPanel = () => (
    <div className="guided-right-panel">
      {isGeneratingMetrics && (
        <div className="metrics-loading-overlay">
          <div className="metrics-loading-spinner"></div>
          <p className="metrics-loading-text">Generating metrics…</p>
          <p className="metrics-loading-subtext">Analyzing your description and selecting measurement methods</p>
        </div>
      )}
      <div className="right-panel-header">
        <h3>📊 Suggested Metrics & Thresholds</h3>
        <p>Edit any field below. Add or remove metrics as needed.</p>
      </div>
      <div className="right-panel-content">
        <div className="form-group">
          <label>Eval Name</label>
          <input
            type="text"
            value={evalConfig.name}
            onChange={(e) => updateConfig({ name: e.target.value })}
            placeholder="my_eval_name"
          />
        </div>

        <div className="form-group">
          <label>Description</label>
          <textarea
            value={evalConfig.description}
            onChange={(e) => updateConfig({ description: e.target.value })}
            rows={2}
            placeholder="What does this eval measure?"
          />
        </div>

        <table className="metrics-table guided-metrics-table">
          <thead>
            <tr>
              <th className="col-metric">Metric</th>
              <th className="col-measurement">Measurement</th>
              <th className="col-baseline">Baseline %</th>
              <th className="col-target">Target %</th>
              <th className="col-action"></th>
            </tr>
          </thead>
          <tbody>
            {evalConfig.metrics.map((metric, i) => (
              <tr key={i}>
                <td>
                  <input
                    type="text"
                    className="metric-field-input"
                    value={metric.field}
                    onChange={(e) => handleMetricChange(i, 'field', e.target.value)}
                    placeholder="Metric name"
                  />
                </td>
                <td>
                  <select
                    value={metric.measurement?.[0] || ''}
                    onChange={(e) => handleMetricChange(i, 'measurement', e.target.value ? [e.target.value] : [])}
                    className="metric-measurement-select"
                  >
                    <option value="">Select...</option>
                    {MEASUREMENT_OPTIONS.map(o => (
                      <option key={o.id} value={o.id}>{o.name}</option>
                    ))}
                  </select>
                </td>
                <td>
                  <input
                    type="number"
                    className="threshold-input"
                    min="0" max="100"
                    value={metric.thresholds?.baseline || 80}
                    onChange={(e) => handleThresholdChange(i, 'baseline', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    className="threshold-input"
                    min="0" max="100"
                    value={metric.thresholds?.target || 95}
                    onChange={(e) => handleThresholdChange(i, 'target', e.target.value)}
                  />
                </td>
                <td>
                  <button className="btn-remove" onClick={() => handleRemoveMetric(i)} title="Remove">✕</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <button className="btn-secondary add-metric-btn" onClick={handleAddMetric}>
          + Add Metric
        </button>
      </div>
      <div className="right-panel-cta">
        <button className="btn-primary" onClick={handlePhaseAdvance}>
          Looks Good, Continue →
        </button>
      </div>
    </div>
  );

  // --- RENDER: Right panel for SAMPLE DATA phase ---
  const renderSampleDataPanel = () => (
    <div className="guided-right-panel">
      <div className="right-panel-header">
        <h3>🗂️ Sample Data</h3>
        <p>Add sample input/output pairs to validate your eval config. Aim for 5-10 representative examples.</p>
      </div>
      <div className="right-panel-content">
        <div className="form-group">
          <label>Data Source</label>
          <select value={evalConfig.datasetSource} onChange={(e) => updateConfig({ datasetSource: e.target.value })}>
            <option value="csv">CSV File Upload</option>
            <option value="manual">Manual Entry</option>
            <option value="gsheet">Google Sheet</option>
            <option value="hive">Hive Table</option>
          </select>
        </div>

        {evalConfig.datasetSource === 'manual' && (
          <>
            <table className="metrics-table guided-metrics-table sample-data-table">
              <thead>
                <tr>
                  <th>Input</th>
                  <th>Expected Output</th>
                  <th>Context (optional)</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {(evalConfig.sampleData || []).map((row, i) => (
                  <tr key={i}>
                    <td>
                      <input
                        type="text"
                        value={row.input}
                        onChange={(e) => handleSampleDataChange(i, 'input', e.target.value)}
                        placeholder="e.g., 'Paid $42.50 at Starbucks'"
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={row.expected_output}
                        onChange={(e) => handleSampleDataChange(i, 'expected_output', e.target.value)}
                        placeholder='e.g., {"amount": 42.50, "merchant": "Starbucks"}'
                      />
                    </td>
                    <td>
                      <input
                        type="text"
                        value={row.context || ''}
                        onChange={(e) => handleSampleDataChange(i, 'context', e.target.value)}
                        placeholder="Additional context..."
                      />
                    </td>
                    <td>
                      <button className="btn-remove" onClick={() => handleRemoveSampleRow(i)}>✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button className="btn-secondary add-metric-btn" onClick={handleAddSampleRow}>
              + Add Row
            </button>
          </>
        )}

        {evalConfig.datasetSource === 'csv' && (
          <div className="form-group">
            <label>Upload CSV</label>
            <div className="file-upload-zone">
              <input
                type="file"
                accept=".csv"
                onChange={(e) => updateConfig({ datasetFile: e.target.files[0] })}
              />
              <p className="file-upload-hint">
                CSV should have columns: <code>input</code>, <code>expected_output</code>, and optionally <code>context</code>
              </p>
            </div>
          </div>
        )}

        {evalConfig.datasetSource === 'gsheet' && (
          <div className="form-group">
            <label>Google Sheet URL</label>
            <input
              type="text"
              placeholder="https://docs.google.com/spreadsheets/d/..."
              value={evalConfig.datasetUrl}
              onChange={(e) => updateConfig({ datasetUrl: e.target.value })}
            />
          </div>
        )}

        {evalConfig.datasetSource === 'hive' && (
          <div className="form-group">
            <label>Hive Table</label>
            <input
              type="text"
              placeholder="database.table_name"
              value={evalConfig.datasetUrl}
              onChange={(e) => updateConfig({ datasetUrl: e.target.value })}
            />
          </div>
        )}

        <div className="form-group">
          <label>Target Dataset Size</label>
          <input
            type="number"
            min="10"
            max="10000"
            value={evalConfig.datasetSize}
            onChange={(e) => updateConfig({ datasetSize: parseInt(e.target.value) || 20 })}
          />
          <p className="form-hint">Minimum 20 examples for directional signal. 50+ recommended for reliable results. 100+ for high-confidence benchmarking.</p>
        </div>
      </div>
      {showDryRunPrompt && (
        <div className="dry-run-prompt-overlay">
          <div className="dry-run-prompt-card">
            <h4>🔬 Validate metrics against sample data?</h4>
            <p>I can analyze your sample data against the proposed metrics to check if the thresholds are realistic and suggest refinements.</p>
            <div className="dry-run-prompt-actions">
              <button className="btn-secondary" onClick={handleSkipDryRun}>Skip for now</button>
              <button className="btn-primary" onClick={handleDryRun} disabled={isDryRunning}>
                {isDryRunning ? 'Validating...' : 'Yes, validate'}
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="right-panel-cta">
        <button className="btn-primary" onClick={handlePhaseAdvance} disabled={isDryRunning}>
          Continue to Connect →
        </button>
      </div>
    </div>
  );

  // --- RENDER: Right panel for CONNECT phase ---
  const renderConnectPanel = () => (
    <div className="guided-right-panel">
      <div className="right-panel-header">
        <h3>🔌 Model Connection</h3>
        <p>Configure how the eval runner connects to your model for offline testing and (optionally) production monitoring.</p>
      </div>
      <div className="right-panel-content">
        <div className="connect-section">
          <h4>Model Endpoint</h4>
          <div className="form-group">
            <label>Endpoint URL</label>
            <input
              type="text"
              placeholder="https://your-model-api.fburl.com/v1/predict"
              value={evalConfig.modelEndpoint}
              onChange={(e) => updateConfig({ modelEndpoint: e.target.value })}
            />
            <p className="form-hint">The API endpoint the eval runner will call with test inputs</p>
          </div>

          <div className="form-group">
            <label>Authentication</label>
            <select
              value={evalConfig.modelAuthType}
              onChange={(e) => updateConfig({ modelAuthType: e.target.value })}
            >
              <option value="none">None (internal service)</option>
              <option value="api_key">API Key</option>
              <option value="oauth">OAuth / Service Token</option>
            </select>
          </div>

          {evalConfig.modelAuthType === 'api_key' && (
            <div className="form-group">
              <label>API Key</label>
              <input
                type="password"
                placeholder="sk-..."
                value={evalConfig.modelApiKey}
                onChange={(e) => updateConfig({ modelApiKey: e.target.value })}
              />
            </div>
          )}

          <div className="form-group">
            <label>Request Format</label>
            <select
              value={evalConfig.modelRequestFormat}
              onChange={(e) => updateConfig({ modelRequestFormat: e.target.value })}
            >
              <option value="openai_chat">OpenAI Chat (messages array)</option>
              <option value="anthropic">Anthropic Messages API</option>
              <option value="raw_json">Raw JSON (custom template)</option>
              <option value="text_in_text_out">Plain text in → text out</option>
            </select>
            <p className="form-hint">How the eval runner should structure the request payload</p>
          </div>

          {evalConfig.modelRequestFormat === 'raw_json' && (
            <div className="form-group">
              <label>Request Template</label>
              <textarea
                className="code-textarea"
                placeholder={'{"prompt": "{{input}}", "max_tokens": 1024}'}
                value={evalConfig.modelRequestTemplate}
                onChange={(e) => updateConfig({ modelRequestTemplate: e.target.value })}
                rows={4}
              />
              <p className="form-hint">Use {'{{input}}'} as a placeholder for the test input</p>
            </div>
          )}

          <div className="form-group">
            <label>Response Path</label>
            <input
              type="text"
              placeholder="choices[0].message.content"
              value={evalConfig.modelResponsePath}
              onChange={(e) => updateConfig({ modelResponsePath: e.target.value })}
            />
            <p className="form-hint">JSON path to extract the model's output from the response</p>
          </div>
        </div>

        <div className="connect-section connect-divider">
          <div className="section-toggle">
            <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={evalConfig.prodLogEnabled}
                onChange={(e) => updateConfig({ prodLogEnabled: e.target.checked })}
                style={{ width: '20px', height: '20px' }}
              />
              <span><strong>Enable Production Log Monitoring</strong></span>
            </label>
            <p className="form-hint" style={{ marginTop: '4px' }}>Continuously evaluate real production traffic alongside offline batch evals</p>
          </div>

          {evalConfig.prodLogEnabled && (
            <>
              <div className="form-group">
                <label>Log Source</label>
                <select
                  value={evalConfig.prodLogSource}
                  onChange={(e) => updateConfig({ prodLogSource: e.target.value })}
                >
                  <option value="scuba">Scuba Table</option>
                  <option value="hive">Hive Table</option>
                  <option value="custom_api">Custom API Endpoint</option>
                </select>
              </div>

              <div className="form-group">
                <label>{evalConfig.prodLogSource === 'scuba' ? 'Scuba Table' : evalConfig.prodLogSource === 'hive' ? 'Hive Table' : 'API Endpoint'}</label>
                <input
                  type="text"
                  placeholder={evalConfig.prodLogSource === 'scuba' ? 'mft_model_requests' : evalConfig.prodLogSource === 'hive' ? 'mft_data.model_requests' : 'https://...'}
                  value={evalConfig.prodLogTable}
                  onChange={(e) => updateConfig({ prodLogTable: e.target.value })}
                />
              </div>

              <div className="guided-basics-row">
                <div className="form-group">
                  <label>Input Column</label>
                  <input
                    type="text"
                    placeholder="request_body"
                    value={evalConfig.prodLogInputColumn}
                    onChange={(e) => updateConfig({ prodLogInputColumn: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Output Column</label>
                  <input
                    type="text"
                    placeholder="response_body"
                    value={evalConfig.prodLogOutputColumn}
                    onChange={(e) => updateConfig({ prodLogOutputColumn: e.target.value })}
                  />
                </div>
              </div>

              <div className="guided-basics-row">
                <div className="form-group">
                  <label>Timestamp Column</label>
                  <input
                    type="text"
                    placeholder="created_at"
                    value={evalConfig.prodLogTimestampColumn}
                    onChange={(e) => updateConfig({ prodLogTimestampColumn: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label>Sample Rate (%)</label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={evalConfig.prodLogSampleRate}
                    onChange={(e) => updateConfig({ prodLogSampleRate: parseInt(e.target.value) || 10 })}
                  />
                  <p className="form-hint">% of production requests to evaluate</p>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
      <div className="right-panel-cta">
        <button className="btn-primary" onClick={handlePhaseAdvance}>
          Continue to Manage →
        </button>
      </div>
    </div>
  );

  const renderOwnerField = () => {
    const owner = evalConfig.owner;
    return (
      <div className="form-group">
        <label>Eval Owner</label>
        {owner ? (
          <div className="selected-owner">
            <div className="owner-avatar">
              {owner.name.split(' ').map(n => n[0]).join('')}
            </div>
            <div className="owner-info">
              <div className="owner-name">{owner.name}</div>
              <div className="owner-details">@{owner.username} · {owner.title}</div>
            </div>
            <button className="owner-clear" onClick={() => updateConfig({ owner: null })} title="Change owner">✕</button>
          </div>
        ) : (
          <OwnerSearchInput onSelect={(emp) => updateConfig({ owner: emp })} />
        )}
      </div>
    );
  };

  // --- RENDER: Right panel for MANAGE phase ---
  const renderManagePanel = () => (
    <div className="guided-right-panel">
      <div className="right-panel-header">
        <h3>⚙️ Manage — Ownership, Schedule & Alerts</h3>
        <p>Set the eval owner, team, run schedule, and alert preferences.</p>
      </div>
      <div className="right-panel-content">
        <div className="guided-basics-row">
          {renderOwnerField()}
          <div className="form-group">
            <label>Team</label>
            <select value={evalConfig.team} onChange={(e) => updateConfig({ team: e.target.value })}>
              <option value="">Select team...</option>
              {TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>

        <div className="guided-basics-row">
          <div className="form-group">
            <label>Run Schedule</label>
            <select value={evalConfig.schedule} onChange={(e) => updateConfig({ schedule: e.target.value })}>
              <option value="manual">Manual only</option>
              <option value="daily">Daily (2 AM)</option>
              <option value="weekly">Weekly (Sundays)</option>
              <option value="on_deploy">On every deployment</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={evalConfig.alertOnRegression}
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

        {evalConfig.alertOnRegression && (
          <div className="form-group">
            <label>Alert Channel</label>
            <input
              type="text"
              placeholder="#mft-ai-alerts"
              value={evalConfig.alertChannel}
              onChange={(e) => updateConfig({ alertChannel: e.target.value })}
            />
          </div>
        )}
      </div>
      <div className="right-panel-cta">
        <button className="btn-primary" onClick={handlePhaseAdvance}>
          Review Final Draft →
        </button>
      </div>
    </div>
  );


  // --- RENDER: Right panel for REVIEW phase (full-width) ---
  const renderFinalReview = () => {
    const scheduleLabels = { manual: 'Manual only', daily: 'Daily (2 AM)', weekly: 'Weekly (Sundays)', on_deploy: 'On every deployment' };

    return (
      <div className="guided-right-panel guided-review-panel">
        <div className="right-panel-header">
          <h3>📋 Final Eval Draft</h3>
          <p>Review everything below. All fields are still editable. Click "Create Eval" when ready.</p>
        </div>
        <div className="right-panel-content">
          <div className="review-section">
            <h3>🔹 Basics</h3>
            <div className="form-group">
              <label>Eval Name</label>
              <input type="text" value={evalConfig.name} onChange={(e) => updateConfig({ name: e.target.value })} />
            </div>
            <div className="form-group">
              <label>Description</label>
              <textarea value={evalConfig.description} onChange={(e) => updateConfig({ description: e.target.value })} rows={2} />
            </div>
          </div>

          <div className="review-section">
            <h3>🔹 Metrics & Thresholds</h3>
            <table className="metrics-table guided-metrics-table">
              <thead>
                <tr>
                  <th className="col-metric">Metric</th>
                  <th className="col-measurement">Measurement</th>
                  <th className="col-baseline">Baseline %</th>
                  <th className="col-target">Target %</th>
                  <th className="col-action"></th>
                </tr>
              </thead>
              <tbody>
                {evalConfig.metrics.map((metric, i) => (
                  <tr key={i}>
                    <td>
                      <input type="text" className="metric-field-input" value={metric.field}
                        onChange={(e) => handleMetricChange(i, 'field', e.target.value)} />
                    </td>
                    <td>
                      <select value={metric.measurement?.[0] || ''}
                        onChange={(e) => handleMetricChange(i, 'measurement', e.target.value ? [e.target.value] : [])}
                        className="metric-measurement-select">
                        <option value="">Select...</option>
                        {MEASUREMENT_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
                      </select>
                    </td>
                    <td>
                      <input type="number" className="threshold-input" min="0" max="100"
                        value={metric.thresholds?.baseline || 80}
                        onChange={(e) => handleThresholdChange(i, 'baseline', e.target.value)} />
                    </td>
                    <td>
                      <input type="number" className="threshold-input" min="0" max="100"
                        value={metric.thresholds?.target || 95}
                        onChange={(e) => handleThresholdChange(i, 'target', e.target.value)} />
                    </td>
                    <td>
                      <button className="btn-remove" onClick={() => handleRemoveMetric(i)}>✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button className="btn-secondary add-metric-btn" onClick={handleAddMetric}>+ Add Metric</button>
          </div>

          <div className="review-section">
            <h3>🔹 Sample Data</h3>
            <p style={{ fontSize: '14px', color: '#65676b' }}>
              Source: {evalConfig.datasetSource} · {evalConfig.datasetSize} examples
              {evalConfig.sampleData?.length > 0 && ` · ${evalConfig.sampleData.length} manual entries`}
            </p>
          </div>

          <div className="review-section">
            <h3>🔹 Manage</h3>
            <div className="guided-basics-row">
              {renderOwnerField()}
              <div className="form-group">
                <label>Team</label>
                <select value={evalConfig.team} onChange={(e) => updateConfig({ team: e.target.value })}>
                  <option value="">Select team...</option>
                  {TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>
            <div className="guided-basics-row">
              <div className="form-group">
                <label>Schedule</label>
                <select value={evalConfig.schedule} onChange={(e) => updateConfig({ schedule: e.target.value })}>
                  <option value="manual">Manual only</option>
                  <option value="daily">Daily (2 AM)</option>
                  <option value="weekly">Weekly (Sundays)</option>
                  <option value="on_deploy">On every deployment</option>
                </select>
              </div>
            </div>
            <div className="form-group">
              <label style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
                <input type="checkbox" checked={evalConfig.alertOnRegression}
                  onChange={(e) => updateConfig({ alertOnRegression: e.target.checked })}
                  style={{ width: '20px', height: '20px' }} />
                <span>Alert on regression</span>
              </label>
            </div>
            {evalConfig.alertOnRegression && (
              <div className="form-group">
                <label>Alert Channel</label>
                <input type="text" placeholder="#mft-ai-alerts" value={evalConfig.alertChannel}
                  onChange={(e) => updateConfig({ alertChannel: e.target.value })} />
              </div>
            )}
          </div>

          <div className="review-section">
            <h3>🔹 YAML Preview</h3>
            <div className="yaml-preview">
              <pre>{generateYaml(evalConfig, scheduleLabels)}</pre>
            </div>
          </div>
        </div>

        <div className="right-panel-cta review-actions">
          <button className="btn-secondary" onClick={onCancel}>Cancel</button>
          {createdEvalId ? (
            <>
              <button className="btn-primary" onClick={handleRunEval} disabled={isRunning || !evalConfig.modelEndpoint}>
                {isRunning ? '⏳ Running...' : '▶️ Run Eval'}
              </button>
              <button className="btn-secondary" onClick={() => onComplete(evalConfig)}>
                ✅ Done
              </button>
            </>
          ) : Object.keys(getPhaseValidation()).length > 0 ? (
            <button className="btn-primary" disabled title="Complete all sections before creating">
              🚀 Create Eval
            </button>
          ) : (
            <button className="btn-primary" onClick={handleCreateEval} disabled={isCreating}>
              {isCreating ? '⏳ Creating...' : '🚀 Create Eval'}
            </button>
          )}
        </div>
      </div>
    );
  };

  // Determine which right panel to show
  const renderRightPanel = () => {
    switch (phase) {
      case PHASES.REFINE:
        return renderRefinePanel();
      case PHASES.METRICS:
        return renderMetricsPanel();
      case PHASES.SAMPLE_DATA:
        return renderSampleDataPanel();
      case PHASES.CONNECT:
        return renderConnectPanel();
      case PHASES.MANAGE:
        return renderManagePanel();
      case PHASES.REVIEW:
        return renderFinalReview();
      default:
        return null;
    }
  };

  const validation = getPhaseValidation();
  const hasRightPanel = phase !== PHASES.OBJECTIVE;

  const pillClass = (pillKey, phases) => {
    const isActive = phases.includes(phase);
    const isIncomplete = validation[pillKey];

    // Map pill to its representative phase index for comparison
    const pillPhaseIndex = {
      describe: phaseIndex(PHASES.OBJECTIVE),
      metrics: phaseIndex(PHASES.METRICS),
      data: phaseIndex(PHASES.SAMPLE_DATA),
      connect: phaseIndex(PHASES.CONNECT),
      manage: phaseIndex(PHASES.MANAGE),
      review: phaseIndex(PHASES.REVIEW),
    }[pillKey];

    const highestIdx = phaseIndex(highestPhase);
    const wasReached = pillPhaseIndex <= highestIdx;

    let cls = 'phase-step clickable';
    if (isActive) cls += ' active';

    if (isIncomplete && wasReached && !isActive) {
      // Skipped: user moved past this section without completing it
      cls += ' incomplete';
    } else if (!isIncomplete && wasReached && !isActive) {
      // Completed: section has valid inputs
      cls += ' completed';
    }
    // Otherwise: grey default (not yet reached, or active)
    return cls;
  };

  return (
    <div className="guided-eval">
      <div className="guided-eval-header">
        <h2><ChatAvatar size={22} /> Guided Eval Builder</h2>
        <div className="guided-phase-indicator">
          <span className={pillClass('describe', PILL_PHASES.describe)} onClick={() => navigateToPhase('describe')}>1. Objective</span>
          <span className="phase-arrow">→</span>
          <span className={pillClass('metrics', PILL_PHASES.metrics)} onClick={() => navigateToPhase('metrics')}>2. Metrics</span>
          <span className="phase-arrow">→</span>
          <span className={pillClass('data', PILL_PHASES.data)} onClick={() => navigateToPhase('data')}>3. Data</span>
          <span className="phase-arrow">→</span>
          <span className={pillClass('connect', PILL_PHASES.connect)} onClick={() => navigateToPhase('connect')}>4. Connect</span>
          <span className="phase-arrow">→</span>
          <span className={pillClass('manage', PILL_PHASES.manage)} onClick={() => navigateToPhase('manage')}>5. Manage</span>
          <span className="phase-arrow">→</span>
          <span className={pillClass('review', [])} onClick={() => navigateToPhase('review')}>6. Review</span>
        </div>
        <button className="btn-secondary guided-cancel-btn" onClick={onCancel}>✕</button>
      </div>

      <div className={`guided-eval-body ${hasRightPanel ? 'split-layout' : 'single-layout'}`}>
        {renderChatPanel()}
        {renderRightPanel()}
      </div>
    </div>
  );
}

function renderInlineMarkdown(text) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

function generateYaml(config, scheduleLabels) {
  let yaml = `name: ${config.name || 'untitled_eval'}\n`;
  yaml += `team: ${config.team || 'TBD'}\n`;
  if (config.owner) {
    yaml += `owner: ${config.owner.username}\n`;
  }
  yaml += `description: "${config.description || ''}"\n\n`;
  yaml += `metrics:\n`;
  (config.metrics || []).forEach(m => {
    yaml += `  - field: ${m.field}\n`;
    yaml += `    measurement: [${(m.measurement || []).join(', ')}]\n`;
    yaml += `    description: "${m.description || ''}"\n`;
    yaml += `    baseline: ${m.thresholds?.baseline || 80}%\n`;
    yaml += `    target: ${m.thresholds?.target || 95}%\n`;
  });
  yaml += `\ndataset:\n`;
  yaml += `  source: ${config.datasetSource}\n`;
  yaml += `  size: ${config.datasetSize} examples\n`;
  if (config.sampleData?.length > 0) {
    yaml += `  sample_entries: ${config.sampleData.length}\n`;
  }
  yaml += `\nmodel_connection:\n`;
  yaml += `  endpoint: ${config.modelEndpoint || 'TBD'}\n`;
  yaml += `  auth: ${config.modelAuthType}\n`;
  yaml += `  request_format: ${config.modelRequestFormat}\n`;
  yaml += `  response_path: ${config.modelResponsePath}\n`;
  if (config.prodLogEnabled) {
    yaml += `\nproduction_monitoring:\n`;
    yaml += `  source: ${config.prodLogSource}\n`;
    yaml += `  table: ${config.prodLogTable}\n`;
    yaml += `  input_column: ${config.prodLogInputColumn}\n`;
    yaml += `  output_column: ${config.prodLogOutputColumn}\n`;
    yaml += `  timestamp_column: ${config.prodLogTimestampColumn}\n`;
    yaml += `  sample_rate: ${config.prodLogSampleRate}%\n`;
  }
  yaml += `\nautomation:\n`;
  yaml += `  schedule: ${scheduleLabels[config.schedule] || config.schedule}\n`;
  yaml += `  alert_on_regression: ${config.alertOnRegression}\n`;
  if (config.alertChannel) {
    yaml += `  alert_channel: ${config.alertChannel}\n`;
  }
  return yaml;
}

export default GuidedEval;
