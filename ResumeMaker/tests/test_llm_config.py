import json

from config import load_app_config, update_llm_config
from core import llm as llm_module


def test_create_llm_reads_fresh_app_config_each_call(monkeypatch):
    calls = []

    def fake_load_app_config():
        calls.append(True)
        return {
            "llm": {
                "api_key": "test-key",
                "model": "test-model",
                "temperature": 0.2,
                "timeout": 12,
                "max_retries": 0,
            }
        }

    class FakeChatOpenAI:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(llm_module, "load_app_config", fake_load_app_config)
    monkeypatch.setattr(llm_module, "ChatOpenAI", FakeChatOpenAI)

    first = llm_module.create_llm()
    second = llm_module.create_llm()

    assert len(calls) == 2
    assert first.kwargs["api_key"] == "test-key"
    assert second.kwargs["model"] == "test-model"


def test_update_llm_config_persists_user_inputs(tmp_path, monkeypatch):
    for env_name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(env_name, raising=False)

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "",
                    "base_url": None,
                    "model": "old-model",
                }
            }
        ),
        encoding="utf-8",
    )

    updated = update_llm_config(
        {
            "api_key": " test-key ",
            "base_url": " https://example.com/v1 ",
            "model": " test-model ",
        },
        config_path=config_path,
    )

    assert updated["llm"]["api_key"] == "test-key"
    assert updated["llm"]["base_url"] == "https://example.com/v1"
    assert updated["llm"]["model"] == "test-model"

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["llm"]["api_key"] == "test-key"
    assert saved["llm"]["base_url"] == "https://example.com/v1"
    assert saved["llm"]["model"] == "test-model"


def test_update_llm_config_creates_config_parent_directory(tmp_path, monkeypatch):
    for env_name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(env_name, raising=False)

    config_path = tmp_path / "data" / "config.json"

    update_llm_config(
        {
            "api_key": "saved-from-ui",
            "base_url": "",
            "model": "ui-model",
        },
        config_path=config_path,
    )

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["llm"]["api_key"] == "saved-from-ui"
    assert saved["llm"]["base_url"] is None
    assert saved["llm"]["model"] == "ui-model"


def test_saved_llm_config_takes_precedence_over_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://env.example.com/v1")
    monkeypatch.setenv("LLM_MODEL", "env-model")

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "saved-key",
                    "base_url": "https://saved.example.com/v1",
                    "model": "saved-model",
                }
            }
        ),
        encoding="utf-8",
    )

    llm_config = load_app_config(config_path)["llm"]

    assert llm_config["api_key"] == "saved-key"
    assert llm_config["base_url"] == "https://saved.example.com/v1"
    assert llm_config["model"] == "saved-model"
