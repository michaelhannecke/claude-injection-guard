# claude-injection-guard

**Prompt injection protection for Claude Code agents — hooks-based, two-stage, local-LLM-powered.**

When Claude Code (or a sub-agent) fetches web content, that content enters the agent's context and can contain malicious instructions designed to hijack its behavior. This is called a **prompt injection attack**.

`claude-injection-guard` intercepts fetched content *before* it reaches Claude, using a fast two-stage pipeline:

1. **Stage 1 — Rule Engine** (deterministic, ~1ms): Regex-based pattern matching for known injection signatures. High-confidence hits are blocked immediately; suspicious content escalates to Stage 2.
2. **Stage 2 — Local LLM Guard** (~200–800ms, only for escalations): A small local model (Phi-3.5 mini, Qwen-2.5 1.5B, etc.) classifies suspicious content. No data leaves your machine.

```
[WebFetch result] → [Stage 1: Rules] → SAFE ──────────────────────→ Agent
                                     ↓ SUSPICIOUS
                               [Stage 2: LLM] → SAFE ──────────────→ Agent
                                              ↓ INJECTION
                                        BLOCKED + logged + user notified
```

---

## Features

- 🪝 **Native Claude Code hook** — zero friction, no proxy, no MCP setup
- ⚡ **Two-stage pipeline** — LLM only called when rules are uncertain
- 🏠 **Sovereign by design** — local LLM, no external classification API
- 🔌 **Backend-agnostic** — Ollama, LM Studio, Docker Model Runner, Apple Silicon MLX
- 🐳 **Optional Docker** — bring your own Ollama, or use our compose file
- 📋 **Detailed logging** — every block is logged with reason and matched pattern
- 🧩 **Extensible** — add custom patterns in config, no code changes needed

---

## Requirements

- Python 3.11+
- Claude Code
- One of: [Ollama](https://ollama.com), [LM Studio](https://lmstudio.ai), Docker Desktop with Model Runner, or `mlx-lm`

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/claude-injection-guard
cd claude-injection-guard

# 2. Install (minimal — only pyyaml required)
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
            "command": "python3 /absolute/path/to/claude-injection-guard/hooks/post_tool_use.py"
          }
        ]
      }
    ]
  }
}
```

See `claude_hooks.example.json` for a copy-paste template.

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

### Backend options

| Backend | When to use |
|---|---|
| `ollama` | Ollama installed natively (recommended default) |
| `openai_compatible` | LM Studio, vLLM, any OpenAI-compatible server |
| `docker_model_runner` | Docker Desktop ≥ 4.40 with Model Runner |
| `mlx` | Apple Silicon, maximum performance, `pip install mlx-lm` |

### Optional: Docker backend

If you prefer not to install Ollama natively:

```bash
docker compose up -d
docker compose exec guard-llm ollama pull phi3.5:mini
```

The hook still runs on the host — only the LLM inference runs in Docker.

---

## What gets detected

**Stage 1 — Definitive blocks (immediate, no LLM needed)**
- Direct instruction overrides (`ignore all previous instructions`)
- Role/identity hijacking (`you are now`, `act as`)
- Known jailbreak personas (DAN, STAN, etc.)
- Credential exfiltration instructions
- Hidden instruction markers (`<!-- instruction: -->`, `<instruction>`)

**Stage 1 — Suspicious (escalated to Stage 2)**
- Soft instruction resets (`forget everything you were told`)
- Safety bypass language (`override your restrictions`)
- LLM prompt delimiter injection (`[INST]`, `<|im_start|>`)
- Zero-width character obfuscation
- User deception instructions

**Stage 2 — LLM classification**
- Contextual, semantic injection patterns that evade rules
- Multi-sentence indirect injections
- Domain-specific attack variations

---

## Adding custom patterns

```yaml
# config.yml
stage1:
  custom_patterns:
    - pattern: "(?i)exfiltrate.*company.*data"
      reason: "Custom: company data exfiltration"
      score: 0.9
      definitive: true  # block immediately, skip Stage 2
```

---

## Fail-safe design

The guard is designed to **fail open** by default — if Stage 2 LLM is unavailable, the content passes through rather than breaking your workflow. You can change this behavior:

```yaml
hooks:
  fail_open: false  # block on any guard error (more secure)
```

---

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Roadmap

- [ ] `Bash` tool interception (for `curl`/`wget` in shell commands)
- [ ] MCP server mode (for multi-agent / team setups)
- [ ] Fine-tuned guard model (domain-specific injection dataset)
- [ ] Metrics endpoint (Prometheus-compatible)
- [ ] VS Code extension integration

---

## Security considerations

- Stage 1 patterns are conservative by design — low false positive rate is prioritized
- Stage 2 LLM output is strictly parsed; the guard model cannot itself be injected
- The hook always logs to stderr, separate from Claude's stdout context
- Content is truncated to 50k chars for Stage 1 and 3k for Stage 2 (sufficient for injection patterns, protects against DoS)

---

## License

MIT — see [LICENSE](LICENSE)

---

## Contributing

PRs welcome. Priority areas: additional injection patterns (with test cases), new backend adapters, and evaluation datasets.

Please open an issue before large PRs to discuss approach.
