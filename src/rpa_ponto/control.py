from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

import requests

from .config import Settings


class ControlError(RuntimeError):
    pass


@dataclass(frozen=True)
class Command:
    id: str


def _endpoint(settings: Settings, path: str) -> str:
    if not settings.control_api_url or not settings.control_agent_token:
        raise ControlError("Preencha CONTROL_API_URL e CONTROL_AGENT_TOKEN no .env.")
    return f"{settings.control_api_url}{path}"


def _post(settings: Settings, path: str, payload: dict | None = None) -> dict:
    try:
        response = requests.post(
            _endpoint(settings, path),
            json=payload or {},
            headers={"Authorization": f"Bearer {settings.control_agent_token}"},
            timeout=30,
        )
    except requests.RequestException as exc:
        raise ControlError(f"Painel de controle indisponÃ­vel: {exc}") from exc
    if response.status_code >= 400:
        detail = response.text.strip()[:300]
        raise ControlError(
            f"Painel de controle respondeu HTTP {response.status_code}"
            + (f": {detail}" if detail else ".")
        )
    try:
        data = response.json()
    except ValueError as exc:
        raise ControlError("Resposta invÃ¡lida do painel de controle.") from exc
    if not isinstance(data, dict):
        raise ControlError("Resposta invÃ¡lida do painel de controle.")
    return data


def claim(settings: Settings) -> Command | None:
    data = _post(settings, "/api/agent/claim")
    command = data.get("command")
    if command is None:
        return None
    if not isinstance(command, dict) or not isinstance(command.get("id"), str):
        raise ControlError("Comando invÃ¡lido recebido do painel.")
    return Command(command["id"])


def complete(settings: Settings, command_id: str, success: bool, result: str) -> None:
    _post(
        settings,
        "/api/agent/complete",
        {"id": command_id, "success": success, "result": result[:500]},
    )


def dispatch_once(settings: Settings) -> int:
    command = claim(settings)
    if command is None:
        print("Nenhuma execuÃ§Ã£o pendente no painel.")
        return 0

    print(f"Executando comando remoto {command.id}.")
    result = subprocess.run(
        [sys.executable, "-m", "rpa_ponto.cli", "run"], check=False
    )
    success = result.returncode == 0
    message = (
        "Fluxo concluÃ­do."
        if success
        else f"Fluxo terminou com cÃ³digo {result.returncode}."
    )
    try:
        complete(settings, command.id, success, message)
    except ControlError as exc:
        raise ControlError(
            f"{message} NÃ£o foi possÃ­vel confirmar no painel: {exc}"
        ) from exc
    return result.returncode
