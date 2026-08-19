import json
from pathlib import Path

import pytest

from rpa_ponto.cloudflare import CloudflarePublishError, publish_monitor


def test_publish_monitor_invokes_local_wrangler(tmp_path: Path, monkeypatch):
    monitor = tmp_path / "output" / "monitor"
    monitor.mkdir(parents=True)
    (monitor / "index.html").write_text("relatorio", encoding="utf-8")
    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    executable = bin_dir / "wrangler.cmd"
    executable.write_text("", encoding="utf-8")

    class Result:
        returncode = 0
        stdout = "Deployment complete: https://abc.rpa-ponto.pages.dev"
        stderr = ""

    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        return Result()

    monkeypatch.setattr("rpa_ponto.cloudflare.subprocess.run", fake_run)
    monkeypatch.setattr("rpa_ponto.cloudflare.os.name", "nt")

    url = publish_monitor(monitor, "rpa-ponto", project_root=tmp_path)

    assert url == "https://abc.rpa-ponto.pages.dev"
    assert captured["command"][1:3] == ["pages", "deploy"]
    assert "--project-name" in captured["command"]


def test_publish_monitor_requires_report(tmp_path: Path):
    with pytest.raises(CloudflarePublishError, match="Relatório não encontrado"):
        publish_monitor(tmp_path / "monitor", "rpa-ponto", project_root=tmp_path)


def test_publish_monitor_syncs_auth_secrets_before_deploy(tmp_path: Path, monkeypatch):
    monitor = tmp_path / "output" / "monitor"
    monitor.mkdir(parents=True)
    (monitor / "index.html").write_text("relatorio", encoding="utf-8")
    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "wrangler.cmd").write_text("", encoding="utf-8")
    calls = []

    class Result:
        returncode = 0
        stdout = "https://abc.rpa-ponto.pages.dev"
        stderr = ""

    def fake_run(command, **kwargs):
        if "secret" in command:
            secrets = Path(command[4])
            assert json.loads(secrets.read_text(encoding="utf-8")) == {
                "PONTO_USERNAME": "usuario",
                "PONTO_PASSWORD": "senha",
            }
        calls.append(command)
        return Result()

    monkeypatch.setattr("rpa_ponto.cloudflare.subprocess.run", fake_run)
    monkeypatch.setattr("rpa_ponto.cloudflare.os.name", "nt")

    publish_monitor(
        monitor,
        "rpa-ponto",
        project_root=tmp_path,
        auth_username="usuario",
        auth_password="senha",
    )

    assert calls[0][1:4] == ["pages", "secret", "bulk"]
    assert calls[1][1:3] == ["pages", "deploy"]
