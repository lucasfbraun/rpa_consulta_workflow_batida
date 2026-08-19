import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rpa_ponto.monitor import ExecutionReporter


def test_local_report_contains_run_step_and_screenshot(tmp_path: Path):
    reporter = ExecutionReporter(tmp_path, "run")
    reporter.start()
    reporter.step("abrir_erp", screenshot=b"png")
    reporter.finish("completed")

    assert (tmp_path / "index.html").is_file()
    assert (tmp_path / "login.html").is_file()
    assert (tmp_path / "manifest.webmanifest").is_file()
    assert (tmp_path / "sw.js").is_file()
    assert (tmp_path / "icon.svg").is_file()
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "__RPA_DATA__" not in html
    assert "abrir_erp" in html
    run = json.loads((reporter.run_dir / "run.json").read_text(encoding="utf-8"))
    assert run["status"] == "completed"
    assert run["steps"][0]["name"] == "abrir_erp"
    assert (reporter.run_dir / "001-abrir_erp.png").read_bytes() == b"png"


def test_retention_removes_runs_older_than_history_but_not_afd(tmp_path: Path):
    afd = tmp_path / "AFD00014003750288104.txt"
    afd.write_text("afd", encoding="utf-8")

    first = ExecutionReporter(tmp_path / "monitor", "run", history_days=3)
    first.start()
    first_id = first.run_id
    first.finish("completed")
    first_file = first.run_dir / "run.json"
    first_data = json.loads(first_file.read_text(encoding="utf-8"))
    first_data["started_at"] = (
        datetime.now(timezone.utc) - timedelta(days=4)
    ).isoformat()
    first_file.write_text(json.dumps(first_data), encoding="utf-8")

    second = ExecutionReporter(tmp_path / "monitor", "run", history_days=3)
    second.start()
    second.finish("completed")

    assert not (tmp_path / "monitor" / "runs" / first_id).exists()
    assert (tmp_path / "monitor" / "runs" / second.run_id).is_dir()
    assert afd.is_file()


def test_retention_keeps_all_runs_within_three_days(tmp_path: Path):
    first = ExecutionReporter(tmp_path, "run", history_days=3)
    first.start()
    first.finish("completed")
    second = ExecutionReporter(tmp_path, "run", history_days=3)
    second.start()
    second.finish("completed")

    assert (tmp_path / "runs" / first.run_id).is_dir()
    assert (tmp_path / "runs" / second.run_id).is_dir()


def test_failure_is_visible_in_report(tmp_path: Path):
    reporter = ExecutionReporter(tmp_path, "run")
    reporter.start()
    reporter.step("falha_execucao", status="failed", message="Credencial recusada")
    reporter.finish("failed", "Credencial recusada")

    run = json.loads((reporter.run_dir / "run.json").read_text(encoding="utf-8"))
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert run["status"] == "failed"
    assert run["steps"][-1]["status"] == "failed"
    assert "Credencial recusada" in html


def test_unfinished_run_is_marked_failed_on_shutdown(tmp_path: Path):
    reporter = ExecutionReporter(tmp_path, "run")
    reporter.start()
    reporter._finish_if_running()

    run = json.loads((reporter.run_dir / "run.json").read_text(encoding="utf-8"))
    assert run["status"] == "failed"
    assert run["steps"][-1]["name"] == "falha_execucao"
