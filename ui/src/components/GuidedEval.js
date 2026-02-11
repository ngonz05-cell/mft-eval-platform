import { useState, useRef, useEffect, useCallback } from 'react';
import { sendChatMessage, generateMetrics, checkHealth } from '../api';

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
  AUTOMATION: 'automation',
  REVIEW: 'review',
};

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

// Returns { metrics, rationale } — rationale explains WHY each metric/threshold was chosen
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

// Generates a refined prompt that's more specific and eval-friendly
function generateRefinedPrompt(userMessage) {
  const desc = userMessage.toLowerCase();
  const parts = [];

  // Identify what the product does
  if (desc.includes('extract') || desc.includes('parse')) {
    parts.push('extracts structured data from unstructured inputs');
  } else if (desc.includes('classif') || desc.includes('detect') || desc.includes('categor')) {
    parts.push('classifies or categorizes inputs');
  } else if (desc.includes('generat') || desc.includes('creat') || desc.includes('write') || desc.includes('stor')) {
    parts.push('generates content or text');
  } else if (desc.includes('summar')) {
    parts.push('summarizes information');
  } else if (desc.includes('respond') || desc.includes('answer') || desc.includes('chat')) {
    parts.push('responds to user queries');
  } else {
    parts.push('processes inputs and produces outputs');
  }

  // Identify the domain
  let domain = '';
  if (desc.includes('payment') || desc.includes('transaction') || desc.includes('money') || desc.includes('dollar')) domain = 'in the payments/financial domain';
  else if (desc.includes('fraud') || desc.includes('risk')) domain = 'for fraud/risk detection';
  else if (desc.includes('child') || desc.includes('kid') || desc.includes('age') || desc.includes('stor')) domain = 'for a children/family audience';
  else if (desc.includes('customer') || desc.includes('support')) domain = 'for customer support';
  else if (desc.includes('compli') || desc.includes('legal') || desc.includes('regulat')) domain = 'in a compliance/regulatory context';
  if (domain) parts.push(domain);

  // Identify success criteria hints
  const successCriteria = [];
  if (desc.includes('accur')) successCriteria.push('accuracy of outputs');
  if (desc.includes('safe') || desc.includes('appropriate')) successCriteria.push('content safety and appropriateness');
  if (desc.includes('quality')) successCriteria.push('output quality');
  if (desc.includes('fast') || desc.includes('latency') || desc.includes('speed')) successCriteria.push('response speed/latency');
  if (desc.includes('correct')) successCriteria.push('correctness of results');

  // Build refined prompt
  let refined = userMessage;

  // Only refine if there's room for improvement
  const isAlreadyDetailed = userMessage.length > 100 && successCriteria.length >= 2;
  if (!isAlreadyDetailed) {
    refined = userMessage.trim();
    if (!refined.endsWith('.')) refined += '.';

    // Add specificity about what to measure if not already mentioned
    if (!desc.includes('measure') && !desc.includes('eval') && !desc.includes('metric') && !desc.includes('accur')) {
      refined += ' I want to measure the accuracy and quality of its outputs.';
    }

    // Add specificity about failure modes if not mentioned
    if (!desc.includes('wrong') && !desc.includes('fail') && !desc.includes('error') && !desc.includes('miss') && !desc.includes('incorrect')) {
      if (desc.includes('extract') || desc.includes('parse')) {
        refined += ' Key failure modes include extracting wrong values, missing fields, or incorrect formatting.';
      } else if (desc.includes('classif') || desc.includes('detect')) {
        refined += ' Key failure modes include false positives, false negatives, and misclassifications.';
      } else if (desc.includes('generat') || desc.includes('creat') || desc.includes('stor')) {
        refined += ' Key failure modes include factual inaccuracies, quality issues, or inappropriate content.';
      } else if (desc.includes('safe') || desc.includes('child') || desc.includes('kid')) {
        refined += ' Key failure modes include generating unsafe, inappropriate, or age-inappropriate content.';
      }
    }
  }

  return refined;
}

// Generate clarifying questions based on what's missing from the description
function generateClarifyingQuestions(userMessage) {
  const desc = userMessage.toLowerCase();
  const questions = [];

  // Check for missing specifics
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

  // Domain-specific questions
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

  return questions.slice(0, 3); // Max 3 clarifying questions
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

    // User gave a real description — suggest a refined prompt + ask clarifying questions
    const refinedPrompt = generateRefinedPrompt(userMessage);
    const questions = generateClarifyingQuestions(userMessage);
    const isAlreadyGood = refinedPrompt === userMessage && questions.length === 0;

    if (isAlreadyGood) {
      // Description is already detailed — skip refinement, go to metrics
      const { metrics, rationale } = suggestMetricsWithRationale(userMessage);
      const suggestedName = generateEvalName(userMessage);
      return {
        text: `This is a really detailed description — nice work! I have everything I need to suggest metrics.\n\n👇 **Review the suggested metrics below** — I've included explanations for why each was chosen. Everything is editable.`,
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

    if (questions.length > 0) {
      responseText += `Before I suggest metrics, I have a few clarifying questions:\n\n`;
      questions.forEach((q, i) => {
        responseText += `${i + 1}. ${q}\n`;
      });
      responseText += `\n`;
    }

    if (refinedPrompt !== userMessage) {
      responseText += `Based on what you've told me, here's a **refined description** that will help me suggest better metrics:\n\n`;
      responseText += `👇 **Edit the refined prompt below** if anything needs adjusting, then click **"Use This & Generate Metrics"** when you're happy with it.`;
    } else {
      responseText += `👇 **Review your description below** — you can edit it to add more detail. Then click **"Use This & Generate Metrics"** when ready.`;
    }

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
    // User sent a follow-up message during the refine phase (answering clarifying questions)
    const currentPrompt = evalConfig.refinedPrompt || evalConfig.capabilityWhat || '';
    const additionalContext = userMessage;
    const combinedDescription = currentPrompt.replace(/\.$/, '') + '. ' + additionalContext;
    const newRefined = generateRefinedPrompt(combinedDescription);

    return {
      text: `Got it! I've incorporated your answers into the refined description below. Take a look and click **"Use This & Generate Metrics"** when you're ready.`,
      phase: PHASES.REFINE,
      configUpdates: {
        refinedPrompt: newRefined,
      },
    };
  }

  if (phase === PHASES.METRICS) {
    return {
      text: "I've updated the configuration based on your feedback. Take another look at the metrics below and let me know if everything looks right, or click **\"Looks Good, Continue\"** to move on to ownership and automation settings.",
      phase: PHASES.METRICS,
    };
  }

  if (phase === PHASES.AUTOMATION) {
    return {
      text: "Automation settings updated! Review the schedule and alert configuration below. When you're ready, click **\"Looks Good, Review Final Draft\"** to see the complete eval config.",
      phase: PHASES.AUTOMATION,
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
  const [phase, setPhase] = useState(PHASES.OBJECTIVE);
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: `👋 Hi! I'm here to help you create an eval for your new product/feature.\n\n**Tell me about it** — what user problem is it solving, what does it do, how do you want to measure success?\n\nThe more detail you provide, the better evals I can help you create.\n\n💡 **Example** (${example.product}):\n> ${example.example}`,
    },
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);

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
    datasetSize: 50,
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

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  useEffect(() => {
    inputRef.current?.focus();
  }, [phase]);

  // Check if API backend is available on mount
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

  // --- API-powered send (with offline fallback) ---
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
            // Skip refinement — go straight to generating metrics
            const metricsResult = await generateMetrics(userMsg, [...messages, { role: 'user', text: userMsg }]);
            const metricsData = metricsResult;
            const metrics = metricsData.metrics.map(m => ({
              field: m.field,
              measurement: m.measurement,
              description: m.description,
              thresholds: { baseline: m.baseline, target: m.target },
            }));
            const rationale = metricsData.metrics.map(m => m.rationale);

            setMessages(prev => [...prev, { role: 'assistant', text: data.message }]);
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
            setPhase(PHASES.METRICS);
          } else {
            setMessages(prev => [...prev, { role: 'assistant', text: data.message }]);
            updateConfig({
              capabilityWhat: userMsg,
              refinedPrompt: data.refined_prompt,
            });
            setPhase(PHASES.REFINE);
          }
        } else {
          // General chat response
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
        // Fall back to offline mode for this message
        const response = buildAssistantResponse(phase, userMsg, evalConfig);
        setMessages(prev => [...prev, { role: 'assistant', text: response.text }]);
        if (response.configUpdates) updateConfig(response.configUpdates);
        if (response.phase !== phase) setPhase(response.phase);
      }
    } else {
      // Offline mode — use hardcoded logic
      setTimeout(() => {
        const response = buildAssistantResponse(phase, userMsg, evalConfig);
        setMessages(prev => [...prev, { role: 'assistant', text: response.text }]);
        if (response.configUpdates) updateConfig(response.configUpdates);
        if (response.phase !== phase) setPhase(response.phase);
        setIsTyping(false);
      }, 800 + Math.random() * 600);
      return; // Early return — the setTimeout handles setIsTyping
    }

    setIsTyping(false);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // User confirms the refined prompt — generate metrics and advance
  const handleConfirmRefinedPrompt = async () => {
    const finalDescription = evalConfig.refinedPrompt || evalConfig.capabilityWhat;
    setIsTyping(true);

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
          text: metricsData.message + `\n\n👇 **Review the suggested config on the right** — I've included explanations for why each metric was chosen. Everything is editable. When you're happy, click **"Looks Good, Continue"**.`,
        }]);

        setPhase(PHASES.METRICS);
        setIsTyping(false);
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

    setMessages(prev => [...prev, {
      role: 'assistant',
      text: `Based on your refined description, I've suggested **${metrics.length} metrics** with measurement methods and thresholds.\n\n👇 **Review the suggested config on the right** — I've included explanations for why each metric was chosen to help you understand the reasoning. Everything is editable. When you're happy, click **"Looks Good, Continue"**.`,
    }]);

    setPhase(PHASES.METRICS);
    setIsTyping(false);
  };

  const handlePhaseAdvance = () => {
    if (phase === PHASES.METRICS) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: "Great! Now let's set up **ownership and automation**.\n\n- **Owner:** Defaults to you — change it if someone else should own this eval\n- **Team:** Which team does this eval belong to?\n- **Schedule:** How often should this eval run?\n- **Alerts:** Want to be notified when metrics drop below baseline?\n\n👇 Configure the settings below, or just click **\"Looks Good, Review Final Draft\"** to use the defaults.",
      }]);
      setPhase(PHASES.AUTOMATION);
    } else if (phase === PHASES.AUTOMATION) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: "🎉 **Your eval is ready for review!**\n\nI've compiled everything into a final draft below. Review each section carefully — you can still edit any field. When you're satisfied, click **\"Create Eval\"** to finalize it.",
      }]);
      setPhase(PHASES.REVIEW);
    }
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

  const renderChat = () => (
    <div className="guided-chat">
      <div className="guided-chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            {msg.role === 'assistant' && <div className="chat-avatar">🤖</div>}
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
            <div className="chat-avatar">🤖</div>
            <div className="chat-bubble typing">
              <span className="typing-dot"></span>
              <span className="typing-dot"></span>
              <span className="typing-dot"></span>
            </div>
          </div>
        )}
        <div ref={chatEndRef} />
      </div>

      {/* Refined prompt editor — shown during REFINE phase */}
      {phase === PHASES.REFINE && (
        <div className="refined-prompt-section">
          <label className="refined-prompt-label">✏️ Refined Description (edit as needed)</label>
          <textarea
            className="refined-prompt-textarea"
            value={evalConfig.refinedPrompt}
            onChange={(e) => updateConfig({ refinedPrompt: e.target.value })}
            rows={4}
          />
          <button className="btn-primary refined-prompt-confirm" onClick={handleConfirmRefinedPrompt}>
            Use This & Generate Metrics →
          </button>
        </div>
      )}

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

  const renderMetricsRationale = () => {
    const rationale = evalConfig.rationale || [];
    if (rationale.length === 0) return null;

    return (
      <div className="metrics-rationale">
        <div className="rationale-header">
          <span className="rationale-icon">💡</span>
          <h4>Why these metrics & thresholds?</h4>
        </div>
        <div className="rationale-list">
          {rationale.map((r, i) => (
            <div key={i} className="rationale-item">
              <p>{renderInlineMarkdown(r)}</p>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderMetricsEditor = () => (
    <div className="guided-config-panel">
      <div className="config-panel-header">
        <h3>📊 Suggested Metrics & Thresholds</h3>
        <p>Edit any field below. Add or remove metrics as needed.</p>
      </div>

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
            <th>Metric</th>
            <th>Measurement</th>
            <th>Description</th>
            <th>Baseline %</th>
            <th>Target %</th>
            <th></th>
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
                  type="text"
                  className="metric-desc-input"
                  value={metric.description}
                  onChange={(e) => handleMetricChange(i, 'description', e.target.value)}
                  placeholder="Describe..."
                />
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

      {renderMetricsRationale()}

      <div className="config-panel-actions">
        <button className="btn-primary" onClick={handlePhaseAdvance}>
          Looks Good, Continue →
        </button>
      </div>
    </div>
  );

  const renderAutomationEditor = () => (
    <div className="guided-config-panel">
      <div className="config-panel-header">
        <h3>⚙️ Ownership, Automation & Notifications</h3>
        <p>Set the eval owner, team, run schedule, and alert preferences.</p>
      </div>

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
        <div className="form-group">
          <label>Dataset Source</label>
          <select value={evalConfig.datasetSource} onChange={(e) => updateConfig({ datasetSource: e.target.value })}>
            <option value="csv">CSV File Upload</option>
            <option value="gsheet">Google Sheet</option>
            <option value="hive">Hive Table</option>
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

      <div className="config-panel-actions">
        <button className="btn-primary" onClick={handlePhaseAdvance}>
          Looks Good, Review Final Draft →
        </button>
      </div>
    </div>
  );

  const renderFinalReview = () => {
    const scheduleLabels = { manual: 'Manual only', daily: 'Daily (2 AM)', weekly: 'Weekly (Sundays)', on_deploy: 'On every deployment' };

    return (
      <div className="guided-config-panel guided-review">
        <div className="config-panel-header">
          <h3>📋 Final Eval Draft</h3>
          <p>Review everything below. All fields are still editable. Click "Create Eval" when ready.</p>
        </div>

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
                <th>Metric</th>
                <th>Measurement</th>
                <th>Baseline %</th>
                <th>Target %</th>
                <th></th>
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
          <h3>🔹 Ownership & Automation</h3>
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
            <div className="form-group">
              <label>Dataset Source</label>
              <select value={evalConfig.datasetSource} onChange={(e) => updateConfig({ datasetSource: e.target.value })}>
                <option value="csv">CSV File Upload</option>
                <option value="gsheet">Google Sheet</option>
                <option value="hive">Hive Table</option>
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

        <div className="config-panel-actions review-actions">
          <button className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn-primary" onClick={() => onComplete(evalConfig)}>
            🚀 Create Eval
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="guided-eval">
      <div className="guided-eval-header">
        <h2>🤖 Guided Eval Builder</h2>
        <div className="guided-phase-indicator">
          <span className={`phase-step ${[PHASES.OBJECTIVE, PHASES.REFINE].includes(phase) ? 'active' : 'completed'}`}>1. Describe</span>
          <span className="phase-arrow">→</span>
          <span className={`phase-step ${phase === PHASES.METRICS ? 'active' : [PHASES.AUTOMATION, PHASES.REVIEW].includes(phase) ? 'completed' : ''}`}>2. Metrics</span>
          <span className="phase-arrow">→</span>
          <span className={`phase-step ${phase === PHASES.AUTOMATION ? 'active' : phase === PHASES.REVIEW ? 'completed' : ''}`}>3. Ownership</span>
          <span className="phase-arrow">→</span>
          <span className={`phase-step ${phase === PHASES.REVIEW ? 'active' : ''}`}>4. Review</span>
        </div>
        <button className="btn-secondary guided-cancel-btn" onClick={onCancel}>✕</button>
      </div>

      <div className="guided-eval-body">
        {renderChat()}
        {phase === PHASES.METRICS && renderMetricsEditor()}
        {phase === PHASES.AUTOMATION && renderAutomationEditor()}
        {phase === PHASES.REVIEW && renderFinalReview()}
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
  yaml += `\nautomation:\n`;
  yaml += `  schedule: ${scheduleLabels[config.schedule] || config.schedule}\n`;
  yaml += `  alert_on_regression: ${config.alertOnRegression}\n`;
  if (config.alertChannel) {
    yaml += `  alert_channel: ${config.alertChannel}\n`;
  }
  return yaml;
}

export default GuidedEval;
