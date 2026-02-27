<div align="center">

# claude-injection-guard

**Prompt injection protection for Claude Code agents**

*Hooks-based, two-stage, local-LLM-powered*

[![CI](https://github.com/michaelhannecke/claude-injection-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/michaelhannecke/claude-injection-guard/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://docs.astral.sh/ruff/)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

</div>

---

When Claude Code (or a sub-agent) fetches web content, that content enters the agent's context and can contain malicious instructions designed to hijack its behavior. This is called a **prompt injection attack**.

`claude-injection-guard` intercepts fetched content *before* it reaches Claude, using a fast two-stage pipeline:

1. **Stage 1 — Rule Engine** (deterministic, ~1ms): Regex-based pattern matching for known injection signatures. High-confidence hits are blocked immediately; suspicious content escalates to Stage 2.
2. **Stage 2 — Local LLM Guard** (~200-800ms, only for escalations): A small local model (Phi-3.5 mini, Qwen-2.5 1.5B, etc.) classifies suspicious content. No data leaves your machine.

```
[WebFetch result] --> [Stage 1: Rules] --> SAFE --------------------------> Agent
                                        |  SUSPICIOUS
                                  [Stage 2: LLM] --> SAFE ----------------> Agent
                                                  |  INJECTION
                                            BLOCKED + logged + user notified
```

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Claude Code Hook Setup](#claude-code-hook-setup)
- [Configuration](#configuration)
- [What Gets Detected](#what-gets-detected)
- [Adding Custom Patterns](#adding-custom-patterns)
- [Fail-Safe Design](#fail-safe-design)
- [Running Tests](#running-tests)
- [Roadmap](#roadmap)
- [Security Considerations](#security-considerations)
- [Contributing](#contributing)
- [License](#license)

---

## Features

| | Feature | Description |
|---|---|---|
| :hook: | **Native Claude Code hook** | Zero friction, no proxy, no MCP setup |
| :zap: | **Two-stage pipeline** | LLM only called when rules are uncertain |
| :house: | **Sovereign by design** | Local LLM, no external classification API |
| :electric_plug: | **Backend-agnostic** | Ollama, LM Studio, Docker Model Runner, Apple Silicon MLX |
| :whale: | **Optional Docker** | Bring your own Ollama, or use our compose file |
| :clipboard: | **Detailed logging** | Every block is logged with reason and matched pattern |
| :jigsaw: | **Extensible** | Add custom patterns in config, no code changes needed |

---

## Requirements

- **Python** 3.11+
- **Claude Code** (CLI)
- **One LLM backend** (only needed for Stage 2):
  - [Ollama](https://ollama.com) (recommended)
  - [LM Studio](https://lmstudio.ai)
  - Docker Desktop with Model Runner
  - `mlx-lm` (Apple Silicon)

> **Note:** Stage 1 (rule engine) works without any LLM backend. Stage 2 is optional and only called for ambiguous content.

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/michaelhannecke/claude-injection-guard
cd claude-injection-guard

# 2. Install (minimal -- only pyyaml required)
pip install -e .

# 3. Set up your LLM backend (example: Ollama)
ollama pull phi3.5:mini

# 4. Configure
cp config.example.yml ~/.claude/injection-guard/config.yml
# Edit as needed (defaults work out of the box with Ollama)
```

---

## Claude Code Hook Setup

Add this to your Claude Code hooks configuration (`~/.claude/settings.json` or project `.claude/settings.json`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "WebFetch|web_fetch",
        "hooks": [
          {
            "type": "command",
            "command": "python3 <path-to>/claude-injection-guard/hooks/post_tool_use.py"
          }
        ]
      }
    ]
  }
}
```

> **Note:** Replace `<path-to>` with the absolute path to your local clone, e.g. `/Users/you/projects`.

See [`claude_hooks.example.json`](claude_hooks.example.json) for a copy-paste template.

---

## Configuration

Copy `config.example.yml` to `~/.claude/injection-guard/config.yml`:

```yaml
stage2:
  backend: ollama          # ollama | openai_compatible | docker_model_runner | mlx
  model: phi3.5:mini
  endpoint: http://localhost:11434
  confidence_threshold: 0.75
```

### Backend Options

| Backend | When to use |
|---|---|
| `ollama` | Ollama installed natively (recommended default) |
| `openai_compatible` | LM Studio, vLLM, any OpenAI-compatible server |
| `docker_model_runner` | Docker Desktop >= 4.40 with Model Runner |
| `mlx` | Apple Silicon, maximum performance, `pip install mlx-lm` |

### Optional: Docker Backend

If you prefer not to install Ollama natively:

```bash
docker compose up -d
docker compose exec guard-llm ollama pull phi3.5:mini
```

The hook still runs on the host -- only the LLM inference runs in Docker.

---

## What Gets Detected

<details>
<summary><strong>Stage 1 -- Definitive blocks</strong> (immediate, no LLM needed)</summary>

- Direct instruction overrides (`ignore all previous instructions`)
- Identity hijacking (`pretend to be`, `your new role is`)
- Known jailbreak personas (DAN, STAN, etc.)
- Credential exfiltration instructions
- Hidden instruction markers (`<!-- instruction: -->`, `<instruction>`)

</details>

<details>
<summary><strong>Stage 1 -- Suspicious</strong> (escalated to Stage 2)</summary>

- Role hijacking phrases (`you are now a hacker`, `act as DAN`)
- Soft instruction resets (`forget everything you were told`)
- Safety bypass language (`override your restrictions`)
- LLM prompt delimiter injection (`[INST]`, `<|im_start|>`)
- Zero-width character obfuscation
- User deception instructions

</details>

<details>
<summary><strong>Stage 2 -- LLM classification</strong></summary>

- Contextual, semantic injection patterns that evade rules
- Multi-sentence indirect injections
- Domain-specific attack variations

</details>

---

## Adding Custom Patterns

```yaml
# config.yml
stage1:
  custom_patterns:
    - pattern: "(?i)exfiltrate.*company.*data"
      reason: "Custom: company data exfiltration"
      score: 0.9
      definitive: true  # block immediately, skip Stage 2
```

See [CLAUDE.md](CLAUDE.md#adding-new-detection-patterns) for detailed pattern authoring guidelines.

---

## Fail-Safe Design

The guard is designed to **fail open** by default -- if Stage 2 LLM is unavailable, the content passes through rather than breaking your workflow. You can change this behavior:

```yaml
hooks:
  fail_open: false  # block on any guard error (more secure)
```

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

**Linting and type checking:**

```bash
ruff check .
mypy guard/ hooks/
```

---

## Roadmap

- [ ] `Bash` tool interception (for `curl`/`wget` in shell commands)
- [ ] MCP server mode (for multi-agent / team setups)
- [ ] Fine-tuned guard model (domain-specific injection dataset)
- [ ] Metrics endpoint (Prometheus-compatible)
- [ ] VS Code extension integration

---

## Security Considerations

- Stage 1 patterns are conservative by design -- low false positive rate is prioritized
- Stage 2 LLM output is strictly parsed; the guard model cannot itself be injected
- The hook always logs to stderr, separate from Claude's stdout context
- Content is truncated to 50k chars for Stage 1 and 3k for Stage 2 (sufficient for injection patterns, protects against DoS)

---

## Contributing

Contributions are welcome! Please ensure:

1. All tests pass (`pytest`)
2. Linting is clean (`ruff check .`)
3. Type checking passes (`mypy guard/ hooks/`)

See [CLAUDE.md](CLAUDE.md) for architecture details and coding conventions.

---

## License

Apache 2.0 -- see [LICENSE](LICENSE)
