from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class CloudflarePublishError(RuntimeError):
    pass


def _wrangler_executable(project_root: Path) -> str:
    executable = "wrangler.cmd" if os.name == "nt" else "wrangler"
    local = project_root / "node_modules" / ".bin" / executable
    if local.is_file():
        return str(local)
    installed = shutil.which("wrangler")
    if installed:
        return installed
    raise CloudflarePublishError(
        "Wrangler não encontrado. Execute 'npm install' na pasta do projeto."
    )


def publish_monitor(
    output_dir: Path,
    project_name: str,
    branch: str = "main",
    *,
    project_root: Path | None = None,
    auth_username: str | None = None,
    auth_password: str | None = None,
) -> str | None:
    root = (project_root or Path.cwd()).resolve()
    source = output_dir.resolve()
    if not (source / "index.html").is_file():
        raise CloudflarePublishError(
            f"Relatório não encontrado em {source / 'index.html'}."
        )

    wrangler = _wrangler_executable(root)
    if auth_username and auth_password:
        _sync_auth_secrets(wrangler, root, project_name, auth_username, auth_password)

    command = [
        wrangler,
        "pages",
        "deploy",
        str(source),
        "--project-name",
        project_name,
        "--branch",
        branch,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CloudflarePublishError(f"Não foi possível executar o Wrangler: {exc}") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise CloudflarePublishError(
            "A publicação na Cloudflare falhou"
            + (f": {detail}" if detail else ".")
        )

    output = "\n".join((result.stdout, result.stderr))
    urls = re.findall(r"https://[^\s]+\.pages\.dev", output)
    return urls[-1] if urls else None


def _sync_auth_secrets(
    wrangler: str,
    root: Path,
    project_name: str,
    username: str,
    password: str,
) -> None:
    secret_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as handle:
            json.dump({"PONTO_USERNAME": username, "PONTO_PASSWORD": password}, handle)
            secret_file = Path(handle.name)
        result = subprocess.run(
            [
                wrangler,
                "pages",
                "secret",
                "bulk",
                str(secret_file),
                "--project-name",
                project_name,
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CloudflarePublishError(
            f"Não foi possível configurar o login na Cloudflare: {exc}"
        ) from exc
    finally:
        if secret_file:
            secret_file.unlink(missing_ok=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise CloudflarePublishError(
            "A configuração segura do login na Cloudflare falhou"
            + (f": {detail}" if detail else ".")
        )
