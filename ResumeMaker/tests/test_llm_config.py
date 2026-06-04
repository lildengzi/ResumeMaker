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
