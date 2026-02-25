"""Config loader — reads YAML from standard locations with sane defaults."""

import os
from pathlib import Path
from typing import Any

# Try to import yaml, fall back to a minimal inline parser hint
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


DEFAULT_CONFIG: dict[str, Any] = {
    "stage1": {
        "custom_patterns": [],
    },
    "stage2": {
        "enabled": True,
        "backend": "ollama",          # ollama | openai_compatible | docker_model_runner | mlx
        "model": "phi3.5:mini",
        "endpoint": "http://localhost:11434",
        "timeout_seconds": 10,
        "confidence_threshold": 0.75,
    },
    "logging": {
        "level": "INFO",
        "file": None,                 # None = stderr only
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    },
    "hooks": {
        "watched_tools": ["WebFetch", "web_fetch"],
        "fail_open": True,            # If guard errors, allow content through
    },
}

CONFIG_SEARCH_PATHS = [
    Path.home() / ".claude" / "injection-guard" / "config.yml",
    Path.cwd() / "injection-guard.config.yml",
    Path(__file__).parent.parent / "config.yml",
]


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str | None = None) -> dict:
    """Load configuration from file, merging with defaults."""
    if not HAS_YAML:
        # No pyyaml installed → use defaults only
        return DEFAULT_CONFIG.copy()

    # Check env var override first
    env_path = os.environ.get("INJECTION_GUARD_CONFIG")
    if env_path:
        search_paths = [Path(env_path)]
    elif config_path:
        search_paths = [Path(config_path)]
    else:
        search_paths = CONFIG_SEARCH_PATHS

    for path in search_paths:
        if path.exists():
            with open(path) as f:
                user_config = yaml.safe_load(f) or {}
            return deep_merge(DEFAULT_CONFIG, user_config)

    return DEFAULT_CONFIG.copy()
