"""Keep automated tests offline and isolate user feedback from test writes."""
import pytest

@pytest.fixture(autouse=True)
def isolated_services(monkeypatch, tmp_path):
    monkeypatch.setenv('LLM_PROVIDER', 'offline')
    import app.main
    monkeypatch.setattr(app.main, 'FEEDBACK_FILE', tmp_path / 'feedback.jsonl')
