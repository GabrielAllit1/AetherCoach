import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "aether_coach" / "coach_app.py"
SPEC = importlib.util.spec_from_file_location("aether_coach_app", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_sensitive_redaction():
    value = MODULE.redact_sensitive("mail me at person@example.com, SSN 123-45-6789, card 4111 1111 1111 1111")
    assert "person@example.com" not in value
    assert "123-45-6789" not in value
    assert "4111 1111 1111 1111" not in value


def test_config_forces_local_ollama_and_bounds_values():
    config = MODULE.normalize_config({
        "ollama_host": "https://collector.example",
        "interval_seconds": -1,
        "max_context_chars": 999999,
        "monitor_index": 0,
    })
    assert config["ollama_host"] == "http://localhost:11434"
    assert config["interval_seconds"] == 2.0
    assert config["max_context_chars"] == 8000
    assert config["monitor_index"] == 1


def test_config_rejects_unknown_style():
    assert MODULE.normalize_config({"style": "unknown"})["style"] == MODULE.DEFAULT_CONFIG["style"]
