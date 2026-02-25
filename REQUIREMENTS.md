# Requirements Document — claude-injection-guard

**Version:** 0.1  
**Status:** Draft  
**Owner:** bluetuple.ai  
**Last updated:** 2025-02

---

## 1. Problem Statement

Claude Code agents and sub-agents regularly fetch external web content as part of research, tool use, and autonomous workflows. This content is inserted into the agent's context verbatim, creating a **prompt injection attack surface**: malicious web pages can embed instructions designed to hijack the agent's behavior, leak sensitive information, or cause unintended actions.

There is currently no built-in mechanism in Claude Code to inspect or sanitize tool results before they enter agent context. This project fills that gap.

---

## 2. Goals

- **G1** — Intercept web-fetched content before it reaches agent context
- **G2** — Detect and block prompt injection attempts with high confidence
- **G3** — Minimize false positives to avoid disrupting legitimate research workflows
- **G4** — Keep all classification on-device (sovereign design, no external classification APIs)
- **G5** — Remain backend-agnostic (Ollama, LM Studio, Docker, MLX)
- **G6** — Be easy to install and configure for individual developers and teams

## 3. Non-Goals

- **NG1** — This is not a general-purpose web content filter (no malware/phishing detection)
- **NG2** — This does not protect against injections in user-provided input (only tool results)
- **NG3** — This does not replace network-level controls or Claude Code's built-in safety
- **NG4** — This does not attempt to sanitize and repair injected content (block or pass, no rewrite)
- **NG5** — MCP server mode is explicitly deferred (see Roadmap)

---

## 4. Functional Requirements

### 4.1 Hook Integration

| ID | Requirement | Priority |
|---|---|---|
| F-01 | The guard MUST integrate as a Claude Code `PostToolUse` hook | Must |
| F-02 | The hook MUST be triggered on `WebFetch` and `web_fetch` tool calls | Must |
| F-03 | The hook MUST read tool result content from stdin (Claude Code hook protocol) | Must |
| F-04 | The hook MUST communicate block decisions via non-zero exit code | Must |
| F-05 | The hook MUST write a human-readable block reason to stdout on block | Must |
| F-06 | The hook SHOULD support optional `Bash` tool interception (for curl/wget) | Should |
| F-07 | The watched tool list MUST be configurable without code changes | Must |

### 4.2 Stage 1 — Rule Engine

| ID | Requirement | Priority |
|---|---|---|
| F-10 | Stage 1 MUST run without any external dependencies or network calls | Must |
| F-11 | Stage 1 MUST complete in under 50ms for content up to 100k characters | Must |
| F-12 | Stage 1 MUST detect direct instruction override patterns | Must |
| F-13 | Stage 1 MUST detect identity/role hijacking patterns | Must |
| F-14 | Stage 1 MUST detect known jailbreak persona markers (DAN, STAN, etc.) | Must |
| F-15 | Stage 1 MUST detect credential exfiltration instructions | Must |
| F-16 | Stage 1 MUST detect hidden instruction markers (HTML comments, XML tags) | Must |
| F-17 | Stage 1 MUST detect LLM prompt delimiter injection (`[INST]`, `<\|im_start\|>`, etc.) | Must |
| F-18 | Stage 1 MUST detect zero-width character obfuscation | Must |
| F-19 | Stage 1 MUST support user-defined custom patterns via config (regex + score + definitive flag) | Must |
| F-20 | Stage 1 MUST output one of three states: SAFE / SUSPICIOUS / DEFINITIVE_BLOCK | Must |
| F-21 | DEFINITIVE_BLOCK patterns MUST bypass Stage 2 (no LLM needed) | Must |
| F-22 | SUSPICIOUS content MUST include a cumulative score to allow threshold tuning | Should |

### 4.3 Stage 2 — LLM Guard

| ID | Requirement | Priority |
|---|---|---|
| F-30 | Stage 2 MUST only be invoked on SUSPICIOUS content (not on SAFE or DEFINITIVE_BLOCK) | Must |
| F-31 | Stage 2 MUST support Ollama as the default backend | Must |
| F-32 | Stage 2 MUST support any OpenAI-compatible API endpoint | Must |
| F-33 | Stage 2 MUST support Docker Desktop Model Runner | Should |
| F-34 | Stage 2 MUST support Apple Silicon MLX via `mlx-lm` | Should |
| F-35 | Stage 2 MUST return a structured classification: `is_injection`, `confidence`, `reason` | Must |
| F-36 | Stage 2 MUST have a configurable confidence threshold (default: 0.75) | Must |
| F-37 | Stage 2 MUST have a configurable timeout (default: 10s) | Must |
| F-38 | Stage 2 MUST fail open on timeout or connection error (configurable) | Must |
| F-39 | The classification prompt MUST be designed to resist meta-injection of the guard model itself | Must |
| F-40 | Stage 2 content input MUST be truncated to a safe maximum (default: 3000 chars) | Must |

### 4.4 Configuration

| ID | Requirement | Priority |
|---|---|---|
| F-50 | Configuration MUST be file-based (YAML) | Must |
| F-51 | Config file location MUST follow XDG convention (`~/.claude/injection-guard/config.yml`) | Must |
| F-52 | Config path MUST be overridable via `INJECTION_GUARD_CONFIG` env var | Must |
| F-53 | All config values MUST have sensible defaults (zero-config startup) | Must |
| F-54 | `pyyaml` MUST be the only required dependency for full functionality | Must |
| F-55 | Backend-specific deps (mlx-lm) MUST be optional extras | Must |

### 4.5 Logging & Observability

| ID | Requirement | Priority |
|---|---|---|
| F-60 | All guard decisions MUST be logged with: timestamp, tool name, URL, stage, decision, reason | Must |
| F-61 | Logs MUST be written to stderr (never stdout, which is reserved for hook output) | Must |
| F-62 | Log level MUST be configurable (DEBUG / INFO / WARNING / ERROR) | Must |
| F-63 | Optional file logging MUST be supported (in addition to stderr) | Should |
| F-64 | Block events MUST include the matched pattern (truncated to 100 chars) | Must |
| F-65 | Stage 2 results MUST include inference latency in the log | Should |

---

## 5. Non-Functional Requirements

| ID | Requirement | Target |
|---|---|---|
| NF-01 | Stage 1 latency | < 50ms for 100k char input |
| NF-02 | Stage 2 latency | < 1000ms on Apple Silicon M-series with 1.5B model |
| NF-03 | Stage 1 false positive rate | < 1% on general English web content |
| NF-04 | Stage 1 detection rate | > 95% on known injection pattern test set |
| NF-05 | Python version compatibility | Python 3.11+ |
| NF-06 | Dependency footprint | Minimal — `pyyaml` only for core functionality |
| NF-07 | Test coverage | > 80% for `guard/` package |
| NF-08 | Hook startup time | < 200ms (cold start, Python interpreter init included) |

---

## 6. Security Requirements

| ID | Requirement |
|---|---|
| S-01 | The guard model (Stage 2) MUST not be exploitable via the content it is classifying — the classification prompt MUST treat all web content as untrusted data, never as executable instruction |
| S-02 | Content passed to Stage 2 MUST be explicitly wrapped/delimited to prevent prompt boundary confusion |
| S-03 | Config files MUST NOT contain secrets (API keys, tokens) — only endpoints and model names |
| S-04 | The `fail_open` default MUST be clearly documented, with `fail_closed` as the secure alternative |
| S-05 | Logs MUST NOT contain the full blocked content (only the matched pattern, truncated) |
| S-06 | The guard MUST NOT make outbound network calls except to the configured local LLM endpoint |

---

## 7. Constraints

- **C-01** Claude Code hooks run synchronously — total guard latency directly impacts agent responsiveness
- **C-02** Claude Code provides no mechanism to modify tool results, only to block or allow — no content rewriting
- **C-03** The hook process has no persistent state between invocations — each call is stateless
- **C-04** `stdout` of the hook is interpreted by Claude Code as the block reason message — only write on block

---

## 8. Out of Scope (v0.1)

- MCP server mode for multi-agent / team deployment
- Fine-tuned guard model (custom injection classification dataset)
- Metrics / Prometheus endpoint
- Content rewriting / sanitization (only block or allow)
- Browser automation tool interception (Playwright, Puppeteer)
- Windows native support (not tested, PRs welcome)

---

## 9. Roadmap

### v0.2
- [ ] `Bash` tool interception for curl/wget patterns
- [ ] Metrics logging (JSON structured output for SIEM ingestion)
- [ ] `--dry-run` mode (detect and log but never block)
- [ ] Evaluation script against labeled injection dataset

### v0.3
- [ ] MCP server mode (shared guard for multiple Claude Code instances)
- [ ] Fine-tuned Phi / Qwen guard model (injection-specific dataset)
- [ ] Pattern contribution guide + community pattern library

### v0.4+
- [ ] VS Code / Cursor extension
- [ ] Prometheus metrics endpoint
- [ ] Multi-tenant config for team/enterprise use

---

## 10. Open Questions

| ID | Question | Status |
|---|---|---|
| OQ-01 | Should Stage 2 be async (fire-and-forget with delayed block)? Risk: race condition with agent. | Open |
| OQ-02 | Should blocked content be replaced with a sanitized stub, or fully suppressed? | Decided: suppress |
| OQ-03 | Is a community-maintained pattern library viable without becoming an evasion guide? | Open |
| OQ-04 | Should the guard support rate-limiting per domain to detect coordinated injection campaigns? | Backlog |
