# QualiAI

AI-Powered Testing Agent - Describe tests in natural language; AI executes and generates reports.

```
$ quali run "Test login page: enter correct username and password, verify successful login"
QualiAI test starting

Generated 5 test steps:
  [1] navigate: Open login page
  [2] type: Enter username
  [3] type: Enter password
  [4] click: Click login button
  [5] assert: Verify login success

Executing...
Result: 5/5 passed (0 failed)
Report: reports/login_test.html
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run a test
python3 -m cli.main run "Test search functionality" --url https://example.com

# Replay an existing scenario
python3 -m cli.main replay scenarios/demo/login.json
```

## Architecture

```
User Input: quali run "Test login page"
    |
    v
Planner -- LLM decomposes natural language into executable test steps
    |
    v
Executor -- Playwright executes steps, screenshots each one
    |
    v
Asserter -- AI determines pass/fail per step (Phase 2)
    |
    v
Reporter -- Generates HTML report with screenshots and results
```

## Project Structure

```
quali-ai/
├── cli/main.py       CLI entry point
├── core/
│   ├── planner.py    AI test planner
│   ├── executor.py   Playwright executor + self-healing selectors
│   ├── asserter.py   AI assertion analysis (Phase 2)
│   ├── reporter.py   HTML report generator
│   ├── adb_controller.py   Android ADB device control
│   ├── adb_executor.py     Android test executor
│   └── vision_analyzer.py  AI vision analysis for mobile
├── scenarios/        Saved test scenarios
├── web/              WebUI (Phase 4)
└── reports/          Test report output
```

## Core Features

- **Natural language driven**: Describe test scenarios in plain language; AI automatically decomposes them into executable steps
- **AI assertions**: Screenshot + DOM composite analysis auto-determines test pass/fail
- **Self-healing selectors**: When page UI changes, AI auto-repairs broken CSS selectors
- **Multi-platform**: Web (Playwright) and Android (ADB) support
- **HTML reports**: Per-step screenshots, execution logs, and AI analysis results
- **Scenario record/replay**: Save test scenarios for repeat execution
- **Open source**: Free to use, modify, and self-host

## Roadmap

- [x] Phase 1: CLI + Planner + Executor + Reporter
- [x] Phase 2: AI assertions + self-healing selectors
- [x] Phase 3: Android ADB support
  - ADB device control (tap/type/swipe/screenshot)
  - AI vision analysis (screenshot-based element detection)
  - Command: `quali android "Test login" --app com.example.app`
- [ ] Phase 4: WebUI management interface

## Competitive Landscape

QualiAI is an open-source AI-native testing agent. For a detailed comparison with Selenium, Playwright, Cypress, Applitools, Mabl, Testim, and Diffblue, see [docs/competitive-analysis.md](docs/competitive-analysis.md).

Key differentiators:
- **Open-source**: Free self-hosted alternative to proprietary SaaS testing platforms
- **AI-native from day one**: Built around LLM-based planning, assertion, and self-healing, not retrofitted
- **Multi-platform testing**: Web (Playwright) and Android (ADB) in a single tool
- **Natural language entry point**: No scripting language required

## License

MIT
