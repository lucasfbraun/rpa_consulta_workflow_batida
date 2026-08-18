from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .api import PontoApiError, fetch_afd
from .cloudflare import CloudflarePublishError, publish_monitor
from .config import Settings
from .converter import LayoutPendenteError, generate_import_file
from .erp import ErpAutomationError, import_into_erp
from .filename import AFD_PATTERN, next_afd_path, prune_afd_files
from .monitor import ExecutionReporter, rebuild_report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automação de ponto para o ERP")
    parser.add_argument(
        "command",
        choices=("fetch", "import", "run", "report", "publish"),
        help="Etapa a executar",
    )
    parser.add_argument("--file", type=Path, help="Arquivo existente para importar")
    parser.add_argument("--output", type=Path, help="Caminho do arquivo gerado")
    return parser


def main() -> int:
    args = _parser().parse_args()
    reporter: ExecutionReporter | None = None
    try:
        settings = Settings.from_env()
        if args.command in {"report", "publish"}:
            report = rebuild_report(settings.monitor_output_dir)
            print(f"Relatório HTML: {report.resolve()}")
            if args.command == "publish":
                _publish(settings, force=True)
            return 0
        reporter = ExecutionReporter.from_settings(settings, args.command)
        reporter.start()
        output = args.output or next_afd_path(
            Path("output"), settings.afd_initial_sequence
        )

        if args.command in {"fetch", "run"}:
            payload = fetch_afd(
                settings.ponto_api_url,
                settings.ponto_username,
                settings.ponto_password,
            )
            reporter.step("api_consultada")
            output = generate_import_file(payload, output)
            if AFD_PATTERN.fullmatch(output.name):
                removed = prune_afd_files(output.parent, settings.afd_keep_files)
                if removed:
                    print(f"AFDs antigos removidos: {len(removed)}")
            reporter.step("arquivo_gerado", message=output.name)
            print(f"Arquivo gerado: {output.resolve()}")

        if args.command in {"import", "run"}:
            import_file = args.file if args.command == "import" else output
            if import_file is None:
                raise ValueError("Use --file CAMINHO com o comando import.")
            import_into_erp(settings, import_file, reporter)
            print(f"Importação concluída no ERP: {import_file.resolve()}")
        reporter.finish("completed")
        _publish(settings)
        return 0
    except CloudflarePublishError as exc:
        if reporter:
            reporter.step(
                "falha_publicacao_cloudflare", status="failed", message=str(exc)
            )
            reporter.finish("failed", str(exc))
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except (
        ValueError,
        FileNotFoundError,
        PontoApiError,
        LayoutPendenteError,
        ErpAutomationError,
    ) as exc:
        if reporter:
            reporter.step("falha_execucao", status="failed", message=str(exc))
            reporter.finish("failed", str(exc))
            _publish_after_failure(settings)
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        message = "Execução interrompida pelo usuário."
        if reporter:
            reporter.step("falha_execucao", status="failed", message=message)
            reporter.finish("failed", message)
            _publish_after_failure(settings)
        print(f"Erro: {message}", file=sys.stderr)
        return 130
    except Exception as exc:
        message = f"Falha inesperada: {exc.__class__.__name__}: {exc}"
        if reporter:
            reporter.step("falha_execucao", status="failed", message=message)
            reporter.finish("failed", message)
            _publish_after_failure(settings)
        print(f"Erro: {message}", file=sys.stderr)
    return 1


def _publish(settings: Settings, *, force: bool = False) -> None:
    if not force and not settings.cloudflare_pages_enabled:
        return
    if not settings.cloudflare_pages_project:
        raise CloudflarePublishError("Preencha CLOUDFLARE_PAGES_PROJECT no .env.")
    url = publish_monitor(
        settings.monitor_output_dir,
        settings.cloudflare_pages_project,
        settings.cloudflare_pages_branch,
    )
    print(f"Relatório online: {url or 'publicado com sucesso'}")


def _publish_after_failure(settings: Settings) -> None:
    try:
        _publish(settings)
    except CloudflarePublishError as exc:
        print(f"Aviso: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
