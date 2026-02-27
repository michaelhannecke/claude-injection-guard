#!/usr/bin/env python3
"""
Claude Code Post-Tool-Use Hook: Prompt Injection Guard
Intercepts WebFetch (and optionally Bash) tool results and scans
for prompt injection attempts before they reach the agent context.
"""

import json
import logging
import sys

from guard.stage1_rules import Stage1RuleEngine, RuleResult
from guard.stage2_llm import Stage2LLMGuard
from guard.config import load_config
from guard.logger import setup_logger


def build_block_response(reason: str, stage: str, details: str = "") -> dict:
    """Build a standardized block response that Claude Code will display."""
    message = (
        f"\n⚠️  [INJECTION GUARD] Content BLOCKED by {stage}\n"
        f"   Reason: {reason}\n"
    )
    if details:
        message += f"   Details: {details}\n"
    message += (
        "   The fetched content has been suppressed to protect agent integrity.\n"
        "   If you believe this is a false positive, review the guard logs.\n"
    )
    return {
        "type": "text",
        "text": message
    }


def process_hook_input(raw_input: str, config: dict, logger: logging.Logger) -> None:
    """
    Main processing logic.
    Reads hook JSON from stdin, evaluates content, writes result to stdout.
    Exit code 0 = passthrough, Exit code 1 = blocked (non-zero blocks in Claude Code).
    """
    fail_open = config.get("hooks", {}).get("fail_open", True)

    try:
        hook_data = json.loads(raw_input)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse hook input: {e}")
        sys.exit(0 if fail_open else 1)

    tool_name = hook_data.get("tool_name", "")
    tool_result = hook_data.get("tool_result", {})

    # Only process watched tools (read from config, fall back to defaults)
    watched_tools = set(config.get("hooks", {}).get("watched_tools", ["WebFetch", "web_fetch"]))
    if tool_name not in watched_tools:
        sys.exit(0)

    # Extract content string from tool result
    content = extract_content(tool_result)
    if not content:
        sys.exit(0)

    source_url = hook_data.get("tool_input", {}).get("url", "unknown")
    logger.info(f"Scanning content from: {source_url} ({len(content)} chars)")

    # ── Stage 1: Rule-based fast scan ────────────────────────────────────────
    stage1 = Stage1RuleEngine(config.get("stage1", {}))
    rule_result: RuleResult = stage1.scan(content)

    if rule_result.is_safe:
        logger.debug(f"Stage 1 PASSED for {source_url}")
        sys.exit(0)

    if rule_result.is_definitive_block:
        logger.warning(
            f"Stage 1 BLOCKED (definitive) | url={source_url} | "
            f"pattern='{rule_result.matched_pattern}'"
        )
        print(json.dumps(build_block_response(
            reason=rule_result.reason,
            stage="Stage 1 (Rule Engine)",
            details=f"Matched pattern: {rule_result.matched_pattern}"
        )))
        sys.exit(1)

    # ── Stage 2: LLM-based deep scan (only on suspicious, non-definitive) ────
    if not config.get("stage2", {}).get("enabled", True):
        logger.info("Stage 2 disabled, passing suspicious content through")
        sys.exit(0)

    logger.info(f"Stage 1 SUSPICIOUS → escalating to Stage 2 LLM for {source_url}")

    try:
        stage2 = Stage2LLMGuard(config.get("stage2", {}))
        llm_result = stage2.classify(content, context={"url": source_url})
    except Exception as e:
        logger.error(f"Stage 2 LLM error: {e} — fail_open={fail_open}")
        sys.exit(0 if fail_open else 1)

    if llm_result.is_injection:
        logger.warning(
            f"Stage 2 BLOCKED | url={source_url} | "
            f"confidence={llm_result.confidence:.2f} | reason={llm_result.reason}"
        )
        print(json.dumps(build_block_response(
            reason=llm_result.reason,
            stage=f"Stage 2 (LLM Guard, confidence={llm_result.confidence:.0%})",
        )))
        sys.exit(1)

    logger.info(f"Stage 2 PASSED | url={source_url} | confidence={llm_result.confidence:.2f}")
    sys.exit(0)


def extract_content(tool_result: dict | str) -> str:
    """Extract plain text content from various tool result shapes."""
    if isinstance(tool_result, str):
        return tool_result
    if isinstance(tool_result, dict):
        # Claude Code WebFetch result shape
        if "content" in tool_result:
            content = tool_result["content"]
            if isinstance(content, list):
                return " ".join(
                    block.get("text") or "" for block in content
                    if isinstance(block, dict) and block.get("type") == "text"
                )
            return str(content)
        if "output" in tool_result:
            return str(tool_result["output"])
    return ""


def main():
    try:
        config = load_config()
        logger = setup_logger(config.get("logging", {}))

        raw_input = sys.stdin.read()
        if not raw_input.strip():
            sys.exit(0)

        process_hook_input(raw_input, config, logger)
    except SystemExit:
        raise
    except Exception:
        # Top-level safety net — respect fail_open config
        try:
            fail_open = config.get("hooks", {}).get("fail_open", True)  # type: ignore[possibly-undefined]
        except Exception:
            fail_open = True
        import traceback
        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(0 if fail_open else 1)


if __name__ == "__main__":
    main()
