# 🤝 Contributing to FraudShield Real-Time

First off, thank you for considering contributing to **FraudShield Real-Time**! It's contributions like yours that make FraudShield an open, enterprise-grade, sub-millisecond fraud prevention engine.

---

## 📜 Table of Contents

1. [Code of Conduct](#-code-of-conduct)
2. [How Can I Contribute?](#-how-can-i-contribute)
   - [Reporting Bugs](#reporting-bugs)
   - [Suggesting Enhancements](#suggesting-enhancements)
   - [Pull Requests](#pull-requests)
3. [Development Workflow](#-development-workflow)
   - [Branch Naming Conventions](#branch-naming-conventions)
   - [Code Style & Formatting](#code-style--formatting)
   - [Running Tests](#running-tests)
4. [Pull Request Checklist](#-pull-request-checklist)
5. [Community & Support](#-community--support)

---

## 📜 Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please be respectful, professional, and constructive in all communications and code reviews.

---

## 💡 How Can I Contribute?

### Reporting Bugs

Before creating a bug report, please check the [existing issues](https://github.com/Shweta-Mishra-ai/realtime-fraud-pathway/issues) to avoid duplicates.

When filing a bug report, please include:
- A clear and descriptive title.
- Steps to reproduce the behavior.
- Expected behavior vs. actual behavior.
- Operating System, Python version, Node.js version, and relevant error logs/tracebacks.

### Suggesting Enhancements

Feature requests are always welcome! Please outline:
- The problem your proposal solves.
- Proposed implementation details or API adjustments.
- Impact on performance, real-time latency (<1ms), or streaming capabilities.

---

## 🛠️ Development Workflow

### 1. Fork & Clone
```bash
git clone https://github.com/Shweta-Mishra-ai/realtime-fraud-pathway.git
cd realtime-fraud-pathway
```

### 2. Create a Feature Branch
Use descriptive branch names with appropriate prefixes:
- `feat/add-new-rule-engine`
- `fix/websocket-connection-timeout`
- `docs/update-setup-guide`
- `refactor/pathway-pipeline-aggregator`

```bash
git checkout -b feat/your-feature-name
```

### 3. Setup Virtual Environment
```bash
# Python Backend Environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Web Frontend Environment
cd apps/web
npm install
```

---

## 🎨 Code Style & Formatting

We enforce strict formatting and linting rules across Python and Next.js codebases to maintain high code quality.

### Python Backend Standards
- **Formatter**: `black` (line length: 100)
- **Linter**: `ruff`

Run formatting before committing:
```bash
cd apps/api
black src/ config/ tests/ --line-length=100
ruff check src/ config/ tests/ --select=E,W,F --ignore=E501
```

### Frontend TypeScript Standards
- **Linter**: `eslint`
- **Formatter**: `prettier`

Run frontend validation:
```bash
cd apps/web
npx tsc --noEmit
npm run lint
```

---

## 🧪 Running Tests

Ensure all automated tests pass before opening a Pull Request.

```bash
# Python Backend Unit & Integration Tests (178+ tests)
python apps/api/run_tests.py
pytest apps/api/tests

# Next.js Production Build Test
cd apps/web
npm run build
```

---

## 📋 Pull Request Checklist

Before submitting your PR, make sure you have completed the following:

- [ ] Formatted Python code using `black` (0 `ruff` errors).
- [ ] Next.js app compiles without TypeScript errors (`npm run build`).
- [ ] Added or updated unit tests covering new features/fixes.
- [ ] Verified system evaluation latency remains sub-millisecond (<1ms).
- [ ] Updated documentation (`README.md`, `SETUP_GUIDE.md`) if necessary.
- [ ] Provided a clear PR title and descriptive body explaining changes.

---

## 🌟 Support & Feedback

If you find FraudShield helpful, don't forget to **Give a Star ⭐** on GitHub!

For questions or discussions, feel free to open a [GitHub Issue](https://github.com/Shweta-Mishra-ai/realtime-fraud-pathway/issues).
