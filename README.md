# MFT Eval Platform

A tool for Meta Fintech (MFT) teams to create, manage, and monitor evaluations for LLM/Agent-powered products.

## 🚀 Quick Start

### Option 1: On Demand Instance (Recommended for sharing)

1. **Connect to an OD instance:**
   ```bash
   # In VS Code @Meta, go to Home > On Demand > FBCode > Play
   # OR via CLI:
   dev connect
   # Select "FBCode" and complete Duo auth
   ```

2. **Copy the project to your OD instance:**
   ```bash
   # From your LOCAL machine:
   scp -r /Users/nategonzalez/Desktop/mft-eval-platform <your_od_hostname>:~/

   # OR use the VS Code "Open Folder" to copy
   ```

3. **Run the setup script:**
   ```bash
   cd ~/mft-eval-platform
   chmod +x setup-od.sh
   ./setup-od.sh
   ```

4. **Start the server:**
   ```bash
   cd ui && npm start
   ```

5. **Share the URL** with your team! The OD instance URL will be accessible to anyone on Meta's network.

### Option 2: Local Development

```bash
cd ui
npm install
npm start
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📁 Project Structure

```
mft-eval-platform/
├── ui/                          # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── wizard/          # Eval creation wizard steps
│   │   │   │   ├── StepBasics.js
│   │   │   │   ├── StepScoring.js
│   │   │   │   ├── StepThresholds.js
│   │   │   │   ├── StepDataset.js
│   │   │   │   ├── StepAutomation.js
│   │   │   │   └── StepReview.js
│   │   │   ├── EvalWizard.js    # Main wizard component
│   │   │   ├── EvalList.js      # Dashboard view
│   │   │   └── Header.js
│   │   ├── App.js
│   │   ├── App.css
│   │   └── index.js
│   ├── public/
│   └── package.json
├── mft_evals/                   # Python evaluation framework
│   ├── eval.py
│   ├── dataset.py
│   ├── scorers.py
│   ├── results.py
│   └── runner.py
├── examples/                    # Example eval configurations
├── templates/                   # Eval templates
├── DESIGN.md                    # Architecture documentation
├── setup-od.sh                  # OD instance setup script
└── README.md
```

---

## 🧙 Wizard Flow

The eval creation wizard guides users through 6 steps:

1. **Basics** - Name, team, sub-team, owner, what the eval measures
2. **Metrics & Scoring** - Define metrics table with measurement methods
3. **Thresholds** - Set baseline/target thresholds per metric
4. **Example Data** - Configure dataset source (CSV, Google Sheet, Hive)
5. **Automation** - Run schedule and alert settings
6. **Review & Create** - Summary and YAML export

### Key Features:
- ✅ Click on any tab to navigate directly
- ✅ Incomplete tabs marked in red
- ✅ Multi-select measurement dropdown
- ✅ Per-metric threshold configuration
- ✅ Auto-generated YAML config
- ✅ Team/Sub-team hierarchy

---

## 🌐 Deployment Options

### 1. On Demand Instance (Internal)
Best for sharing within Meta. See Quick Start above.

### 2. Static Docs / Intern Hosting
Deploy the `ui/build` folder to Meta's internal static hosting.

### 3. Vercel (External)
```bash
cd ui
npm run build
# Upload build/ folder to vercel.com
```

### 4. GitHub Pages
```bash
# Add homepage to package.json
npm run build
# Push to GitHub and enable Pages
```

---

## 📊 Measurement Options

The platform supports 8 measurement methods:

| Method | Use Case |
|--------|----------|
| Exact Match Ratio | IDs, categories, yes/no |
| Simple Pass/Fail | Binary assessments |
| Weighted Composite | Multiple metrics combined |
| Contains Check | Keyword presence |
| Numeric match (w/tolerance) | Amounts, percentages |
| Fuzzy String match | Names, addresses |
| Classification (F1 score) | Multi-class predictions |
| LLM-as-judge | Subjective quality |

---

## 🏗️ Architecture

See [DESIGN.md](./DESIGN.md) for the full architecture documentation including:
- Hybrid architecture leveraging Meta's eval infrastructure
- Integration with EvalHub, MUTE, MetaGen, MAIBA, GALA
- 4-layer system design
- Implementation phases

---

## 📝 Reference

Based on the principles from "Building AI Products: Evals Are Your PRD":
- **Evals are your PRD** - If you don't have an eval, you don't yet have an AI product
- **Start with 20-100 examples** - Minimum viable eval
- **Hill-climbing** - Iterate based on eval results
- **Deterministic over LLM judges** - When possible

---

## 👥 Team

- **Owner:** Nate Gonzalez (@nategonzalez)
- **Org:** Meta Fintech (MFT)

---

## 🤝 Contributing

1. Clone the repo
2. Create a feature branch
3. Make changes
4. Submit a diff for review
