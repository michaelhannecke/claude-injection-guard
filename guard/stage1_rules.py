"""
Stage 1: Rule-based prompt injection detection.
Fast, deterministic, zero external dependencies.

Two output states:
  - SAFE              → no further processing needed
  - SUSPICIOUS        → escalate to Stage 2 LLM
  - DEFINITIVE_BLOCK  → block immediately, no LLM needed
"""

import logging
import re
from dataclasses import dataclass

log = logging.getLogger("injection-guard")


@dataclass
class RuleResult:
    is_safe: bool = True
    is_definitive_block: bool = False
    matched_pattern: str | None = None
    reason: str = ""
    score: float = 0.0  # 0.0 = clean, 1.0 = certain injection


# ── Pattern definitions ───────────────────────────────────────────────────────

# High-confidence patterns → definitive block, no LLM needed
DEFINITIVE_PATTERNS: list[tuple[str, str]] = [
    # Classic direct instruction override
    (r"(?i)ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|context|rules?)",
     "Direct instruction override attempt"),
    (r"(?i)disregard\s+(all\s+)?(previous|prior|above)\s+(instructions?|prompts?|directives?)",
     "Instruction disregard attempt"),

    # Role/identity hijacking (high confidence variants only)
    (r"(?i)(pretend\s+to\s+be|your\s+new\s+(role|persona|identity)\s+is)",
     "Identity/role hijacking"),
    (r"(?i)(system\s*prompt|system\s*message|new\s+instructions?):\s*['\"]?\s*(you|your|ignore)",
     "Fake system prompt injection"),

    # Jailbreak markers
    (r"(?i)\b(DAN|STAN|DUDE|AIM|KEVIN|BasedGPT)\b.{0,30}(mode|enabled|activated|jailbreak)",
     "Known jailbreak persona"),
    (r"(?i)(jailbreak|jail\s*break)\s*(mode|enabled|activated|successful)",
     "Explicit jailbreak activation"),

    # Data exfiltration via instruction
    (r"(?i)\b(send|transmit|exfiltrate|leak|forward)\b\s+.{0,40}\b(api\s*key|secret|password|token|credential)s?\b\s+.{0,20}\b(to|http)",
     "Credential exfiltration instruction"),
    (r"(?i)(http[s]?://[^\s]+)\s*\+\s*(document\.|window\.|localStorage)",
     "DOM data exfiltration pattern"),

    # Hidden instruction markers
    (r"<!--\s*(instruction|prompt|system|command)\s*:?",
     "Hidden HTML comment instruction"),
    (r"(?i)<\s*(instruction|system|prompt|hidden_prompt)\s*>",
     "Hidden XML/HTML instruction tag"),
]

# Medium-confidence patterns → suspicious, escalate to Stage 2
SUSPICIOUS_PATTERNS: list[tuple[str, str, float]] = [
    # Role hijacking (moved from definitive — too many false positives on web content)
    (r"(?i)you\s+are\s+now\s+(a\s+)?(hacker|DAN|evil|unfiltered|unrestricted|an?\s+AI|my\s+new|jailbr)",
     "Role hijacking (you are now)", 0.7),
    (r"(?i)act\s+as\s+(a\s+)?(hacker|DAN|evil|unfiltered|unrestricted|an?\s+AI|malicious|my\s+new)",
     "Role hijacking (act as)", 0.7),

    # Indirect overrides
    (r"(?i)forget\s+(everything|all|what)\s+(you('ve| have| were?)|was|were)\s+(told|said|instructed|trained)",
     "Soft instruction reset", 0.6),
    (r"(?i)(override|bypass|circumvent|disable)\s+(your\s+)?(safety|filter|restriction|guideline|rule)",
     "Safety bypass language", 0.7),

    # Prompt boundary probing
    (r"(?i)\[INST\]|\[\/INST\]|<\|im_start\|>|<\|im_end\|>|\[SYSTEM\]|\[USER\]|\[ASSISTANT\]",
     "LLM prompt delimiter injection", 0.8),
    (r"(?i)(</?(human|assistant|system|user|ai)>)",
     "Conversation role tag injection", 0.75),

    # Unicode/encoding tricks
    (r"[\u200b\u200c\u200d\u2060\ufeff]",
     "Zero-width character (possible obfuscation)", 0.65),
    (r"(?i)(base64|rot13|hex\s*decode|url\s*decode).{0,30}(instruction|prompt|command)",
     "Encoded instruction delivery", 0.7),

    # Behavioral manipulation
    (r"(?i)(do\s+not\s+|never\s+|stop\s+)(tell|inform|show|reveal|mention)\s+(the\s+)?(user|human|person)",
     "User deception instruction", 0.65),
    (r"(?i)(this\s+is|these\s+are)\s+(your\s+)?(new|updated|real|actual|true)\s+(instructions?|rules?|prompt)",
     "Instruction replacement framing", 0.7),

    # Resource exhaustion / DoS patterns
    (r"(?i)repeat\s+(the\s+)?(following|this|above).{0,20}(forever|indefinitely|\d{3,}\s*times)",
     "Potential DoS loop instruction", 0.6),
]

# Scoring thresholds
SUSPICIOUS_THRESHOLD = 0.55   # escalate to Stage 2
DEFINITIVE_THRESHOLD = 1.0    # block immediately


class Stage1RuleEngine:
    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._compiled_definitive = [
            (re.compile(pattern), reason)
            for pattern, reason in DEFINITIVE_PATTERNS
        ]
        self._compiled_suspicious = [
            (re.compile(pattern), reason, score)
            for pattern, reason, score in SUSPICIOUS_PATTERNS
        ]
        self.custom_patterns = self._load_custom_patterns()

    def _load_custom_patterns(self) -> list:
        """Load user-defined patterns from config."""
        custom = self.config.get("custom_patterns", [])
        compiled = []
        for entry in custom:
            try:
                compiled.append((
                    re.compile(entry["pattern"]),
                    entry.get("reason", "Custom pattern match"),
                    float(entry.get("score", 0.7)),
                    entry.get("definitive", False)
                ))
            except re.error as e:
                log.warning("Skipping invalid custom pattern %r: %s", entry.get("pattern"), e)
        return compiled

    def scan(self, content: str) -> RuleResult:
        """
        Scan content against all rule sets.
        Returns RuleResult with classification.
        """
        # Truncate for performance (first 50k chars are enough for injection detection)
        scan_content = content[:50_000]

        # ── Check definitive patterns first ──────────────────────────────────
        for pattern, reason in self._compiled_definitive:
            match = pattern.search(scan_content)
            if match:
                return RuleResult(
                    is_safe=False,
                    is_definitive_block=True,
                    matched_pattern=match.group(0)[:100],
                    reason=reason,
                    score=1.0,
                )

        # ── Check custom definitive patterns ─────────────────────────────────
        for pattern, reason, score, is_definitive in self.custom_patterns:
            if is_definitive:
                match = pattern.search(scan_content)
                if match:
                    return RuleResult(
                        is_safe=False,
                        is_definitive_block=True,
                        matched_pattern=match.group(0)[:100],
                        reason=reason,
                        score=1.0,
                    )

        # ── Accumulate suspicious scores ──────────────────────────────────────
        total_score = 0.0
        first_match = None
        first_reason = ""

        for pattern, reason, score in self._compiled_suspicious:
            match = pattern.search(scan_content)
            if match:
                total_score = min(1.0, total_score + score)
                if first_match is None:
                    first_match = match.group(0)[:100]
                    first_reason = reason

        # ── Custom suspicious patterns ────────────────────────────────────────
        for pattern, reason, score, is_definitive in self.custom_patterns:
            if not is_definitive:
                match = pattern.search(scan_content)
                if match:
                    total_score = min(1.0, total_score + score)
                    if first_match is None:
                        first_match = match.group(0)[:100]
                        first_reason = reason

        if total_score >= SUSPICIOUS_THRESHOLD:
            return RuleResult(
                is_safe=False,
                is_definitive_block=False,
                matched_pattern=first_match,
                reason=first_reason,
                score=total_score,
            )

        return RuleResult(is_safe=True, score=total_score)
