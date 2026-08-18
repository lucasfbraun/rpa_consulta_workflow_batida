from __future__ import annotations

from dataclasses import dataclass

import requests
from requests.auth import HTTPBasicAuth


class PontoApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiPayload:
    content: bytes
    content_type: str
    suggested_filename: str | None


def fetch_afd(
    url: str,
    username: str,
    password: str,
    *,
    timeout_seconds: int = 60,
) -> ApiPayload:
    try:
        response = requests.get(
            url,
            auth=HTTPBasicAuth(username, password),
            headers={"Accept": "application/json, text/plain, application/octet-stream"},
            timeout=timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        status = getattr(exc.response, "status_code", None)
        suffix = f" (HTTP {status})" if status else ""
        raise PontoApiError(f"Falha ao consultar a API de ponto{suffix}") from exc

    disposition = response.headers.get("Content-Disposition", "")
    filename = None
    if "filename=" in disposition:
        filename = disposition.split("filename=", 1)[1].strip().strip('"')

    return ApiPayload(
        content=response.content,
        content_type=response.headers.get("Content-Type", "application/octet-stream"),
        suggested_filename=filename,
    )

