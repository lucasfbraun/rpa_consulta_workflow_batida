from __future__ import annotations

import json
from pathlib import Path

from .api import ApiPayload


class LayoutPendenteError(RuntimeError):
    pass


def generate_import_file(payload: ApiPayload, destination: Path) -> Path:
    """Gera o arquivo de importação.

    Se a API já devolver um arquivo, preserva seus bytes. Para uma resposta JSON,
    o mapeamento será implementado após recebermos o arquivo-modelo do ERP.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if "json" in payload.content_type.lower():
        try:
            parsed = json.loads(payload.content)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LayoutPendenteError("A API declarou JSON, mas a resposta é inválida.") from exc

        debug_file = destination.with_suffix(".resposta-api.json")
        debug_file.write_text(
            json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise LayoutPendenteError(
            "A resposta é JSON. Falta mapear os campos para o layout do ERP. "
            f"Uma cópia sem senha foi salva em: {debug_file}"
        )

    destination.write_bytes(payload.content)
    return destination

