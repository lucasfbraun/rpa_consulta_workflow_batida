from pathlib import Path

import pytest

from rpa_ponto.filename import next_afd_path, prune_afd_files


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


def test_prune_keeps_only_highest_afd_and_unrelated_files(tmp_path: Path):
    for sequence in (104, 105, 110):
        (tmp_path / f"AFD{sequence:020d}.txt").write_text("afd", encoding="utf-8")
    unrelated = tmp_path / "arquivo.txt"
    unrelated.write_text("preservar", encoding="utf-8")

    removed = prune_afd_files(tmp_path, keep=1)

    assert len(removed) == 2
    assert (tmp_path / f"AFD{110:020d}.txt").is_file()
    assert unrelated.is_file()
