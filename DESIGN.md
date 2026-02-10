# MFT Eval Platform - Design Document

## Vision
A unified platform that enables anyone in Meta Fintech (PM/ENG/DS) to create, run, and monitor evaluations for LLM/Agent-powered features, feeding into an MFT-wide dashboard for cross-team visibility.

---

## Core Principles (from Reference Doc)

1. **"Evals are your PRD"** - If you can't write the eval, the PRD isn't done
2. **Enable Hill-Climbing** - Make a change → Measure → Keep what helps → Repeat
3. **Start Simple** - 50-100 examples, binary pass/fail, iterate from there
4. **Automate Everything** - If it's not automated, it's not an eval
5. **Track Over Time** - Scores, versions, regressions, coverage

---

## User Personas & Needs

| Persona | Primary Need | Interface Preference |
|---------|-------------|---------------------|
| **PM** | Define what "good" looks like, set thresholds, track progress | Web UI, templates |
| **Data Scientist** | Create datasets, define scoring functions, analyze results | Notebooks, SQL |
| **Engineer** | Automate runs, integrate with CI, debug failures | CLI, API, code |
| **Leadership** | Cross-team visibility, coverage gaps, trends | Dashboard |

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MFT Eval Platform                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐ │
│  │   Web UI     │  │  Bento       │  │    CLI       │  │      API         │ │
│  │  (PM/DS)     │  │  Notebooks   │  │   (Eng)      │  │   (Automation)   │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘ │
│         │                 │                 │                    │          │
│         └─────────────────┴─────────────────┴────────────────────┘          │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         Eval Definition Layer                           ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │ Eval Config │  │  Datasets   │  │   Scorers   │  │   Thresholds    │ ││
│  │  │   (YAML)    │  │  (Hive/GCS) │  │  (Python)   │  │   & Baselines   │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                         Execution Engine                                 ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │  Scheduler  │  │  Runner     │  │  Graders    │  │   Result Store  │ ││
│  │  │  (Cron/CI)  │  │  (Batch)    │  │  (LLM/Det.) │  │   (Hive/Scuba)  │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                      MFT Eval Dashboard (Unidash)                       ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │  Coverage   │  │  Scores &   │  │ Regressions │  │   Team Views    │ ││
│  │  │   Matrix    │  │   Trends    │  │  & Alerts   │  │   & Ownership   │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Model

### Eval Definition (YAML Config)

```yaml
# eval_config.yaml
name: payment_metadata_extraction
version: "1.2.0"
team: payments_platform
owner:
  pm: "@nategonzalez"
  eng: "@engineer_oncall"

description: |
  Measures accuracy of AI system extracting structured payment data
  from raw transaction descriptions and receipts.

capability:
  what: "Extract payment metadata (amount, currency, date, merchant, etc.)"
  why: "Enable automated dispute resolution and reconciliation"

dataset:
  source: hive://mft_evals/payment_extraction_v2
  size: 3000
  split:
    validation: 0.7
    test: 0.3
  refresh_schedule: quarterly

expected_output:
  schema:
    transaction_id: string
    amount: float
    currency: string  # ISO 4217
    date: date
    merchant: string
    payment_method: enum[card, ach, wire, crypto]

scoring:
  primary_metric: weighted_score
  metrics:
    - name: full_match
      type: exact_match
      weight: 0.30
    - name: amount_f1
      type: f1_score
      field: amount
      weight: 0.25
    - name: date_accuracy
      type: exact_match
      field: date
      tolerance: 0_days
      weight: 0.20
    - name: currency_f1
      type: f1_score
      field: currency
      weight: 0.15
    - name: merchant_f1
      type: token_f1
      field: merchant
      weight: 0.10

thresholds:
  baseline:
    weighted_score: 0.85
    amount_f1: 0.92
    date_accuracy: 0.90
  target:
    weighted_score: 0.93
    amount_f1: 0.96
    date_accuracy: 0.95
  blocking: true  # Blocks deploy if below baseline

automation:
  schedule: "0 2 * * *"  # Nightly at 2am
  ci_integration: true
  alert_on_regression: true
  alert_channel: "#mft-ai-alerts"

tags:
  - payments
  - extraction
  - production
```

### Eval Run Result

```python
@dataclass
class EvalResult:
    eval_name: str
    eval_version: str
    run_id: str
    timestamp: datetime

    # What was evaluated
    model_version: str
    prompt_version: str
    config_hash: str

    # Scores
    metrics: Dict[str, float]
    primary_score: float

    # Thresholds
    passed_baseline: bool
    passed_target: bool

    # Details
    num_examples: int
    failures: List[FailureCase]

    # Comparison
    delta_vs_previous: Dict[str, float]
    regression_detected: bool
```

---

## Key Components

### 1. Eval Registry (Central Catalog)

All evals registered in a central catalog with:
- Searchable metadata (team, tags, capability)
- Version history
- Ownership and contacts
- Coverage tracking (which AI features have evals?)

```sql
-- Hive table: mft_evals.eval_registry
CREATE TABLE eval_registry (
    eval_id STRING,
    name STRING,
    version STRING,
    team STRING,
    owner_pm STRING,
    owner_eng STRING,
    capability_description STRING,
    dataset_location STRING,
    created_at TIMESTAMP,
    last_run_at TIMESTAMP,
    last_score DOUBLE,
    status STRING,  -- active, deprecated, draft
    tags ARRAY<STRING>
)
```

### 2. Dataset Management

Support multiple dataset sources:
- **Hive tables** - For large, production-sampled datasets
- **Google Sheets** - For quick PM-created test cases
- **CSV uploads** - For ad-hoc testing
- **Synthetic generation** - Templates for generating test cases

Dataset requirements:
- Must be anonymized (no PII/UII)
- Versioned and immutable
- Includes ground truth labels
- Tracks lineage (where did examples come from?)

### 3. Scorer Library

Pre-built scorers for common patterns:

| Scorer | Use Case | Example |
|--------|----------|---------|
| `ExactMatch` | IDs, enums | Transaction ID matches |
| `F1Score` | Precision/recall balance | Amount extraction |
| `TokenF1` | Fuzzy string matching | Merchant name variations |
| `NumericTolerance` | Approximate numbers | Amount within $0.01 |
| `DateMatch` | Date parsing | ±0 days tolerance |
| `LLMJudge` | Subjective quality | Response helpfulness |
| `BinaryPassFail` | Simple checks | Valid JSON output |
| `CompositeScore` | Weighted combination | Overall quality score |

### 4. Execution Engine

Leverages existing Meta infrastructure:
- **ScoreTRON** for batch evaluation runs
- **MetaGen** for generation + evaluation
- **AIX** for experiment tracking
- **Chronos** for scheduling

### 5. MFT Dashboard (Unidash)

Central visibility for all MFT evals:

**Views:**

1. **Coverage Matrix**
   - All AI features vs. eval status
   - Red/Yellow/Green for coverage gaps
   - Drill down to team/product level

2. **Scores & Trends**
   - Time series of all eval scores
   - Filter by team, tag, product
   - Compare across model versions

3. **Regression Alerts**
   - Real-time regression detection
   - Links to failing runs
   - Auto-assign to owners

4. **Team Leaderboard**
   - Eval coverage by team
   - Improvement velocity
   - Quality scores

---

## User Workflows

### Workflow 1: PM Creates New Eval (Web UI)

```
1. PM opens MFT Eval Platform → "Create New Eval"
2. Fills in template:
   - Name, description, capability
   - Uploads dataset (CSV or Google Sheet link)
   - Selects scoring method from dropdown
   - Sets thresholds
   - Assigns engineering owner
3. Platform validates config and dataset
4. PM clicks "Run Test Eval" → sees initial scores
5. PM refines thresholds based on baseline
6. PM clicks "Activate" → Eval goes live
7. Eval appears on MFT Dashboard
```

### Workflow 2: Engineer Automates Eval (CLI/Code)

```python
from mft_evals import Eval, Dataset, Scorer

# Define eval in code
eval = Eval(
    name="transaction_classifier",
    dataset=Dataset.from_hive("mft_evals.txn_classifier_v3"),
    model=TransactionClassifier(model_id="llama-3-70b"),
    scorers=[
        Scorer.accuracy(field="category"),
        Scorer.f1(field="category", average="macro"),
    ],
    thresholds={"accuracy": 0.95, "macro_f1": 0.90}
)

# Run locally
results = eval.run()
print(results.summary())

# Register for automated runs
eval.register(
    schedule="nightly",
    ci_blocking=True,
    alert_channel="#payments-ai"
)
```

### Workflow 3: DS Analyzes Results (Notebook)

```python
# In Bento notebook
from mft_evals import EvalResults

# Load recent runs
results = EvalResults.load(
    eval_name="payment_metadata_extraction",
    last_n_runs=30
)

# Plot trends
results.plot_metrics_over_time()

# Analyze failures
failures = results.get_failures(min_severity="high")
failures.to_dataframe().display()

# Compare model versions
results.compare(
    baseline="llama-3-70b-v1",
    candidate="llama-3-70b-v2"
)
```

---

## Integration with Existing Meta Infra

| Component | Meta Tool | Integration |
|-----------|-----------|-------------|
| Eval Execution | ScoreTRON | Wrap ScoreTRON with MFT-specific defaults |
| Experiment Tracking | AIX + MLHub | Auto-log all runs to AIX |
| Scheduling | Chronos | Cron jobs for nightly runs |
| Dataset Storage | Hive | Standard MFT namespace |
| Dashboard | Unidash | Custom MFT eval dashboard |
| Alerting | Workplace + OpsGenie | Regression notifications |
| CI Integration | Sandcastle | Pre-commit eval gates |

---

## Implementation Phases (Hybrid Approach)

### Phase 1: Foundation (Weeks 1-4)
**Goal: Get first eval running end-to-end using existing platforms**

- [ ] **Platform Selection**: Evaluate MetaGen vs EvalHub for primary orchestration
- [ ] **Hive Setup**: Create `mft_evals` namespace with standard schemas
- [ ] **First Pilot Eval**: Implement one eval using MetaGen + MUTE judges
- [ ] **Custom Judges**: Build 2 MFT-specific judges (PaymentAmount, Currency)
- [ ] **Basic Dashboard**: Create simple Unidash with pilot eval scores
- [ ] **Simple Eval Template**: Python-based template matching reference doc

### Phase 2: Integration (Weeks 5-8)
**Goal: Integrate MAIBA tool calling and human validation**

- [ ] **MAIBA Integration**: Configure ToolCallingEvaluator for fintech tools
- [ ] **GALA Workflow**: Set up golden label workflow for edge cases
- [ ] **Judge Registry**: Build unified registry for all judge types
- [ ] **Automation**: Chronos scheduling for nightly runs
- [ ] **Alerting**: Regression detection with Workplace notifications

### Phase 3: PM Enablement (Weeks 9-12)
**Goal: Enable non-engineers to create and manage evals**

- [ ] **Eval Templates**: Pre-built configs for common fintech scenarios
- [ ] **Google Sheets Integration**: Dataset creation from spreadsheets
- [ ] **Web UI**: Simple form for creating evals (leverage MetaGen UI)
- [ ] **Documentation**: Onboarding guide and video tutorials
- [ ] **Coverage Dashboard**: Matrix view of all MFT AI features vs eval status

### Phase 4: Scale & Governance (Weeks 13-16)
**Goal: Org-wide adoption with governance**

- [ ] **All Teams Onboarded**: Each MFT team has at least one eval
- [ ] **Quarterly Audit**: Automated eval health checks
- [ ] **Research Handoff**: Standard format for sharing with core AI
- [ ] **Compliance Reporting**: Audit-ready eval documentation
- [ ] **Cost Tracking**: GPU/compute attribution per team

---

## Success Metrics

| Metric | Baseline | 3-Month Target | 6-Month Target |
|--------|----------|----------------|----------------|
| Eval coverage (% of AI features) | 0% | 50% | 90% |
| Evals created | 0 | 15 | 40 |
| Teams with active evals | 0 | 5 | 10 |
| Regressions caught before prod | 0 | 10+ | 30+ |
| Avg time to create new eval | N/A | < 2 hours | < 30 min |

---

## Open Questions

1. **Authentication & ACLs** - Who can create/modify evals? Team-level permissions?
2. **Data sensitivity** - How to handle payment data in eval datasets? Anonymization requirements?
3. **Cross-team evals** - How to handle evals that span multiple teams?
4. **Research handoff** - Standard format for sharing evals with core AI teams?
5. **Cost tracking** - How to attribute GPU/compute costs for eval runs?

---

## Existing Meta Eval Platforms to Leverage

Based on comprehensive research, here are the key eval platforms across Meta that MFT can leverage or learn from:

### Tier 1: Primary Platforms (Recommended for MFT)

| Platform | Team/Org | Why It's Relevant | Reusability |
|----------|----------|-------------------|-------------|
| **EvalHub** | ARC + Social AI Foundation | DAG-native workflow engine, multi-modal support, human-in-the-loop, central catalog | ★★★★★ |
| **MUTE** | Llama Evals Platform (MSL) | 500+ pre-built judges, production monitoring, cross-team reporting | ★★★★★ |
| **MetaGen Evaluations** | MetaGen/MSL Infra | UI-based bulk generation, scorecards, Data Explorer, Hive integration | ★★★★★ |
| **Sales AI Eval Platform** | Monetization / Sales AI | Quality Score design, human eval via QMS, golden sets, continuous monitoring | ★★★★★ |
| **MAIBA Framework** | Monetization | Business assistant evals, tool calling evaluation library | ★★★★★ |

### Tier 2: Specialized Frameworks

| Platform | Team/Org | Key Capability | Best For |
|----------|----------|----------------|----------|
| **Jellybean** | MSL Infra | Successor to PromptForge, A/B prompt comparison, multi-modal | Prompt engineering |
| **EvalHawk** | Enterprise Products / Metamate | Codeless agent evals, agentic traces, Dumont integration | Agent evals |
| **Ads AI Auto Eval** | Ads AI / Monetization | Modular Judge Framework, tiered evaluation (unit → E2E) | Complex pipelines |
| **Meta Inspect** | MSL / FAIR | OSS Inspect wrapper, VS Code extension, flexible | Custom evals |
| **GALA** | Data Labeling Infra | 92% agreement with humans, AI QA, MetaGen integration | Human annotation |

### Tier 3: Code & Libraries to Reuse

| Library | Location | What It Does |
|---------|----------|--------------|
| **Tool Calling Evaluator** | MAIBA / AI4C | Handles complex tool parameters, sequential calls, scoring weights |
| **ScoreTron Graders** | `fbcode/ai_productivity/benchmarks/` | BLEU, ROUGE, SQL matching, LLM graders |
| **Ads Agent Evaluation** | `fbcode/ai_productivity/benchmarks/ads/agent_evaluation` | Modular judges, rubric-based scoring |
| **LLM Evaluator** | `fbcode/ads_ai/text/evaluator/llm_evaluator.py` | LLM-as-judge implementation |
| **Consumption AI Eval** | `fbcode/consumption_ai/evaluation/llm/` | Agent graders, model configs |

### Platform Comparison Matrix

| Capability | EvalHub | MUTE | MetaGen | Sales AI | Build Custom |
|------------|---------|------|---------|----------|--------------|
| **UI for non-engineers** | ✅ | ⚠️ | ✅ | ⚠️ | 🔧 |
| **500+ judges** | ⚠️ | ✅ | ⚠️ | ❌ | ❌ |
| **Tool calling evals** | ✅ | ⚠️ | ❌ | ✅ | 🔧 |
| **Human-in-the-loop** | ✅ | ⚠️ | ⚠️ | ✅ | 🔧 |
| **Dashboard/monitoring** | ✅ | ✅ | ✅ | ✅ | 🔧 |
| **CI/CD integration** | ✅ | ✅ | ✅ | ⚠️ | 🔧 |
| **Custom scorers** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Fintech-specific** | ❌ | ❌ | ❌ | ❌ | ✅ |

*Legend: ✅ = Full support, ⚠️ = Partial/Limited, ❌ = Not available, 🔧 = Needs building*

### Recommended Approach: Hybrid Architecture

Rather than building from scratch, MFT should adopt a **layered hybrid architecture**:

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        MFT EVAL PLATFORM (Hybrid Architecture)                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ LAYER 4: MFT-SPECIFIC                                                        ││
│  │ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────────┐ ││
│  │ │ Fintech       │ │ PM Templates  │ │ MFT Dashboard │ │ Compliance        │ ││
│  │ │ Scorers       │ │ & Onboarding  │ │ (Unidash)     │ │ Reporting         │ ││
│  │ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                         │                                        │
│                                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ LAYER 3: ORCHESTRATION (Choose One)                                         ││
│  │ ┌───────────────────────────────┐  ┌───────────────────────────────────────┐││
│  │ │ MetaGen Evaluations           │  │ EvalHub (For Complex DAG Workflows)   │││
│  │ │ • UI-driven bulk eval         │  │ • Multi-step evaluations              │││
│  │ │ • Scorecards & Catalog        │  │ • Product simulation                  │││
│  │ │ • Best for most MFT use cases │  │ • Complex dependencies                │││
│  │ └───────────────────────────────┘  └───────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                         │                                        │
│                                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ LAYER 2: JUDGES & EVALUATORS                                                 ││
│  │ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────────┐ ││
│  │ │ MUTE Judges   │ │ MAIBA Tool    │ │ MetaGen WWW   │ │ Custom MFT        │ ││
│  │ │ (500+ judges) │ │ Calling Eval  │ │ Evaluators    │ │ Judges            │ ││
│  │ └───────────────┘ └───────────────┘ └───────────────┘ └───────────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                         │                                        │
│                                         ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │ LAYER 1: DATA & HUMAN VALIDATION                                             ││
│  │ ┌───────────────────────────────┐  ┌───────────────────────────────────────┐││
│  │ │ Hive (Central Data Hub)       │  │ GALA (Human Annotation)               │││
│  │ │ • Datasets                    │  │ • Golden label creation               │││
│  │ │ • Results                     │  │ • Judge calibration                   │││
│  │ │ • Cross-platform aggregation  │  │ • Edge case validation                │││
│  │ └───────────────────────────────┘  └───────────────────────────────────────┘││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

#### Layer 1: Data & Human Validation

**Hive as Central Hub:**
- All datasets stored in `mft_evals.*` namespace
- Cross-platform results aggregated for unified reporting
- Versioned datasets with lineage tracking

**GALA for Human Validation:**
- Golden label creation workflow (Human Multi-Review → AI Audit → Expert Escalation)
- Judge calibration against human labels
- Continuous quality monitoring

#### Layer 2: Judges & Evaluators

**MUTE Judges (500+ available):**
- Safety judges (refusal, toxicity)
- Capability judges (QA correctness, reasoning)
- Tool calling judges
- Rubric-based multi-dimensional scoring

**MAIBA Tool Calling Evaluator:**
- Complex sequential tool calls
- Dynamic/time-dependent parameters
- Self-correction handling
- Diff score computation

**MetaGen WWW Evaluators:**
- JSON format validation
- String matching
- Response length
- LLM-as-judge

**Custom MFT Judges (to build):**
- Payment amount accuracy
- Currency handling
- Date/timezone parsing
- Compliance checks

#### Layer 3: Orchestration

**MetaGen Evaluations (Primary - for most use cases):**
- UI-driven bulk generation and evaluation
- Evaluation Catalog with versioning
- Scorecards for model comparison
- Data Explorer for results visualization
- Integration with Genie backend

**EvalHub (Secondary - for complex workflows):**
- DAG-native workflow engine
- Multi-step evaluations with dependencies
- Product simulation integration
- Human-in-the-loop via Halo

#### Layer 4: MFT-Specific

**Fintech Scorers:**
- `PaymentAmountScorer` - Validates extracted amounts
- `CurrencyScorer` - ISO 4217 compliance
- `TransactionIDScorer` - ID format validation
- `ComplianceScorer` - Regulatory checks

**PM Templates:**
- Pre-built eval configs for common fintech scenarios
- Google Sheets integration for quick dataset creation
- Guided onboarding flow

**MFT Dashboard:**
- Unidash aggregating all team evals
- Coverage matrix
- Regression alerts
- Team leaderboards

---

## Detailed Integration Patterns

### Pattern 1: Using MUTE Judges in MetaGen

```python
# Register MUTE judge as MetaGen evaluator
from gen_ai.genie_projects.mute.judges import ExpectAnswerJudge

class MUTEJudgeWrapper(MetaGenBenchmarkEvaluator):
    """Wraps a MUTE judge for use in MetaGen Evaluations"""

    def __init__(self, mute_judge_class):
        self.judge = mute_judge_class()

    async def genEvaluateImpl(self, input_data):
        # Convert MetaGen input to MUTE DataRow
        row = self._to_mute_row(input_data)
        verdict = await self.judge(row)
        return MetaGenEvaluatorOutput(
            score=verdict.value,
            rationale=verdict.rationale
        )
```

### Pattern 2: MAIBA Tool Calling in MFT Evals

```python
from mgp.framework.eval.tool_calling_eval.tool_calling_eval_utils import (
    ToolCallingEvaluator,
    ToolCallingEvaluatorConfig,
)

# Configure for fintech tool calls
mft_tool_config = ToolCallingEvaluatorConfig(
    # Ignore session metadata
    ignore_params=["session_id", "request_id", "timestamp"],

    # Handle dynamic dates in payment queries
    dynamic_params=[
        DayBeforeDateDynamicParam(
            syntax="<TRANSACTION_DATE>",
            format="%Y-%m-%d"
        )
    ],

    # Allow self-corrections (agent retries)
    ignore_all_extra_tools=True,

    # Weights for fintech - amount errors are critical
    weights={
        "extra_tool": 0.5,
        "missing_tool": 1.0,
        "incorrect_param": 1.0,  # Strict on parameters
    }
)

# Evaluate tool calls
evaluator = ToolCallingEvaluator(config=mft_tool_config)
result = await evaluator.evaluate_tool_calls(
    predicted=agent_tool_calls,
    expected=golden_tool_calls
)
```

### Pattern 3: GALA Golden Label Workflow

```
MFT Eval Run (Low Confidence Cases)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                    GALA Workflow                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. Human Multi-Review (3-5 reviewers)                       │
│     └── Stop at consensus (3/5 agreement)                    │
│                    │                                         │
│         ┌─────────┴─────────┐                                │
│         ▼                   ▼                                │
│  2a. AI Blind Audit    2b. No Consensus                      │
│      (if consensus)        └── Expert Review                 │
│         │                           │                        │
│    ┌────┴────┐                      │                        │
│    ▼         ▼                      ▼                        │
│  Agrees   Disagrees          Expert Decision                 │
│    │         │                      │                        │
│    ▼         ▼                      ▼                        │
│  ✅ Golden  Expert Review    ✅ Golden Label                  │
│    Label         │                                           │
│                  ▼                                           │
│           ✅ Golden Label                                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
    Golden Labels → Hive → Judge Calibration
```

### Pattern 4: Cross-Platform Results Aggregation

```sql
-- Unified results schema for all platforms
CREATE TABLE mft_evals.unified_results (
    -- Identifiers
    run_id STRING,
    eval_name STRING,
    eval_version STRING,

    -- Source platform
    platform STRING,  -- 'metagen', 'mute', 'evalhub', 'custom'

    -- Test case
    test_case_id STRING,
    input TEXT,
    expected_output TEXT,
    actual_output TEXT,

    -- Scores
    primary_score DOUBLE,
    metrics MAP<STRING, DOUBLE>,

    -- Metadata
    model_version STRING,
    prompt_version STRING,
    judge_name STRING,
    judge_rationale STRING,

    -- Timestamps
    created_at TIMESTAMP,
    ds STRING
)
PARTITIONED BY (ds, eval_name, platform)
```

### Pattern 5: Unified MFT Evaluation Runner

```python
class MFTHybridEvaluator:
    """
    Unified evaluation runner that orchestrates across platforms.
    Uses MetaGen for bulk eval, MUTE judges, MAIBA for tool calls,
    and GALA for human validation.
    """

    def __init__(self, eval_config: MFTEvalConfig):
        self.config = eval_config
        self.judge_registry = JudgeRegistry()
        self.metagen_client = MetaGenClient()
        self.gala_client = GALAClient()

    async def run(self, dataset_path: str) -> EvalResults:
        # 1. Load dataset
        dataset = await self.load_dataset(dataset_path)

        # 2. Run generation (if needed)
        if self.config.needs_generation:
            responses = await self.metagen_client.generate(
                dataset=dataset,
                model=self.config.model
            )
        else:
            responses = dataset  # Pre-generated

        # 3. Apply judges based on eval type
        results = []

        for judge_config in self.config.judges:
            judge = self.judge_registry.get(judge_config.name)

            if judge_config.type == "mute":
                scores = await self._run_mute_judge(judge, responses)
            elif judge_config.type == "maiba_tool":
                scores = await self._run_tool_eval(responses)
            elif judge_config.type == "metagen":
                scores = await self._run_metagen_evaluator(judge, responses)
            elif judge_config.type == "custom":
                scores = await self._run_custom_judge(judge, responses)

            results.append(scores)

        # 4. Aggregate scores
        aggregated = self._aggregate_results(results)

        # 5. Identify low-confidence cases for GALA
        low_confidence = self._filter_low_confidence(
            aggregated,
            threshold=self.config.confidence_threshold
        )

        if low_confidence and self.config.enable_human_review:
            await self.gala_client.submit_for_review(low_confidence)

        # 6. Log to Hive
        await self._log_to_hive(aggregated)

        # 7. Check thresholds
        passed = self._check_thresholds(aggregated)

        return EvalResults(
            scores=aggregated,
            passed_baseline=passed.baseline,
            passed_target=passed.target,
            low_confidence_count=len(low_confidence)
        )
```

---

## MFT-Specific Judges to Build

Based on the fintech domain, we need these custom judges:

### 1. PaymentAmountJudge

```python
class PaymentAmountJudge(mt.Judge[float]):
    """
    Evaluates accuracy of extracted payment amounts.
    Handles currency formatting, decimal precision, and edge cases.
    """

    ONCALL = "mft_ai_oncall"

    async def __call__(self, row: mt.DataRow) -> mt.Verdict[float]:
        expected = self._parse_amount(row.extra_fields["expected_amount"])
        actual = self._parse_amount(row.response[0].body)

        # Exact match required for financial data
        if expected == actual:
            return mt.Verdict(value=1.0, rationale="Amount matches exactly")

        # Check if within acceptable tolerance (e.g., rounding)
        if abs(expected - actual) < 0.01:
            return mt.Verdict(value=0.9, rationale=f"Amount within $0.01 tolerance")

        return mt.Verdict(
            value=0.0,
            rationale=f"Amount mismatch: expected {expected}, got {actual}"
        )
```

### 2. CurrencyComplianceJudge

```python
class CurrencyComplianceJudge(mt.Judge[float]):
    """
    Validates currency codes against ISO 4217 standard.
    """

    ONCALL = "mft_ai_oncall"
    ISO_4217_CODES = {"USD", "EUR", "GBP", "JPY", ...}

    async def __call__(self, row: mt.DataRow) -> mt.Verdict[float]:
        extracted_currency = self._extract_currency(row.response[0].body)

        if extracted_currency in self.ISO_4217_CODES:
            expected = row.extra_fields.get("expected_currency")
            if extracted_currency == expected:
                return mt.Verdict(value=1.0, rationale="Currency correct")
            return mt.Verdict(value=0.5, rationale="Valid currency but wrong")

        return mt.Verdict(value=0.0, rationale=f"Invalid currency: {extracted_currency}")
```

### 3. TransactionDateJudge

```python
class TransactionDateJudge(mt.Judge[float]):
    """
    Evaluates date extraction with timezone awareness.
    Critical for payment settlement timing.
    """

    ONCALL = "mft_ai_oncall"
    TOLERANCE_DAYS = 0  # Must be exact for financial transactions

    async def __call__(self, row: mt.DataRow) -> mt.Verdict[float]:
        expected_date = parse_date(row.extra_fields["expected_date"])
        actual_date = self._extract_date(row.response[0].body)

        if actual_date is None:
            return mt.Verdict(value=0.0, rationale="Could not parse date")

        diff_days = abs((expected_date - actual_date).days)

        if diff_days <= self.TOLERANCE_DAYS:
            return mt.Verdict(value=1.0, rationale="Date matches exactly")

        # Partial credit for close dates (configurable)
        if diff_days <= 1:
            return mt.Verdict(value=0.5, rationale=f"Date off by {diff_days} day(s)")

        return mt.Verdict(value=0.0, rationale=f"Date mismatch: off by {diff_days} days")
```

### 4. FraudDetectionJudge

```python
class FraudDetectionJudge(mt.Judge[float]):
    """
    Evaluates fraud classification accuracy.
    Weighted heavily towards false negatives (missed fraud).
    """

    ONCALL = "mft_ai_oncall"

    async def __call__(self, row: mt.DataRow) -> mt.Verdict[float]:
        expected_fraud = row.extra_fields["is_fraud"]
        predicted_fraud = self._extract_prediction(row.response[0].body)

        if expected_fraud == predicted_fraud:
            return mt.Verdict(value=1.0, rationale="Correct classification")

        # False negative (missed fraud) is worse than false positive
        if expected_fraud and not predicted_fraud:
            return mt.Verdict(
                value=0.0,
                rationale="CRITICAL: Missed fraud case (false negative)"
            )

        # False positive (flagged legitimate transaction)
        return mt.Verdict(
            value=0.3,
            rationale="False positive: flagged legitimate transaction"
        )
```

### Key Links

| Resource | URL |
|----------|-----|
| **EvalHub Canonical Doc** | [Google Doc](https://docs.google.com/document/d/1lICIkxxdFUKfiXkMgDJVxLGBTPmS0gDpvMRxGzK_RgM) |
| **MetaGen Evaluations** | [Static Docs](https://www.internalfb.com/intern/staticdocs/metagen/docs/evaluations/mg-evals-getting-started) |
| **Sales AI Eval Platform** | [Google Doc](https://docs.google.com/document/d/18d3PLUgfQc7m--iFuVQQ-J5OnaQyKb0iZ4dGWg5KctU) |
| **Jellybean Wiki** | [Wiki](https://www.internalfb.com/wiki/Jellybean) |
| **EvalHawk** | [Tool](https://fburl.com/eval_hawk/ua1y2qev) |
| **Sales AI Dashboard** | [Unidash](https://fburl.com/unidash/6nw963vf) |
| **GALA** | [Google Doc](https://docs.google.com/document/d/1Z_6GcbcNYm-d2F58SlvKym1wAxROXd7qNzq28_NcGko) |
| **Ads Agent Eval Code** | `fbcode/ai_productivity/benchmarks/ads/agent_evaluation` |

### Architecture Patterns from Successful Teams

#### Sales AI Quality Score Pattern
```
                    ┌─────────────────────────────────────────┐
                    │           Quality Score (0-100)          │
                    │  = Σ (rubric_weight × rubric_score)      │
                    └─────────────────────────────────────────┘
                                       ▲
                    ┌──────────────────┴──────────────────┐
                    │                                      │
            ┌───────┴───────┐                    ┌────────┴────────┐
            │   T0: LLM     │                    │   T1: Human     │
            │   Judges      │                    │   Review        │
            │  (60-90% acc) │                    │  (90-95% acc)   │
            └───────┬───────┘                    └────────┬────────┘
                    │                                      │
                    │ All samples                          │ Strategic sample
                    ▼                                      ▼
            ┌───────────────┐                    ┌─────────────────┐
            │ Routing Judge │                    │ QMS Pipeline    │
            │ Relevance     │                    │ Golden Dataset  │
            │ Factual Acc   │                    │ Calibration     │
            └───────────────┘                    └─────────────────┘
```

#### Ads AI Tiered Evaluation Pattern
```
    ┌─────────────────────────────────────────────────────────────┐
    │                    Evaluation Tiers                          │
    ├─────────────────────────────────────────────────────────────┤
    │                                                              │
    │   Tier 1: Domain Knowledge                                   │
    │   └── Does the agent understand the domain?                  │
    │                                                              │
    │   Tier 2: Unit Tool Call                                     │
    │   └── Can it invoke individual tools correctly?              │
    │                                                              │
    │   Tier 3: Optimal Chaining                                   │
    │   └── Does it chain tools in the right sequence?             │
    │                                                              │
    │   Tier 4: End-to-End Workflow                                │
    │   └── Does the full workflow produce correct results?        │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
```

---

## Next Steps

1. **Review this design with MFT AI leads**
2. **Evaluate EvalHub vs MetaGen** as primary execution engine
3. **Meet with Sales AI team** to learn from their implementation
4. **Identify 2-3 pilot teams/features** for Phase 1
5. **Set up initial infrastructure** (Hive namespace, Unidash shell)
6. **Build MVP** leveraging existing platforms
7. **Create first eval** with a pilot team

---

## Appendix A: Eval Template (Quick Start)

Copy this template to create a new eval:

```yaml
name: [your_eval_name]
version: "1.0.0"
team: [your_team]
owner:
  pm: "@your_pm"
  eng: "@your_eng"

description: |
  [What capability does this eval measure?]

capability:
  what: "[Precise behavior being tested]"
  why: "[Why this matters for users/business]"

dataset:
  source: "[hive://path or gsheet://url or upload]"
  size: [number of examples]

scoring:
  primary_metric: [accuracy/f1/custom]
  metrics:
    - name: [metric_name]
      type: [exact_match/f1/llm_judge/etc]

thresholds:
  baseline:
    [metric_name]: [value]
  target:
    [metric_name]: [value]
  blocking: [true/false]

automation:
  schedule: "[cron expression or 'manual']"
  ci_integration: [true/false]
  alert_on_regression: [true/false]
```
