from pathlib import Path

import pytest

from rpa_ponto.filename import next_afd_path


def test_starts_after_initial_sequence(tmp_path: Path):
    assert next_afd_path(tmp_path, "00014003750288103").name == (
        "AFD00014003750288104.txt"
    )


def test_increments_highest_existing_output(tmp_path: Path):
    (tmp_path / "AFD00014003750288104.txt").touch()
    (tmp_path / "AFD00014003750288107.txt").touch()
    (tmp_path / "arquivo-qualquer.txt").touch()

    assert next_afd_path(tmp_path, "00014003750288103").name == (
        "AFD00014003750288108.txt"
    )


def test_rejects_non_numeric_initial_sequence(tmp_path: Path):
    with pytest.raises(ValueError):
        next_afd_path(tmp_path, "123ABC")

