"""Tests for config loader."""

import yaml

from guard.config import load_config, deep_merge, DEFAULT_CONFIG


class TestDeepMerge:
    def test_deep_merge_nested(self):
        base = {"a": {"b": 1, "c": 2}, "d": 3}
        override = {"a": {"b": 99}}
        result = deep_merge(base, override)
        assert result == {"a": {"b": 99, "c": 2}, "d": 3}

    def test_deep_merge_override_leaf(self):
        base = {"a": {"b": 1}}
        override = {"a": "flat"}
        result = deep_merge(base, override)
        assert result == {"a": "flat"}

    def test_deep_merge_adds_new_keys(self):
        base = {"a": 1}
        override = {"b": 2}
        result = deep_merge(base, override)
        assert result == {"a": 1, "b": 2}


class TestLoadConfig:
    def test_default_config_returned_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.delenv("INJECTION_GUARD_CONFIG", raising=False)
        # Point search paths to a directory with no config files
        monkeypatch.setattr("guard.config.CONFIG_SEARCH_PATHS", [tmp_path / "nonexistent.yml"])
        config = load_config()
        assert config["stage2"]["backend"] == DEFAULT_CONFIG["stage2"]["backend"]
        assert config["hooks"]["fail_open"] is True

    def test_env_var_config_path(self, tmp_path, monkeypatch):
        config_file = tmp_path / "custom.yml"
        config_file.write_text(yaml.dump({"stage2": {"model": "custom-model"}}))
        monkeypatch.setenv("INJECTION_GUARD_CONFIG", str(config_file))
        config = load_config()
        assert config["stage2"]["model"] == "custom-model"
        # Defaults still present for unset keys
        assert config["stage2"]["backend"] == "ollama"

    def test_load_config_from_explicit_path(self, tmp_path, monkeypatch):
        monkeypatch.delenv("INJECTION_GUARD_CONFIG", raising=False)
        config_file = tmp_path / "explicit.yml"
        config_file.write_text(yaml.dump({"logging": {"level": "DEBUG"}}))
        config = load_config(config_path=str(config_file))
        assert config["logging"]["level"] == "DEBUG"
