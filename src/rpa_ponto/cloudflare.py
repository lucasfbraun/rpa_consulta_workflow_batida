from __future__ import annotations

import os
import re
import shutil
import subprocess
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
) -> str | None:
    root = (project_root or Path.cwd()).resolve()
    source = output_dir.resolve()
    if not (source / "index.html").is_file():
        raise CloudflarePublishError(
            f"Relatório não encontrado em {source / 'index.html'}."
        )

    command = [
        _wrangler_executable(root),
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
