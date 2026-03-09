# Security Policy

## Scope

`claude-injection-guard` is a defensive security tool that intercepts and classifies prompt injection attempts targeting Claude Code agents. It processes untrusted web content by design.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.1.x (current, alpha) | Yes |

## Reporting a Vulnerability

If you discover a security issue — especially one that could allow an attacker to bypass the injection guard or cause it to misclassify malicious content — please report it responsibly.

**Email:** info(a)bluetuple.ai

Please include:

- Description of the vulnerability and its potential impact
- Steps to reproduce (sample payload, config, backend used)
- Whether the bypass affects Stage 1, Stage 2, or both
- Your suggested severity (critical / high / medium / low)

I aim to acknowledge reports within 48 hours and provide an initial assessment within 7 days. I will credit reporters in the fix commit unless they prefer to remain anonymous.

**Please do not open public GitHub issues for security vulnerabilities.**

## What Qualifies as a Security Issue

- Stage 1 regex bypass (injection payload passes rule engine undetected)
- Stage 2 LLM prompt injection (adversarial content that manipulates the guard model itself into misclassifying)
- Configuration handling flaws that weaken the guard silently (e.g., fail-open triggered unexpectedly)
- Log injection or information disclosure through the logging pipeline
- Dependency vulnerabilities in `pyyaml` or dev dependencies that affect runtime behavior

## What Does NOT Qualify

- False positives on benign content (please open a regular GitHub issue)
- Feature requests for additional detection patterns
- Issues specific to a particular LLM backend (Ollama, LM Studio, etc.) that are not caused by this project

## Design Decisions Relevant to Security

- **Fail-open by default:** If Stage 2 is unavailable, content passes through. This is a deliberate trade-off favoring availability over security. Users who need stricter guarantees should set `fail_open: false` in their config.
- **Content truncation:** Stage 1 scans the first 50,000 characters; Stage 2 receives 3,000 characters. Injections beyond these boundaries will not be detected.
- **Local-only processing:** No content leaves the machine. Stage 2 classification runs against a local LLM backend. There are no external API calls, telemetry, or analytics.
- **Guard model isolation:** The Stage 2 classification prompt uses randomized delimiters to reduce the risk of the guard model itself being manipulated by adversarial content. This is a mitigation, not a guarantee.

## Dependencies

This project has a single runtime dependency (`pyyaml`). The dev dependencies (`pytest`, `ruff`, `mypy`) are not required at runtime and do not affect the security posture of a deployed guard.
