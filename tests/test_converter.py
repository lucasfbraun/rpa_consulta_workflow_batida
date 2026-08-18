from pathlib import Path

import pytest

from rpa_ponto.api import ApiPayload
from rpa_ponto.converter import LayoutPendenteError, generate_import_file


def test_preserves_file_response(tmp_path: Path):
    payload = ApiPayload(b"linha 1\r\nlinha 2\r\n", "text/plain", None)
    destination = tmp_path / "arquivo.txt"

    assert generate_import_file(payload, destination) == destination
    assert destination.read_bytes() == payload.content


def test_json_is_saved_for_mapping(tmp_path: Path):
    payload = ApiPayload(b'{"records": [{"id": 1}]}', "application/json", None)
    destination = tmp_path / "arquivo.txt"

    with pytest.raises(LayoutPendenteError):
        generate_import_file(payload, destination)
    assert destination.with_suffix(".resposta-api.json").is_file()

