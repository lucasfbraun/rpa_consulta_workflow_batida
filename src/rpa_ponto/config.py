from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _as_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "sim", "on"}:
        return True
    if normalized in {"0", "false", "no", "nao", "não", "off"}:
        return False
    raise ValueError(f"Valor booleano inválido: {value!r}")


def _as_milliseconds(name: str, *, default: int = 0) -> int:
    raw_value = os.getenv(name)
    try:
        value = default if raw_value is None else int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} deve ser um número inteiro.") from exc
    if value < 0:
        raise ValueError(f"{name} não pode ser negativo.")
    return value


@dataclass(frozen=True)
class Settings:
    ponto_api_url: str
    ponto_username: str
    ponto_password: str
    afd_initial_sequence: str
    erp_url: str
    erp_username: str | None
    erp_password: str | None
    erp_program_code: str
    erp_import_kind: str
    erp_close_active_sessions: bool
    erp_verify_tls: bool
    headless: bool
    global_delay_ms: int

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(dotenv_path=env_file)
        required = ("PONTO_API_URL", "PONTO_USERNAME", "PONTO_PASSWORD", "ERP_URL")
        missing = [name for name in required if not os.getenv(name)]
        if missing:
            raise ValueError(
                "Preencha as variáveis obrigatórias no .env: " + ", ".join(missing)
            )
        afd_initial_sequence = os.getenv(
            "AFD_INITIAL_SEQUENCE", "00014003750288103"
        ).strip()
        if not afd_initial_sequence.isdigit():
            raise ValueError("AFD_INITIAL_SEQUENCE deve conter somente números.")

        legacy_global_delay = os.getenv("RPA_STEP_DELAY_MS")
        try:
            global_delay_default = (
                int(legacy_global_delay) if legacy_global_delay else 300
            )
        except ValueError as exc:
            raise ValueError("RPA_STEP_DELAY_MS deve ser um número inteiro.") from exc
        global_delay_ms = _as_milliseconds(
            "RPA_GLOBAL_DELAY_MS", default=global_delay_default
        )

        return cls(
            ponto_api_url=os.environ["PONTO_API_URL"],
            ponto_username=os.environ["PONTO_USERNAME"],
            ponto_password=os.environ["PONTO_PASSWORD"],
            afd_initial_sequence=afd_initial_sequence,
            erp_url=os.environ["ERP_URL"],
            erp_username=os.getenv("ERP_USERNAME") or None,
            erp_password=os.getenv("ERP_PASSWORD") or None,
            erp_program_code=os.getenv("ERP_PROGRAM_CODE", "CCRHP055"),
            erp_import_kind=os.getenv("ERP_IMPORT_KIND", "Apuração"),
            erp_close_active_sessions=_as_bool(
                os.getenv("ERP_CLOSE_ACTIVE_SESSIONS"), default=False
            ),
            erp_verify_tls=_as_bool(os.getenv("ERP_VERIFY_TLS"), default=True),
            headless=_as_bool(os.getenv("RPA_HEADLESS"), default=True),
            global_delay_ms=global_delay_ms,
        )
