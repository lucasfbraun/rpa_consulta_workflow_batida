from types import SimpleNamespace

import pytest

from rpa_ponto.control import ControlError, claim, dispatch_once


def settings():
    return SimpleNamespace(
        control_api_url="https://painel.example",
        control_agent_token="segredo",
    )


def test_claim_sends_bearer_token(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        text = ""

        @staticmethod
        def json():
            return {"command": {"id": "cmd-1"}}

    def fake_post(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return Response()

    monkeypatch.setattr("rpa_ponto.control.requests.post", fake_post)

    command = claim(settings())

    assert command.id == "cmd-1"
    assert captured["url"] == "https://painel.example/api/agent/claim"
    assert captured["kwargs"]["headers"] == {"Authorization": "Bearer segredo"}


def test_dispatch_runs_flow_and_completes(monkeypatch):
    calls = []
    monkeypatch.setattr("rpa_ponto.control.claim", lambda _settings: SimpleNamespace(id="cmd-2"))
    monkeypatch.setattr(
        "rpa_ponto.control.subprocess.run",
        lambda command, **_kwargs: calls.append(command) or SimpleNamespace(returncode=0),
    )
    monkeypatch.setattr(
        "rpa_ponto.control.complete",
        lambda _settings, command_id, success, result: calls.append(
            (command_id, success, result)
        ),
    )

    assert dispatch_once(settings()) == 0
    assert calls[0][-2:] == ["rpa_ponto.cli", "run"]
    assert calls[1] == ("cmd-2", True, "Fluxo concluÃ­do.")


def test_missing_control_configuration():
    empty = SimpleNamespace(control_api_url=None, control_agent_token=None)
    with pytest.raises(ControlError, match="CONTROL_API_URL"):
        claim(empty)
